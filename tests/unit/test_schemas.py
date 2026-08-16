import json

from elementzero.atlas_pin import REPO_ROOT

SCHEMAS = REPO_ROOT / "schemas"


def test_schemas_are_readable_json():
    names = [
        "nuclear_observation.schema.json",
        "knowledge_freeze.schema.json",
        "target_manifest.schema.json",
        "prediction_certificate.schema.json",
        "run_manifest.schema.json",
        "geographic_region.schema.json",
        "geographic_split_manifest.schema.json",
        "shell_mask.schema.json",
        "shell_challenge.schema.json",
        "wo11_failure_record.schema.json",
        "wo11_adjudication_report.schema.json",
        "frontier_model_candidate.schema.json",
    ]
    for name in names:
        payload = json.loads((SCHEMAS / name).read_text(encoding="utf-8"))
        assert payload["title"]
        assert "$schema" in payload
