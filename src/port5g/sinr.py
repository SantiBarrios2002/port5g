"""Uplink SINR map over the yard grid with average inter-cell interference from neighbour cells.

Model (deterministic, documented for the report):
* Serving cell = lowest mean coupling loss (LOS-probability-weighted path loss, no shadowing).
* UE Tx power per PRB from open-loop fractional power control (TS 38.213 §7.1.1), parameters in band.yaml.
* UL interference at serving gNB s from neighbour cell c = UE Tx power × E over c's served grid points of
  the linear coupling gain to s (uniform UE distribution, full load, one co-scheduled UE per cell per PRB).
* Optional log-normal shadowing and blockage drawn with the master seed (rule §10.4) — off by default so
  figure 2 is reproducible in shape; on for the Monte-Carlo availability check.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import channel
from .geometry import Grid, Mount
from .linkbudget import prb_bandwidth_hz, thermal_noise_dbm


@dataclass
class SinrMap:
    grid: Grid
    serving: np.ndarray          # (N,) index into sites
    sinr_ul_db: np.ndarray       # (N,)
    rsrp_dbm: np.ndarray         # (N,) best-server received power per PRB (UL)
    coupling_db: np.ndarray      # (N, S) mean coupling loss to each site


def coupling_matrix(cfg, grid: Grid, sites: list[Mount], zone_ch: dict[str, channel.ZoneChannel],
                    ue_heights: dict[str, float]) -> np.ndarray:
    """Mean path loss [dB] from each grid point to each site, using the grid point's zone model."""
    fc = cfg.band.carrier.fc_ghz
    N, S = len(grid), len(sites)
    pl = np.full((N, S), np.inf)
    for zname, zc in zone_ch.items():
        m = grid.zone == zname
        if not m.any():
            continue
        h_ut = ue_heights[zname]
        for j, s in enumerate(sites):
            d2d = np.hypot(grid.x[m] - s.x, grid.y[m] - s.y)
            d3d = channel.d3d_from_d2d(d2d, s.h, h_ut)
            pl[m, j] = zc.mean_pl(d3d, fc, s.h, h_ut, check=False)
    return pl


def uplink_sinr_map(cfg, grid: Grid, sites: list[Mount], zone_ch: dict[str, channel.ZoneChannel],
                    ue_class: str, n_prb_alloc: int, shadowing: bool = False,
                    rng: np.random.Generator | None = None) -> SinrMap:
    ue = cfg.ues.classes[ue_class]
    g = cfg.ues.gnb
    ue_h = {z: ue.height_m for z in zone_ch}
    pl = coupling_matrix(cfg, grid, sites, zone_ch, ue_h)
    if shadowing:
        assert rng is not None, "seeded rng required for shadowing"
        for zname, zc in zone_ch.items():
            m = grid.zone == zname
            pl[m] += channel.sample_shadowing(rng, zc.sigma_nlos(), (int(m.sum()), len(sites)))
            pl[m] += channel.stochastic_blockage_db(rng, zc.blockage_prob, zc.blockage_loss_db, (int(m.sum()), len(sites)))
    ant = (ue.antenna_gain_dbi - ue.body_loss_db - (ue.cable_loss_db if "cable_loss_db" in ue else 0.0)
           + g.antenna_gain_dbi + g.beamforming_gain_db - g.cable_loss_db)
    cl = pl - ant                                   # coupling loss (N,S) incl. antenna gains
    serving = np.argmin(cl, axis=1)
    cl_serv = cl[np.arange(len(grid)), serving]
    # TS 38.213 §7.1.1 open-loop fractional power control, per-PRB transmit power
    pc = cfg.band.ul_power_control
    mu = cfg.band.numerology.mu
    p_prb_max = ue.tx_power_dbm - 10 * np.log10(n_prb_alloc)
    p_prb = np.minimum(p_prb_max, pc.p0_dbm + 10 * np.log10(2**mu) + pc.alpha * cl_serv)   # (N,)
    rx_prb = p_prb - cl_serv
    # average interference at each site from one co-scheduled UE per neighbour cell (uniform over the cell)
    S = len(sites)
    interf_lin = np.zeros(S)
    for c in range(S):
        m = serving == c
        if not m.any():
            continue
        rx_at_sites = 10 ** ((p_prb[m][:, None] - cl[m]) / 10)      # (n_c, S)
        mean_rx = rx_at_sites.mean(axis=0)
        mean_rx[c] = 0.0
        interf_lin += mean_rx
    noise_lin = 10 ** (thermal_noise_dbm(prb_bandwidth_hz(mu, 1), g.noise_figure_db) / 10)
    sinr = 10 * np.log10(10 ** (rx_prb / 10) / (interf_lin[serving] + noise_lin))
    return SinrMap(grid, serving, sinr, rx_prb, pl)

