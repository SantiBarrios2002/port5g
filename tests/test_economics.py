import copy

import numpy as np
import pytest

from port5g import economics


def test_npv_and_payback_hand_computed():
    cf = economics.cash_flows(100.0, 10.0, 60.0, [0.5], 3)     # [-100, 20, 50, 50]
    assert cf.tolist() == [-100.0, 20.0, 50.0, 50.0]
    assert economics.npv(cf, 0.0) == pytest.approx(20.0)
    assert economics.npv(cf, 0.1) == pytest.approx(-100 + 20 / 1.1 + 50 / 1.1**2 + 50 / 1.1**3)
    assert economics.payback_year(cf, 0.0) == pytest.approx(2 + 30 / 50)   # cum: -100, -80, -30, +20
    assert economics.payback_year(np.array([-100.0, 10.0]), 0.0) is None


def test_network_cost_scales_with_sites(cfg):
    c5, c10 = economics.network_capex(cfg, 5), economics.network_capex(cfg, 10)
    assert c10["RAN"] == pytest.approx(2 * c5["RAN"])
    assert c10["site works"] == pytest.approx(2 * c5["site works"])
    assert c10["CPE / devices"] == c5["CPE / devices"]          # devices do not depend on site count


def test_pni_npn_swaps_core_and_spectrum_for_mno_fee(cfg):
    s = economics.network_capex(cfg, 8, "snpn"); p = economics.network_capex(cfg, 8, "pni_npn")
    assert p["5GC (on-site)"] == 0 and s["5GC (on-site)"] > 0
    assert p["MEC"] == s["MEC"]                                   # local UPF/MEC needed in both (latency proof)
    op = economics.network_opex(cfg, 8, sum(p.values()), "pni_npn")
    assert op["spectrum fee"] == 0 and op["network ops staff"] == 0 and op["MNO service fee"] > 0
    with pytest.raises(ValueError):
        economics.network_capex(cfg, 8, "mno")


def test_no_labour_saving_at_one_to_one_supervision(cfg):
    c = copy.deepcopy(cfg)
    c.data["economics"]["benefits"]["cranes_per_remote_operator"] = 1
    c.data["economics"]["benefits"]["vehicles_per_remote_supervisor"] = 1
    b = economics.annual_benefits(c)
    assert b["crane operators"] == 0 and b["shuttle drivers"] == 0


def test_automation_cost_is_charged_against_savings(cfg):
    e = economics.evaluate(cfg, 10)
    total_capex = sum(e["network_capex"].values()) + sum(e["automation_capex"].values())
    assert e["use_case_cash_flow"][0] == pytest.approx(-total_capex)


def test_tornado_skips_design_choices(cfg):
    knobs = economics._numeric_inputs(cfg)
    assert "economics.benefits.shuttle_drivers_per_vehicle_manual" not in knobs
    assert "economics.network_capex.cpe_eur.iot_module" in knobs
    design = {p.path for p in cfg.registry if p.confidence == "design"}
    assert not design & set(knobs)
