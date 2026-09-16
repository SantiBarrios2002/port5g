import json
import warnings

import numpy as np
import pytest

from port5g import admission, capacity, latency, scenario, slicing


def test_tdd_duty_cycle():
    d = capacity.tdd_duty_cycle("DDDSU", {"dl": 10, "gp": 2, "ul": 2})
    assert d.dl_fraction == pytest.approx((3 * 14 + 10) / 70)
    assert d.ul_fraction == pytest.approx((14 + 2) / 70)
    assert d.dl_fraction + d.ul_fraction + d.gp_fraction == pytest.approx(1.0)
    with pytest.raises(ValueError):
        capacity.tdd_duty_cycle("DDXU")


def test_offered_load_is_computed_not_hardcoded(cfg):
    load = slicing.offered_load_ul_mbps(cfg)
    s1 = cfg.services.S1_crane_control
    assert load["S1_video"] == pytest.approx(s1.n_devices * s1.activity_factor * s1.ul_video_rate_per_crane_mbps)


def test_arp_semantics():
    from port5g.slicing import Arp
    hi = Arp(1, True, False)
    lo = Arp(12, False, True)
    assert hi.can_preempt(lo) and not lo.can_preempt(hi)
    assert not Arp(1, False, False).can_preempt(lo)          # no capability
    assert not hi.can_preempt(Arp(12, False, False))          # victim not vulnerable


def test_latency_budgets_and_local_upf(cfg):
    b = latency.all_budgets(cfg)
    assert len(b) >= 4
    for x in b:
        assert x.total_ms == pytest.approx(sum(x.terms.values()))
    proof = latency.local_upf_proof(cfg)
    assert proof["local_meets"] and not proof["remote_meets"]


def test_admission_deterministic_and_control_protected(cfg):
    slices = slicing.slices_from_config(cfg)
    flows = slicing.flows_from_config(cfg)
    load = slicing.offered_load_ul_mbps(cfg)
    a = admission.simulate(cfg, 300.0, slices, flows, load, seed=1)
    b = admission.simulate(cfg, 300.0, slices, flows, load, seed=1)
    assert a.blocked == b.blocked and a.preempted == b.preempted
    assert np.array_equal(a.used_by_slice["vision"], b.used_by_slice["vision"])
    assert a.preempted["control"] == 0                      # ARP 1, NOT_PREEMPTABLE
    assert a.preempted["telemetry"] > 0                     # MIoT is squeezed first


def test_full_run_is_reproducible(tmp_path, cfg):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r1 = scenario.run(cfg, seed=5)
        r2 = scenario.run(cfg, seed=5)
    scenario.save(r1, tmp_path / "a.json"); scenario.save(r2, tmp_path / "b.json")
    assert (tmp_path / "a.json").read_bytes() == (tmp_path / "b.json").read_bytes()
    assert r1["plan"]["n_sites"] >= 1
    assert json.loads((tmp_path / "a.json").read_text())["seed"] == 5
