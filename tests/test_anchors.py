"""Numeric anchors from brief §4 — the project is not complete unless every one passes (brief §9)."""
import math
import pytest
from port5g import capacity, channel, linkbudget


def test_umi_sc_los_anchor():
    assert channel.umi_sc_los(100.0, 3.7, 10.0, 1.5, check=False) == pytest.approx(85.76, abs=0.1)


def test_inf_los_anchor():
    assert channel.inf_los(100.0, 3.7) == pytest.approx(85.64, abs=0.1)


def test_inf_dh_nlos_anchor():
    assert channel.inf_nlos(100.0, 3.7, "InF-DH") == pytest.approx(88.79, abs=0.1)


@pytest.mark.parametrize("sub,sigma", [("InF-SL", 5.7), ("InF-DL", 7.2), ("InF-SH", 5.9), ("InF-DH", 4.0)])
def test_inf_shadow_sigma(sub, sigma):
    assert channel.shadow_sigma_db("InF", False, sub) == sigma


def test_inf_los_sigma():
    assert channel.shadow_sigma_db("InF", True) == 4.3


def test_thermal_noise_100mhz():
    assert linkbudget.thermal_noise_dbm(100e6) == pytest.approx(-94.0, abs=0.05)


def test_thermal_noise_one_prb_30khz():
    assert linkbudget.thermal_noise_dbm(linkbudget.prb_bandwidth_hz(1)) == pytest.approx(-118.4, abs=0.05)


def test_38306_dl_anchor():
    assert capacity.data_rate_38306(4, 8, 1.0, 273, 1, 0.14) == pytest.approx(2337, abs=1)


def test_38306_ul_anchor():
    assert capacity.data_rate_38306(1, 6, 1.0, 273, 1, 0.08) == pytest.approx(469, abs=1)


def test_38306_carrier_aggregation_sums():
    single = capacity.data_rate_38306(1, 6, 1.0, 273, 1, 0.08)
    ca = capacity.data_rate_38306([1, 1], [6, 6], [1.0, 1.0], [273, 273], [1, 1], [0.08, 0.08])
    assert ca == pytest.approx(2 * single)


def test_symbol_duration():
    assert capacity.symbol_duration_s(1) == pytest.approx(1e-3 / 28)
    assert math.isclose(capacity.slot_duration_ms(2), 0.25)
