#!/usr/bin/env python3
"""
MCP promotion pipeline — security scan, smoke test, and version pinning.

Usage:
    mcp-promote.py check                            # Show available updates
    mcp-promote.py scan <package> <version>         # Security scan npm package
    mcp-promote.py scan-git <name>                  # Scan git repo changes
    mcp-promote.py test <server> [--version VER]    # MCP handshake smoke test
    mcp-promote.py promote <package> <version>      # Bump version pins
    mcp-promote.py promote-git <name>               # Git pull to update
"""

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

CLAUDE_JSON = Path.home() / ".claude.json"
MCP_VERSIONS = Path.home() / "scripts" / "mcp-versions.py"
MCP_STACK_SKILL = Path.home() / ".claude" / "skills" / "mcp-stack" / "SKILL.md"

# Package name → server name(s) in claude.json
PACKAGE_TO_SERVERS = {
    "slack-mcp-server": ["slack"],
    "mcp-remote": ["notion"],
    "mcp-fantastical": ["fantastical"],
    "@playwright/mcp": ["playwright"],
    "@piotr-agier/google-drive-mcp": ["gdrive-work", "gdrive-personal"],
    "codex-mcp-server": ["codex"],
}

GIT_REPOS = {
    "telegram-mcp": {
        "path": str(Path.home() / ".local/share/telegram-mcp"),
        "remote": "origin",
        "branch": "main",
        "servers": ["telegram"],
    },
    "discord-mcp": {
        "path": str(Path.home() / ".local/share/discord-mcp"),
        "remote": "fork",
        "branch": "master",
        "servers": ["discord"],
    },
}

# Patterns flagged in source code — focus on genuinely suspicious constructs
SOURCE_PATTERNS = [
    (r'\beval\s*\(', "eval() — dynamic code execution"),
    (r'\bnew\s+Function\s*\(', "new Function() — dynamic code execution"),
    (r'\bvm\.(run|createContext|Script)', "vm module — sandboxed code execution"),
    (r'child_process|\.execSync?\s*\(|\.spawnSync?\s*\(', "process spawn — shell access"),
    (r'fs\.(write|append|unlink|rm|rename|chmod|mkdir)', "fs mutation — file system writes"),
    (r'Buffer\.from\([^)]*["\']base64', "base64 decode — possible obfuscation"),
    (r'\\x[0-9a-fA-F]{2}(?:\\x[0-9a-fA-F]{2}){3,}', "hex escape chain — obfuscation"),
    (r'crypto\.create(?:Cipher|Decipher)', "crypto cipher — encryption"),
    (r'net\.(connect|createServer|Socket)', "net socket — network connection"),
    (r'dns\.(resolve|lookup)', "DNS lookup"),
    (r'WebSocket\s*\(', "WebSocket — persistent connection"),
]


def load_config() -> dict:
    return json.loads(CLAUDE_JSON.read_text())


def save_config(data: dict):
    CLAUDE_JSON.write_text(json.dumps(data, indent=2) + "\n")


# ---------------------------------------------------------------------------
# CHECK
# ---------------------------------------------------------------------------
def cmd_check():
    """Delegate to mcp-versions.py."""
    subprocess.run([sys.executable, str(MCP_VERSIONS)])


# ---------------------------------------------------------------------------
# SCAN NPM
# ---------------------------------------------------------------------------
def cmd_scan_npm(package: str, version: str) -> str:
    """Install npm package in temp dir and run security analysis."""
    with tempfile.TemporaryDirectory(prefix="mcp-scan-") as tmpdir:
        subprocess.run(["npm", "init", "-y"], cwd=tmpdir, capture_output=True)
        result = subprocess.run(
            ["npm", "install", f"{package}@{version}"],
            cwd=tmpdir, capture_output=True, text=True,
        )
        if result.returncode != 0:
            return json.dumps({"error": f"npm install failed: {result.stderr}"}, indent=2)

        # npm audit
        audit_result = subprocess.run(
            ["npm", "audit", "--json"],
            cwd=tmpdir, capture_output=True, text=True,
        )
        try:
            audit_data = json.loads(audit_result.stdout)
            vulns = audit_data.get("vulnerabilities", {})
            vulnerabilities = {
                k: {
                    "severity": v.get("severity"),
                    "via": [
                        x.get("title", str(x)) if isinstance(x, dict) else x
                        for x in v.get("via", [])
                    ],
                }
                for k, v in vulns.items()
            }
        except json.JSONDecodeError:
            vulnerabilities = {}

        # Source pattern scan
        pkg_dir = Path(tmpdir) / "node_modules" / package
        findings = _scan_source(pkg_dir) if pkg_dir.exists() else {}

        # Dependency count
        nm = Path(tmpdir) / "node_modules"
        dep_count = 0
        if nm.exists():
            for item in nm.iterdir():
                if not item.is_dir() or item.name.startswith("."):
                    continue
                if item.name.startswith("@"):
                    dep_count += sum(1 for sub in item.iterdir() if sub.is_dir())
                else:
                    dep_count += 1

        # Package size
        pkg_size = sum(
            f.stat().st_size for f in pkg_dir.rglob("*") if f.is_file()
        ) if pkg_dir.exists() else 0

        report = {
            "package": package,
            "version": version,
            "vulnerabilities": vulnerabilities,
            "vulnerability_count": len(vulnerabilities),
            "source_findings": findings,
            "finding_count": sum(f["count"] for f in findings.values()),
            "dependency_count": dep_count,
            "package_size_kb": round(pkg_size / 1024),
        }

    return json.dumps(report, indent=2)


def _scan_source(pkg_dir: Path) -> dict:
    """Scan source files for suspicious patterns."""
    findings = {}
    for pattern_re, label in SOURCE_PATTERNS:
        matches = []
        for f in pkg_dir.rglob("*"):
            if f.suffix not in (".js", ".ts", ".mjs", ".cjs"):
                continue
            if ".min." in f.name or f.name.endswith(".map"):
                continue
            try:
                for i, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
                    if re.search(pattern_re, line):
                        matches.append({
                            "file": str(f.relative_to(pkg_dir)),
                            "line": i,
                            "text": line.strip()[:150],
                        })
            except Exception:
                continue
        if matches:
            findings[label] = {"count": len(matches), "samples": matches[:5]}
    return findings


# ---------------------------------------------------------------------------
# SCAN GIT
# ---------------------------------------------------------------------------
def cmd_scan_git(name: str):
    """Fetch and diff git repo, scan changes for suspicious patterns."""
    repo = GIT_REPOS.get(name)
    if not repo:
        print(json.dumps({"error": f"Unknown repo: {name}. Known: {list(GIT_REPOS)}"}, indent=2))
        return

    path, remote, branch = repo["path"], repo["remote"], repo["branch"]

    subprocess.run(["git", "-C", path, "fetch", remote], capture_output=True)

    log = subprocess.run(
        ["git", "-C", path, "log", f"HEAD..{remote}/{branch}", "--oneline"],
        capture_output=True, text=True,
    ).stdout.strip()

    diff = subprocess.run(
        ["git", "-C", path, "diff", f"HEAD..{remote}/{branch}"],
        capture_output=True, text=True,
    ).stdout

    # Scan added lines only
    findings = {}
    for pattern_re, label in SOURCE_PATTERNS:
        matches = []
        for line in diff.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                if re.search(pattern_re, line):
                    matches.append(line[1:].strip()[:150])
        if matches:
            findings[label] = {"count": len(matches), "samples": matches[:5]}

    added = sum(1 for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++"))
    removed = sum(1 for l in diff.splitlines() if l.startswith("-") and not l.startswith("---"))

    report = {
        "repo": name,
        "commits": log,
        "lines_added": added,
        "lines_removed": removed,
        "source_findings": findings,
        "finding_count": sum(f["count"] for f in findings.values()),
    }

    print(json.dumps(report, indent=2))
    if diff:
        print("\n--- FULL DIFF ---")
        print(diff)


# ---------------------------------------------------------------------------
# TEST (MCP handshake smoke test)
# ---------------------------------------------------------------------------
def _resolve_npm_bin(package: str, version: str) -> tuple[str, str] | None:
    """Install npm package to tmpdir and return (executable, entrypoint_path).

    npx doesn't forward stdin to child processes, so we resolve the actual
    entrypoint and run it directly. Handles two cases:
    - Pure Node.js servers: returns (node, script.js)
    - Native binary wrappers (e.g. slack Go binary): returns (binary, "")
    """
    tmpdir = tempfile.mkdtemp(prefix="mcp-test-")
    subprocess.run(["npm", "init", "-y"], cwd=tmpdir, capture_output=True)
    result = subprocess.run(
        ["npm", "install", f"{package}@{version}"],
        cwd=tmpdir, capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None

    pkg_dir = Path(tmpdir) / "node_modules" / package
    pkg_json = pkg_dir / "package.json"
    if not pkg_json.exists():
        return None

    meta = json.loads(pkg_json.read_text())
    bin_entry = meta.get("bin", {})
    if isinstance(bin_entry, str):
        entry = bin_entry
    elif isinstance(bin_entry, dict):
        entry = next(iter(bin_entry.values()), meta.get("main", "index.js"))
    else:
        entry = meta.get("main", "index.js")

    entrypoint = pkg_dir / entry
    if not entrypoint.exists():
        return None

    # Check if the bin wrapper launches a native binary via execFileSync.
    # If so, resolve the native binary path and run it directly.
    try:
        wrapper_src = entrypoint.read_text(errors="replace")
        if "execFileSync" in wrapper_src:
            native = _find_native_binary(Path(tmpdir) / "node_modules")
            if native:
                return (str(native), "")
    except Exception:
        pass

    node = subprocess.run(
        ["which", "node"], capture_output=True, text=True,
    ).stdout.strip()
    return (node, str(entrypoint))


def _find_native_binary(node_modules: Path) -> Path | None:
    """Find a platform-specific native binary in node_modules."""
    import platform
    arch = "arm64" if platform.machine() == "arm64" else "amd64"
    plat = "darwin" if sys.platform == "darwin" else "linux"
    pattern = f"*-{plat}-{arch}"

    for d in node_modules.iterdir():
        if d.is_dir() and d.name.endswith(f"-{plat}-{arch}"):
            bin_dir = d / "bin"
            if bin_dir.exists():
                for f in bin_dir.iterdir():
                    if f.is_file() and os.access(f, os.X_OK):
                        return f
    return None


async def cmd_test(server_name: str, version: str | None = None) -> str:
    """Start MCP server and run protocol handshake + tools/list."""
    config = load_config()
    srv = config.get("mcpServers", {}).get(server_name)
    if not srv:
        return json.dumps({"error": f"Server '{server_name}' not found in claude.json"}, indent=2)

    command = srv["command"]
    args = list(srv.get("args", []))
    env_vars = srv.get("env", {})

    # npx and uv don't forward stdin to child processes, so we bypass them
    # and run the actual entrypoint directly.
    if command == "npx":
        pkg_name = None
        pkg_version = None
        extra_args = []
        for arg in args:
            if arg == "-y":
                continue
            elif "@" in arg and not pkg_name:
                parts = arg.rsplit("@", 1)
                pkg_name = parts[0]
                pkg_version = parts[1] if len(parts) > 1 else None
            else:
                extra_args.append(arg)

        if pkg_name:
            test_version = version or pkg_version or "latest"
            resolved = _resolve_npm_bin(pkg_name, test_version)
            if resolved:
                if resolved[1]:  # Node.js script
                    command = resolved[0]  # node
                    args = [resolved[1]] + extra_args
                else:  # Native binary
                    command = resolved[0]
                    args = extra_args
            else:
                return json.dumps({"error": f"Failed to resolve bin for {pkg_name}@{test_version}"}, indent=2)

    elif command.endswith("/uv") or os.path.basename(command) == "uv":
        # uv run: extract --directory and script, run with venv python directly
        project_dir = None
        script = None
        i = 0
        while i < len(args):
            if args[i] == "--directory" and i + 1 < len(args):
                project_dir = args[i + 1]
                i += 2
            elif args[i] == "run" and i + 1 < len(args):
                script = args[i + 1]
                i += 2
            else:
                i += 1

        if project_dir and script:
            venv_python = Path(project_dir) / ".venv" / "bin" / "python"
            script_path = Path(project_dir) / script
            if venv_python.exists() and script_path.exists():
                command = str(venv_python)
                args = [str(script_path)]
            else:
                return json.dumps({"error": f"venv or script not found in {project_dir}"}, indent=2)

    env = os.environ.copy()
    env.update(env_vars)

    proc = None
    try:
        proc = await asyncio.create_subprocess_exec(
            command, *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        init_resp = await _mcp_exchange(proc, {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "mcp-promote", "version": "0.1.0"},
            },
        }, timeout=30)

        # Initialized notification (no response expected)
        msg = json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"
        proc.stdin.write(msg.encode())
        await proc.stdin.drain()
        await asyncio.sleep(0.2)

        tools_resp = await _mcp_exchange(proc, {
            "jsonrpc": "2.0", "id": 2, "method": "tools/list",
        }, timeout=10)

        tools = tools_resp.get("result", {}).get("tools", [])
        report = {
            "server": server_name,
            "version": version or "current",
            "status": "PASS",
            "protocol_version": init_resp.get("result", {}).get("protocolVersion", "?"),
            "server_info": init_resp.get("result", {}).get("serverInfo", {}),
            "tool_count": len(tools),
            "tools": sorted(t.get("name", "?") for t in tools),
        }

    except asyncio.TimeoutError:
        report = {"server": server_name, "status": "FAIL", "error": "timeout during handshake"}
    except EOFError as e:
        stderr_out = ""
        if proc and proc.stderr:
            try:
                stderr_out = (await asyncio.wait_for(proc.stderr.read(4096), timeout=2)).decode(errors="replace")
            except Exception:
                pass
        report = {"server": server_name, "status": "FAIL", "error": str(e), "stderr": stderr_out}
    except Exception as e:
        report = {"server": server_name, "status": "FAIL", "error": str(e)}
    finally:
        if proc:
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass

    return json.dumps(report, indent=2)


async def _mcp_exchange(proc, message: dict, timeout: float = 15) -> dict:
    """Send JSON-RPC message and read response, skipping non-JSON lines."""
    msg = json.dumps(message) + "\n"
    proc.stdin.write(msg.encode())
    await proc.stdin.drain()

    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            raise asyncio.TimeoutError()
        line = await asyncio.wait_for(proc.stdout.readline(), timeout=remaining)
        if not line:
            raise EOFError("Server closed stdout")
        try:
            return json.loads(line.decode())
        except json.JSONDecodeError:
            continue  # Skip non-JSON output (log lines, etc.)


# ---------------------------------------------------------------------------
# PROMOTE NPM
# ---------------------------------------------------------------------------
def cmd_promote_npm(package: str, version: str) -> str:
    """Update version pins in claude.json, mcp-versions.py, and mcp-stack skill."""
    # 1. claude.json
    config = load_config()
    updated_servers = []
    for name, srv in config.get("mcpServers", {}).items():
        for i, arg in enumerate(srv.get("args", [])):
            if f"{package}@" in arg:
                srv["args"][i] = f"{package}@{version}"
                updated_servers.append(name)

    if not updated_servers:
        return json.dumps({"error": f"{package} not found in claude.json args"}, indent=2)

    save_config(config)

    # 2. mcp-versions.py
    content = MCP_VERSIONS.read_text()
    pattern = rf'("{re.escape(package)}":\s*")[^"]*(")'
    new_content = re.sub(pattern, rf"\g<1>{version}\2", content)
    MCP_VERSIONS.write_text(new_content)

    # 3. mcp-stack skill (version table)
    skill_updated = False
    if MCP_STACK_SKILL.exists():
        skill = MCP_STACK_SKILL.read_text()
        pkg_escaped = re.escape(package)
        skill_pattern = rf'(\|\s*{pkg_escaped}\s*\|[^|]*\|\s*)[^\s|]+(\s*\|)'
        new_skill = re.sub(skill_pattern, rf"\g<1>{version}\2", skill)
        if new_skill != skill:
            MCP_STACK_SKILL.write_text(new_skill)
            skill_updated = True

    return json.dumps({
        "package": package,
        "version": version,
        "updated_servers": updated_servers,
        "updated_files": [
            "~/.claude.json",
            "~/scripts/mcp-versions.py",
            *(["~/.claude/skills/mcp-stack/SKILL.md"] if skill_updated else []),
        ],
    }, indent=2)


# ---------------------------------------------------------------------------
# PROMOTE GIT
# ---------------------------------------------------------------------------
def cmd_promote_git(name: str) -> str:
    """Git pull to update repo."""
    repo = GIT_REPOS.get(name)
    if not repo:
        return json.dumps({"error": f"Unknown repo: {name}. Known: {list(GIT_REPOS)}"}, indent=2)

    path, remote, branch = repo["path"], repo["remote"], repo["branch"]

    result = subprocess.run(
        ["git", "-C", path, "pull", remote, branch],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return json.dumps({"error": f"git pull failed: {result.stderr}"}, indent=2)

    head = subprocess.run(
        ["git", "-C", path, "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True,
    ).stdout.strip()

    # Update mcp-stack skill commit hash
    skill_updated = False
    if MCP_STACK_SKILL.exists():
        skill = MCP_STACK_SKILL.read_text()
        name_escaped = re.escape(name)
        pattern = rf'(\|\s*{name_escaped}\s*\|\s*git\s*\|\s*HEAD\s*\()[^)]+(\))'
        new_skill = re.sub(pattern, rf"\g<1>{head}\2", skill)
        if new_skill != skill:
            MCP_STACK_SKILL.write_text(new_skill)
            skill_updated = True

    return json.dumps({
        "repo": name,
        "new_commit": head,
        "output": result.stdout.strip(),
        "updated_files": [*(["~/.claude/skills/mcp-stack/SKILL.md"] if skill_updated else [])],
    }, indent=2)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="MCP promotion pipeline")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("check", help="Show available updates")

    p = sub.add_parser("scan", help="Security scan an npm package version")
    p.add_argument("package")
    p.add_argument("version")

    p = sub.add_parser("scan-git", help="Scan git repo changes")
    p.add_argument("name")

    p = sub.add_parser("test", help="MCP handshake smoke test")
    p.add_argument("server", help="Server name from claude.json")
    p.add_argument("--version", help="Version to test (npm only)")

    p = sub.add_parser("promote", help="Bump npm package version")
    p.add_argument("package")
    p.add_argument("version")

    p = sub.add_parser("promote-git", help="Git pull to update repo")
    p.add_argument("name")

    args = parser.parse_args()

    if args.command == "check":
        cmd_check()
    elif args.command == "scan":
        print(cmd_scan_npm(args.package, args.version))
    elif args.command == "scan-git":
        cmd_scan_git(args.name)
    elif args.command == "test":
        print(asyncio.run(cmd_test(args.server, args.version)))
    elif args.command == "promote":
        print(cmd_promote_npm(args.package, args.version))
    elif args.command == "promote-git":
        print(cmd_promote_git(args.name))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
