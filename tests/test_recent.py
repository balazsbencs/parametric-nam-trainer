import json
import os
import time
from pathlib import Path

import pytest
from nam.capture.project import save_project

from parametric_mac.controls import ControlModel, ControlProject
from parametric_mac.control_editor import starter
from parametric_mac.recent import (
    ProjectStatus, RecentProject, default_project_dir, dump_recent, forget, parse_recent,
    project_status, projects_root, remember, resume_step, safe_folder_name,
)


def make_project(folder: Path, captured: int, total: int, workflow: dict | None = None) -> Path:
    """A saved capture project with `total` planned entries, `captured` of them recorded."""
    from parametric_mac.workflow import make_plan, quality_settings
    controls, train, tests = quality_settings(starter(False), 0)
    project = make_plan(controls, train, tests) if total else ControlProject(
        name="Rat", knobs=[ControlModel.from_spec(c) for c in controls])
    entries = project.entries[:total]
    for entry in entries[:captured]:
        entry.status = "captured"
    project = project.model_copy(update={"name": "Rat", "entries": entries})
    folder.mkdir(parents=True, exist_ok=True)
    save_project(project, folder)
    if workflow is not None:
        (folder / "workflow.json").write_text(json.dumps(workflow))
    return folder


def add_run(folder: Path, name: str, status: str, model: bool, age: float = 0) -> Path:
    run = folder / "outputs" / name
    run.mkdir(parents=True)
    (run / "manifest.json").write_text("{}")
    (run / "status.json").write_text(json.dumps({"status": status}))
    if model:
        (run / "model_parametric.nam").write_text("{}")
    stamp = time.time() - age
    os.utime(run / "manifest.json", (stamp, stamp))
    return run


def test_safe_folder_name_review_focus_2():
    assert safe_folder_name("Fuzz/Face") == "Fuzz-Face"
    assert safe_folder_name("a:b") == "a-b"
    assert safe_folder_name("   ") == "Untitled capture"
    assert safe_folder_name(".hidden") == "hidden"
    assert safe_folder_name("tab\there") == "tab-here"
    assert len(safe_folder_name("x" * 300)) == 80


def test_default_project_dir_never_escapes_root(tmp_path):
    for name in ("../evil", "/abs", "Fuzz/Face", "..", "a\\b"):
        assert default_project_dir(tmp_path, name).parent == tmp_path, name


def test_default_project_dir_numbers_existing(tmp_path):
    (tmp_path / "Rat").mkdir()
    (tmp_path / "Rat 2").mkdir()
    assert default_project_dir(tmp_path, "Rat").name == "Rat 3"
    assert default_project_dir(tmp_path, "Fuzz").name == "Fuzz"


def test_projects_root_reads_environment_at_call_time(monkeypatch, tmp_path):
    monkeypatch.setenv("PARAMETRIC_PROJECTS_ROOT", str(tmp_path))
    assert projects_root() == tmp_path
    monkeypatch.delenv("PARAMETRIC_PROJECTS_ROOT")
    assert projects_root() == Path.home() / "Music" / "Parametric"


def test_remember_is_immutable_and_deduplicates(tmp_path):
    first = remember((), tmp_path / "a", "A", now=1.0)
    second = remember(first, tmp_path / "b", "B", now=2.0)
    third = remember(second, tmp_path / "a" / ".." / "a", "A again", now=3.0)
    assert first == (RecentProject(str((tmp_path / "a").resolve()), "A", 1.0),)
    assert [r.name for r in third] == ["A again", "B"]
    assert len(second) == 2  # the earlier tuple is unchanged
    many = ()
    for i in range(20):
        many = remember(many, tmp_path / str(i), str(i), now=float(i))
    assert len(many) == 12 and many[0].name == "19"
    assert [r.name for r in forget(third, tmp_path / "a")] == ["B"]


def test_parse_recent_ignores_bad_entries():
    good = {"path": "/x", "name": "X", "opened_at": 1.5}
    raw = json.dumps([good, {"path": 3}, "junk", {"name": "no path"}])
    assert parse_recent(raw) == (RecentProject("/x", "X", 1.5),)
    assert parse_recent("{not json") == ()
    assert parse_recent(None) == ()
    assert parse_recent(dump_recent(parse_recent(raw))) == parse_recent(raw)


def test_status_missing_and_corrupt_review_focus_5(tmp_path):
    assert project_status(tmp_path / "gone") == ProjectStatus("missing", "Folder not found", 0, 0)
    (tmp_path / "capture_project.json").write_text("{not json")
    assert project_status(tmp_path).state == "unreadable"
    assert project_status(tmp_path).detail == "Cannot read this project"


@pytest.mark.parametrize("captured,total,runs,state,step", [
    (0, 0, [], "new", "connect"),
    (0, 5, [], "recording", "connect"),
    (3, 5, [], "recording", "connect"),
    (5, 5, [], "recorded", "train"),
    (5, 5, [("r1", "failed_or_interrupted", False, 0)], "stopped", "train"),
    (5, 5, [("r1", "exported", True, 100), ("r2", "failed_or_interrupted", False, 0)], "ready", "listen"),
])
def test_status_and_resume_step(tmp_path, captured, total, runs, state, step):
    folder = make_project(tmp_path / "p", captured, total)
    for name, status, model, age in runs:
        add_run(folder, name, status, model, age)
    status = project_status(folder)
    assert (status.state, status.captured, status.total) == (state, captured, total)
    assert resume_step(status) == step


def test_resume_step_for_old_project_review_focus_1(tmp_path):
    old = {"quality": 4, "plan_locked": True, "gear_kind": "Pedal", "fixed_notes": "Level at 5"}
    folder = make_project(tmp_path / "old", 1, 40, workflow=old)
    status = project_status(folder)
    assert status.state == "recording" and status.captured == 1
    assert resume_step(status) == "connect"
    assert resume_step(ProjectStatus("new", "", 0, 0)) == "connect"
