import json
import shutil
from pathlib import Path

from elementzero.atlas_pin import REPO_ROOT
from elementzero.cli import main
from elementzero.visuals.build import build_visual_table

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "visuals"


def test_visual_build_without_benchmark_outputs(tmp_path):
    artifacts = tmp_path / "input" / ".artifacts" / "tests"
    artifacts.mkdir(parents=True)
    shutil.copy(FIXTURES / "pytest-report.json", artifacts / "pytest-report.json")
    out = tmp_path / "visuals"
    result = build_visual_table(input_root=tmp_path / "input", output_root=out)
    state = json.loads(Path(result["state"]).read_text())
    assert state["test_health"]["overall"] == "pass"
    assert state["test_health"]["unit"] == "pass"
    assert all(item["project_primary_stage"] == "not_touched" for item in state["elements"])
    assert Path(result["html"]).is_file()
    assert Path(result["svg"]).is_file()
    assert "Unit tests: PASS" in Path(result["html"]).read_text()


def test_visual_from_ci_and_benchmark_fixtures(tmp_path):
    root = tmp_path / "input"
    shutil.copytree(FIXTURES, root / "fixtures")
    ame = REPO_ROOT / "tests" / "fixtures" / "amdc" / "ame2020_golden.txt"
    shutil.copy(ame, root / "ame2020_golden.txt")
    out = tmp_path / "out"
    assert main(["visual", "build", "--input-root", str(root), "--output-root", str(out)]) == 0
    state = json.loads((out / "element_table_state.json").read_text())
    by_z = {item["Z"]: item for item in state["elements"]}
    assert by_z[8]["project_primary_stage"] == "historically_validated"
    assert by_z[26]["project_primary_stage"] == "geographic_holdout_validated"
    assert by_z[50]["project_primary_stage"] == "shell_rediscovery_validated"
    assert by_z[120]["project_primary_stage"] == "candidate_island_focus"
    assert by_z[1]["counts"]["eligible_observation_count"] >= 1
    html = (out / "element_table.html").read_text()
    svg = (out / "element_table.svg").read_text()
    assert "Candidate island focus" in html
    assert "stage-candidate_island_focus" in svg
    bundle = json.loads((out / "visual_render_bundle.json").read_text())
    assert bundle["html_hash"]
    assert bundle["svg_hash"]
