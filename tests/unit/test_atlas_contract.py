import json

import pir
import pytest
from tests.unit.test_atlas_adapter import _graph

from elementzero import __atlas_pir_contract__
from elementzero.atlas_pin import assert_pin_consistent
from elementzero.evidence.atlas_adapter import (
    PUBLIC_PIR_SYMBOLS,
    AtlasEvidenceAdapter,
    fact_from_dict,
    provenance_record_from_dict,
    rehydrate_facts_from_dicts,
    write_atlas_bundle,
)


def test_pir_version_is_supported():
    assert pir.__version__ == __atlas_pir_contract__
    assert pir.__version__ in {"0.1.0"}


def test_public_symbols_exist():
    for name in PUBLIC_PIR_SYMBOLS:
        assert hasattr(pir, name), name


def test_pin_is_immutable_and_consistent():
    ref = assert_pin_consistent()
    assert len(ref) == 40
    assert ref != "main"


def test_atlas_fact_has_to_dict_but_no_from_dict():
    # The pinned Atlas baseline serializes facts but does not deserialize them,
    # which is why the inverse lives in elementzero.evidence.atlas_adapter.
    assert hasattr(pir.Fact, "to_dict")
    assert not hasattr(pir.Fact, "from_dict")


def test_atlas_fact_bundle_round_trip(tmp_path):
    adapter = AtlasEvidenceAdapter(created_at="2026-08-15T00:00:00Z")
    graph = _graph(adapter, n_predictions=2)
    adapter.append_provenance(
        entity=graph["training"].fact_id,
        activity_type="LOWER",
        used=(graph["artifact"].artifact_id,),
        generated=(graph["training"].fact_id,),
    )
    adapter.append_provenance(
        entity=graph["prediction_set"].fact_id,
        activity_type="ANALYZE",
        agent_id="elementzero.models.predict",
        used=tuple(p.fact_id for p in graph["predictions"]),
        generated=(graph["prediction_set"].fact_id,),
    )
    facts = adapter.store.facts()
    write_atlas_bundle(
        tmp_path,
        stage="predict",
        facts=facts,
        provenance=adapter.store.provenance(),
        artifacts=[graph["artifact"]],
        events=[graph["event"]],
    )
    payloads = json.loads((tmp_path / "atlas" / "facts.json").read_text(encoding="utf-8"))
    assert [p["fact_id"] for p in payloads] == sorted(f.fact_id for f in facts)

    rebuilt = {f.fact_id: f for f in rehydrate_facts_from_dicts(payloads)}
    assert set(rebuilt) == {f.fact_id for f in facts}
    for fact in facts:
        other = rebuilt[fact.fact_id]
        assert other.to_dict() == fact.to_dict()
        assert other.evidence_level is fact.evidence_level
        assert other.namespace is fact.namespace
        assert other.status is fact.status
        assert other.analyzer.tag is fact.analyzer.tag
        assert other.warnings == fact.warnings
        # A rehydrated fact still content-addresses to the stored Atlas ID.
        assert (
            pir.Fact.compute_id(
                other.content,
                other.analyzer,
                depends_on_facts=other.depends_on_facts,
                assumptions=other.assumptions,
            )
            == fact.fact_id
        )

    # Rehydration is ordered so an append-only store accepts it as-is.
    replay = AtlasEvidenceAdapter(created_at="2026-08-15T00:00:00Z")
    replay.rehydrate(payloads)
    assert len(replay.store) == len(facts)

    provenance = json.loads(
        (tmp_path / "atlas" / "provenance.json").read_text(encoding="utf-8")
    )
    assert len(provenance) == 2
    for payload in provenance:
        assert provenance_record_from_dict(payload).to_dict() == payload


def test_rehydration_rejects_a_dependency_cycle():
    left = {
        "fact_id": "fct_a",
        "pir_level": "L2",
        "evidence_level": "E2",
        "layer": "DOMAIN",
        "namespace": "domain",
        "status": "SUPPORTED",
        "analyzer": {"id": "x", "version": "0.3.0", "tag": "SOUND"},
        "content": {"kind": "left"},
        "created_at": "2026-08-15T00:00:00Z",
        "depends_on_facts": ["fct_b"],
        "assumptions": [],
        "source_spans": [{"artifact_id": "art", "span": "s"}],
        "measurement_interface": ["mi:nuclear_atomic_mass_excess"],
        "warnings": [],
        "verdict": None,
    }
    right = dict(left, fact_id="fct_b", depends_on_facts=["fct_a"], content={"kind": "right"})
    assert fact_from_dict(left).fact_id == "fct_a"
    with pytest.raises(ValueError):
        rehydrate_facts_from_dicts([left, right])
