from port5g.config import CONFIDENCE_LEVELS, load_config


def test_every_param_has_source_and_confidence(cfg):
    assert cfg.registry, "registry empty — loader broken"
    for p in cfg.registry:
        assert p.source.strip(), f"{p.path} has empty source"
        assert p.confidence in CONFIDENCE_LEVELS


def test_unverified_are_marked_in_source(cfg):
    for p in cfg.unverified():
        assert "UNVERIFIED" in p.source.upper(), f"{p.path}: unverified values must say [UNVERIFIED] in their source text"


def test_int_yaml_keys(cfg):
    assert cfg.qos.standard_5qi[82].pdb_ms == 10
    assert cfg.qos.standard_5qi["85"].pdb_ms == 5
