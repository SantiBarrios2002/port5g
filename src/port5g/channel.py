"""TR 38.901 path-loss models: UMi-Street Canyon and Indoor Factory (InF), LOS probability, shadowing, blockage.

Pure functions, no globals (brief §6 module contract). Shadowing is applied by the caller with a seeded RNG.

Coefficients: 3GPP TR 38.901 Table 7.4.1-1 (path loss), Table 7.4.2-1 (LOS probability), Table 7.2-4
(InF sub-scenario parameters). All coefficients are SECONDARY (from the spec as remembered/transcribed) and
must be re-verified against the current TR before shipping — the §4.1 anchors in tests/test_channel.py check
the transcription at one operating point only.

Validity ranges are enforced with warnings (brief §10.7): the code never silently extrapolates.
"""
from __future__ import annotations

import math
import warnings
from dataclasses import dataclass

import numpy as np

C_LIGHT = 299_792_458.0  # m/s

MODELS = ("UMi_SC", "InF")
INF_SUBSCENARIOS = ("InF-SL", "InF-DL", "InF-SH", "InF-DH")

# Shadow-fading σ [dB], TR 38.901 Table 7.4.1-1
SF_SIGMA_DB = {
    ("UMi_SC", True): 4.0,
    ("UMi_SC", False): 7.82,
    ("InF", True): 4.3,
    ("InF-SL", False): 5.7,
    ("InF-DL", False): 7.2,
    ("InF-SH", False): 5.9,
    ("InF-DH", False): 4.0,
}

# Validity ranges (TR 38.901 Table 7.4.1-1 notes)
UMI_D2D_RANGE_M = (10.0, 5000.0)
UMI_HUT_RANGE_M = (1.5, 22.5)
INF_D3D_RANGE_M = (1.0, 600.0)
FC_RANGE_GHZ = (0.5, 100.0)


class ModelValidityWarning(UserWarning):
    """A path-loss model was evaluated outside its stated validity range."""


def _check_range(name: str, x, lo: float, hi: float, model: str) -> None:
    x = np.asarray(x, dtype=float)
    if np.any(x < lo) or np.any(x > hi):
        warnings.warn(
            f"{model}: {name} outside validity range [{lo}, {hi}] "
            f"(min={float(np.min(x)):.3g}, max={float(np.max(x)):.3g}) — TR 38.901 Table 7.4.1-1 note",
            ModelValidityWarning,
            stacklevel=3,
        )


def d3d_from_d2d(d2d, h_bs: float, h_ut: float):
    return np.sqrt(np.asarray(d2d, dtype=float) ** 2 + (h_bs - h_ut) ** 2)


def d2d_from_d3d(d3d, h_bs: float, h_ut: float):
    d3d = np.asarray(d3d, dtype=float)
    return np.sqrt(np.maximum(d3d**2 - (h_bs - h_ut) ** 2, 0.0))


# --------------------------------------------------------------------------------------------------
# UMi — Street Canyon (TR 38.901 Table 7.4.1-1)
# --------------------------------------------------------------------------------------------------
def umi_breakpoint_distance_m(fc_ghz: float, h_bs: float, h_ut: float) -> float:
    """d'_BP = 4 h'_BS h'_UT f_c / c with h' = h − h_E, h_E = 1.0 m for UMi (TR 38.901 note 1)."""
    h_e = 1.0
    return 4.0 * (h_bs - h_e) * (h_ut - h_e) * fc_ghz * 1e9 / C_LIGHT


def umi_sc_los(d3d, fc_ghz: float, h_bs: float, h_ut: float, check: bool = True):
    """UMi-SC LOS path loss [dB]. PL1 below the breakpoint distance, PL2 above."""
    d3d = np.asarray(d3d, dtype=float)
    d2d = d2d_from_d3d(d3d, h_bs, h_ut)
    if check:
        _check_range("d2D", d2d, *UMI_D2D_RANGE_M, "UMi-SC LOS")
        _check_range("h_UT", h_ut, *UMI_HUT_RANGE_M, "UMi-SC LOS")
        _check_range("f_c", fc_ghz, *FC_RANGE_GHZ, "UMi-SC LOS")
    dbp = umi_breakpoint_distance_m(fc_ghz, h_bs, h_ut)
    pl1 = 32.4 + 21.0 * np.log10(d3d) + 20.0 * np.log10(fc_ghz)
    pl2 = (32.4 + 40.0 * np.log10(d3d) + 20.0 * np.log10(fc_ghz)
           - 9.5 * np.log10(dbp**2 + (h_bs - h_ut) ** 2))
    return np.where(d2d <= dbp, pl1, pl2)


def umi_sc_nlos(d3d, fc_ghz: float, h_bs: float, h_ut: float, check: bool = True):
    """UMi-SC NLOS path loss [dB] = max(PL_LOS, PL'_NLOS)."""
    d3d = np.asarray(d3d, dtype=float)
    pl_los = umi_sc_los(d3d, fc_ghz, h_bs, h_ut, check=check)
    pl_nlos = 35.3 * np.log10(d3d) + 22.4 + 21.3 * np.log10(fc_ghz) - 0.3 * (h_ut - 1.5)
    return np.maximum(pl_los, pl_nlos)


def umi_los_probability(d2d):
    """TR 38.901 Table 7.4.2-1, UMi-Street Canyon (outdoor users)."""
    d2d = np.asarray(d2d, dtype=float)
    d = np.maximum(d2d, 1e-9)
    p = 18.0 / d + np.exp(-d / 36.0) * (1.0 - 18.0 / d)
    return np.where(d2d <= 18.0, 1.0, p)


# --------------------------------------------------------------------------------------------------
# InF — Indoor Factory (TR 38.901 Table 7.4.1-1)
# --------------------------------------------------------------------------------------------------
def inf_los(d3d, fc_ghz: float, check: bool = True):
    d3d = np.asarray(d3d, dtype=float)
    if check:
        _check_range("d3D", d3d, *INF_D3D_RANGE_M, "InF LOS")
        _check_range("f_c", fc_ghz, *FC_RANGE_GHZ, "InF LOS")
    return 31.84 + 21.50 * np.log10(d3d) + 19.00 * np.log10(fc_ghz)


_INF_NLOS_COEFF = {  # PL' = A + B log10(d3D) + C log10(fc)
    "InF-SL": (33.0, 25.5, 20.0),
    "InF-DL": (18.6, 35.7, 20.0),
    "InF-SH": (32.4, 23.0, 20.0),
    "InF-DH": (33.63, 21.9, 20.0),
}


def inf_nlos(d3d, fc_ghz: float, sub_scenario: str, check: bool = True):
    """InF NLOS path loss [dB] = max(PL_LOS, PL'_sub). InF-DL additionally takes max with InF-SL."""
    if sub_scenario not in INF_SUBSCENARIOS:
        raise ValueError(f"unknown InF sub-scenario {sub_scenario!r}; choose from {INF_SUBSCENARIOS}")
    d3d = np.asarray(d3d, dtype=float)
    pl_los = inf_los(d3d, fc_ghz, check=check)
    a, b, c = _INF_NLOS_COEFF[sub_scenario]
    pl = a + b * np.log10(d3d) + c * np.log10(fc_ghz)
    if sub_scenario == "InF-DL":
        a2, b2, c2 = _INF_NLOS_COEFF["InF-SL"]
        pl = np.maximum(pl, a2 + b2 * np.log10(d3d) + c2 * np.log10(fc_ghz))
    return np.maximum(pl_los, pl)


def inf_los_probability(d2d, sub_scenario: str, d_clutter_m: float, r: float,
                        h_bs: float, h_ut: float, h_c: float):
    """TR 38.901 Table 7.4.2-1 InF: P_LOS = exp(−d2D / k_subsce).

    k = −d_clutter / ln(1 − r)                              for InF-SL, InF-DL (low BS)
    k = −d_clutter / ln(1 − r) · (h_BS − h_UT)/(h_c − h_UT) for InF-SH, InF-DH (BS above clutter)

    This is the mapping the report must state explicitly: r = ground fraction covered by container stacks,
    h_c = stack height, d_clutter = characteristic stack/container size.
    """
    if not 0.0 < r < 1.0:
        raise ValueError("clutter density r must be in (0, 1)")
    k = -d_clutter_m / math.log(1.0 - r)
    if sub_scenario in ("InF-SH", "InF-DH"):
        if h_c <= h_ut:
            raise ValueError("InF-SH/DH require h_c > h_UT (BS elevated above clutter, UT below it)")
        k *= (h_bs - h_ut) / (h_c - h_ut)
    return np.exp(-np.asarray(d2d, dtype=float) / k)


# --------------------------------------------------------------------------------------------------
# Unified interface
# --------------------------------------------------------------------------------------------------
def path_loss(model: str, d3d, fc_ghz: float, h_bs: float, h_ut: float, los: bool,
              sub_scenario: str | None = None, check: bool = True):
    """Path loss [dB]. model ∈ {'UMi_SC', 'InF'}; sub_scenario required for InF NLOS."""
    if model == "UMi_SC":
        return umi_sc_los(d3d, fc_ghz, h_bs, h_ut, check) if los else umi_sc_nlos(d3d, fc_ghz, h_bs, h_ut, check)
    if model == "InF":
        if los:
            return inf_los(d3d, fc_ghz, check)
        if sub_scenario is None:
            raise ValueError("InF NLOS needs sub_scenario")
        return inf_nlos(d3d, fc_ghz, sub_scenario, check)
    raise ValueError(f"unknown model {model!r}; choose from {MODELS}")


def shadow_sigma_db(model: str, los: bool, sub_scenario: str | None = None) -> float:
    key = ("InF", True) if (model == "InF" and los) else ((sub_scenario, False) if model == "InF" else (model, los))
    return SF_SIGMA_DB[key]


def los_probability(model: str, d2d, **inf_kwargs):
    if model == "UMi_SC":
        return umi_los_probability(d2d)
    if model == "InF":
        return inf_los_probability(d2d, **inf_kwargs)
    raise ValueError(model)


def mean_path_loss(model: str, d3d, fc_ghz: float, h_bs: float, h_ut: float,
                   sub_scenario: str | None = None, inf_kwargs: dict | None = None, check: bool = True):
    """LOS-probability-weighted path loss in the linear (power) domain, for the deterministic planning pass."""
    d2d = d2d_from_d3d(d3d, h_bs, h_ut)
    p = los_probability(model, d2d, **(inf_kwargs or {})) if model == "InF" else umi_los_probability(d2d)
    pl_l = path_loss(model, d3d, fc_ghz, h_bs, h_ut, True, sub_scenario, check)
    pl_n = path_loss(model, d3d, fc_ghz, h_bs, h_ut, False, sub_scenario, check)
    # mean of linear gains -> dB (i.e. E[10^(-PL/10)])
    g = p * 10 ** (-pl_l / 10) + (1 - p) * 10 ** (-pl_n / 10)
    return -10 * np.log10(g)


def sample_shadowing(rng: np.random.Generator, sigma_db: float, shape) -> np.ndarray:
    """Log-normal shadow fading samples [dB] from a caller-seeded RNG (rule §10.4)."""
    return rng.normal(0.0, sigma_db, size=shape)


def stochastic_blockage_db(rng: np.random.Generator, p_block: float, loss_db: float, shape) -> np.ndarray:
    """Simple Bernoulli blockage term (brief §4.1 allows this instead of TR 38.901 Blockage Model A/B)."""
    return np.where(rng.random(shape) < p_block, loss_db, 0.0)


@dataclass(frozen=True)
class ZoneChannel:
    """Per-zone channel assignment resolved from config/scenario_best.yaml."""
    name: str
    model: str
    sub_scenario: str | None
    inf_kwargs: dict
    blockage_prob: float
    blockage_loss_db: float

    def mean_pl(self, d3d, fc_ghz: float, h_bs: float, h_ut: float, check: bool = True):
        kw = dict(self.inf_kwargs, h_bs=h_bs, h_ut=h_ut) if self.model == "InF" else None
        return mean_path_loss(self.model, d3d, fc_ghz, h_bs, h_ut, self.sub_scenario, kw, check)

    def sigma_los(self) -> float:
        return shadow_sigma_db(self.model, True, self.sub_scenario)

    def sigma_nlos(self) -> float:
        return shadow_sigma_db(self.model, False, self.sub_scenario)


def zone_channels_from_config(cfg) -> dict[str, ZoneChannel]:
    out = {}
    for name, z in cfg.scenario_best.zones.items():
        model = z.channel_model
        sub = z.inf_params.sub_scenario if model == "InF" else None
        inf_kwargs = {}
        if model == "InF":
            inf_kwargs = dict(sub_scenario=sub, d_clutter_m=z.inf_params.d_clutter_m,
                              r=z.inf_params.r, h_c=z.inf_params.h_c_m)
        out[name] = ZoneChannel(name, model, sub, inf_kwargs, z.blockage_prob, z.blockage_loss_db)
    return out
