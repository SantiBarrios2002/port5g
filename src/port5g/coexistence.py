"""TDD cross-link interference against the adjacent MNO n78 carrier (brief §2.2 — the "coexistence trap").

If our pattern is uplink-heavy (e.g. DSUUU) while the adjacent MNO runs DDDSU, some symbols have one network
transmitting downlink while the other receives uplink. Four interference links result:

* ours U / MNO D:  MNO gNB -> our gNB (victim: us)       and  our UE -> MNO UE (victim: MNO)
* ours D / MNO U:  our gNB -> MNO gNB (victim: MNO)      and  MNO UE -> our UE (victim: us)

Method — minimum coupling loss (MCL), deterministic:

    I = EIRP_aggressor + G_rx_victim - losses - PL(d) - ACIR,   1/ACIR = 1/ACLR + 1/ACS   (linear)
    N = -174 dBm/Hz + 10 log10(BW) + NF_victim
    required PL = I(PL=0) - N - (I/N)_protection  ->  separation distance from free-space path loss.

Free space is the worst case (LOS over the apron/water); real clutter only helps. Beamforming gain is excluded on
both sides (beams are not steered at the other network). Frames are assumed aligned with the same numerology.
"""
from __future__ import annotations

import warnings

import numpy as np

from .linkbudget import thermal_noise_dbm

C_M_S = 299_792_458.0


def expand_symbols(pattern: str, special: dict) -> str:
    """Slot pattern -> symbol string of D/G/U (14 symbols per slot, special slot split per TS 38.213 §11.1)."""
    out = []
    for s in pattern:
        if s == "D":
            out.append("D" * 14)
        elif s == "U":
            out.append("U" * 14)
        elif s == "S":
            if special["dl"] + special["gp"] + special["ul"] != 14:
                raise ValueError(f"special slot split {special} does not sum to 14 symbols")
            out.append("D" * special["dl"] + "G" * special["gp"] + "U" * special["ul"])
        else:
            raise ValueError(f"unknown slot letter '{s}' in {pattern}")
    return "".join(out)


def conflict_fractions(ours: str, mno: str, special: dict) -> dict[str, float]:
    """Fraction of symbols in each cross-link state. Patterns must have the same period (aligned frames)."""
    a, b = expand_symbols(ours, special), expand_symbols(mno, special)
    if len(a) != len(b):
        raise ValueError(f"patterns {ours} and {mno} have different periods; aligned-frame model does not apply")
    n = len(a)
    return {"ours_U_mno_D": sum(x == "U" and y == "D" for x, y in zip(a, b)) / n,
            "ours_D_mno_U": sum(x == "D" and y == "U" for x, y in zip(a, b)) / n}


def fspl_db(d_m, f_ghz: float):
    """Free-space path loss 20 log10(4 pi d f / c) [dB]."""
    return 20 * np.log10(4 * np.pi * np.asarray(d_m, dtype=float) * f_ghz * 1e9 / C_M_S)


def fspl_distance_m(pl_db: float, f_ghz: float) -> float:
    """Inverse of fspl_db."""
    return float(10 ** (pl_db / 20) * C_M_S / (4 * np.pi * f_ghz * 1e9))


def acir_db(aclr_db: float, acs_db: float) -> float:
    return float(-10 * np.log10(10 ** (-aclr_db / 10) + 10 ** (-acs_db / 10)))


def _ue_eirp(ue) -> float:
    return ue.tx_power_dbm + ue.antenna_gain_dbi - ue.body_loss_db - (ue.cable_loss_db if "cable_loss_db" in ue else 0.0)


def _ue_rx_gain(ue) -> float:
    return ue.antenna_gain_dbi - ue.body_loss_db - (ue.cable_loss_db if "cable_loss_db" in ue else 0.0)


def links(cfg) -> dict[str, dict]:
    """The four cross-link budgets: interference at PL = 0 dB, victim noise, required path loss and separation."""
    co = cfg.band.coexistence
    g, pw = cfg.ues.gnb, cfg.band.power
    bw_hz = cfg.band.carrier.bandwidth_mhz * 1e6
    fc = cfg.band.carrier.fc_ghz
    our_ue = cfg.ues.classes[co.our_ue_aggressor_class]
    mno_ue = cfg.ues.classes[co.mno_ue_class]
    our_victim_ue = cfg.ues.classes["handheld"]
    acir_bs = acir_db(co.bs_aclr_db, co.bs_acs_db)
    acir_ue = acir_db(co.ue_aclr_db, co.ue_acs_db)
    our_gnb_eirp = pw.gnb_tx_power_dbm_per_port + 10 * np.log10(pw.gnb_n_tx_ports) + g.antenna_gain_dbi - g.cable_loss_db
    raw = {
        # name: (state, victim, I at PL=0 [dBm], victim NF [dB])
        "MNO gNB -> our gNB": ("ours_U_mno_D", "ours",
                               co.mno_gnb_eirp_dbm - co.mno_antenna_discrimination_db + g.antenna_gain_dbi - g.cable_loss_db - acir_bs,
                               g.noise_figure_db),
        "our UE -> MNO UE": ("ours_U_mno_D", "MNO", _ue_eirp(our_ue) + _ue_rx_gain(mno_ue) - acir_ue, mno_ue.noise_figure_db),
        "our gNB -> MNO gNB": ("ours_D_mno_U", "MNO",
                               our_gnb_eirp + co.mno_gnb_rx_antenna_gain_dbi - co.mno_antenna_discrimination_db - acir_bs,
                               co.mno_gnb_noise_figure_db),
        "MNO UE -> our UE": ("ours_D_mno_U", "ours", _ue_eirp(mno_ue) + _ue_rx_gain(our_victim_ue) - acir_ue,
                             our_victim_ue.noise_figure_db),
    }
    out = {}
    for name, (state, victim, i0, nf) in raw.items():
        n = thermal_noise_dbm(bw_hz, nf)
        req_pl = i0 - n - co.protection_i_over_n_db
        out[name] = {"state": state, "victim": victim, "i_at_0db_dbm": float(i0), "noise_dbm": float(n),
                     "acir_db": acir_bs if "gNB ->" in name else acir_ue,
                     "required_pl_db": float(req_pl), "required_separation_m": fspl_distance_m(req_pl, fc)}
    return out


def spectrum_fit(cfg) -> dict:
    """Carrier edges vs the declared self-provision sub-range and the MNO band edge."""
    fc_mhz = cfg.band.carrier.fc_ghz * 1e3
    half = cfg.band.carrier.bandwidth_mhz / 2
    lo, hi = fc_mhz - half, fc_mhz + half
    sub = cfg.band.spectrum.cnaf.local_broadband_low_medium_power_mhz
    inside = bool(sub[0] <= lo and hi <= sub[1])
    if not inside:
        warnings.warn(f"carrier {lo:.0f}-{hi:.0f} MHz is not inside the declared sub-range {sub[0]}-{sub[1]} MHz "
                      "(band.carrier.fc_ghz / bandwidth_mhz vs spectrum.cnaf)", UserWarning, stacklevel=2)
    return {"carrier_mhz": [lo, hi], "subrange_mhz": list(sub), "inside_subrange": inside,
            "guard_to_mno_mhz": lo - cfg.band.coexistence.mno_band_upper_edge_mhz}


def run(cfg) -> dict:
    co = cfg.band.coexistence
    special = dict(cfg.band.tdd.special_slot_symbols)
    lk = links(cfg)
    d_near = co.mno_nearest_site_distance_m
    fc = cfg.band.carrier.fc_ghz
    by_pattern = {}
    for pat in cfg.band.tdd.candidates:
        frac = conflict_fractions(pat, co.mno_pattern, special)
        active = [k for k, v in lk.items() if frac[v["state"]] > 0]
        bs_active = [k for k in active if "gNB ->" in k]
        # I/N at the nearest MNO site for the active gNB-gNB links: > protection -> unsynchronised operation fails
        in_at_site = {k: lk[k]["i_at_0db_dbm"] - float(fspl_db(d_near, fc)) - lk[k]["noise_dbm"] for k in bs_active}
        by_pattern[pat] = {"conflict_fraction": frac, "active_links": active,
                           "i_over_n_at_nearest_mno_site_db": in_at_site,
                           "bs_bs_feasible_at_nearest_site": all(v <= co.protection_i_over_n_db for v in in_at_site.values()),
                           "extra_isolation_needed_db": max([v - co.protection_i_over_n_db for v in in_at_site.values()] + [0.0])}
    ever_active = sorted({k for v in by_pattern.values() for k in v["active_links"]})
    unverified = [p.path for p in cfg.registry if p.path.startswith("band.coexistence.") and p.unverified]
    return {"n_unverified_inputs": len(unverified), "unverified_inputs": unverified, "ever_active_links": ever_active,
            "mno_pattern": co.mno_pattern, "protection_i_over_n_db": co.protection_i_over_n_db,
            "nearest_mno_site_m": d_near, "links": lk, "by_pattern": by_pattern, "spectrum_fit": spectrum_fit(cfg),
            "guard_band_note": ("TS 38.104 BS ACLR is the same in the first and second adjacent channel, so with "
                                "minimum-spec equipment a guard band gives no extra isolation; only extra filtering "
                                "(product datasheet), separation, or synchronisation reduce the interference.")}
