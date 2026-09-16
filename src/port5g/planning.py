"""Site placement over candidate mounts: greedy weighted set cover (default) or ILP via PuLP if installed.

Coverage requirement: every demand grid point in zone z must be within the UL cell radius R[z, service]
of at least one selected site, for the most demanding service in that zone. Greedy is O(S·N) and
deterministic; ILP gives the true minimum and is used automatically when `pulp` imports.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .geometry import Grid, Mount


@dataclass
class Plan:
    selected: list[Mount]
    coverage: np.ndarray       # bool (N,)
    coverage_fraction: float
    method: str
    uncovered_by_zone: dict[str, int]


def _cover_matrix(grid: Grid, mounts: list[Mount], radius_by_zone: dict[str, float]) -> np.ndarray:
    r = np.array([radius_by_zone[z] for z in grid.zone])
    cov = np.zeros((len(mounts), len(grid)), dtype=bool)
    for j, m in enumerate(mounts):
        d = np.hypot(grid.x - m.x, grid.y - m.y)
        cov[j] = d <= r
    return cov


def greedy_set_cover(grid: Grid, mounts: list[Mount], radius_by_zone: dict[str, float],
                     max_sites: int = 40) -> Plan:
    cov = _cover_matrix(grid, mounts, radius_by_zone)
    coverable = cov.any(axis=0)
    covered = np.zeros(len(grid), dtype=bool)
    chosen: list[int] = []
    while (~covered & coverable).any() and len(chosen) < max_sites:
        gains = (cov & ~covered).sum(axis=1)
        gains[chosen] = -1
        j = int(np.argmax(gains))     # deterministic tie-break: lowest index
        if gains[j] <= 0:
            break
        chosen.append(j)
        covered |= cov[j]
    return _finish(grid, mounts, chosen, covered, "greedy set cover")


def ilp_set_cover(grid: Grid, mounts: list[Mount], radius_by_zone: dict[str, float]) -> Plan:
    import pulp  # optional dependency
    cov = _cover_matrix(grid, mounts, radius_by_zone)
    coverable = np.where(cov.any(axis=0))[0]
    prob = pulp.LpProblem("site_cover", pulp.LpMinimize)
    x = [pulp.LpVariable(f"x{j}", cat="Binary") for j in range(len(mounts))]
    prob += pulp.lpSum(x)
    for i in coverable:
        prob += pulp.lpSum(x[j] for j in range(len(mounts)) if cov[j, i]) >= 1
    prob.solve(pulp.PULP_CBC_CMD(msg=False))
    chosen = [j for j in range(len(mounts)) if x[j].value() > 0.5]
    covered = cov[chosen].any(axis=0) if chosen else np.zeros(len(grid), bool)
    return _finish(grid, mounts, chosen, covered, "ILP (PuLP/CBC)")


def _finish(grid, mounts, chosen, covered, method) -> Plan:
    unc = {z: int(((grid.zone == z) & ~covered).sum()) for z in np.unique(grid.zone)}
    return Plan([mounts[j] for j in chosen], covered, float(covered.mean()), method, unc)


def place_sites(grid: Grid, mounts: list[Mount], radius_by_zone: dict[str, float], prefer_ilp: bool = True) -> Plan:
    if prefer_ilp:
        try:
            return ilp_set_cover(grid, mounts, radius_by_zone)
        except ImportError:
            pass
    return greedy_set_cover(grid, mounts, radius_by_zone)
