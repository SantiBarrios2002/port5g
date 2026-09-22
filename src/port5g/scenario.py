"""Orchestration: config -> results dict (results/results.json). Every number in the report comes from here."""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np

from . import admission, capacity, channel, economics, geometry, latency, linkbudget, planning, reliability, sinr, slicing
from .config import Config, load_config

# Service -> (zone it must be served in, target SE per layer [bit/s/Hz], BLER, PRB allocation for the budget)
# target_se/PRB alloc are derived below from the flow GFBR, not hard-coded.


def _to_jsonable(o):
    if isinstance(o, dict):
        return {str(k): _to_jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_to_jsonable(v) for v in o]
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o


def link_budgets(cfg: Config, zone_ch: dict[str, channel.ZoneChannel], mount_h: float) -> dict:
    """UL and DL budgets per service flow in its zone; the PRB allocation is what the flow's GFBR needs at
    a reference spectral efficiency (CQI 7, 1.4766 bit/s/Hz) so the noise bandwidth is realistic."""
    from .tables import CQI_TABLE_1
    ll = cfg.latency.link_level
    duty = capacity.tdd_duty_cycle(cfg.band.tdd.pattern, cfg.band.tdd.special_slot_symbols)
    mu = cfg.band.numerology.mu
    flows = slicing.flows_from_config(cfg)
    svc_of_flow = {"S1_control": "S1_crane_control", "S1_video": "S1_crane_control",
                   "S2_video": "S2_shuttle_carriers", "S2_telemetry": "S2_shuttle_carriers",
                   "S3_reefer": "S3_monitoring", "S3_gate": "S3_monitoring", "S3_handheld": "S3_monitoring"}
    ref_se = CQI_TABLE_1[7][2]
    out = {}
    for fname, f in flows.items():
        svc = cfg.services[svc_of_flow[fname]]
        zone = svc.zone
        zc = zone_ch[zone]
        ue = cfg.ues.classes[f.ue_class]
        bw_prb = linkbudget.prb_bandwidth_hz(mu)
        need = max(f.gfbr_ul_mbps, f.mfbr_ul_mbps * 0.5) * 1e6
        n_prb = int(np.clip(np.ceil(need / (ref_se * bw_prb * duty.ul_fraction * (1 - 0.08))), 1, cfg.band.numerology.n_prb))
        se = need / (n_prb * bw_prb * duty.ul_fraction * (1 - 0.08))
        bler = ll.first_tx_bler_urllc if f.resource_type.startswith("delay-critical") else ll.first_tx_bler_embb
        n_exp = linkbudget.pl_exponent_estimate(zc, cfg.band.carrier.fc_ghz, mount_h, ue.height_m)
        ul = linkbudget.uplink_budget(cfg, svc_of_flow[fname], zone, se, bler, n_prb, svc.area_availability_target, zc.sigma_nlos(), n_exp)
        dl = linkbudget.downlink_budget(cfg, svc_of_flow[fname], zone, se, bler, n_prb, svc.area_availability_target, zc.sigma_nlos(), n_exp)
        r_ul = linkbudget.cell_radius_m(zc, ul.mapl_db, cfg.band.carrier.fc_ghz, mount_h, ue.height_m)
        r_dl = linkbudget.cell_radius_m(zc, dl.mapl_db, cfg.band.carrier.fc_ghz, mount_h, ue.height_m)
        out[fname] = {"zone": zone, "ue_class": f.ue_class, "n_prb": n_prb, "target_se": se, "bler": bler,
                      "pl_exponent": n_exp, "ul": vars(ul), "dl": vars(dl),
                      "radius_ul_m": r_ul, "radius_dl_m": r_dl, "limiting": "UL" if r_ul < r_dl else "DL"}
    return out


def run(cfg: Config | None = None, seed: int | None = None, sinr_shadowing: bool = False) -> dict:
    cfg = cfg or load_config(warn=False)
    seed = int(cfg.scenario_best.simulation.seed if seed is None else seed)
    rng = np.random.default_rng(seed)
    res: dict = {"seed": seed, "band": cfg.band.raw() if hasattr(cfg.band, "raw") else None}

    # --- geometry ------------------------------------------------------------------------------
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        site = geometry.load_site(cfg)
    res["site"] = {"area_ha": site.area_ha, "placeholder": site.placeholder,
                   "clutter_density": {z: site.clutter_density(z) for z in site.zones},
                   "warnings": [str(x.message) for x in w]}
    mounts = geometry.candidate_mounts(cfg)
    grid = geometry.demand_grid(site, cfg.scenario_best.simulation.grid_resolution_m)
    zone_ch = channel.zone_channels_from_config(cfg)

    # --- link budgets & radii ------------------------------------------------------------------
    mast_h = cfg.ues.gnb.height_m_by_mount.lighting_mast
    res["link_budgets"] = link_budgets(cfg, zone_ch, mast_h)
    # radius requirement per zone = most demanding UL flow in that zone
    radius_by_zone = {}
    for f, r in res["link_budgets"].items():
        radius_by_zone[r["zone"]] = min(radius_by_zone.get(r["zone"], 1e9), r["radius_ul_m"])
    res["radius_by_zone_m"] = radius_by_zone

    # --- planning -------------------------------------------------------------------------------
    plan = planning.place_sites(grid, mounts, radius_by_zone)
    res["plan"] = {"method": plan.method, "n_sites": len(plan.selected),
                   "sites": [vars(m) for m in plan.selected], "coverage_fraction": plan.coverage_fraction,
                   "uncovered_by_zone": plan.uncovered_by_zone, "n_candidates": len(mounts)}

    # --- SINR map (vehicle CPE, 1-PRB reference) -----------------------------------------------
    maps = {}
    for pat in cfg.band.tdd.candidates:
        smap = sinr.uplink_sinr_map(cfg, grid, plan.selected, zone_ch, "vehicle_cpe", 20, sinr_shadowing, rng)
        maps[pat] = {"sinr_db": smap.sinr_ul_db, "serving": smap.serving}   # pattern does not change SINR; only capacity
    res["grid"] = {"x": grid.x, "y": grid.y, "zone": grid.zone, "res_m": grid.res_m}
    res["sinr_maps"] = maps
    res["cross_link_note"] = sinr.cross_link_interference_note()

    # --- capacity per TDD pattern & slice --------------------------------------------------------
    ll = cfg.latency.link_level
    se_map = capacity.spectral_efficiency_from_sinr(maps[cfg.band.tdd.pattern]["sinr_db"], ll.attenuated_shannon_alpha, ll.max_spectral_efficiency_ul)
    n_sites = max(len(plan.selected), 1)
    offered_flow = slicing.offered_load_ul_mbps(cfg)
    offered_slice = slicing.offered_load_per_slice(cfg)
    slices = slicing.slices_from_config(cfg)
    res["capacity"] = {"peak": capacity.peak_rates_from_config(cfg), "offered_ul_mbps_by_flow": offered_flow,
                       "offered_ul_mbps_by_slice": offered_slice, "by_pattern": {}}
    for pat in cfg.band.tdd.candidates:
        duty = capacity.tdd_duty_cycle(pat, cfg.band.tdd.special_slot_symbols)
        per_cell = capacity.cell_throughput_mbps(se_map, cfg.band.numerology.n_prb, cfg.band.numerology.mu, 1, 0.08, duty.ul_fraction)
        total = per_cell * n_sites
        ach = {s: total * sl.share_max for s, sl in slices.items()}
        per_cell_2l = capacity.cell_throughput_mbps(se_map, cfg.band.numerology.n_prb, cfg.band.numerology.mu, 2, 0.08, duty.ul_fraction)
        tot_off = sum(offered_slice.values())
        res["capacity"]["by_pattern"][pat] = {"ul_fraction": duty.ul_fraction, "dl_fraction": duty.dl_fraction,
                                              "ul_cell_mean_mbps": per_cell, "ul_network_mbps": total,
                                              "sites_needed_for_capacity_1layer": int(np.ceil(tot_off / per_cell)),
                                              "sites_needed_for_capacity_2layer": int(np.ceil(tot_off / per_cell_2l)),
                                              "coverage_driven_sites": n_sites,
                                              "achievable_by_slice_max_share": ach,
                                              "deficit_by_slice": {s: offered_slice.get(s, 0) - ach[s] for s in ach},
                                              "closes": all(offered_slice.get(s, 0) <= ach[s] for s in ach)}

    # --- latency & reliability -----------------------------------------------------------------
    buds = latency.all_budgets(cfg)
    pdb = cfg.qos.standard_5qi[str(cfg.qos.flows.S1_control.qi)].pdb_ms
    res["latency"] = {"pdb_ms": pdb, "budgets": [{"name": b.name, "terms": b.terms, "total_ms": b.total_ms,
                                                  "mean_total_ms": b.mean_total_ms, "harq_rtt_ms": b.harq_rtt_ms,
                                                  "residual_error": b.residual_error, "meets_pdb": b.total_ms <= pdb}
                                                 for b in buds],
                      "local_upf_proof": latency.local_upf_proof(cfg)}
    b_ref = buds[3]  # CG, mu=1, mini-slot, 1 retx
    base = b_ref.total_ms - b_ref.terms.get("HARQ retx x1", 0.0)
    pareto = reliability.pareto_harq_vs_duplication(ll.first_tx_bler_embb, ll.harq_bler_per_retx, b_ref.harq_rtt_ms, base)
    pareto["conservative_mcs"] = {"latency_ms": base, "residual": ll.first_tx_bler_urllc,
                                  "sinr_cost_db": linkbudget.bler_penalty_db(1.4766, ll.finite_blocklength_n, ll.first_tx_bler_urllc)}
    res["reliability"] = {"pareto": pareto,
                          "target": cfg.services.S1_crane_control.reliability_target,
                          "bler_penalty_db_1e5_vs_1e1": linkbudget.bler_penalty_db(1.4766, ll.finite_blocklength_n, ll.first_tx_bler_urllc),
                          "n_tx_needed_at_bler0.1": reliability.min_transmissions_for_target(0.1, 1 - cfg.services.S1_crane_control.reliability_target)}

    # --- admission ------------------------------------------------------------------------------
    pat = cfg.band.tdd.pattern
    cap_ul = res["capacity"]["by_pattern"][pat]["ul_network_mbps"]
    adm = admission.simulate(cfg, cap_ul, slices, slicing.flows_from_config(cfg), offered_flow, seed + 1)
    res["admission"] = {"capacity_mbps": cap_ul, "t": adm.t, "used": adm.used_by_slice, "offered": adm.offered_by_slice,
                        "blocked": adm.blocked, "preempted": adm.preempted, "admitted": adm.admitted, "arrivals": adm.arrivals,
                        "blocking_probability": adm.blocking_probability(), "preemption_rate": adm.preemption_rate()}

    # --- sensitivity tornado on site count -----------------------------------------------------
    res["sensitivity"] = sensitivity_site_count(cfg, zone_ch, grid, mounts, mast_h)

    # --- techno-economics (report Ch. 5): site counts from above -> CAPEX/OPEX/NPV ------------------
    bp = res["capacity"]["by_pattern"]
    res["economics"] = economics.run(
        cfg,
        {"coverage": n_sites, "capacity_1layer": bp[pat]["sites_needed_for_capacity_1layer"],
         "capacity_2layer": bp[pat]["sites_needed_for_capacity_2layer"]},
        {p: bp[p]["sites_needed_for_capacity_2layer"] for p in cfg.band.tdd.candidates})
    return res


def sensitivity_site_count(cfg, zone_ch, grid, mounts, mast_h) -> list[dict]:
    """±perturb one assumption at a time and re-plan; the code — not the team — says which dominates."""
    import copy
    base_sites = None
    rows = []
    knobs = [
        ("latency.link_level.interference_margin_db", 0.0, 6.0),
        ("latency.link_level.implementation_loss_db", 0.0, 4.0),
        ("ues.gnb.beamforming_gain_db", 0.0, 9.0),
        ("services.S1_crane_control.area_availability_target", 0.99, 0.9999),
        ("scenario_best.zones.asc_blocks.inf_params.r", 0.4, 0.8),
        ("ues.classes.vehicle_cpe.antenna_gain_dbi", 0.0, 8.0),
        ("ues.gnb.height_m_by_mount.lighting_mast", 20.0, 40.0),
        ("scenario_best.zones.asc_blocks.channel_model", "InF", "UMi_SC"),   # model-suitability question, brief §4.1
    ]
    def _set(c, path, val):
        d = c.data
        parts = path.split(".")
        for p in parts[:-1]:
            d = d[p]
        d[parts[-1]] = val
    def _count(c):
        zc = channel.zone_channels_from_config(c)
        lb = link_budgets(c, zc, c.ues.gnb.height_m_by_mount.lighting_mast)
        rbz = {}
        for f, r in lb.items():
            rbz[r["zone"]] = min(rbz.get(r["zone"], 1e9), r["radius_ul_m"])
        return len(planning.place_sites(grid, mounts, rbz, prefer_ilp=True).selected)
    base_sites = _count(cfg)
    for path, lo, hi in knobs:
        c_lo, c_hi = copy.deepcopy(cfg), copy.deepcopy(cfg)
        _set(c_lo, path, lo); _set(c_hi, path, hi)
        rows.append({"assumption": path, "low": lo, "high": hi, "sites_low": _count(c_lo), "sites_high": _count(c_hi), "sites_base": base_sites})
    rows.sort(key=lambda r: -abs(r["sites_high"] - r["sites_low"]))
    return rows


def save(res: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # insertion order is deterministic and meaningful (waterfall term order) -> no sort_keys
    path.write_text(json.dumps(_to_jsonable(res), indent=1, sort_keys=False), encoding="utf-8")
