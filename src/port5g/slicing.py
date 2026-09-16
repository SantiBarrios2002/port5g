"""Slice model: S-NSSAI, capacity quotas, QoS flow catalogue with ARP semantics (TS 23.501 §5.7.2.2).

ARP: priority level 1..15 (1 = highest), pre-emption capability, pre-emption vulnerability.
A new flow with capability=MAY_PREEMPT may pre-empt an existing flow if (a) the existing flow is
PREEMPTABLE and (b) its priority level is numerically higher (lower priority) than the new flow's.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Arp:
    priority_level: int
    may_preempt: bool
    preemptable: bool

    @staticmethod
    def from_cfg(d: dict) -> "Arp":
        return Arp(int(d["priority_level"]), d["pre_emption_capability"] == "MAY_PREEMPT",
                   d["pre_emption_vulnerability"] == "PREEMPTABLE")

    def can_preempt(self, victim: "Arp") -> bool:
        return self.may_preempt and victim.preemptable and victim.priority_level > self.priority_level


@dataclass(frozen=True)
class QosFlow:
    name: str
    slice: str
    qi: str
    arp: Arp
    gfbr_ul_mbps: float
    mfbr_ul_mbps: float
    gfbr_dl_mbps: float
    mfbr_dl_mbps: float
    ue_class: str
    pdb_ms: float
    per: float
    resource_type: str


@dataclass(frozen=True)
class Slice:
    name: str
    sst: int
    sd: str
    dnn: str
    share_min: float
    share_max: float

    @property
    def s_nssai(self) -> str:
        return f"SST={self.sst}/SD={self.sd}"


def slices_from_config(cfg) -> dict[str, Slice]:
    return {n: Slice(n, s.sst, s.sd, s.dnn, s.ul_capacity_share_min, s.ul_capacity_share_max)
            for n, s in cfg.qos.slices.items()}


def flows_from_config(cfg) -> dict[str, QosFlow]:
    out = {}
    for n, f in cfg.qos.flows.items():
        qi = str(f.qi)
        if qi.startswith("custom:"):
            row = cfg.qos.custom_5qi[qi.split(":", 1)[1]]
        else:
            row = cfg.qos.standard_5qi[qi]
        out[n] = QosFlow(n, f.slice, qi, Arp.from_cfg(f.arp.raw()), f.gfbr_ul_mbps, f.mfbr_ul_mbps,
                         f.gfbr_dl_mbps, f.mfbr_dl_mbps, f.ue_class, row.pdb_ms, row.per, row.resource_type)
    return out


def offered_load_ul_mbps(cfg) -> dict[str, float]:
    """Offered uplink load per flow, computed from services.yaml primitives (never hard-coded)."""
    s = cfg.services
    s1, s2, s3 = s.S1_crane_control, s.S2_shuttle_carriers, s.S3_monitoring
    return {
        "S1_control": s1.n_devices * s1.activity_factor * s1.control_loop_rate_hz * s1.control_packet_bytes * 8 / 1e6,
        "S1_video": s1.n_devices * s1.activity_factor * s1.ul_video_rate_per_crane_mbps,
        "S2_video": s2.n_devices * s2.activity_factor * s2.cameras_per_vehicle * s2.ul_rate_per_camera_mbps,
        "S2_telemetry": s2.n_devices * s2.activity_factor * s2.telemetry_rate_mbps,
        "S3_reefer": (s3.reefer_plugs + s3.asset_tags) * s3.reefer_report_bytes * 8 / s3.reefer_report_period_s / 1e6,
        "S3_gate": s3.gate_trucks_per_hour * s3.gate_ocr_burst_mb * 8 / 3600.0,
        "S3_handheld": s3.handhelds * s3.handheld_rate_mbps,
    }


def offered_load_per_slice(cfg) -> dict[str, float]:
    flows = flows_from_config(cfg)
    load = offered_load_ul_mbps(cfg)
    out: dict[str, float] = {}
    for n, mbps in load.items():
        out[flows[n].slice] = out.get(flows[n].slice, 0.0) + mbps
    return out
