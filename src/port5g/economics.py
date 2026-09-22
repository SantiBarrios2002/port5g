"""Techno-economic model (report Ch. 5): site count -> CAPEX/OPEX -> cash flow, NPV, payback.

Two questions, kept separate on purpose:

* **Network TCO** — what the private network costs, per site-count scenario and per deployment option:
  ``snpn`` (own core on self-provision spectrum) vs ``pni_npn`` (core + operations bought from an MNO; RAN, CPE and
  MEC still on site because the S1 latency budget needs a local UPF).
* **Use-case business case** — labour savings enabled by remote cranes and driverless shuttles, net of *both* the
  network cost and the automation retrofit cost. The savings come from automation; 5G is the enabler, so crediting
  them to the network alone would overstate the return.

Year 0 carries all CAPEX; OPEX and benefits run over years 1..horizon, benefits scaled by ``benefit_ramp``.
Site counts are inputs (from scenario.py), never computed here.
"""
from __future__ import annotations

import copy

import numpy as np

from .config import Config

OPTIONS = ("snpn", "pni_npn")


def device_counts(cfg: Config) -> dict[str, int]:
    """One CPE per crane / shuttle (design), one module per reefer plug and asset tag, one handheld per user."""
    s3 = cfg.services.S3_monitoring
    return {"crane_cpe": int(cfg.services.S1_crane_control.n_devices),
            "vehicle_cpe": int(cfg.services.S2_shuttle_carriers.n_devices),
            "iot_module": int(s3.reefer_plugs + s3.asset_tags),
            "handheld": int(s3.handhelds)}


def network_capex(cfg: Config, n_sites: int, option: str = "snpn") -> dict[str, float]:
    if option not in OPTIONS:
        raise ValueError(f"option must be one of {OPTIONS}")
    c = cfg.economics.network_capex
    n = device_counts(cfg)
    out = {"RAN": n_sites * c.ran_per_site_eur,
           "site works": n_sites * c.site_works_per_site_eur,
           "5GC (on-site)": c.core_eur if option == "snpn" else 0.0,
           "MEC": c.mec_eur,
           "integration": c.integration_eur,
           "CPE / devices": sum(n[k] * c.cpe_eur[k] for k in n)}
    return {k: float(v) for k, v in out.items()}


def automation_capex(cfg: Config) -> dict[str, float]:
    a = cfg.economics.automation_capex
    return {"crane remote retrofit": float(cfg.services.S1_crane_control.n_devices * a.crane_remote_retrofit_per_crane_eur),
            "shuttle autonomy kits": float(cfg.services.S2_shuttle_carriers.n_devices * a.shuttle_autonomy_kit_per_vehicle_eur),
            "remote ops centre": float(a.remote_ops_centre_eur)}


def network_opex(cfg: Config, n_sites: int, net_capex_total: float, option: str = "snpn") -> dict[str, float]:
    """Annual network OPEX [EUR/year]."""
    o = cfg.economics.network_opex
    snpn = option == "snpn"
    out = {"maintenance": o.maintenance_fraction_of_capex * net_capex_total,
           "energy": n_sites * o.power_per_site_kw * 8760 * o.electricity_eur_per_kwh,
           "spectrum fee": o.spectrum_fee_eur_per_year if snpn else 0.0,
           "network ops staff": o.network_ops_fte * o.network_ops_cost_eur_per_fte if snpn else 0.0,
           "MNO service fee": 0.0 if snpn else o.mno_service_fee_eur_per_year}
    return {k: float(v) for k, v in out.items()}


def annual_benefits(cfg: Config) -> dict[str, float]:
    """Full-rate annual savings [EUR/year]: posts removed x FTE per 24/7 post x loaded cost."""
    b = cfg.economics.benefits
    n_cranes = cfg.services.S1_crane_control.n_devices
    n_veh = cfg.services.S2_shuttle_carriers.n_devices
    crane_posts_saved = n_cranes * b.crane_operators_per_crane_manual - np.ceil(n_cranes / b.cranes_per_remote_operator)
    driver_posts_saved = n_veh * b.shuttle_drivers_per_vehicle_manual - np.ceil(n_veh / b.vehicles_per_remote_supervisor)
    return {"crane operators": float(crane_posts_saved * b.fte_per_24x7_post * b.crane_operator_cost_eur_per_fte),
            "shuttle drivers": float(driver_posts_saved * b.fte_per_24x7_post * b.driver_cost_eur_per_fte),
            "legacy network": float(b.legacy_network_saving_eur_per_year)}


def cash_flows(capex: float, opex_per_year: float, benefit_per_year: float, ramp: list[float], horizon: int) -> np.ndarray:
    """Undiscounted net cash flow for years 0..horizon."""
    cf = np.zeros(horizon + 1)
    cf[0] = -capex
    for y in range(1, horizon + 1):
        r = ramp[y - 1] if y - 1 < len(ramp) else 1.0
        cf[y] = r * benefit_per_year - opex_per_year
    return cf


def discount(cf: np.ndarray, rate: float) -> np.ndarray:
    return cf / (1 + rate) ** np.arange(len(cf))


def npv(cf: np.ndarray, rate: float) -> float:
    return float(discount(cf, rate).sum())


def payback_year(cf: np.ndarray, rate: float) -> float | None:
    """Discounted payback, linearly interpolated inside the crossing year; None if never within the horizon."""
    cum = np.cumsum(discount(cf, rate))
    idx = np.flatnonzero(cum >= 0)
    if idx.size == 0:
        return None
    y = int(idx[0])
    if y == 0:
        return 0.0
    return float(y - 1 + (-cum[y - 1]) / (cum[y] - cum[y - 1]))


def evaluate(cfg: Config, n_sites: int, option: str = "snpn") -> dict:
    m = cfg.economics.model
    ncap = network_capex(cfg, n_sites, option)
    acap = automation_capex(cfg)
    nop = network_opex(cfg, n_sites, sum(ncap.values()), option)
    ben = annual_benefits(cfg)
    H, rate, ramp = int(m.horizon_years), float(m.discount_rate), list(m.benefit_ramp)
    net_cf = cash_flows(sum(ncap.values()), sum(nop.values()), 0.0, ramp, H)          # network alone: pure cost
    uc_cf = cash_flows(sum(ncap.values()) + sum(acap.values()), sum(nop.values()), sum(ben.values()), ramp, H)
    return {"n_sites": n_sites, "option": option,
            "network_capex": ncap, "automation_capex": acap, "network_opex_per_year": nop, "benefits_per_year": ben,
            "network_tco_discounted": -npv(net_cf, rate),
            "use_case_cash_flow": uc_cf, "use_case_cum_discounted": np.cumsum(discount(uc_cf, rate)),
            "use_case_npv": npv(uc_cf, rate), "use_case_payback_years": payback_year(uc_cf, rate)}


def _numeric_inputs(cfg: Config) -> list[str]:
    """Tornado knobs: scalar economic inputs that are external facts (not `design` choices such as one driver per
    vehicle, whose +/-30 % would be meaningless); model settings excluded."""
    secs = tuple(f"economics.{s}." for s in ("network_capex", "automation_capex", "network_opex", "benefits"))
    return [p.path for p in cfg.registry
            if p.path.startswith(secs) and p.confidence != "design"
            and isinstance(p.value, (int, float)) and not isinstance(p.value, bool)]


def _set(cfg: Config, path: str, val) -> None:
    d = cfg.data
    parts = path.split(".")
    for p in parts[:-1]:
        d = d[p]
    d[parts[-1]] = val


def _get(cfg: Config, path: str):
    d = cfg.data
    for p in path.split("."):
        d = d[p]
    return d


def npv_sensitivity(cfg: Config, n_sites: int, option: str = "snpn") -> list[dict]:
    """+/- sensitivity_fraction on one economic input at a time -> use-case NPV; sorted by swing."""
    f = float(cfg.economics.model.sensitivity_fraction)
    base = evaluate(cfg, n_sites, option)["use_case_npv"]
    rows = []
    for path in _numeric_inputs(cfg):
        v = _get(cfg, path)
        out = {}
        for tag, k in (("low", 1 - f), ("high", 1 + f)):
            c = copy.deepcopy(cfg)
            nv = v * k
            if path.endswith(("cranes_per_remote_operator", "vehicles_per_remote_supervisor")):
                nv = max(1.0, nv)                  # a ratio below one operator per crane is meaningless
            _set(c, path, nv)
            out[tag] = evaluate(c, n_sites, option)["use_case_npv"]
        rows.append({"input": path, "value": v, "npv_low": out["low"], "npv_high": out["high"], "npv_base": base})
    rows.sort(key=lambda r: -abs(r["npv_high"] - r["npv_low"]))
    return rows


def run(cfg: Config, site_scenarios: dict[str, int], sites_by_pattern: dict[str, int]) -> dict:
    """site_scenarios: {coverage, capacity_1layer, capacity_2layer} for the configured TDD pattern;
    sites_by_pattern: reference (2-layer capacity) site count per TDD pattern -> cost of the TDD choice."""
    m = cfg.economics.model
    base_key = m.base_site_scenario
    if base_key not in site_scenarios:
        raise ValueError(f"economics.model.base_site_scenario '{base_key}' not in {list(site_scenarios)}")
    unverified = [p.path for p in cfg.registry if p.path.startswith("economics.") and p.unverified]
    return {"n_unverified_inputs": len(unverified), "unverified_inputs": unverified,
            "device_counts": device_counts(cfg),
            "base_site_scenario": base_key, "base_n_sites": site_scenarios[base_key],
            "scenarios": {k: {opt: evaluate(cfg, n, opt) for opt in OPTIONS} for k, n in site_scenarios.items()},
            "tco_by_tdd_pattern": {p: {"n_sites": n, "snpn_tco": evaluate(cfg, n, "snpn")["network_tco_discounted"]}
                                   for p, n in sites_by_pattern.items()},
            "npv_sensitivity": npv_sensitivity(cfg, site_scenarios[base_key], "snpn")}
