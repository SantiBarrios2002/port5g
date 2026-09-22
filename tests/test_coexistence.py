import copy
import warnings

import pytest

from port5g import coexistence

SPECIAL = {"dl": 10, "gp": 2, "ul": 2}


def test_symbol_expansion_and_conflicts_hand_counted():
    assert coexistence.expand_symbols("DSU", SPECIAL) == "D" * 14 + "D" * 10 + "GG" + "UU" + "U" * 14
    assert coexistence.conflict_fractions("DDDSU", "DDDSU", SPECIAL) == {"ours_U_mno_D": 0.0, "ours_D_mno_U": 0.0}
    # DSUUU vs DDDSU: slot 1 S vs D -> 2 U symbols; slot 2 U vs D -> 14; slot 3 U vs S -> 10 (MNO D part)
    fr = coexistence.conflict_fractions("DSUUU", "DDDSU", SPECIAL)
    assert fr["ours_U_mno_D"] == pytest.approx(26 / 70)
    assert fr["ours_D_mno_U"] == 0.0
    with pytest.raises(ValueError):
        coexistence.conflict_fractions("DSUU", "DDDSU", SPECIAL)       # different period
    with pytest.raises(ValueError):
        coexistence.expand_symbols("DSU", {"dl": 10, "gp": 2, "ul": 3})


def test_fspl_anchor_and_inverse():
    # 20 log10(4 pi f / c) at 3.9 GHz = 44.27 dB; +60 dB at 1 km
    assert coexistence.fspl_db(1000, 3.9) == pytest.approx(104.27, abs=0.01)
    assert coexistence.fspl_distance_m(float(coexistence.fspl_db(2500, 3.9)), 3.9) == pytest.approx(2500)


def test_acir_combination():
    assert coexistence.acir_db(45, 45) == pytest.approx(45 - 3.0103, abs=1e-3)
    assert coexistence.acir_db(30, 80) == pytest.approx(30, abs=1e-3)      # dominated by the worse of the two


def test_link_budget_bookkeeping(cfg):
    lk = coexistence.links(cfg)
    co = cfg.band.coexistence
    for v in lk.values():
        assert v["required_pl_db"] == pytest.approx(v["i_at_0db_dbm"] - v["noise_dbm"] - co.protection_i_over_n_db)
    # more ACLR -> less interference -> shorter separation
    c = copy.deepcopy(cfg)
    c.data["band"]["coexistence"]["bs_aclr_db"] = co.bs_aclr_db + 10
    assert coexistence.links(c)["MNO gNB -> our gNB"]["required_separation_m"] < lk["MNO gNB -> our gNB"]["required_separation_m"]


def test_synchronised_pattern_has_no_active_links(cfg):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = coexistence.run(cfg)
    same = r["by_pattern"][cfg.band.coexistence.mno_pattern]
    assert same["active_links"] == [] and same["extra_isolation_needed_db"] == 0.0


def test_spectrum_fit_flags_carrier_outside_subrange(cfg):
    c = copy.deepcopy(cfg)
    c.data["band"]["carrier"]["fc_ghz"] = 3.86           # 3810-3910 MHz: inside 3800-3920
    assert coexistence.spectrum_fit(c)["inside_subrange"]
    c.data["band"]["carrier"]["fc_ghz"] = 3.95           # 3900-4000 MHz: outside
    with pytest.warns(UserWarning):
        assert not coexistence.spectrum_fit(c)["inside_subrange"]
