#!/usr/bin/env python3
"""MCP promotion pipeline — security scan, smoke test, and version pinning.

Usage:
    mcp-promote.py --config config.json check
    mcp-promote.py --config config.json scan <package> <version>
    mcp-promote.py --config config.json scan-git <name>
    mcp-promote.py --config config.json test <server> [--version VER]
    mcp-promote.py --config config.json promote <package> <version>
    mcp-promote.py --config config.json promote-git <name>
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

# Built-in source scan patterns
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


def load_plugin_config(config_path: Path) -> dict:
    """Load plugin configuration."""
    if not config_path.exists():
        print(f"ERROR: config file not found: {config_path}", file=sys.stderr)
        print("Copy config.example.json to config.json and edit.", file=sys.stderr)
        sys.exit(1)
    return json.loads(config_path.read_text())


def load_claude_config(config: dict) -> dict:
    """Load claude.json from path in config."""
    path = Path(os.path.expanduser(config.get("claude_json_path", "~/.claude.json")))
    return json.loads(path.read_text())


def save_claude_config(config: dict, data: dict):
    """Save claude.json."""
    path = Path(os.path.expanduser(config.get("claude_json_path", "~/.claude.json")))
    path.write_text(json.dumps(data, indent=2) + "\n")


def get_scan_patterns(config: dict) -> list[tuple[str, str]]:
    """Get scan patterns including any extras from config."""
    patterns = list(SOURCE_PATTERNS)
    for extra in config.get("extra_scan_patterns", []):
        if isinstance(extra, list) and len(extra) == 2:
            patterns.append((extra[0], extra[1]))
    return patterns


# ---------------------------------------------------------------------------
# CHECK
# ---------------------------------------------------------------------------
def cmd_check(config: dict):
    """Delegate to mcp-versions.py."""
    versions_script = Path(__file__).resolve().parent / "mcp-versions.py"
    config_path = Path(__file__).resolve().parent.parent / "config.json"
    subprocess.run([sys.executable, str(versions_script), "--config", str(config_path)])


# ---------------------------------------------------------------------------
# SCAN NPM
# ---------------------------------------------------------------------------
def cmd_scan_npm(config: dict, package: str, version: str) -> str:
    """Install npm package in temp dir and run security analysis."""
    patterns = get_scan_patterns(config)

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
        findings = _scan_source(pkg_dir, patterns) if pkg_dir.exists() else {}

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


def _scan_source(pkg_dir: Path, patterns: list[tuple[str, str]]) -> dict:
    """Scan source files for suspicious patterns."""
    findings = {}
    for pattern_re, label in patterns:
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
def cmd_scan_git(config: dict, name: str):
    """Fetch and diff git repo, scan changes for suspicious patterns."""
    git_repos = {r["name"]: r for r in config.get("git_repos", [])}
    repo = git_repos.get(name)
    if not repo:
        print(json.dumps({"error": f"Unknown repo: {name}. Known: {list(git_repos)}"}, indent=2))
        return

    path = os.path.expanduser(repo["path"])
    remote, branch = repo["remote"], repo["branch"]
    patterns = get_scan_patterns(config)

    subprocess.run(["git", "-C", path, "fetch", remote], capture_output=True)

    log = subprocess.run(
        ["git", "-C", path, "log", f"HEAD..{remote}/{branch}", "--oneline"],
        capture_output=True, text=True,
    ).stdout.strip()

    diff = subprocess.run(
        ["git", "-C", path, "diff", f"HEAD..{remote}/{branch}"],
        capture_output=True, text=True,
    ).stdout

    findings = {}
    for pattern_re, label in patterns:
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
    """Install npm package to tmpdir and return (executable, entrypoint_path)."""
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

    # Check if the bin wrapper launches a native binary
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

    for d in node_modules.iterdir():
        if d.is_dir() and d.name.endswith(f"-{plat}-{arch}"):
            bin_dir = d / "bin"
            if bin_dir.exists():
                for f in bin_dir.iterdir():
                    if f.is_file() and os.access(f, os.X_OK):
                        return f
    return None


async def cmd_test(config: dict, server_name: str, version: str | None = None) -> str:
    """Start MCP server and run protocol handshake + tools/list."""
    claude_cfg = load_claude_config(config)
    srv = claude_cfg.get("mcpServers", {}).get(server_name)
    if not srv:
        return json.dumps({"error": f"Server '{server_name}' not found in claude.json"}, indent=2)

    command = srv["command"]
    args = list(srv.get("args", []))
    env_vars = srv.get("env", {})

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
                if resolved[1]:
                    command = resolved[0]
                    args = [resolved[1]] + extra_args
                else:
                    command = resolved[0]
                    args = extra_args
            else:
                return json.dumps({"error": f"Failed to resolve bin for {pkg_name}@{test_version}"}, indent=2)

    elif command.endswith("/uv") or os.path.basename(command) == "uv":
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
            continue


# ---------------------------------------------------------------------------
# PROMOTE NPM
# ---------------------------------------------------------------------------
def cmd_promote_npm(config: dict, package: str, version: str) -> str:
    """Update version pins in claude.json and tracking files."""
    # 1. claude.json
    claude_cfg = load_claude_config(config)
    updated_servers = []
    for name, srv in claude_cfg.get("mcpServers", {}).items():
        for i, arg in enumerate(srv.get("args", [])):
            if f"{package}@" in arg:
                srv["args"][i] = f"{package}@{version}"
                updated_servers.append(name)

    if not updated_servers:
        return json.dumps({"error": f"{package} not found in claude.json args"}, indent=2)

    save_claude_config(config, claude_cfg)

    # 2. Version tracking files
    updated_files = [config.get("claude_json_path", "~/.claude.json")]
    for tracking_file in config.get("version_tracking_files", []):
        path = Path(os.path.expanduser(tracking_file))
        if path.exists():
            content = path.read_text()
            pattern = rf'("{re.escape(package)}":\s*")[^"]*(")'
            new_content = re.sub(pattern, rf"\g<1>{version}\2", content)
            if new_content != content:
                path.write_text(new_content)
                updated_files.append(tracking_file)

    return json.dumps({
        "package": package,
        "version": version,
        "updated_servers": updated_servers,
        "updated_files": updated_files,
    }, indent=2)


# ---------------------------------------------------------------------------
# PROMOTE GIT
# ---------------------------------------------------------------------------
def cmd_promote_git(config: dict, name: str) -> str:
    """Git pull to update repo."""
    git_repos = {r["name"]: r for r in config.get("git_repos", [])}
    repo = git_repos.get(name)
    if not repo:
        return json.dumps({"error": f"Unknown repo: {name}. Known: {list(git_repos)}"}, indent=2)

    path = os.path.expanduser(repo["path"])
    remote, branch = repo["remote"], repo["branch"]

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

    return json.dumps({
        "repo": name,
        "new_commit": head,
        "output": result.stdout.strip(),
    }, indent=2)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="MCP promotion pipeline")
    parser.add_argument(
        "--config", type=Path,
        default=Path(__file__).resolve().parent.parent / "config.json",
        help="Path to config.json",
    )
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
    config = load_plugin_config(args.config)

    if args.command == "check":
        cmd_check(config)
    elif args.command == "scan":
        print(cmd_scan_npm(config, args.package, args.version))
    elif args.command == "scan-git":
        cmd_scan_git(config, args.name)
    elif args.command == "test":
        print(asyncio.run(cmd_test(config, args.server, args.version)))
    elif args.command == "promote":
        print(cmd_promote_npm(config, args.package, args.version))
    elif args.command == "promote-git":
        print(cmd_promote_git(config, args.name))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
