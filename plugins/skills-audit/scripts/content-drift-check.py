#!/usr/bin/env python3
"""Content drift detection for skills that reference code-backed sources.

Two tiers:
  Hard drift (anchors): Skill quotes a specific value (version, config, class name).
    Script greps the source file for a regex. No match = high-confidence alert.
  Soft drift (file watchlist): Skill references source files. Script checks git
    for changes since last run. Changed files = informational flag.

Usage:
    python3 content-drift-check.py [--init] [--dry-run] [--verbose]
    python3 content-drift-check.py --state-path PATH --queue-path PATH
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


def _default_state_path() -> Path:
    return Path(__file__).resolve().parent.parent / "drift-state.json"


def _default_queue_path() -> Path:
    return Path(__file__).resolve().parent.parent / "queue.json"


def _default_skills_dir() -> Path:
    return Path.home() / ".claude" / "skills"


def load_drift_state(path: Path) -> dict[str, Any]:
    """Load drift state from JSON. Return empty structure if missing."""
    if not path.exists():
        return {"skills": {}, "last_run": None}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        print(f"WARN: could not read drift state: {e}", file=sys.stderr)
        return {"skills": {}, "last_run": None}


def save_drift_state(state: dict[str, Any], path: Path) -> None:
    """Write drift state to JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n")


def resolve_path(raw: str) -> Path:
    """Expand ~ and env vars in a path string."""
    return Path(os.path.expandvars(os.path.expanduser(raw)))


def get_repo_head(repo_path: Path) -> str | None:
    """Return current HEAD SHA for a git repo, or None."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=repo_path,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except (subprocess.TimeoutExpired, OSError):
        return None


def get_changed_files_since(repo_path: Path, since_sha: str) -> list[str]:
    """Return list of files changed between since_sha and HEAD."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{since_sha}..HEAD"],
            capture_output=True, text=True, timeout=10,
            cwd=repo_path,
        )
        if result.returncode != 0:
            return []
        return [f for f in result.stdout.strip().split("\n") if f]
    except (subprocess.TimeoutExpired, OSError):
        return []


def check_anchor(repo_path: Path, rel_file: str, pattern: str) -> bool:
    """Check if pattern matches anywhere in the source file. Returns True if found."""
    target = repo_path / rel_file
    if not target.exists():
        return False
    try:
        content = target.read_text()
        return bool(re.search(pattern, content))
    except OSError:
        return False


def check_anchors(skill_name: str, skill_cfg: dict, verbose: bool = False) -> list[dict]:
    """Check all anchors for a skill. Return list of broken findings."""
    findings = []
    repo_path = resolve_path(skill_cfg.get("repo", ""))
    if not repo_path.is_dir():
        if verbose:
            print(f"  SKIP {skill_name}: repo {repo_path} not found")
        return findings

    for anchor in skill_cfg.get("anchors", []):
        rel_file = anchor["file"]
        pattern = anchor["pattern"]
        desc = anchor.get("description", f"{rel_file} ~ {pattern}")

        found = check_anchor(repo_path, rel_file, pattern)
        if verbose:
            status = "OK" if found else "BROKEN"
            print(f"  [{status}] {desc}")

        if not found:
            findings.append({
                "skill": skill_name,
                "severity": "hard",
                "type": "content-drift",
                "file": rel_file,
                "pattern": pattern,
                "description": desc,
            })

    return findings


def check_watched_files(
    skill_name: str,
    skill_cfg: dict,
    verbose: bool = False,
) -> list[dict]:
    """Check if any watched files changed since last audit. Return findings."""
    findings = []
    repo_path = resolve_path(skill_cfg.get("repo", ""))
    if not repo_path.is_dir():
        return findings

    last_sha = skill_cfg.get("last_audited_sha")
    if not last_sha:
        return findings

    changed = get_changed_files_since(repo_path, last_sha)
    if not changed:
        return findings

    watched = set(skill_cfg.get("watched_files", []))
    overlap = watched & set(changed)

    if verbose and overlap:
        print(f"  Watched files changed since {last_sha[:8]}: {sorted(overlap)}")

    for f in sorted(overlap):
        findings.append({
            "skill": skill_name,
            "severity": "soft",
            "type": "content-drift",
            "file": f,
            "description": f"Watched file changed since last audit: {f}",
        })

    return findings


def load_queue(path: Path) -> list[dict]:
    """Load the audit queue."""
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return []


def save_queue(queue: list[dict], path: Path) -> None:
    """Write the audit queue."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(queue, indent=2) + "\n")


def is_already_queued(queue: list[dict], skill: str, detail: str) -> bool:
    """Check if a similar drift finding is already in the queue (pending or in-progress)."""
    for item in queue:
        if item.get("status") in ("done", "wontfix"):
            continue
        if item.get("type") == "content-drift" and skill in item.get("skills", []):
            if detail in item.get("detail", ""):
                return True
    return False


def queue_finding(queue: list[dict], finding: dict) -> bool:
    """Add a hard drift finding to the queue. Returns True if added."""
    skill = finding["skill"]
    detail = f"Anchor broken: {finding['description']} (pattern: {finding['pattern']})"

    if is_already_queued(queue, skill, finding["description"]):
        return False

    queue.append({
        "id": f"drift-{uuid4().hex[:8]}",
        "type": "content-drift",
        "priority": "high",
        "title": f"Content drift: {skill} — {finding['description']}",
        "detail": detail,
        "skills": [skill],
        "added": datetime.now().strftime("%Y-%m-%d"),
        "status": "pending",
    })
    return True


def extract_watched_files_from_skill(skill_path: Path) -> list[str]:
    """Extract file references from a SKILL.md for auto-populating watched_files.

    Looks for backtick-quoted relative paths and code block references.
    """
    if not skill_path.exists():
        return []

    text = skill_path.read_text()
    files = set()

    # Match backtick-quoted paths like `config/pipelines/pr-scout.json`
    for m in re.finditer(r"`([a-zA-Z0-9_./-]+\.[a-zA-Z0-9]+)`", text):
        candidate = m.group(1)
        # Filter to likely repo-relative paths (has directory separator, common extensions)
        if "/" in candidate and not candidate.startswith("http"):
            files.add(candidate)

    # Match paths in code blocks after common prefixes
    for m in re.finditer(r"(?:^|\s)((?:src|config|scripts|templates|tests)/[a-zA-Z0-9_./-]+)", text):
        files.add(m.group(1))

    return sorted(files)


def init_drift_config(
    state: dict[str, Any],
    skills_dir: Path,
    verbose: bool = False,
) -> dict[str, Any]:
    """Bootstrap: scan skills with repos, extract refs, set current HEAD as baseline."""
    for skill_name, skill_cfg in state.get("skills", {}).items():
        repo_path = resolve_path(skill_cfg.get("repo", ""))
        if not repo_path.is_dir():
            if verbose:
                print(f"  SKIP {skill_name}: repo not found at {repo_path}")
            continue

        # Set baseline SHA
        head = get_repo_head(repo_path)
        if head:
            skill_cfg["last_audited_sha"] = head
            if verbose:
                print(f"  {skill_name}: baseline SHA = {head[:8]}")

        # Auto-extract watched files from SKILL.md if not explicitly set
        if not skill_cfg.get("watched_files"):
            skill_dir = skills_dir / skill_name / "SKILL.md"
            extracted = extract_watched_files_from_skill(skill_dir)
            if extracted:
                skill_cfg["watched_files"] = extracted
                if verbose:
                    print(f"  {skill_name}: extracted {len(extracted)} watched files")

    state["last_run"] = datetime.now().isoformat()
    return state


def run_drift_check(
    state_path: Path | None = None,
    queue_path: Path | None = None,
    skills_dir: Path | None = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> list[dict]:
    """Run drift detection. Returns all findings (hard + soft)."""
    if state_path is None:
        state_path = _default_state_path()
    if queue_path is None:
        queue_path = _default_queue_path()
    if skills_dir is None:
        skills_dir = _default_skills_dir()

    state = load_drift_state(state_path)
    queue = load_queue(queue_path)
    all_findings: list[dict] = []

    for skill_name, skill_cfg in state.get("skills", {}).items():
        if verbose:
            print(f"\nChecking {skill_name}:")

        # Hard drift: anchor checks
        hard = check_anchors(skill_name, skill_cfg, verbose=verbose)
        all_findings.extend(hard)

        # Soft drift: watched file changes
        soft = check_watched_files(skill_name, skill_cfg, verbose=verbose)
        all_findings.extend(soft)

    # Queue hard drift findings
    queued_count = 0
    for finding in all_findings:
        if finding["severity"] == "hard" and not dry_run:
            if queue_finding(queue, finding):
                queued_count += 1

    # Update SHAs for next run
    if not dry_run:
        for skill_name, skill_cfg in state.get("skills", {}).items():
            repo_path = resolve_path(skill_cfg.get("repo", ""))
            if repo_path.is_dir():
                head = get_repo_head(repo_path)
                if head:
                    skill_cfg["last_audited_sha"] = head

        state["last_run"] = datetime.now().isoformat()
        save_drift_state(state, state_path)
        if queued_count > 0:
            save_queue(queue, queue_path)

    return all_findings


def main():
    parser = argparse.ArgumentParser(description="Content drift detection for skills")
    parser.add_argument("--init", action="store_true", help="Bootstrap: set baseline SHAs and extract watched files")
    parser.add_argument("--dry-run", action="store_true", help="Report findings without writing state or queue")
    parser.add_argument("--verbose", action="store_true", help="Print detailed check output")
    parser.add_argument("--state-path", type=Path, default=None, help="Path to drift-state.json")
    parser.add_argument("--queue-path", type=Path, default=None, help="Path to queue.json")
    parser.add_argument("--skills-dir", type=Path, default=None, help="Path to skills directory")
    args = parser.parse_args()

    state_path = args.state_path or _default_state_path()
    queue_path = args.queue_path or _default_queue_path()
    skills_dir = args.skills_dir or _default_skills_dir()

    if args.init:
        state = load_drift_state(state_path)
        if not state.get("skills"):
            print("ERROR: drift-state.json has no skills defined. Seed it first.", file=sys.stderr)
            sys.exit(1)

        print("Initializing drift baselines...")
        state = init_drift_config(state, skills_dir, verbose=True)
        save_drift_state(state, state_path)
        print(f"\nBaselines set. State saved to {state_path}")
        sys.exit(0)

    findings = run_drift_check(
        state_path=state_path,
        queue_path=queue_path,
        skills_dir=skills_dir,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )

    hard = [f for f in findings if f["severity"] == "hard"]
    soft = [f for f in findings if f["severity"] == "soft"]

    if not findings:
        print("Content drift check: all clear")
        sys.exit(0)

    if hard:
        print(f"\nHard drift ({len(hard)} broken anchor{'s' if len(hard) != 1 else ''}):")
        for f in hard:
            print(f"  [{f['skill']}] {f['description']}")
            print(f"    file: {f['file']}  pattern: {f['pattern']}")

    if soft:
        print(f"\nSoft drift ({len(soft)} watched file{'s' if len(soft) != 1 else ''} changed):")
        for f in soft:
            print(f"  [{f['skill']}] {f['file']}")

    if args.dry_run:
        print("\n(dry run — no state or queue changes)")


if __name__ == "__main__":
    main()
