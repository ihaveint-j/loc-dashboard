"""Extract LOC snapshots using git archive + cloc for ground-truth line counts."""

from __future__ import annotations

import subprocess
import tempfile
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class LOCSnapshot:
    """A true LOC snapshot at a specific commit, measured by cloc."""

    month: str  # e.g. "2024-05"
    commit_hash: str
    commit_date: datetime
    repo_total: int = 0
    repo_by_lang: Dict[str, int] = field(default_factory=dict)
    subdir_totals: Dict[str, int] = field(default_factory=dict)
    subdir_by_lang: Dict[str, Dict[str, int]] = field(default_factory=dict)

    def subdir_pct(self, subdir: str) -> float:
        if self.repo_total == 0:
            return 0.0
        return (self.subdir_totals.get(subdir, 0) / self.repo_total) * 100


def _run(cmd: List[str], cwd: str, timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout
    )


def get_monthly_commits(repo_path: str, branch: str = "main") -> List[dict]:
    """Get the last commit on the branch for each year-month."""
    result = _run(
        ["git", "log", branch, "--format=%H %ai", "--reverse"],
        cwd=repo_path,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git log failed: {result.stderr}")

    monthly: Dict[str, dict] = {}
    for line in result.stdout.strip().splitlines():
        parts = line.split()
        commit_hash = parts[0]
        date_str = parts[1]  # YYYY-MM-DD
        month = date_str[:7]  # YYYY-MM
        commit_date = datetime.fromisoformat(f"{parts[1]}T{parts[2]}")
        monthly[month] = {"hash": commit_hash, "date": commit_date, "month": month}

    return [monthly[k] for k in sorted(monthly.keys())]


def _cloc_from_archive(
    repo_path: str, commit_hash: str, subpath: Optional[str] = None
) -> tuple[int, Dict[str, int]]:
    """Run git archive | cloc and return (total_loc, {lang: loc})."""
    with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        git_cmd = ["git", "archive", commit_hash]
        if subpath:
            git_cmd += ["--", subpath]

        with open(tmp_path, "wb") as f:
            proc = subprocess.run(
                git_cmd, stdout=f, stderr=subprocess.PIPE, cwd=repo_path, timeout=120
            )
            if proc.returncode != 0:
                return 0, {}

        cloc_result = subprocess.run(
            ["cloc", tmp_path, "--csv", "--quiet"],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if cloc_result.returncode != 0:
            return 0, {}

        total = 0
        by_lang: Dict[str, int] = {}

        for line in cloc_result.stdout.strip().splitlines():
            if line.startswith("files") or not line[0].isdigit():
                continue
            parts = line.split(",")
            if len(parts) < 5:
                continue
            lang = parts[1]
            code = int(parts[4])
            if lang == "SUM":
                total = code
            else:
                by_lang[lang] = code

        return total, by_lang
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _has_subpath(repo_path: str, commit_hash: str, subpath: str) -> bool:
    result = _run(
        ["git", "ls-tree", "-d", commit_hash, "--", subpath],
        cwd=repo_path,
    )
    return result.returncode == 0 and result.stdout.strip() != ""


def collect_snapshots(
    repo_path: str,
    branch: str = "main",
    subdirs: Optional[List[str]] = None,
    on_progress=None,
) -> List[LOCSnapshot]:
    """Collect monthly LOC snapshots for the entire repo and optional subdirectories."""
    commits = get_monthly_commits(repo_path, branch)
    snapshots: List[LOCSnapshot] = []
    subdirs = subdirs or []

    # Normalize: ensure trailing slash for git ls-tree
    normalized = []
    for sd in subdirs:
        sd = sd.strip("/") + "/"
        normalized.append(sd)
    subdirs = normalized

    for i, entry in enumerate(commits):
        month = entry["month"]
        commit_hash = entry["hash"]
        commit_date = entry["date"]

        if on_progress:
            on_progress(i + 1, len(commits), month)

        # Full repo
        repo_total, repo_by_lang = _cloc_from_archive(repo_path, commit_hash)

        # Subdirectories
        subdir_totals: Dict[str, int] = {}
        subdir_by_lang: Dict[str, Dict[str, int]] = {}

        for sd in subdirs:
            if _has_subpath(repo_path, commit_hash, sd):
                total, by_lang = _cloc_from_archive(repo_path, commit_hash, sd)
                subdir_totals[sd] = total
                subdir_by_lang[sd] = by_lang
            else:
                subdir_totals[sd] = 0
                subdir_by_lang[sd] = {}

        snapshots.append(
            LOCSnapshot(
                month=month,
                commit_hash=commit_hash,
                commit_date=commit_date,
                repo_total=repo_total,
                repo_by_lang=repo_by_lang,
                subdir_totals=subdir_totals,
                subdir_by_lang=subdir_by_lang,
            )
        )

    return snapshots
