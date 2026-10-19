"""Recent capture projects, their saved state, and safe default folders. No Qt."""
import json
import logging
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

PROJECTS_ENV = "PARAMETRIC_PROJECTS_ROOT"
RECENT_KEY = "recent/projects"
MAX_FOLDER_NAME = 80
UNTITLED = "Untitled capture"
_UNSAFE = re.compile(r'[/\\:*?"<>|\x00-\x1f\x7f]')

ProjectState = Literal["missing", "unreadable", "new", "recording", "recorded", "ready", "stopped"]


@dataclass(frozen=True)
class RecentProject:
    path: str
    name: str
    opened_at: float


@dataclass(frozen=True)
class ProjectStatus:
    state: ProjectState
    detail: str
    captured: int
    total: int


def projects_root() -> Path:
    """Where new projects go by default. Read at call time so tests can redirect it."""
    override = os.environ.get(PROJECTS_ENV)
    return Path(override) if override else Path.home() / "Music" / "Parametric"


def safe_folder_name(name: str) -> str:
    cleaned = _UNSAFE.sub("-", name).strip(" .")
    return cleaned[:MAX_FOLDER_NAME].strip(" .") or UNTITLED


def default_project_dir(root: Path, name: str) -> Path:
    """`root/<safe name>`, numbered "<name> 2", "<name> 3", … if that folder exists."""
    base = safe_folder_name(name)
    candidate, number = root / base, 2
    while candidate.exists():
        candidate, number = root / f"{base} {number}", number + 1
    return candidate


def parse_recent(raw: object) -> tuple[RecentProject, ...]:
    try:
        items = json.loads(raw) if isinstance(raw, str) else []
    except ValueError:
        return ()
    if not isinstance(items, list):
        return ()
    result = []
    for item in items:
        if (isinstance(item, dict) and isinstance(item.get("path"), str) and isinstance(item.get("name"), str)
                and isinstance(item.get("opened_at"), (int, float))):
            result.append(RecentProject(item["path"], item["name"], float(item["opened_at"])))
    return tuple(result)


def dump_recent(items: tuple[RecentProject, ...]) -> str:
    return json.dumps([asdict(item) for item in items])


def remember(items: tuple[RecentProject, ...], path: Path, name: str, now: float,
             limit: int = 12) -> tuple[RecentProject, ...]:
    """A new list with `path` first, without older entries for the same folder."""
    resolved = str(Path(path).resolve())
    rest = tuple(item for item in items if item.path != resolved)
    return ((RecentProject(resolved, name, now),) + rest)[:limit]


def forget(items: tuple[RecentProject, ...], path: Path) -> tuple[RecentProject, ...]:
    resolved = str(Path(path).resolve())
    return tuple(item for item in items if item.path != resolved)


def _runs(folder: Path) -> list[Path]:
    outputs = folder / "outputs"
    if not outputs.is_dir():
        return []
    runs = [p for p in outputs.iterdir() if p.is_dir() and (p / "manifest.json").is_file()]
    return sorted(runs, key=lambda p: (p / "manifest.json").stat().st_mtime_ns, reverse=True)


def _run_status(run: Path) -> str:
    try:
        value = json.loads((run / "status.json").read_text())
    except (OSError, ValueError):
        return ""
    return value.get("status", "") if isinstance(value, dict) else ""


def project_status(path: Path) -> ProjectStatus:
    """The saved state of a project folder, read from its files. Never raises."""
    folder = Path(path)
    if not folder.is_dir():
        return ProjectStatus("missing", "Folder not found", 0, 0)
    try:
        from .controls import load_project
        project = load_project(folder)
        runs = _runs(folder)
    except Exception as exc:  # Any unreadable project must show a state, not crash Start.
        logging.getLogger(__name__).warning("Cannot read project %s: %s", folder, exc)
        return ProjectStatus("unreadable", "Cannot read this project", 0, 0)
    from .workflow import takes_to_record
    total = len(project.entries)
    captured = total - len(takes_to_record(project))
    if total == 0:
        return ProjectStatus("new", "No recordings planned yet", 0, 0)
    if captured < total:
        return ProjectStatus("recording", f"Recording · {captured} of {total} takes", captured, total)
    if any((run / "model_parametric.nam").is_file() for run in runs):
        return ProjectStatus("ready", "Model ready", captured, total)
    if runs and _run_status(runs[0]) != "exported":
        return ProjectStatus("stopped", "Training did not finish", captured, total)
    return ProjectStatus("recorded", f"All {total} takes saved", captured, total)


def resume_step(status: ProjectStatus) -> str:
    """The step to open after a reopen. Recording always passes Connect first (new level check)."""
    if status.state in ("new", "recording"):
        return "connect"
    if status.state == "ready":
        return "listen"
    return "train"
