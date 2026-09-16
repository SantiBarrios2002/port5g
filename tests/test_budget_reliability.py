import math
import pytest
from port5g import linkbudget, reliability


def test_required_snr_shannon_limit():
    # SE = 1 bit/s/Hz -> SNR = 0 dB in the Shannon limit
    assert linkbudget.required_snr_db(1.0, 0.1, None) == pytest.approx(0.0, abs=1e-9)


def test_finite_blocklength_penalty_positive_and_shrinks_with_n():
    p500 = linkbudget.bler_penalty_db(1.5, 500, 1e-5)
    p5000 = linkbudget.bler_penalty_db(1.5, 5000, 1e-5)
    assert p500 > p5000 > 0


def test_jakes_textbook_point():
    # Jakes/Rappaport example: sigma 8 dB, n = 4, 75 % edge -> ~90 % area
    assert reliability.jakes_area_coverage(0.75, 8.0, 4.0) == pytest.approx(0.907, abs=0.01)


def test_area_margin_monotone():
    m95, _ = reliability.shadow_margin_for_area_availability(0.95, 7.82, 3.0)
    m999, _ = reliability.shadow_margin_for_area_availability(0.999, 7.82, 3.0)
    assert m999 > m95 > 0


def test_harq_and_duplication_residuals():
    assert reliability.residual_error_harq(0.1, 3) == pytest.approx(1e-3)
    assert reliability.residual_error_duplication(0.1) == pytest.approx(1e-2)
    assert reliability.min_transmissions_for_target(0.1, 1e-5) == 5


def test_nines():
    assert reliability.as_nines(0.99999) == pytest.approx(5.0)


def test_uplink_budget_terms_sum_to_mapl(cfg):
    from port5g import channel
    zc = channel.zone_channels_from_config(cfg)["quay_apron"]
    lb = linkbudget.uplink_budget(cfg, "S1_crane_control", "quay_apron", 1.0, 1e-5, 10, 0.999, zc.sigma_nlos(), 3.0)
    assert lb.mapl_db == pytest.approx(sum(lb.terms.values()))
    assert lb.direction == "UL" and math.isfinite(lb.mapl_db)


def test_cell_radius_capped_at_model_validity(cfg):
    from port5g import channel
    zc = channel.zone_channels_from_config(cfg)["asc_blocks"]
    r = linkbudget.cell_radius_m(zc, 200.0, 3.9, 30, 4.5)
    assert r == channel.INF_D3D_RANGE_M[1]
