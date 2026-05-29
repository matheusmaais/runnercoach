from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


WORKFLOW_PATH = Path(".github/workflows/operational-intake.yml")
INPUT_EXPRESSION_RE = re.compile(r"\$\{\{\s*inputs\.")


def _workflow() -> dict[str, Any]:
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


def test_workflow_dispatch_inputs_are_not_interpolated_inside_run_blocks() -> None:
    offenders: list[str] = []

    for workflow_path in sorted(Path(".github/workflows").glob("*.y*ml")):
        workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
        for job_name, job in workflow.get("jobs", {}).items():
            for index, step in enumerate(job.get("steps", []), start=1):
                run_block = step.get("run")
                if isinstance(run_block, str) and INPUT_EXPRESSION_RE.search(run_block):
                    step_name = step.get("name", f"step {index}")
                    offenders.append(f"{workflow_path}:{job_name}:{step_name}")

    assert offenders == []


def test_operational_intake_path_is_validated_from_environment_before_use() -> None:
    workflow = _workflow()
    steps = workflow["jobs"]["process"]["steps"]
    process_step = next(step for step in steps if step.get("name") == "Process frontend intake")

    assert process_step.get("env", {}).get("INTAKE_PATH") == "${{ inputs.intake_path }}"
    run_block = process_step["run"]
    assert "os.environ[\"INTAKE_PATH\"]" in run_block
    assert "re.fullmatch" in run_block
    assert "data/manual/frontend_intake/" in run_block
    assert ".json" in run_block
    assert ".." in run_block
    assert "Invalid intake_path" in run_block
