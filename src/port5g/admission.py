"""Time-stepped admission control & ARP pre-emption simulator (brief §6 module contract, figure 8).

Sessions arrive per QoS flow as Poisson processes (rate scaled by a load ramp), hold for an exponential
time, and each reserves its GFBR (non-GBR flows reserve a nominal MFBR fraction so the MIoT slice can
still be squeezed). The controller enforces:
  * per-slice guaranteed minimum share (never pre-emptable by other slices) and maximum share,
  * a common pool between minimum shares,
  * ARP pre-emption exactly per TS 23.501 §5.7.2.2 (priority level, capability, vulnerability).
All randomness comes from a numpy Generator seeded from config (rule §10.4).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .slicing import QosFlow, Slice


@dataclass
class Session:
    id: int
    flow: str
    slice: str
    bw: float
    t_end: float


@dataclass
class AdmissionResult:
    t: np.ndarray
    used_by_slice: dict[str, np.ndarray]
    offered_by_slice: dict[str, np.ndarray]
    blocked: dict[str, int]
    preempted: dict[str, int]
    admitted: dict[str, int]
    arrivals: dict[str, int]

    def blocking_probability(self) -> dict[str, float]:
        return {s: self.blocked[s] / max(self.arrivals[s], 1) for s in self.arrivals}

    def preemption_rate(self) -> dict[str, float]:
        return {s: self.preempted[s] / max(self.admitted[s], 1) for s in self.admitted}


class AdmissionController:
    def __init__(self, capacity_mbps: float, slices: dict[str, Slice], flows: dict[str, QosFlow]):
        self.C = capacity_mbps
        self.slices = slices
        self.flows = flows
        self.active: list[Session] = []
        self.preempted = {s: 0 for s in slices}

    def used(self, slice_name: str) -> float:
        return sum(s.bw for s in self.active if s.slice == slice_name)

    def _fits(self, slice_name: str, bw: float) -> bool:
        sl = self.slices[slice_name]
        used = self.used(slice_name)
        if used + bw > sl.share_max * self.C:
            return False
        # capacity available to this slice = its guaranteed min + free part of the common pool
        reserved_others = sum(max(self.used(o), self.slices[o].share_min * self.C) for o in self.slices if o != slice_name)
        return used + bw <= self.C - reserved_others

    def try_admit(self, s: Session) -> tuple[bool, list[Session]]:
        if self._fits(s.slice, s.bw):
            self.active.append(s)
            return True, []
        # ARP pre-emption: victims must be preemptable, lower priority, and not protected by their slice minimum
        me = self.flows[s.flow].arp
        victims: list[Session] = []
        cands = sorted(self.active,
                       key=lambda v: (-self.flows[v.flow].arp.priority_level, v.t_end))
        for v in cands:
            if not me.can_preempt(self.flows[v.flow].arp):
                continue
            # a victim slice may only be squeezed down to its guaranteed minimum
            if self.used(v.slice) - v.bw < self.slices[v.slice].share_min * self.C and v.slice != s.slice:
                continue
            victims.append(v)
            self.active.remove(v)
            if self._fits(s.slice, s.bw):
                self.active.append(s)
                for x in victims:
                    self.preempted[x.slice] += 1
                return True, victims
        self.active.extend(victims)  # roll back
        return False, []

    def expire(self, t: float) -> None:
        self.active = [s for s in self.active if s.t_end > t]


def simulate(cfg, capacity_mbps: float, slices: dict[str, Slice], flows: dict[str, QosFlow],
             offered_mbps: dict[str, float], seed: int) -> AdmissionResult:
    sim = cfg.scenario_best.simulation.admission
    rng = np.random.default_rng(seed)
    T, dt, ramp = sim.duration_s, sim.dt_s, sim.ramp_factor_max
    hold = {s: sim.mean_holding_time_s[s] for s in slices}
    ctrl = AdmissionController(capacity_mbps, slices, flows)
    # The ramp is expressed relative to CAPACITY (0 -> ramp_factor x capacity) keeping the nominal traffic mix,
    # so figure 8 shows the controller's behaviour around saturation whatever the absolute offered load is.
    tot = sum(offered_mbps.values()) or 1.0
    offered_mbps = {k: v / tot * capacity_mbps for k, v in offered_mbps.items()}
    steps = int(T / dt)
    t = np.arange(steps) * dt
    used = {s: np.zeros(steps) for s in slices}
    offered = {s: np.zeros(steps) for s in slices}
    blocked = {s: 0 for s in slices}; admitted = {s: 0 for s in slices}; arrivals = {s: 0 for s in slices}
    sid = 0
    for k in range(steps):
        load_factor = ramp * (k / steps)
        ctrl.expire(t[k])
        for fname in sorted(flows):           # deterministic order
            f = flows[fname]
            bw = f.gfbr_ul_mbps if f.gfbr_ul_mbps > 0 else f.mfbr_ul_mbps
            if bw <= 0:
                continue
            # session arrival rate such that mean offered load = load_factor * offered_mbps (Little's law)
            lam = load_factor * offered_mbps.get(fname, 0.0) / bw / hold[f.slice]
            n_arr = rng.poisson(lam * dt)
            for _ in range(n_arr):
                sid += 1; arrivals[f.slice] += 1
                s = Session(sid, fname, f.slice, bw, t[k] + rng.exponential(hold[f.slice]))
                ok, _ = ctrl.try_admit(s)
                if ok:
                    admitted[f.slice] += 1
                else:
                    blocked[f.slice] += 1
            offered[f.slice][k] += load_factor * offered_mbps.get(fname, 0.0)
        for s in slices:
            used[s][k] = ctrl.used(s)
    return AdmissionResult(t, used, offered, blocked, dict(ctrl.preempted), admitted, arrivals)
