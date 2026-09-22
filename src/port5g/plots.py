"""Every figure in the report (brief §7). Reads results/results.json; deterministic output (no timestamps)."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

SAVE_KW = dict(dpi=130, bbox_inches="tight", metadata={"Software": None})
FIG_ORDER = ["fig01_terminal_map", "fig02_ul_sinr_map", "fig03_link_budget_waterfall", "fig04_radius_vs_throughput",
             "fig05_latency_budget", "fig06_reliability_pareto", "fig07_offered_vs_achievable",
             "fig08_admission_timeseries", "fig09_sensitivity_tornado", "fig10_cost_breakdown",
             "fig11_cash_flow", "fig12_npv_tornado", "fig13_cross_link"]


def _load(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _placeholder_stamp(ax, res):
    if res["site"]["placeholder"]:
        ax.text(0.5, 0.5, "PLACEHOLDER GEOMETRY\nnot reportable", transform=ax.transAxes, ha="center", va="center",
                fontsize=22, color="red", alpha=0.25, rotation=20, weight="bold")


def fig01_terminal_map(res, cfg, out):
    g = res["grid"]; x, y, z = np.array(g["x"]), np.array(g["y"]), np.array(g["zone"])
    fig, ax = plt.subplots(figsize=(11, 5))
    for zn, c in zip(sorted(set(z)), ["#c8e6c9", "#ffe0b2", "#bbdefb"]):
        m = z == zn; ax.scatter(x[m], y[m], s=4, c=c, label=zn, marker="s")
    from .geometry import candidate_mounts
    for mnt in candidate_mounts(cfg):
        ax.plot(mnt.x, mnt.y, "k+", ms=6)
    for s in res["plan"]["sites"]:
        ax.plot(s["x"], s["y"], "r^", ms=10)
        r = res["radius_by_zone_m"]
        ax.add_patch(plt.Circle((s["x"], s["y"]), min(r.values()), fill=False, ec="r", ls="--", lw=0.8))
    ax.plot([], [], "k+", label="candidate mount"); ax.plot([], [], "r^", label=f"selected site ({res['plan']['n_sites']}, {res['plan']['method']})")
    ax.set_aspect("equal"); ax.set_xlabel("x along quay [m]"); ax.set_ylabel("y inland [m]")
    ax.set_title("Fig. 1 — Terminal zones, candidate mounts, selected sites (min UL radius circles)")
    ax.legend(loc="upper right", fontsize=7); _placeholder_stamp(ax, res)
    fig.savefig(out / "fig01_terminal_map.png", **SAVE_KW); plt.close(fig)


def fig02_ul_sinr_map(res, cfg, out):
    g = res["grid"]; x, y = np.array(g["x"]), np.array(g["y"])
    pats = list(res["sinr_maps"])
    fig, axes = plt.subplots(1, len(pats), figsize=(5 * len(pats), 3.6), sharey=True)
    for ax, p in zip(np.atleast_1d(axes), pats):
        s = np.array(res["sinr_maps"][p]["sinr_db"])
        sc = ax.scatter(x, y, c=s, s=5, marker="s", cmap="viridis", vmin=-5, vmax=30)
        ax.set_aspect("equal"); ax.set_title(f"UL SINR (vehicle CPE) — TDD {p}\nUL frac {res['capacity']['by_pattern'][p]['ul_fraction']:.2f}", fontsize=9)
        _placeholder_stamp(ax, res)
    fig.colorbar(sc, ax=axes, label="SINR [dB]"); fig.suptitle("Fig. 2 — Uplink SINR heatmap (interference-aware, mean channel)")
    fig.savefig(out / "fig02_ul_sinr_map.png", **SAVE_KW); plt.close(fig)


def _waterfall(ax, terms, title):
    names, vals = list(terms), list(terms.values())
    cum = np.cumsum([0] + vals[:-1])
    colors = ["#2e7d32" if v >= 0 else "#c62828" for v in vals]
    ax.bar(range(len(vals)), vals, bottom=cum, color=colors)
    ax.axhline(sum(vals), color="k", ls="--", lw=1)
    ax.text(len(vals) - 0.5, sum(vals), f"MAPL {sum(vals):.1f} dB", ha="right", va="bottom", fontsize=8)
    ax.set_xticks(range(len(vals))); ax.set_xticklabels(names, rotation=70, ha="right", fontsize=7)
    ax.set_title(title, fontsize=9); ax.set_ylabel("dB")


def fig03_link_budget_waterfall(res, cfg, out):
    lb = res["link_budgets"]["S1_control"]
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    _waterfall(axes[0], lb["ul"]["terms"], f"UL — S1 control, {lb['zone']} (radius {lb['radius_ul_m']:.0f} m)")
    _waterfall(axes[1], lb["dl"]["terms"], f"DL — S1 control, {lb['zone']} (radius {lb['radius_dl_m']:.0f} m)")
    fig.suptitle(f"Fig. 3 — Link budget waterfall; limiting direction: {lb['limiting']}")
    fig.savefig(out / "fig03_link_budget_waterfall.png", **SAVE_KW); plt.close(fig)


def fig04_radius_vs_throughput(res, cfg, out):
    from . import channel, linkbudget
    zcs = channel.zone_channels_from_config(cfg)
    th = np.linspace(1, 60, 40)
    fig, ax = plt.subplots(figsize=(7, 4.2))
    for uc, zone in [("handheld", "gate_rail"), ("vehicle_cpe", "asc_blocks"), ("crane_cpe", "quay_apron")]:
        r = linkbudget.radius_vs_throughput(cfg, zcs[zone], uc, th, cfg.ues.gnb.height_m_by_mount.lighting_mast, 0.1, 0.99, 50)
        ax.plot(th, r, label=f"{uc} ({cfg.ues.classes[uc].tx_power_dbm:.0f} dBm) in {zone} [{zcs[zone].sub_scenario or zcs[zone].model}]")
    ax.set_xlabel("required UL throughput per UE [Mbit/s] (50 PRB, BLER 0.1, 99% area)"); ax.set_ylabel("cell radius [m] (capped at model validity)")
    ax.set_title("Fig. 4 — Cell radius vs required uplink throughput per UE power class"); ax.grid(alpha=.3); ax.legend(fontsize=7)
    fig.savefig(out / "fig04_radius_vs_throughput.png", **SAVE_KW); plt.close(fig)


def fig05_latency_budget(res, cfg, out):
    buds, pdb = res["latency"]["budgets"], res["latency"]["pdb_ms"]
    fig, ax = plt.subplots(figsize=(10, 5))
    allkeys: list[str] = []                       # ordered, no set iteration (rule §10.4)
    for b in buds:
        for k in b["terms"]:
            if k not in allkeys:
                allkeys.append(k)
    bottom = np.zeros(len(buds))
    cmap = plt.get_cmap("tab20")
    for i, k in enumerate(allkeys):
        v = np.array([b["terms"].get(k, 0.0) for b in buds])
        ax.bar(range(len(buds)), v, bottom=bottom, label=k, color=cmap(i % 20)); bottom += v
    ax.axhline(pdb, color="r", ls="--", label=f"5QI 82 PDB = {pdb} ms")
    ax.set_xticks(range(len(buds))); ax.set_xticklabels([b["name"] for b in buds], rotation=25, ha="right", fontsize=7)
    ax.set_ylabel("one-way latency [ms], worst-case alignment"); ax.set_title("Fig. 5 — S1 latency budget per configuration")
    ax.legend(fontsize=6, ncol=2); fig.savefig(out / "fig05_latency_budget.png", **SAVE_KW); plt.close(fig)


def fig06_reliability_pareto(res, cfg, out):
    p = res["reliability"]["pareto"]; tgt = 1 - res["reliability"]["target"]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    h = p["harq"]
    ax.plot([q["latency_ms"] for q in h], [q["residual"] for q in h], "o-", label="HARQ chain (serial)")
    for q in h:
        ax.annotate(f"{q['n_tx']} tx", (q["latency_ms"], q["residual"]), fontsize=7, xytext=(4, 4), textcoords="offset points")
    d = p["duplication"]
    ax.plot(d["latency_ms"], d["residual"], "s", ms=9, color="orange", label="PDCP duplication x2 CA (parallel; 2x spectral cost)")
    c = p["conservative_mcs"]
    ax.plot(c["latency_ms"], c["residual"], "D", ms=9, color="green", label=f"conservative MCS, 1 tx (+{c['sinr_cost_db']:.1f} dB SINR)")
    ax.axhline(tgt, color="r", ls="--", label=f"target residual {tgt:.0e}")
    ax.axvline(res["latency"]["pdb_ms"], color="k", ls=":", label="PDB")
    ax.set_yscale("log"); ax.set_xlabel("one-way latency [ms]"); ax.set_ylabel("residual error probability")
    ax.set_title("Fig. 6 — Reliability vs latency: HARQ repetition vs PDCP duplication"); ax.grid(alpha=.3, which="both"); ax.legend(fontsize=7)
    fig.savefig(out / "fig06_reliability_pareto.png", **SAVE_KW); plt.close(fig)


def fig07_offered_vs_achievable(res, cfg, out):
    cap = res["capacity"]; pats = list(cap["by_pattern"]); slices = list(cap["offered_ul_mbps_by_slice"])
    fig, ax = plt.subplots(figsize=(8, 4.5)); w = 0.8 / (len(pats) + 1); xs = np.arange(len(slices))
    ax.bar(xs, [cap["offered_ul_mbps_by_slice"][s] for s in slices], w, color="gray", label="offered UL")
    for i, p in enumerate(pats):
        a = [cap["by_pattern"][p]["achievable_by_slice_max_share"][s] for s in slices]
        ax.bar(xs + (i + 1) * w, a, w, label=f"achievable {p}")
        for j, s in enumerate(slices):
            if cap["offered_ul_mbps_by_slice"][s] > a[j]:
                ax.text(xs[j] + (i + 1) * w, a[j], "deficit", ha="center", va="bottom", color="r", fontsize=7, rotation=90)
    ax.set_xticks(xs + 0.4); ax.set_xticklabels(slices); ax.set_ylabel("Mbit/s (network, max slice share)")
    ax.set_title(f"Fig. 7 — Offered vs achievable UL per slice ({res['plan']['n_sites']} sites)"); ax.legend(fontsize=8)
    fig.savefig(out / "fig07_offered_vs_achievable.png", **SAVE_KW); plt.close(fig)


def fig08_admission_timeseries(res, cfg, out):
    a = res["admission"]; t = np.array(a["t"])
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.stackplot(t, *[np.array(a["used"][s]) for s in a["used"]], labels=[f"{s} (blocked {a['blocked'][s]}, pre-empted {a['preempted'][s]})" for s in a["used"]], alpha=.8)
    ax.plot(t, sum(np.array(a["offered"][s]) for s in a["offered"]), "k--", lw=1, label="total offered (ramp)")
    ax.axhline(a["capacity_mbps"], color="r", ls=":", label="UL capacity")
    ax.set_xlabel("time [s]"); ax.set_ylabel("reserved UL Mbit/s"); ax.set_ylim(0, a["capacity_mbps"] * 1.6)
    ax.set_title("Fig. 8 — Admission control under load ramp (0 -> 3x capacity): ARP pre-emption")
    ax.legend(fontsize=7, loc="upper left"); fig.savefig(out / "fig08_admission_timeseries.png", **SAVE_KW); plt.close(fig)


def fig09_sensitivity_tornado(res, cfg, out):
    rows = res["sensitivity"]
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.2), sharey=True)
    panels = (("cap_sites", f"capacity-driven (TDD {cfg.band.tdd.pattern}, 2-layer UL) — sets the budget"),
              ("sites", "coverage-driven"))
    for ax, (key, title) in zip(axes, panels):
        base = rows[0][f"{key}_base"] if rows else 0
        for i, r in enumerate(rows[::-1]):
            ax.barh(i, r[f"{key}_low"] - base, color="#1976d2", left=base); ax.barh(i, r[f"{key}_high"] - base, color="#f57c00", left=base)
        ax.axvline(base, color="k"); ax.set_xlabel(f"site count (base = {base}; blue = low, orange = high)"); ax.set_title(title, fontsize=9)
        _placeholder_stamp(ax, res)
    axes[0].set_yticks(range(len(rows)))
    axes[0].set_yticklabels([f"{r['assumption'].split('.')[-1]} [{r['low']}..{r['high']}]" for r in rows[::-1]], fontsize=7)
    fig.suptitle("Fig. 9 — Sensitivity of site count to single assumptions")
    fig.savefig(out / "fig09_sensitivity_tornado.png", **SAVE_KW); plt.close(fig)


def fig13_cross_link(res, cfg, out):
    co = res["coexistence"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 4.3), gridspec_kw={"width_ratios": [1, 1.3]})
    from .coexistence import expand_symbols, fspl_db
    special = dict(cfg.band.tdd.special_slot_symbols)
    mno = expand_symbols(co["mno_pattern"], special)
    colors = {"D": "#1976d2", "U": "#f57c00", "G": "#bdbdbd"}
    pats = list(co["by_pattern"])
    for row, pat in enumerate(pats):
        ours = expand_symbols(pat, special)
        for k, (x, y) in enumerate(zip(ours, mno)):
            a1.add_patch(plt.Rectangle((k, row * 3 + 1), 1, 0.9, color=colors[x], lw=0))
            if (x, y) in (("U", "D"), ("D", "U")):
                a1.add_patch(plt.Rectangle((k, row * 3), 1, 0.9, color="red", lw=0))
        fr = co["by_pattern"][pat]["conflict_fraction"]
        a1.text(len(ours) + 1, row * 3 + 0.9, f"{pat}\nconflict {fr['ours_U_mno_D'] + fr['ours_D_mno_U']:.0%}", fontsize=8, va="center")
    for k, y in enumerate(mno):
        a1.add_patch(plt.Rectangle((k, len(pats) * 3 + 1), 1, 0.9, color=colors[y], lw=0))
    a1.text(len(mno) + 1, len(pats) * 3 + 1.4, f"MNO {co['mno_pattern']}", fontsize=8, va="center")
    a1.set_xlim(0, len(mno) + 16); a1.set_ylim(-0.5, len(pats) * 3 + 2.5); a1.set_yticks([])
    a1.set_xlabel("symbol in 2.5 ms period (blue D, orange U, grey guard; red = cross-link conflict)")
    a1.set_title("Symbol-level conflicts vs the adjacent MNO", fontsize=9)
    d = np.logspace(*np.log10(cfg.band.coexistence.distance_range_m), 200)
    fc = cfg.band.carrier.fc_ghz
    for name, lk in co["links"].items():
        on = name in co["ever_active_links"]
        a2.semilogx(d, lk["i_at_0db_dbm"] - fspl_db(d, fc) - lk["noise_dbm"], ls="-" if on else ":", alpha=1 if on else 0.5,
                    label=f"{name} (victim {lk['victim']}): {lk['required_separation_m']:,.0f} m" + ("" if on else " — no conflict symbols"))
    a2.axhline(co["protection_i_over_n_db"], color="k", ls="--", lw=0.8, label=f"protection I/N = {co['protection_i_over_n_db']} dB")
    a2.axvline(co["nearest_mno_site_m"], color="grey", ls=":", label=f"nearest MNO site (placeholder) {co['nearest_mno_site_m']} m")
    a2.set_xlabel("separation [m] (free-space, worst case)"); a2.set_ylabel("I/N [dB]"); a2.legend(fontsize=7)
    a2.set_title("Cross-link I/N vs separation (required separation in legend)", fontsize=9)
    if co["n_unverified_inputs"]:
        a2.text(0.5, 0.5, f"{co['n_unverified_inputs']} UNVERIFIED INPUTS", transform=a2.transAxes, ha="center", va="center",
                fontsize=18, color="red", alpha=0.25, rotation=20, weight="bold")
    fig.suptitle("Fig. 13 — TDD coexistence: cost of an uplink-heavy pattern next to MNO n78")
    fig.savefig(out / "fig13_cross_link.png", **SAVE_KW); plt.close(fig)


def _unverified_cost_stamp(ax, res):
    n = res["economics"]["n_unverified_inputs"]
    if n:
        ax.text(0.5, 0.5, f"{n} UNVERIFIED COST INPUTS\nillustrative only", transform=ax.transAxes, ha="center",
                va="center", fontsize=18, color="red", alpha=0.25, rotation=20, weight="bold")


def fig10_cost_breakdown(res, cfg, out):
    ec = res["economics"]
    keys = list(ec["scenarios"])
    labels = [f"{k}\n({ec['scenarios'][k]['snpn']['n_sites']} sites)" for k in keys]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.2))
    for ax, part, title in ((a1, "network_capex", "Network CAPEX (SNPN)"), (a2, "network_opex_per_year", "Network OPEX per year (SNPN)")):
        items = list(ec["scenarios"][keys[0]]["snpn"][part])
        bottom = np.zeros(len(keys))
        for it in items:
            v = np.array([ec["scenarios"][k]["snpn"][part][it] for k in keys]) / 1e6
            ax.bar(labels, v, bottom=bottom, label=it); bottom += v
        ax.set_ylabel("MEUR" if part == "network_capex" else "MEUR / year"); ax.set_title(title, fontsize=10)
        ax.legend(fontsize=7, loc="upper left"); ax.set_ylim(0, bottom.max() * 1.45); _unverified_cost_stamp(ax, res)
    auto = sum(ec["scenarios"][keys[0]]["snpn"]["automation_capex"].values()) / 1e6
    fig.suptitle(f"Fig. 10 — Network cost per site-count scenario (automation retrofit, not shown: {auto:.1f} MEUR)")
    fig.savefig(out / "fig10_cost_breakdown.png", **SAVE_KW); plt.close(fig)


def fig11_cash_flow(res, cfg, out):
    ec = res["economics"]
    fig, ax = plt.subplots(figsize=(8, 4.2))
    for k, byopt in ec["scenarios"].items():
        for opt, ls in (("snpn", "-"), ("pni_npn", "--")):
            e = byopt[opt]; y = np.array(e["use_case_cum_discounted"]) / 1e6
            ax.plot(np.arange(len(y)), y, ls, marker=".", label=f"{k} ({e['n_sites']} sites), {opt}")
    ax.axhline(0, color="k", lw=0.8); ax.set_xlabel("year"); ax.set_ylabel("cumulative discounted cash flow [MEUR]")
    ax.set_title("Fig. 11 — Use-case business case (network + automation cost vs labour savings)", fontsize=10)
    ax.legend(fontsize=7); _unverified_cost_stamp(ax, res)
    fig.savefig(out / "fig11_cash_flow.png", **SAVE_KW); plt.close(fig)


def fig12_npv_tornado(res, cfg, out):
    ec = res["economics"]; rows = ec["npv_sensitivity"][:10]
    base = rows[0]["npv_base"] / 1e6
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for i, r in enumerate(rows[::-1]):
        lo, hi = r["npv_low"] / 1e6, r["npv_high"] / 1e6
        ax.barh(i, lo - base, left=base, color="#1976d2"); ax.barh(i, hi - base, left=base, color="#f57c00")
    f = cfg.economics.model.sensitivity_fraction
    ax.set_yticks(range(len(rows))); ax.set_yticklabels([r["input"].split(".", 2)[-1] for r in rows[::-1]], fontsize=7)
    ax.axvline(base, color="k"); ax.set_xlabel(f"use-case NPV [MEUR] (base = {base:.1f}; blue -{f:.0%}, orange +{f:.0%})")
    ax.set_title(f"Fig. 12 — NPV sensitivity ({ec['base_site_scenario']}, {ec['base_n_sites']} sites, SNPN)", fontsize=10)
    _unverified_cost_stamp(ax, res)
    fig.savefig(out / "fig12_npv_tornado.png", **SAVE_KW); plt.close(fig)


def make_all(results_path: Path, out_dir: Path, cfg) -> list[Path]:
    res = _load(results_path); out_dir.mkdir(parents=True, exist_ok=True); made = []
    for name in FIG_ORDER:
        globals()[name](res, cfg, out_dir); made.append(out_dir / f"{name}.png")
    (out_dir / "MANIFEST.md").write_text("# Figure manifest (generated by `make figures`)\n\n" +
        "\n".join(f"- `{p.name}` — brief §7 item {i+1}" for i, p in enumerate(made)) + "\n", encoding="utf-8")
    return made
