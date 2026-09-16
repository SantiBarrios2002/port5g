"""TS 38.306 §4.1.2 approximate maximum data rate, TDD duty cycle, SINR -> spectral efficiency.

data_rate_38306 implements the formula EXACTLY with the spec's parameter names so it can be checked line by
line against TS 38.306 §4.1.2:

    R = 1e-6 · Σ_j ( v_layers^(j) · Qm^(j) · f^(j) · R_max · (N_PRB^{BW(j),µ} · 12) / T_s^µ · (1 − OH^(j)) )

with R_max = 948/1024 and T_s^µ = 1e-3 / (14 · 2^µ).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .tables import OH_FR1_DL, OH_FR1_UL, OH_FR2_DL, OH_FR2_UL, R_MAX, SUBCARRIERS_PER_PRB, SYMBOLS_PER_SLOT


def symbol_duration_s(mu: int) -> float:
    """T_s^µ = 1e-3 / (14 · 2^µ) — average OFDM symbol duration in a subframe for numerology µ."""
    return 1e-3 / (SYMBOLS_PER_SLOT * 2**mu)


def slot_duration_ms(mu: int) -> float:
    return 1.0 / 2**mu


def data_rate_38306(v_layers, Qm, f, N_PRB, mu, OH, R_max: float = R_MAX) -> float:
    """Approximate max data rate [Mbit/s], TS 38.306 §4.1.2. Scalar args = a single carrier (J = 1);
    list args = per-carrier components summed over j (carrier aggregation)."""
    v_layers, Qm, f, N_PRB, mu, OH = (np.atleast_1d(np.asarray(x, dtype=float)) for x in (v_layers, Qm, f, N_PRB, mu, OH))
    T_s = 1e-3 / (SYMBOLS_PER_SLOT * 2.0**mu)
    per_carrier = v_layers * Qm * f * R_max * (N_PRB * SUBCARRIERS_PER_PRB) / T_s * (1.0 - OH)
    return float(1e-6 * np.sum(per_carrier))


def overhead(direction: str, fr: int = 1) -> float:
    if fr == 1:
        return OH_FR1_DL if direction == "DL" else OH_FR1_UL
    return OH_FR2_DL if direction == "DL" else OH_FR2_UL


@dataclass(frozen=True)
class TddDuty:
    pattern: str
    dl_fraction: float
    ul_fraction: float
    gp_fraction: float


def tdd_duty_cycle(pattern: str, special: dict | None = None) -> TddDuty:
    """Symbol-level DL/UL/GP fractions for a slot-format string such as 'DDDSU'.

    `special` = {dl: n_D, gp: n_G, ul: n_U} symbols in the S slot (must sum to 14).
    """
    special = special or {"dl": 10, "gp": 2, "ul": 2}
    if sum(special.values()) != SYMBOLS_PER_SLOT:
        raise ValueError("special-slot symbols must sum to 14")
    n = len(pattern) * SYMBOLS_PER_SLOT
    dl = ul = gp = 0
    for ch in pattern.upper():
        if ch == "D":
            dl += SYMBOLS_PER_SLOT
        elif ch == "U":
            ul += SYMBOLS_PER_SLOT
        elif ch == "S":
            dl += special["dl"]; gp += special["gp"]; ul += special["ul"]
        else:
            raise ValueError(f"bad slot letter {ch!r}")
    return TddDuty(pattern.upper(), dl / n, ul / n, gp / n)


def spectral_efficiency_from_sinr(sinr_db, alpha: float, se_max: float, sinr_min_db: float = -10.0):
    """Attenuated-Shannon mapping (TR 36.942 Annex A.2): SE = α·log2(1+SINR), clipped to [0, se_max];
    below sinr_min_db the link is declared out of coverage (SE = 0)."""
    sinr_db = np.asarray(sinr_db, dtype=float)
    se = alpha * np.log2(1.0 + 10 ** (sinr_db / 10.0))
    se = np.where(sinr_db < sinr_min_db, 0.0, np.minimum(se, se_max))
    return se


def cell_throughput_mbps(se_bit_s_hz, n_prb: int, mu: int, layers: int, oh: float, duty: float) -> float:
    """Achievable throughput given a spectral efficiency (per layer), PRBs, layers, overhead and TDD duty."""
    from .tables import SCS_KHZ
    bw_hz = n_prb * SUBCARRIERS_PER_PRB * SCS_KHZ[mu] * 1e3
    return float(np.mean(se_bit_s_hz) * bw_hz * layers * (1.0 - oh) * duty / 1e6)


def peak_rates_from_config(cfg) -> dict:
    """Peak DL/UL for the configured carrier (used as a sanity line in figure 7)."""
    b = cfg.band
    mu, n_prb = b.numerology.mu, b.numerology.n_prb
    fr = 2 if b.carrier.fc_ghz > 7.125 else 1
    return {
        "dl_peak_mbps": data_rate_38306(4, 8, 1.0, n_prb, mu, overhead("DL", fr)),
        "ul_peak_mbps": data_rate_38306(1, 6, 1.0, n_prb, mu, overhead("UL", fr)),
        "ul_peak_2layer_mbps": data_rate_38306(2, 6, 1.0, n_prb, mu, overhead("UL", fr)),
    }
