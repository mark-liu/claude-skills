#!/usr/bin/env python3
"""
MCP version checker — compares locally cached npm package versions against
npm registry latest, and local git repo HEADs against remote. Reports
advisories from npm audit.

Outputs JSON to stdout. Can be called standalone or as a sub-script.

Requires: Python 3.11+ (stdlib only, no external deps)
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration — update versions here when upgrading packages
# ---------------------------------------------------------------------------
NPM_PACKAGES = {
    "slack-mcp-server": "1.2.3",
    "mcp-remote": "0.1.38",
    "mcp-fantastical": "1.1.0",
    "@playwright/mcp": "0.0.68",
    "@piotr-agier/google-drive-mcp": "1.7.3",
    "codex-mcp-server": "1.4.0",
}

GIT_REPOS = [
    {
        "name": "telegram-mcp",
        "path": os.path.expanduser("~/.local/share/telegram-mcp"),
        "remote": "origin",
        "branch": "main",
    },
    {
        "name": "discord-mcp",
        "path": os.path.expanduser("~/.local/share/discord-mcp"),
        "remote": "fork",
        "branch": "master",
    },
]

NPX_CACHE = Path.home() / ".npm" / "_npx"


# ---------------------------------------------------------------------------
# npm version checks
# ---------------------------------------------------------------------------
async def _check_npm(package: str, current: str) -> dict:
    """Check a single npm package for updates via `npm info`."""
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
    path = repo["path"]
    remote = repo["remote"]
    branch = repo["branch"]

    if not Path(path).is_dir():
        return {"repo": name, "error": f"directory not found: {path}"}

    try:
        # Local HEAD
        proc = await asyncio.create_subprocess_exec(
            "git", "-C", path, "rev-parse", "--short", "HEAD",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
        if proc.returncode != 0:
            return {"repo": name, "error": "git rev-parse failed"}
        local_commit = stdout.decode().strip()

        # Remote HEAD (read-only, no fetch)
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
            "update_available": not remote_full.startswith(local_commit.replace("", "")),
        }
    except asyncio.TimeoutError:
        return {"repo": name, "error": "timeout"}
    except Exception as e:
        return {"repo": name, "error": str(e)}


# ---------------------------------------------------------------------------
# npm audit (advisories)
# ---------------------------------------------------------------------------
def _find_npx_dir_for_package(package: str, pinned_version: str) -> Path | None:
    """Find the npx cache directory matching a package at its pinned version.

    Only returns the cache dir whose resolved version matches our pin,
    avoiding stale cache entries that inflate audit results.
    """
    if not NPX_CACHE.is_dir():
        return None
    for cache_dir in NPX_CACHE.iterdir():
        if not cache_dir.is_dir():
            continue
        lock = cache_dir / "node_modules" / ".package-lock.json"
        if not lock.is_file():
            continue
        try:
            data = json.loads(lock.read_text())
            packages = data.get("packages", {})
            pkg_key = f"node_modules/{package}"
            if pkg_key in packages and packages[pkg_key].get("version") == pinned_version:
                return cache_dir
        except (json.JSONDecodeError, OSError):
            continue
    return None


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
        # npm audit exits non-zero when advisories exist, that's expected
        raw = stdout.decode().strip()
        if not raw:
            return []

        data = json.loads(raw)
        advisories = []
        # npm audit v2+ format: vulnerabilities dict
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


async def _check_advisories() -> list[dict]:
    """Scan npx cache for advisories across all tracked packages.

    Only audits cache dirs matching our pinned versions — stale cache
    entries from previous installs are ignored.
    """
    audit_targets: list[tuple[str, Path]] = []
    for package, version in NPM_PACKAGES.items():
        cache_dir = _find_npx_dir_for_package(package, version)
        if cache_dir:
            audit_targets.append((package, cache_dir))

    if not audit_targets:
        return []

    # Deduplicate dirs (multiple packages may share one cache dir)
    seen_dirs: dict[Path, list[str]] = {}
    for package, cache_dir in audit_targets:
        seen_dirs.setdefault(cache_dir, []).append(package)

    tasks = [_audit_dir(d) for d in seen_dirs]
    results = await asyncio.gather(*tasks)

    # Deduplicate by (title, url) and tag with parent MCP server
    seen: set[tuple[str, str]] = set()
    advisories = []
    for (cache_dir, packages), batch in zip(seen_dirs.items(), results):
        for adv in batch:
            key = (adv.get("title", ""), adv.get("url", ""))
            if key not in seen:
                seen.add(key)
                adv["mcp_server"] = packages[0]
                advisories.append(adv)

    return advisories


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def async_main():
    """Run all checks concurrently and output JSON."""
    npm_tasks = [_check_npm(pkg, ver) for pkg, ver in NPM_PACKAGES.items()]
    git_tasks = [_check_git(repo) for repo in GIT_REPOS]
    advisory_task = _check_advisories()

    npm_results, git_results, advisories = await asyncio.gather(
        asyncio.gather(*npm_tasks),
        asyncio.gather(*git_tasks),
        advisory_task,
    )

    npm_updates = list(npm_results)
    git_updates = list(git_results)

    # Summary line
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
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
