"""S1 one-way latency budget decomposition (brief §4.4) and HARQ / duplication comparison.

Each configuration in config/latency.yaml (grant type, numerology, mini-slot length, HARQ retx, UE
capability) produces an ordered dict of named terms in ms. Worst-case slot alignment (one full slot) is used
because the budget is for a 99.999 % target, not the mean; the mean case is also returned.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .capacity import slot_duration_ms, symbol_duration_s
from .reliability import residual_error_harq


@dataclass
class LatencyBudget:
    name: str
    terms: dict[str, float] = field(default_factory=dict)  # ms, in pipeline order
    harq_rtt_ms: float = 0.0
    residual_error: float = 1.0

    @property
    def total_ms(self) -> float:
        return sum(self.terms.values())

    @property
    def mean_total_ms(self) -> float:
        return self.total_ms - 0.5 * self.terms.get("Slot alignment (worst)", 0.0)


def transport_latency_ms(cfg) -> float:
    t = cfg.latency.terms
    fibre = t.fronthaul_fibre_km * t.fibre_propagation_us_per_km
    switches = t.switch_hops * t.switch_hop_latency_us
    return (fibre + switches) / 1000.0


def harq_rtt_ms(cfg, mu: int, symbols: int, ue_cap: int) -> float:
    """UL HARQ round trip: gNB decode -> grant for retx (DCI) -> UE prep (N2) -> retransmission.
    Worst-case slot alignment included once for the grant."""
    t = cfg.latency.terms
    sym = symbol_duration_s(mu) * 1e3
    n2 = t.ue_pusch_preparation_symbols[f"cap{ue_cap}"] * sym
    tx = symbols * sym
    return t.gnb_processing_ms + t.harq_feedback_k1_slots * slot_duration_ms(mu) + n2 + tx + t.gnb_processing_ms


def budget_for(cfg, conf: dict, upf_local: bool = True) -> LatencyBudget:
    t, ll = cfg.latency.terms, cfg.latency.link_level
    mu, symbols, retx, cap = conf["mu"], conf["symbols"], conf["harq_retx"], conf["ue_cap"]
    sym_ms = symbol_duration_s(mu) * 1e3
    b = LatencyBudget(conf["name"])
    b.terms["UE app processing"] = t.ue_app_processing_ms
    b.terms["UE PUSCH preparation (N2)"] = t.ue_pusch_preparation_symbols[f"cap{cap}"] * sym_ms
    if conf["grant"] == "SR":
        b.terms["SR wait (worst)"] = t.scheduling_request_ms.sr_periodicity_slots * slot_duration_ms(mu)
        b.terms["SR->grant pipeline"] = t.scheduling_request_ms.grant_pipeline_ms
    else:
        b.terms["Configured grant (no SR)"] = 0.0
    b.terms["Slot alignment (worst)"] = slot_duration_ms(mu) if symbols >= 14 else symbols * sym_ms
    b.terms[f"Transmission ({symbols} sym)"] = symbols * sym_ms
    b.terms["gNB processing"] = t.gnb_processing_ms
    rtt = harq_rtt_ms(cfg, mu, symbols, cap)
    b.harq_rtt_ms = rtt
    b.terms[f"HARQ retx x{retx}"] = retx * rtt
    b.terms["Fronthaul/midhaul transport"] = transport_latency_ms(cfg)
    b.terms["UPF forwarding"] = t.upf_forwarding_ms + (0.0 if upf_local else t.remote_upf_extra_rtt_ms)
    b.terms["MEC app processing"] = t.mec_app_processing_ms
    # residual error: first tx at strict BLER if 0 retx; otherwise chain with per-retx BLER
    if retx == 0:
        b.residual_error = ll.first_tx_bler_urllc
    else:
        b.residual_error = residual_error_harq(ll.harq_bler_per_retx, retx + 1)
    return b


def all_budgets(cfg) -> list[LatencyBudget]:
    return [budget_for(cfg, c) for c in cfg.latency.configurations]


def local_upf_proof(cfg) -> dict:
    """Brief §3.2: prove the UPF must be on-site — same best config with remote vs local UPF vs PDB."""
    best = min(cfg.latency.configurations, key=lambda c: (c["harq_retx"] != 1, c["mu"] != 1))
    local = budget_for(cfg, best, upf_local=True)
    remote = budget_for(cfg, best, upf_local=False)
    pdb = cfg.qos.standard_5qi[str(cfg.qos.flows.S1_control.qi)].pdb_ms
    return {"config": best["name"], "local_ms": local.total_ms, "remote_ms": remote.total_ms,
            "pdb_ms": pdb, "local_meets": local.total_ms <= pdb, "remote_meets": remote.total_ms <= pdb}
