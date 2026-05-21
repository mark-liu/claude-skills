#!/usr/bin/env python3
"""Lightweight skills/memory staleness checker.

Checks:
1. Memory file staleness (dates from knowledge index)
2. Pending items in audit queue
3. Content drift (broken anchors in code-backed skills)
4. Skills without cross-references (taxonomy-aware)
5. Security scan (secrets, permissions, hooks, MCP config)
6. Backup integrity (symlinks, untracked skills/memory files)

Outputs findings as JSON to stdout and optionally writes to an output directory.

Usage:
    python3 audit-check.py [--config CONFIG] [--dry-run] [--output-dir DIR] [--no-notify]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Configure these paths for your setup.
# The defaults assume a standard Claude Code project layout. Override via
# config.json or CLI args if your project uses a different structure.
# ---------------------------------------------------------------------------
DEFAULT_MEMORY_DIR = ".claude/projects/memory"
DEFAULT_MEMORY_INDEX = ".claude/projects/memory/MEMORY.md"
DEFAULT_SKILLS_DIR = ".claude/skills"
DEFAULT_QUEUE_PATH = ""       # empty = plugin-relative queue.json
DEFAULT_DRIFT_STATE_PATH = "" # empty = plugin-relative drift-state.json


def load_config(config_path: Path) -> dict:
    """Load configuration from JSON file."""
    if not config_path.exists():
        print(f"ERROR: config file not found: {config_path}", file=sys.stderr)
        print("Copy config.example.json to config.json and edit paths.", file=sys.stderr)
        sys.exit(1)
    return json.loads(config_path.read_text())


def resolve_config_path(raw: str, fallback_relative: str = "") -> Path:
    """Resolve a config path string, expanding ~ and env vars.

    If raw is empty and fallback_relative is provided, use fallback_relative
    relative to the plugin root (two levels up from scripts/).
    """
    if raw:
        return Path(os.path.expandvars(os.path.expanduser(raw)))
    if fallback_relative:
        return Path(__file__).resolve().parent.parent / fallback_relative
    return Path("")


def parse_knowledge_index(memory_index: Path) -> dict[str, str]:
    """Extract topic_file -> date from knowledge index tables.

    Matches rows like: | `ken-mail.md` | `ken-mail` | ... | 2026-02-23 |
    Parses both hot tier (the index file) and cold tier (index-cold.md sibling).
    """
    entries = {}
    row_pattern = re.compile(
        r"\|\s*`([^`]+\.md)`\s*\|.*?\|\s*(\d{4}-\d{2}-\d{2})\s*\|"
    )

    if memory_index.exists():
        for match in row_pattern.finditer(memory_index.read_text()):
            entries[match.group(1)] = match.group(2)

    # Parse cold tier if present
    cold_index = memory_index.parent / "index-cold.md"
    if cold_index.exists():
        for match in row_pattern.finditer(cold_index.read_text()):
            if match.group(1) not in entries:
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


def check_missing_crossrefs(
    skills_dir: Path,
    utility_skills: set[str] | None = None,
    standalone_skills: set[str] | None = None,
) -> list[dict]:
    """Find skills missing expected cross-reference sections based on taxonomy.

    Three categories:
    - Utility skills: should have `## Used By` section
    - Domain skills: should have `## Cross-References` section
    - Standalone skills: exempt from cross-ref requirements
    """
    if utility_skills is None:
        utility_skills = set()
    if standalone_skills is None:
        standalone_skills = set()

    missing = []
    if not skills_dir.is_dir():
        return missing

    for skill_dir in sorted(skills_dir.iterdir()):
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            continue

        text = skill_file.read_text()
        name_match = re.search(r"^name:\s*(.+)$", text, re.MULTILINE)
        name = name_match.group(1).strip() if name_match else skill_dir.name

        # Standalone skills are exempt from cross-ref requirements
        if name in standalone_skills or skill_dir.name in standalone_skills:
            continue

        has_crossrefs = "## Cross-References" in text or "## Cross References" in text
        has_used_by = "## Used By" in text

        if name in utility_skills or skill_dir.name in utility_skills:
            # Utility skills should have `## Used By`
            if not has_used_by:
                missing.append({
                    "skill": name,
                    "dir": skill_dir.name,
                    "type": "taxonomy",
                    "detail": "utility skill missing ## Used By section",
                })
        else:
            # Domain skills should have `## Cross-References`
            if not has_crossrefs:
                missing.append({
                    "skill": name,
                    "dir": skill_dir.name,
                    "type": "missing_crossrefs",
                })

    return missing


# Inserted after check_missing_crossrefs by patch script.

# Thariq's 9 category taxonomy. Each entry: (slug, keyword regex list).
# Keywords are deliberately broad — straddle detection looks for skills that
# score on 3+ categories with no clear winner.
SKILL_CATEGORIES = {
    "library-api-ref":   [r"\blibrary\b", r"\bAPI\b", r"\bCLI\b", r"\bSDK\b", r"\bgotcha", r"\bedge case", r"\busage pattern"],
    "product-verify":    [r"\bverify\b", r"\bverification\b", r"\bplaywright\b", r"\bbrowser\b", r"\be2e\b", r"\bsmoke test", r"\bUI flow"],
    "data-analysis":     [r"\bquery\b", r"\bdashboard\b", r"\bprometheus\b", r"\bgrafana\b", r"\bloki\b", r"\bbigquery\b", r"\bmetrics\b"],
    "business-process":  [r"\bstandup\b", r"\bticket\b", r"\bslack\b", r"\bnotion\b", r"\bautomate\b", r"\binvoice\b", r"\bcalendar"],
    "scaffolding":       [r"\bscaffold\b", r"\btemplate\b", r"\bgenerate\b", r"\bcreate\s+(?:app|repo|skill)\b", r"\bboilerplate"],
    "code-quality":      [r"\breview\b", r"\bcode quality\b", r"\bstyle\b", r"\blint\b", r"\badversarial\b", r"\btest practice"],
    "cicd-deploy":       [r"\bdeploy\b", r"\bGH Actions\b", r"\bGitHub Actions\b", r"\bpush\b", r"\bmerge\b", r"\brelease\b", r"\bcherry-pick"],
    "runbook":           [r"\binvestigate\b", r"\bsymptom\b", r"\boncall\b", r"\balert\b", r"\bdebug\b", r"\bdiagnose\b", r"\btriage\b"],
    "infra-ops":         [r"\bcluster\b", r"\bterraform\b", r"\bupgrade\b", r"\bfleet\b", r"\bvalidator\b", r"\bk8s\b", r"\bkubernetes\b", r"\bargocd\b"],
}


def check_category_straddle(skills_dir: Path, exempt: set[str] | None = None) -> list[dict]:
    """Score each skill against Thariq's 9-category taxonomy.

    Per Thariq (https://x.com/trq212/status/2033949937936085378):
    "Best skills fit cleanly into one. Straddling several = confused skill."

    Implementation: hit-count per category from frontmatter+body. Flag a skill
    when its top category has <2x the score of category #2 AND at least 3
    categories score >0. That's the "no clear winner" signal — not the same
    as a multi-tag skill (e.g. argocd-operations legitimately spans infra-ops
    + runbook, which is fine because infra-ops wins decisively).
    """
    findings = []
    if exempt is None:
        exempt = set()
    if not skills_dir.is_dir():
        return findings

    compiled = {
        cat: [re.compile(pat, re.IGNORECASE) for pat in pats]
        for cat, pats in SKILL_CATEGORIES.items()
    }

    for skill_dir in sorted(skills_dir.iterdir()):
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            continue

        if skill_dir.name in exempt:
            continue
        text = skill_file.read_text()
        # Score: count distinct keyword *hits* per category (cap each pattern at 3 to avoid
        # dominant-keyword skew).
        scores = {}
        for cat, patterns in compiled.items():
            total = 0
            for p in patterns:
                total += min(len(p.findall(text)), 3)
            if total:
                scores[cat] = total

        if len(scores) < 3:
            continue
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        top_cat, top_score = ranked[0]
        runner_cat, runner_score = ranked[1]
        third_score = ranked[2][1]
        # Straddle = no clear winner: top < 1.4x runner AND third > 60% of top.
        # Avoids flagging skills with a dominant primary + natural secondary
        # (e.g. infra-ops + runbook for ops-investigation skills).
        if runner_score >= 5 and top_score < runner_score * 1.4 and third_score * 1.0 / top_score >= 0.6:
            findings.append({
                "skill": skill_dir.name,
                "type": "category_straddle",
                "top": top_cat,
                "top_score": top_score,
                "runner_up": runner_cat,
                "runner_score": runner_score,
                "all_scored": dict(ranked),
                "detail": f"no dominant category: {top_cat}={top_score} vs {runner_cat}={runner_score}; consider splitting or sharpening description",
            })

    return findings


def check_missing_gotchas(skills_dir: Path, min_age_days: int = 30) -> list[dict]:
    """Flag mature skills missing a gotchas section.

    Per Thariq: gotchas are "the highest-signal content in any skill" and
    should grow iteratively (1 entry day 1 → 10 entries by month 3). A
    >30-day-old skill with no gotchas section either hasn't been used
    much, or has accumulated tribal-knowledge that should be written down.
    """
    findings = []
    if not skills_dir.is_dir():
        return findings

    threshold = datetime.now() - timedelta(days=min_age_days)
    for skill_dir in sorted(skills_dir.iterdir()):
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            continue
        mtime = datetime.fromtimestamp(skill_file.stat().st_mtime)
        if mtime > threshold:
            continue
        text = skill_file.read_text().lower()
        # Permissive: any header variant containing "gotcha"
        if re.search(r"^#+\s+[^\n]*gotcha", text, re.MULTILINE):
            continue
        # Heuristic exemption: short reference cards (< 1500 chars body) don't need it.
        body = re.sub(r"^---.*?---", "", skill_file.read_text(), count=1, flags=re.DOTALL)
        if len(body) < 1500:
            continue
        findings.append({
            "skill": skill_dir.name,
            "type": "missing_gotchas",
            "age_days": (datetime.now() - mtime).days,
            "detail": f"skill is {(datetime.now() - mtime).days}d old, no '## Gotchas'/'## Known Gotchas' section",
        })

    return findings


def check_backup_integrity(
    expected_symlinks: dict[Path, Path] | None = None,
    backup_repo: Path | None = None,
) -> list[dict]:
    """Verify symlinks to backup repo and check for untracked skills/memory files.

    Pass expected_symlinks as {live_path: expected_target} dict.
    If backup_repo is provided, also checks for untracked/uncommitted files.
    """
    findings = []

    # 1. Verify expected symlinks
    if expected_symlinks:
        for live_path, expected_target in expected_symlinks.items():
            if not live_path.exists() and not live_path.is_symlink():
                findings.append({
                    "type": "missing_symlink",
                    "path": str(live_path),
                    "expected_target": str(expected_target),
                    "detail": "Path does not exist",
                })
            elif not live_path.is_symlink():
                findings.append({
                    "type": "broken_symlink",
                    "path": str(live_path),
                    "expected_target": str(expected_target),
                    "detail": "Not a symlink (real file/dir) — backup repo may not track changes",
                })
            else:
                actual_target = live_path.resolve()
                expected_resolved = expected_target.resolve()
                if actual_target != expected_resolved:
                    findings.append({
                        "type": "wrong_symlink",
                        "path": str(live_path),
                        "expected_target": str(expected_target),
                        "actual_target": str(actual_target),
                        "detail": "Symlink points to wrong location",
                    })

    # 2. Check for untracked files in the backup repo
    if backup_repo and backup_repo.is_dir():
        try:
            result = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard"],
                cwd=backup_repo,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                untracked = [
                    f for f in result.stdout.strip().splitlines()
                    if f.startswith(("skills/", "project-memory/"))
                ]
                for f in untracked:
                    findings.append({
                        "type": "untracked_file",
                        "path": f,
                        "detail": "File exists in repo dir but not tracked by git",
                    })
        except (subprocess.TimeoutExpired, OSError):
            pass

        # 3. Check for uncommitted changes in skills/ and project-memory/
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain", "--", "skills/", "project-memory/"],
                cwd=backup_repo,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                uncommitted = result.stdout.strip().splitlines()
                for line in uncommitted:
                    status = line[:2].strip()
                    filepath = line[3:]
                    if status in ("M", "A", "D", "??"):
                        findings.append({
                            "type": "uncommitted_change",
                            "path": filepath,
                            "status": status,
                            "detail": f"Uncommitted change ({status}) — autocommit hook may have failed",
                        })
        except (subprocess.TimeoutExpired, OSError):
            pass

    return findings


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
        if str(script_dir) in sys.path:
            sys.path.remove(str(script_dir))

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


def notify(title: str, message: str) -> None:
    """Send macOS notification (no-op on other platforms)."""
    if sys.platform != "darwin":
        return
    safe_title = title.replace("\\", "\\\\").replace('"', '\\"')
    safe_message = message.replace("\\", "\\\\").replace('"', '\\"')
    try:
        subprocess.run(
            [
                "osascript", "-e",
                f'display notification "{safe_message}" with title "{safe_title}"',
            ],
            capture_output=True,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, OSError):
        pass


def main():
    parser = argparse.ArgumentParser(description="Skills/memory staleness check")
    parser.add_argument(
        "--config", type=Path,
        default=Path(__file__).resolve().parent.parent / "config.json",
        help="Path to config.json (default: plugin's config.json)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print findings, don't write output")
    parser.add_argument("--no-notify", action="store_true", help="Skip macOS notification")
    parser.add_argument("--output-dir", type=Path, help="Directory to write findings JSON")
    args = parser.parse_args()

    cfg = load_config(args.config)

    memory_index = resolve_config_path(
        cfg.get("memory_index", ""),
        DEFAULT_MEMORY_INDEX,
    )
    skills_dir = resolve_config_path(
        cfg.get("skills_dir", ""),
        DEFAULT_SKILLS_DIR,
    )
    queue_path = resolve_config_path(
        cfg.get("queue_path", ""),
        "queue.json",
    )
    drift_state_path = resolve_config_path(
        cfg.get("drift_state_path", ""),
        "drift-state.json",
    )
    backup_repo = resolve_config_path(cfg.get("backup_repo", ""))

    staleness_cfg = cfg.get("staleness_thresholds", {})
    infra_days = staleness_cfg.get("infra_days", 14)
    reference_days = staleness_cfg.get("reference_days", 30)
    infra_keywords = cfg.get("infra_keywords")
    exempt_files = set(cfg.get("exempt_files", []))

    # Skill taxonomy for cross-ref checking
    utility_skills = set(cfg.get("utility_skills", []))
    standalone_skills = set(cfg.get("standalone_skills", []))

    # Symlink verification (optional)
    symlink_map = {}
    for entry in cfg.get("expected_symlinks", []):
        live = Path(os.path.expanduser(entry["live"]))
        target = Path(os.path.expanduser(entry["target"]))
        symlink_map[live] = target

    if not memory_index.exists():
        print(f"ERROR: memory index not found: {memory_index}", file=sys.stderr)
        sys.exit(1)

    index = parse_knowledge_index(memory_index)
    stale = check_staleness(index, infra_days, reference_days, infra_keywords, exempt_files)
    pending_queue = check_queue(queue_path)
    no_xrefs = check_missing_crossrefs(skills_dir, utility_skills, standalone_skills)
    straddles = check_category_straddle(skills_dir, set(cfg.get("straddle_exempt_skills", [])))
    missing_gotchas = check_missing_gotchas(skills_dir, min_age_days=cfg.get("gotchas_min_age_days", 30))
    hard_drift, soft_drift = check_content_drift(drift_state_path, queue_path, skills_dir)
    backup_issues = check_backup_integrity(symlink_map or None, backup_repo or None)

    # Security scan (optional — import from sibling script if available)
    security_high = []
    security_other = []
    script_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(script_dir))
    try:
        from security_scan import run_security_scan
        security_findings = run_security_scan()
        security_high = [f for f in security_findings if f.severity in ("critical", "high")]
        security_other = [f for f in security_findings if f.severity not in ("critical", "high")]
    except ImportError:
        pass
    finally:
        if str(script_dir) in sys.path:
            sys.path.remove(str(script_dir))

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
    if straddles:
        parts.append(f"{len(straddles)} category-straddle{'s' if len(straddles) != 1 else ''}")
    if missing_gotchas:
        parts.append(f"{len(missing_gotchas)} skill{'s' if len(missing_gotchas) != 1 else ''} missing gotchas section")
    if security_high:
        parts.append(f"{len(security_high)} security finding{'s' if len(security_high) != 1 else ''}")
    if backup_issues:
        parts.append(f"{len(backup_issues)} backup issue{'s' if len(backup_issues) != 1 else ''}")

    if not parts:
        print(json.dumps({"summary": "all clear", "findings": {}}, indent=2))
        if security_other:
            print(f"  ({len(security_other)} info-level security items logged)", file=sys.stderr)
        sys.exit(0)

    summary = "Skills audit: " + ", ".join(parts)

    # Print human-readable output
    print(summary)

    if stale:
        print("\nStale files:")
        for f in stale:
            print(f"  {f['file']}: {f['age_days']}d old (threshold: {f['threshold']}d)")

    if pending_queue:
        print(f"\nPending queue items: {len(pending_queue)}")
        for item in pending_queue:
            print(f"  [{item.get('priority', '?')}] {item.get('title', '?')}")

    if hard_drift:
        print("\nBroken anchors (content drift):")
        for f in hard_drift:
            print(f"  [{f['skill']}] {f['description']}")

    if soft_drift:
        print("\nWatched files changed (informational):")
        for f in soft_drift:
            print(f"  [{f['skill']}] {f['file']}")

    if no_xrefs:
        print(f"\nSkills without cross-references: {len(no_xrefs)}")
        for s in no_xrefs:
            detail = s.get("detail", "missing ## Cross-References section")
            print(f"  {s['skill']}: {detail}")

    if straddles:
        print(f"\nCategory-straddle skills ({len(straddles)}):")
        for s in straddles:
            print(f"  {s['skill']}: {s['detail']}")

    if missing_gotchas:
        print(f"\nSkills missing gotchas section ({len(missing_gotchas)}):")
        for s in missing_gotchas:
            print(f"  {s['skill']}: {s['detail']}")

    if security_high:
        print(f"\nSecurity findings ({len(security_high)} high/critical):")
        for f in security_high:
            print(f"  [{f.severity}] {f.title}: {f.file}")
    if security_other:
        print(f"\nSecurity info: {len(security_other)} items (info/low/medium)")

    if backup_issues:
        print(f"\nBackup integrity ({len(backup_issues)} issue{'s' if len(backup_issues) != 1 else ''}):")
        for b in backup_issues:
            print(f"  [{b['type']}] {b['path']}: {b['detail']}")

    # Build JSON findings
    findings = {
        "summary": summary,
        "stale_files": stale,
        "pending_queue": pending_queue,
        "hard_drift": hard_drift,
        "soft_drift": soft_drift,
        "missing_crossrefs": no_xrefs,
        "category_straddles": straddles,
        "missing_gotchas": missing_gotchas,
        "backup_issues": backup_issues,
    }
    if security_high:
        try:
            from dataclasses import asdict
            findings["security_high"] = [asdict(f) for f in security_high]
        except (ImportError, TypeError):
            findings["security_high"] = [str(f) for f in security_high]
    if security_other:
        findings["security_info_count"] = len(security_other)

    # Only notify/write output for actionable findings
    actionable = bool(stale or pending_queue or hard_drift or security_high or backup_issues)

    if not args.dry_run and args.output_dir and actionable:
        output_path = write_output(findings, args.output_dir)
        print(f"\nWrote to: {output_path}", file=sys.stderr)

    if not args.no_notify and actionable:
        alert_parts = []
        if stale:
            alert_parts.append(f"{len(stale)} stale file{'s' if len(stale) != 1 else ''}")
        if pending_queue:
            alert_parts.append(f"{len(pending_queue)} queued item{'s' if len(pending_queue) != 1 else ''}")
        if hard_drift:
            alert_parts.append(f"{len(hard_drift)} broken anchor{'s' if len(hard_drift) != 1 else ''}")
        if security_high:
            alert_parts.append(f"{len(security_high)} security issue{'s' if len(security_high) != 1 else ''}")
        if backup_issues:
            alert_parts.append(f"{len(backup_issues)} backup issue{'s' if len(backup_issues) != 1 else ''}")
        notify("Skills Audit", ", ".join(alert_parts))


if __name__ == "__main__":
    main()
