"""Uplink/downlink link budget: thermal noise, required SINR, margins, MAPL, cell radius inversion.

Brief §4.2. The uplink governs site count; `budget_pair()` returns both directions so figure 3 can show which
is limiting. Every term comes from config (with provenance) or is derived here from a stated formula.

Required SINR is NOT guessed: it is derived from the target spectral efficiency via the normal approximation
(Polyanskiy–Poor–Verdú 2010) at the target BLER and blocklength, plus a configured implementation loss.
The 1e-5 vs 1e-1 BLER difference is therefore quantified, not asserted.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import brentq
from scipy.stats import norm

from . import channel
from .tables import NOISE_DENSITY_DBM_HZ, SCS_KHZ, SUBCARRIERS_PER_PRB


def thermal_noise_dbm(bandwidth_hz: float, noise_figure_db: float = 0.0) -> float:
    """N = −174 dBm/Hz + 10·log10(B) + NF.  Anchors: 100 MHz → −94.0 dBm; 360 kHz → −118.4 dBm."""
    return NOISE_DENSITY_DBM_HZ + 10.0 * math.log10(bandwidth_hz) + noise_figure_db


def prb_bandwidth_hz(mu: int, n_prb: int = 1) -> float:
    return n_prb * SUBCARRIERS_PER_PRB * SCS_KHZ[mu] * 1e3


# --------------------------------------------------------------------------------------------------
# Required SINR from spectral efficiency and BLER (finite-blocklength normal approximation)
# --------------------------------------------------------------------------------------------------
def _normal_approx_rate(snr_lin: float, n: int, eps: float) -> float:
    """Achievable rate [bit/channel use]: C − sqrt(V/n)·Q⁻¹(ε) + (log2 n)/(2n)  (PPV 2010, AWGN)."""
    c = math.log2(1.0 + snr_lin)
    v = (1.0 - 1.0 / (1.0 + snr_lin) ** 2) * (math.log2(math.e)) ** 2
    return c - math.sqrt(v / n) * norm.isf(eps) + math.log2(n) / (2.0 * n)


def required_snr_db(spectral_eff: float, bler: float, blocklength: int | None = None,
                    implementation_loss_db: float = 0.0) -> float:
    """SNR [dB] needed for `spectral_eff` bit/s/Hz (per layer) at block error rate `bler`.

    blocklength=None → Shannon limit (infinite n). The BLER penalty is the difference between calls with
    bler=1e-5 and bler=1e-1 at the same n — the brief asks for exactly that number.
    """
    if spectral_eff <= 0:
        return -math.inf
    if blocklength is None:
        snr = 2.0**spectral_eff - 1.0
    else:
        f = lambda s: _normal_approx_rate(s, blocklength, bler) - spectral_eff  # noqa: E731
        snr = brentq(f, 1e-6, 1e9, xtol=1e-9)
    return 10.0 * math.log10(snr) + implementation_loss_db


def bler_penalty_db(spectral_eff: float, blocklength: int, bler_strict: float, bler_loose: float = 0.1) -> float:
    return required_snr_db(spectral_eff, bler_strict, blocklength) - required_snr_db(spectral_eff, bler_loose, blocklength)


# --------------------------------------------------------------------------------------------------
# Budget
# --------------------------------------------------------------------------------------------------
@dataclass
class LinkBudget:
    direction: str            # "UL" | "DL"
    service: str
    zone: str
    ue_class: str
    terms: dict[str, float] = field(default_factory=dict)   # ordered: gains (+) and losses (−) in dB
    mapl_db: float = 0.0
    required_sinr_db: float = 0.0
    noise_dbm: float = 0.0
    notes: list[str] = field(default_factory=list)

    def waterfall(self) -> list[tuple[str, float]]:
        return list(self.terms.items())


def _diversity_gain_db(n_rx: int) -> float:
    """Ideal MRC array gain in a noise-limited regime (upper bound): 10·log10(N_rx)."""
    return 10.0 * math.log10(max(n_rx, 1))


def uplink_budget(cfg, service: str, zone: str, target_se: float, bler: float, n_prb_alloc: int,
                  area_availability: float, sigma_db: float, pl_exponent: float,
                  interference_margin_db: float | None = None, blocklength: int | None = None) -> LinkBudget:
    from .reliability import shadow_margin_for_area_availability

    ue = cfg.ues.classes[cfg.services[service].ue_class]
    g = cfg.ues.gnb
    ll = cfg.latency.link_level
    mu = cfg.band.numerology.mu
    im = ll.interference_margin_db if interference_margin_db is None else interference_margin_db
    n_bl = ll.finite_blocklength_n if blocklength is None else blocklength

    noise = thermal_noise_dbm(prb_bandwidth_hz(mu, n_prb_alloc), g.noise_figure_db)
    req_sinr = required_snr_db(target_se, bler, n_bl, ll.implementation_loss_db)
    sf_margin, edge_p = shadow_margin_for_area_availability(area_availability, sigma_db, pl_exponent)

    terms = {
        "UE Tx power": ue.tx_power_dbm,
        "UE antenna gain": +ue.antenna_gain_dbi,
        "UE cable loss": -(ue.cable_loss_db if "cable_loss_db" in ue else 0.0),
        "Body/mounting loss": -ue.body_loss_db,
        "gNB antenna gain": +g.antenna_gain_dbi,
        "gNB beamforming gain": +g.beamforming_gain_db,
        "gNB cable loss": -g.cable_loss_db,
        "Rx diversity (MRC)": +_diversity_gain_db(cfg.band.power.gnb_n_rx_ports),
        f"Thermal noise ({n_prb_alloc} PRB)": -noise,
        "Required SINR": -req_sinr,
        "Interference margin": -im,
        f"Shadow margin ({area_availability:.1%} area)": -sf_margin,
        "Blockage margin": -cfg.scenario_best.zones[zone].blockage_loss_db * cfg.scenario_best.zones[zone].blockage_prob,
    }
    mapl = sum(terms.values())
    lb = LinkBudget("UL", service, zone, cfg.services[service].ue_class, terms, mapl, req_sinr, noise)
    lb.notes.append(f"shadow margin sized for {area_availability:.1%} area availability -> edge p={edge_p:.4f}")
    lb.notes.append(f"required SINR at BLER {bler:g}, n={n_bl}: {req_sinr:.2f} dB "
                    f"(penalty vs BLER 0.1: {bler_penalty_db(target_se, n_bl, bler):.2f} dB)")
    lb.notes.append("blockage term = E[loss] = p_block x loss (mean, not tail) — see assumptions")
    return lb


def downlink_budget(cfg, service: str, zone: str, target_se: float, bler: float, n_prb_alloc: int,
                    area_availability: float, sigma_db: float, pl_exponent: float,
                    interference_margin_db: float | None = None) -> LinkBudget:
    from .reliability import shadow_margin_for_area_availability

    ue = cfg.ues.classes[cfg.services[service].ue_class]
    g = cfg.ues.gnb
    ll = cfg.latency.link_level
    mu = cfg.band.numerology.mu
    im = ll.interference_margin_db if interference_margin_db is None else interference_margin_db
    n_tx = cfg.band.power.gnb_n_tx_ports
    # Power per PRB: total power spread over all PRBs of the carrier; +10log10(N_tx) for coherent combining
    p_tot = cfg.band.power.gnb_tx_power_dbm_per_port + 10 * math.log10(n_tx)
    p_prb = p_tot - 10 * math.log10(cfg.band.numerology.n_prb / n_prb_alloc)

    noise = thermal_noise_dbm(prb_bandwidth_hz(mu, n_prb_alloc), ue.noise_figure_db)
    req_sinr = required_snr_db(target_se, bler, ll.finite_blocklength_n, ll.implementation_loss_db)
    sf_margin, _ = shadow_margin_for_area_availability(area_availability, sigma_db, pl_exponent)
    terms = {
        f"gNB Tx power ({n_prb_alloc} PRB share)": p_prb,
        "gNB antenna gain": +g.antenna_gain_dbi,
        "gNB beamforming gain": +g.beamforming_gain_db,
        "gNB cable loss": -g.cable_loss_db,
        "UE antenna gain": +ue.antenna_gain_dbi,
        "Body/mounting loss": -ue.body_loss_db,
        "Rx diversity (MRC)": +_diversity_gain_db(ue.n_rx_antennas),
        f"Thermal noise ({n_prb_alloc} PRB)": -noise,
        "Required SINR": -req_sinr,
        "Interference margin": -im,
        f"Shadow margin ({area_availability:.1%} area)": -sf_margin,
        "Blockage margin": -cfg.scenario_best.zones[zone].blockage_loss_db * cfg.scenario_best.zones[zone].blockage_prob,
    }
    mapl = sum(terms.values())
    lb = LinkBudget("DL", service, zone, cfg.services[service].ue_class, terms, mapl, req_sinr, noise)
    lb.notes.append("regulatory EIRP cap from CNAF not applied — [UNVERIFIED]; check band.yaml power.regulatory_eirp_limit_dbm")
    return lb


def cell_radius_m(zc: channel.ZoneChannel, mapl_db: float, fc_ghz: float, h_bs: float, h_ut: float,
                  d_max: float | None = None) -> float:
    """Invert the zone's LOS-probability-weighted mean path loss to the 2-D distance where PL = MAPL.

    The result is capped at the model's validity limit (InF: d3D <= 600 m; UMi: 5 km) — rule §10.7. A radius
    equal to the cap means 'coverage-unlimited within the model', not a measured 600 m cell."""
    if d_max is None:
        d_max = channel.INF_D3D_RANGE_M[1] if zc.model == "InF" else channel.UMI_D2D_RANGE_M[1]
    def f(d2d):
        d3d = channel.d3d_from_d2d(d2d, h_bs, h_ut)
        return float(zc.mean_pl(d3d, fc_ghz, h_bs, h_ut, check=False)) - mapl_db
    if f(1.0) > 0:
        return 0.0
    if f(d_max) < 0:
        return d_max
    return float(brentq(f, 1.0, d_max, xtol=0.01))


def pl_exponent_estimate(zc: channel.ZoneChannel, fc_ghz: float, h_bs: float, h_ut: float,
                         d1: float = 50.0, d2: float = 300.0) -> float:
    """Local path-loss exponent n of the zone's mean model between d1 and d2 (for the Jakes formula)."""
    p1 = float(zc.mean_pl(channel.d3d_from_d2d(d1, h_bs, h_ut), fc_ghz, h_bs, h_ut, check=False))
    p2 = float(zc.mean_pl(channel.d3d_from_d2d(d2, h_bs, h_ut), fc_ghz, h_bs, h_ut, check=False))
    return (p2 - p1) / (10.0 * math.log10(d2 / d1))


def radius_vs_throughput(cfg, zc: channel.ZoneChannel, ue_class: str, throughputs_mbps: np.ndarray,
                         h_bs: float, bler: float, area_availability: float, n_prb_alloc: int) -> np.ndarray:
    """Figure 4: cell radius as a function of required UL throughput for one UE power class."""
    from .reliability import shadow_margin_for_area_availability
    ue = cfg.ues.classes[ue_class]
    g, ll, mu = cfg.ues.gnb, cfg.latency.link_level, cfg.band.numerology.mu
    fc = cfg.band.carrier.fc_ghz
    bw = prb_bandwidth_hz(mu, n_prb_alloc)
    duty = _ul_duty(cfg)
    noise = thermal_noise_dbm(bw, g.noise_figure_db)
    n_exp = pl_exponent_estimate(zc, fc, h_bs, ue.height_m)
    sf_margin, _ = shadow_margin_for_area_availability(area_availability, zc.sigma_nlos(), n_exp)
    fixed = (ue.tx_power_dbm + ue.antenna_gain_dbi - ue.body_loss_db - (ue.cable_loss_db if "cable_loss_db" in ue else 0.0)
             + g.antenna_gain_dbi + g.beamforming_gain_db - g.cable_loss_db
             + _diversity_gain_db(cfg.band.power.gnb_n_rx_ports) - noise - ll.interference_margin_db - sf_margin)
    out = []
    for t in throughputs_mbps:
        se = t * 1e6 / (bw * duty * (1 - 0.08))   # bit/s/Hz needed on the allocated PRBs
        if se > ll.max_spectral_efficiency_ul:
            out.append(0.0); continue
        req = required_snr_db(se, bler, ll.finite_blocklength_n, ll.implementation_loss_db)
        out.append(cell_radius_m(zc, fixed - req, fc, h_bs, ue.height_m))
    return np.asarray(out)


def _ul_duty(cfg) -> float:
    from .capacity import tdd_duty_cycle
    return tdd_duty_cycle(cfg.band.tdd.pattern, cfg.band.tdd.special_slot_symbols).ul_fraction
