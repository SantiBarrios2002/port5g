"""Residual error, availability and area coverage (Jakes) — brief §4.2, §4.4.

Formulas (all standard; sources in docstrings):
* Q-function via scipy.stats.norm.sf.
* Residual error after k independent (re)transmissions: BLER^k (chase/IR gain ignored — conservative,
  stated in report).
* PDCP duplication over 2 carriers (parallel): residual = BLER1 * BLER2 (independent fading assumed).
* Jakes area-coverage formula: W. C. Jakes, "Microwave Mobile Communications", 1974, §2.5 (also Rappaport
  "Wireless Communications", Eq. 4.xx): F_u = ½[1 − erf(a) + exp((1−2ab)/b²)(1 − erf((1−ab)/b))].
"""
from __future__ import annotations

import math

import numpy as np
from scipy.optimize import brentq
from scipy.special import erf
from scipy.stats import norm


def q_function(x: float) -> float:
    return float(norm.sf(x))


def q_inverse(p: float) -> float:
    return float(norm.isf(p))


def residual_error_harq(bler: float, n_tx: int) -> float:
    """P(all n_tx transmissions fail) under independent errors."""
    if n_tx < 1:
        raise ValueError("n_tx >= 1")
    return bler**n_tx


def residual_error_duplication(bler: float, n_legs: int = 2) -> float:
    """PDCP duplication: packet lost only if every leg fails simultaneously (single shot)."""
    return bler**n_legs


def min_transmissions_for_target(bler: float, target_residual: float) -> int:
    """Smallest n with bler^n <= target_residual."""
    n = 1
    while n * math.log10(bler) > math.log10(target_residual) + 1e-9:   # log domain avoids 0.1**5 > 1e-5 round-off
        n += 1
        if n > 32:
            raise RuntimeError("target unreachable with HARQ alone")
    return n


def cell_edge_margin_db(sigma_db: float, edge_prob: float) -> float:
    """Shadow margin so that the edge point is served with probability edge_prob."""
    return sigma_db * q_inverse(1.0 - edge_prob)


def jakes_area_coverage(edge_prob: float, sigma_db: float, pl_exponent: float) -> float:
    """Area coverage probability F_u given cell-edge coverage probability, σ and path-loss exponent n.

    a = Q⁻¹(1 − p_edge) · (1/√2) sign-convention: margin M = σ·Q⁻¹(1−p_edge); a = −M/(σ√2)
    b = 10·n·log10(e) / (σ√2)
    """
    margin = cell_edge_margin_db(sigma_db, edge_prob)
    a = -margin / (sigma_db * math.sqrt(2.0))
    b = 10.0 * pl_exponent * math.log10(math.e) / (sigma_db * math.sqrt(2.0))
    return 0.5 * (1.0 - erf(a) + math.exp((1.0 - 2.0 * a * b) / b**2) * (1.0 - erf((1.0 - a * b) / b)))


def shadow_margin_for_area_availability(target_area_prob: float, sigma_db: float,
                                        pl_exponent: float) -> tuple[float, float]:
    """Invert Jakes: find the cell-edge probability (and hence margin, dB) giving the target area coverage.

    Returns (margin_db, edge_prob). This is why 99.9 % area availability needs a very different margin
    from 95 % (brief §4.2).
    """
    f = lambda pe: jakes_area_coverage(pe, sigma_db, pl_exponent) - target_area_prob  # noqa: E731
    lo, hi = 0.5, 1.0 - 1e-9
    if f(lo) >= 0:
        return cell_edge_margin_db(sigma_db, lo), lo
    pe = brentq(f, lo, hi, xtol=1e-10)
    return cell_edge_margin_db(sigma_db, pe), pe


def availability_from_residual(residual: float) -> float:
    return 1.0 - residual


def pareto_harq_vs_duplication(bler_first: float, bler_retx: float, harq_rtt_ms: float,
                               base_latency_ms: float, max_retx: int = 3) -> dict:
    """Points for figure 6: latency (worst-case) vs residual error, HARQ chain vs 2-leg duplication."""
    harq = []
    for k in range(0, max_retx + 1):
        lat = base_latency_ms + k * harq_rtt_ms
        res = bler_first * (bler_retx**k) if k else bler_first
        harq.append({"n_tx": k + 1, "latency_ms": lat, "residual": res})
    dup = {"n_legs": 2, "latency_ms": base_latency_ms, "residual": residual_error_duplication(bler_first, 2),
           "spectral_efficiency_cost": 2.0}
    return {"harq": harq, "duplication": dup}


def as_nines(p: float) -> float:
    """Reliability expressed in 'nines': 0.99999 -> 5.0"""
    return -math.log10(max(1.0 - p, 1e-300))


__all__ = [n for n in dir() if not n.startswith("_")]
_ = np  # keep numpy import for callers doing vector math
