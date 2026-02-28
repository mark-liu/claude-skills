#!/usr/bin/env python3
"""Lightweight skills/memory staleness checker.

Checks:
1. Memory file staleness (dates from knowledge index)
2. Pending items in audit queue
3. Content drift (broken anchors in code-backed skills)
4. Skills without cross-references

Outputs findings as JSON to stdout and optionally writes to an output directory.

Usage:
    python3 audit-check.py [--config CONFIG] [--dry-run] [--output-dir DIR]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


def load_config(config_path: Path) -> dict:
    """Load configuration from JSON file."""
    if not config_path.exists():
        print(f"ERROR: config file not found: {config_path}", file=sys.stderr)
        print("Copy config.example.json to config.json and edit paths.", file=sys.stderr)
        sys.exit(1)
    return json.loads(config_path.read_text())


def parse_knowledge_index(memory_index: Path) -> dict[str, str]:
    """Extract topic_file -> date from the knowledge index table.

    Matches rows like: | `ken-mail.md` | `ken-mail` | ... | 2026-02-23 |
    """
    if not memory_index.exists():
        return {}
    entries = {}
    text = memory_index.read_text()
    row_pattern = re.compile(
        r"\|\s*`([^`]+\.md)`\s*\|.*?\|\s*(\d{4}-\d{2}-\d{2})\s*\|"
    )
    for match in row_pattern.finditer(text):
        entries[match.group(1)] = match.group(2)
    return entries


def check_staleness(
    index: dict[str, str],
    infra_days: int = 14,
    reference_days: int = 30,
    infra_keywords: list[str] | None = None,
    exempt_files: set[str] | None = None,
) -> list[dict]:
    """Find stale memory files based on knowledge index dates."""
    if infra_keywords is None:
        infra_keywords = ["infra", "ops", "deploy", "monitor", "agents", "projects", "people"]
    if exempt_files is None:
        exempt_files = set()

    findings = []
    now = datetime.now()

    for filename, date_str in index.items():
        if filename in exempt_files:
            continue

        try:
            file_date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue

        age_days = (now - file_date).days
        is_infra = any(kw in filename.lower() for kw in infra_keywords)
        threshold = infra_days if is_infra else reference_days

        if age_days > threshold:
            findings.append({
                "file": filename,
                "last_updated": date_str,
                "age_days": age_days,
                "threshold": threshold,
                "type": "infra" if is_infra else "reference",
            })

    return sorted(findings, key=lambda f: f["age_days"], reverse=True)


def check_queue(queue_path: Path) -> list[dict]:
    """Return pending items from the audit queue."""
    if not queue_path.exists():
        return []
    try:
        queue = json.loads(queue_path.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    return [item for item in queue if item.get("status") == "pending"]


def check_missing_crossrefs(skills_dir: Path) -> list[dict]:
    """Find skills without a Cross-References section."""
    missing = []
    if not skills_dir.is_dir():
        return missing

    for skill_dir in sorted(skills_dir.iterdir()):
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            continue

        text = skill_file.read_text()
        if "## Cross-References" not in text and "## Cross References" not in text:
            name_match = re.search(r"^name:\s*(.+)$", text, re.MULTILINE)
            name = name_match.group(1).strip() if name_match else skill_dir.name
            missing.append({"skill": name, "dir": skill_dir.name})

    return missing


def check_content_drift(
    drift_state_path: Path,
    queue_path: Path,
    skills_dir: Path,
) -> tuple[list[dict], list[dict]]:
    """Run content drift detection. Returns (hard_findings, soft_findings)."""
    if not drift_state_path.exists():
        return [], []

    script_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(script_dir))
    try:
        from content_drift_check import run_drift_check
    except ImportError:
        return [], []
    finally:
        sys.path.pop(0)

    findings = run_drift_check(
        state_path=drift_state_path,
        queue_path=queue_path,
        skills_dir=skills_dir,
    )
    hard = [f for f in findings if f["severity"] == "hard"]
    soft = [f for f in findings if f["severity"] == "soft"]
    return hard, soft


def write_output(findings: dict, output_dir: Path) -> Path:
    """Write findings to output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    output_file = output_dir / f"skills-audit-{today}.json"

    result = {
        "id": f"skills-audit-{today}",
        "type": "skills-audit",
        "status": "completed",
        "timestamp": datetime.now().isoformat(),
        "summary": findings["summary"],
        "details": findings,
    }

    output_file.write_text(json.dumps(result, indent=2) + "\n")
    return output_file


def main():
    parser = argparse.ArgumentParser(description="Skills/memory staleness check")
    parser.add_argument(
        "--config", type=Path,
        default=Path(__file__).resolve().parent.parent / "config.json",
        help="Path to config.json (default: plugin's config.json)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print findings, don't write output")
    parser.add_argument("--output-dir", type=Path, help="Directory to write findings JSON")
    args = parser.parse_args()

    cfg = load_config(args.config)

    memory_index = Path(cfg["memory_index"]).expanduser()
    skills_dir = Path(cfg["skills_dir"]).expanduser()
    queue_path = Path(cfg.get("queue_path", str(Path(__file__).resolve().parent.parent / "queue.json"))).expanduser()
    drift_state_path = Path(cfg.get("drift_state_path", str(Path(__file__).resolve().parent.parent / "drift-state.json"))).expanduser()

    staleness_cfg = cfg.get("staleness_thresholds", {})
    infra_days = staleness_cfg.get("infra_days", 14)
    reference_days = staleness_cfg.get("reference_days", 30)
    infra_keywords = cfg.get("infra_keywords")
    exempt_files = set(cfg.get("exempt_files", []))

    if not memory_index.exists():
        print(f"ERROR: memory index not found: {memory_index}", file=sys.stderr)
        sys.exit(1)

    index = parse_knowledge_index(memory_index)
    stale = check_staleness(index, infra_days, reference_days, infra_keywords, exempt_files)
    pending_queue = check_queue(queue_path)
    no_xrefs = check_missing_crossrefs(skills_dir)
    hard_drift, soft_drift = check_content_drift(drift_state_path, queue_path, skills_dir)

    # Build summary
    parts = []
    if stale:
        parts.append(f"{len(stale)} stale file{'s' if len(stale) != 1 else ''}")
    if pending_queue:
        parts.append(f"{len(pending_queue)} queued item{'s' if len(pending_queue) != 1 else ''}")
    if hard_drift:
        parts.append(f"{len(hard_drift)} broken anchor{'s' if len(hard_drift) != 1 else ''}")
    if no_xrefs:
        parts.append(f"{len(no_xrefs)} skill{'s' if len(no_xrefs) != 1 else ''} without cross-refs")

    if not parts:
        print(json.dumps({"summary": "all clear", "findings": {}}, indent=2))
        sys.exit(0)

    summary = "Skills audit: " + ", ".join(parts)

    findings = {
        "summary": summary,
        "stale_files": stale,
        "pending_queue": pending_queue,
        "hard_drift": hard_drift,
        "soft_drift": soft_drift,
        "missing_crossrefs": no_xrefs,
    }

    print(json.dumps(findings, indent=2))

    if not args.dry_run and args.output_dir:
        output_path = write_output(findings, args.output_dir)
        print(f"\nWrote to: {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
