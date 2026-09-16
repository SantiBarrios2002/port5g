import numpy as np
import pytest
from port5g import channel


def test_umi_nlos_ge_los():
    d = np.linspace(20, 500, 50)
    assert np.all(channel.umi_sc_nlos(d, 3.9, 10, 1.5, check=False) >= channel.umi_sc_los(d, 3.9, 10, 1.5, check=False))


def test_inf_nlos_ge_los_all_subscenarios():
    d = np.linspace(2, 500, 50)
    for sub in channel.INF_SUBSCENARIOS:
        assert np.all(channel.inf_nlos(d, 3.9, sub) >= channel.inf_los(d, 3.9))


def test_inf_dl_ge_sl():
    d = np.linspace(2, 500, 50)
    assert np.all(channel.inf_nlos(d, 3.9, "InF-DL") >= channel.inf_nlos(d, 3.9, "InF-SL"))


def test_validity_warning_outside_range():
    with pytest.warns(channel.ModelValidityWarning):
        channel.inf_los(700.0, 3.9)
    with pytest.warns(channel.ModelValidityWarning):
        channel.umi_sc_los(5.0, 3.9, 10, 1.5)


def test_los_probability_bounds_and_monotone():
    d = np.linspace(1, 1000, 200)
    p = channel.umi_los_probability(d)
    assert np.all((p >= 0) & (p <= 1)) and np.all(np.diff(p) <= 1e-12)
    p2 = channel.inf_los_probability(d, "InF-DH", 12.192, 0.6, 30, 4.5, 12.955)
    assert p2[0] > 0.9 and p2[-1] < 1e-6 and np.all(np.diff(p2) <= 0)


def test_umi_breakpoint_continuity():
    fc, hb, hu = 3.9, 10.0, 1.5
    dbp = channel.umi_breakpoint_distance_m(fc, hb, hu)
    d3 = channel.d3d_from_d2d(np.array([dbp * 0.999, dbp * 1.001]), hb, hu)
    pl = channel.umi_sc_los(d3, fc, hb, hu, check=False)
    assert abs(pl[1] - pl[0]) < 0.2


def test_shadowing_reproducible_from_seed():
    a = channel.sample_shadowing(np.random.default_rng(7), 4.0, 100)
    b = channel.sample_shadowing(np.random.default_rng(7), 4.0, 100)
    assert np.array_equal(a, b)


def test_zone_channels_from_config(cfg):
    zc = channel.zone_channels_from_config(cfg)
    assert set(zc) == {"quay_apron", "asc_blocks", "gate_rail"}
    assert zc["asc_blocks"].sub_scenario == "InF-DH"
