#!/usr/bin/env python3
"""MCP version checker — compares locally pinned npm package versions against
npm registry latest, and local git repo HEADs against remote. Reports
advisories from npm audit.

Outputs JSON to stdout.

Requires: Python 3.11+ (stdlib only, no external deps)

Usage:
    python3 mcp-versions.py --config config.json
"""

import asyncio
import argparse
import json
import os
import sys
from pathlib import Path

NPX_CACHE = Path.home() / ".npm" / "_npx"


def load_config(config_path: Path) -> dict:
    """Load configuration from JSON file."""
    if not config_path.exists():
        print(f"ERROR: config file not found: {config_path}", file=sys.stderr)
        print("Copy config.example.json to config.json and edit.", file=sys.stderr)
        sys.exit(1)
    return json.loads(config_path.read_text())


# ---------------------------------------------------------------------------
# npm version checks
# ---------------------------------------------------------------------------
async def _check_npm(package: str, current: str) -> dict:
    """Check a single npm package for updates via npm info."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "npm", "info", package, "version", "--json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        if proc.returncode != 0:
            return {"package": package, "current": current, "error": f"npm info exit {proc.returncode}"}

        raw = stdout.decode().strip()
        latest = json.loads(raw) if raw.startswith('"') else raw.strip('"')
        return {
            "package": package,
            "current": current,
            "latest": latest,
            "update_available": latest != current,
        }
    except asyncio.TimeoutError:
        return {"package": package, "current": current, "error": "timeout"}
    except Exception as e:
        return {"package": package, "current": current, "error": str(e)}


# ---------------------------------------------------------------------------
# git version checks
# ---------------------------------------------------------------------------
async def _check_git(repo: dict) -> dict:
    """Compare local HEAD against remote HEAD via git ls-remote."""
    name = repo["name"]
    path = os.path.expanduser(repo["path"])
    remote = repo["remote"]
    branch = repo["branch"]

    if not Path(path).is_dir():
        return {"repo": name, "error": f"directory not found: {path}"}

    try:
        proc = await asyncio.create_subprocess_exec(
            "git", "-C", path, "rev-parse", "--short", "HEAD",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
        if proc.returncode != 0:
            return {"repo": name, "error": "git rev-parse failed"}
        local_commit = stdout.decode().strip()

        proc = await asyncio.create_subprocess_exec(
            "git", "-C", path, "ls-remote", "--heads", remote, branch,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        if proc.returncode != 0:
            return {"repo": name, "local_commit": local_commit, "error": "git ls-remote failed"}

        line = stdout.decode().strip()
        if not line:
            return {"repo": name, "local_commit": local_commit, "error": f"branch {branch} not found on {remote}"}

        remote_full = line.split()[0]
        remote_commit = remote_full[:len(local_commit)]

        return {
            "repo": name,
            "local_commit": local_commit,
            "remote_commit": remote_commit,
            "update_available": not remote_full.startswith(local_commit),
        }
    except asyncio.TimeoutError:
        return {"repo": name, "error": "timeout"}
    except Exception as e:
        return {"repo": name, "error": str(e)}


# ---------------------------------------------------------------------------
# npm audit (advisories)
# ---------------------------------------------------------------------------
def _find_npx_dirs_for_package(package: str) -> list[Path]:
    """Find npx cache directories containing a given package."""
    dirs = []
    if not NPX_CACHE.is_dir():
        return dirs
    for cache_dir in NPX_CACHE.iterdir():
        if not cache_dir.is_dir():
            continue
        lock = cache_dir / "node_modules" / ".package-lock.json"
        if not lock.is_file():
            continue
        try:
            data = json.loads(lock.read_text())
            packages = data.get("packages", {})
            if f"node_modules/{package}" in packages:
                dirs.append(cache_dir)
        except (json.JSONDecodeError, OSError):
            continue
    return dirs


async def _audit_dir(cache_dir: Path) -> list[dict]:
    """Run npm audit --json in a cache directory, return advisory list."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "npm", "audit", "--json",
            cwd=str(cache_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
        raw = stdout.decode().strip()
        if not raw:
            return []

        data = json.loads(raw)
        advisories = []
        vulns = data.get("vulnerabilities", {})
        for dep_name, info in vulns.items():
            via = info.get("via", [])
            for v in via:
                if isinstance(v, dict):
                    advisories.append({
                        "dependency": dep_name,
                        "severity": v.get("severity", "unknown"),
                        "title": v.get("title", ""),
                        "url": v.get("url", ""),
                    })
        return advisories
    except (asyncio.TimeoutError, json.JSONDecodeError, Exception):
        return []


async def _check_advisories(npm_packages: dict) -> list[dict]:
    """Scan npx cache for advisories across all tracked packages."""
    seen_dirs: set[Path] = set()
    for package in npm_packages:
        for d in _find_npx_dirs_for_package(package):
            seen_dirs.add(d)

    if not seen_dirs:
        return []

    tasks = [_audit_dir(d) for d in seen_dirs]
    results = await asyncio.gather(*tasks)

    seen: set[tuple[str, str]] = set()
    advisories = []
    for batch in results:
        for adv in batch:
            key = (adv.get("title", ""), adv.get("url", ""))
            if key not in seen:
                seen.add(key)
                advisories.append(adv)

    return advisories


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def async_main(config: dict):
    """Run all checks concurrently and output JSON."""
    npm_packages = config.get("npm_packages", {})
    git_repos = config.get("git_repos", [])

    npm_tasks = [_check_npm(pkg, ver) for pkg, ver in npm_packages.items()]
    git_tasks = [_check_git(repo) for repo in git_repos]
    advisory_task = _check_advisories(npm_packages)

    npm_results, git_results, advisories = await asyncio.gather(
        asyncio.gather(*npm_tasks),
        asyncio.gather(*git_tasks),
        advisory_task,
    )

    npm_updates = list(npm_results)
    git_updates = list(git_results)

    npm_update_count = sum(1 for r in npm_updates if r.get("update_available"))
    git_update_count = sum(1 for r in git_updates if r.get("update_available"))
    adv_count = len(advisories)

    output = {
        "npm_updates": npm_updates,
        "git_updates": git_updates,
        "advisories": advisories,
        "summary": (
            f"{npm_update_count} npm update{'s' if npm_update_count != 1 else ''}, "
            f"{git_update_count} git update{'s' if git_update_count != 1 else ''}, "
            f"{adv_count} advisor{'ies' if adv_count != 1 else 'y'}"
        ),
    }

    print(json.dumps(output, indent=2))


def main():
    parser = argparse.ArgumentParser(description="MCP version checker")
    parser.add_argument(
        "--config", type=Path,
        default=Path(__file__).resolve().parent.parent / "config.json",
        help="Path to config.json",
    )
    args = parser.parse_args()
    config = load_config(args.config)
    asyncio.run(async_main(config))


if __name__ == "__main__":
    main()
