#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

REMOTE_HOST="${AI_LAB_HOST:-ai-lab}"
REMOTE_USER="${AI_LAB_USER:-jaydreyer}"
REMOTE_SSH_KEY="${AI_LAB_SSH_KEY:-}"
REMOTE_OPENCLAW_ROOT="${OPENCLAW_ROOT:-/home/jaydreyer/.openclaw}"
TARGET_RELATIVE_PATH="${OPENCLAW_TARGET_RELATIVE_PATH:-workspace/mission-control}"
MIN_AGE_MINUTES="${OPENCLAW_MIN_AGE_MINUTES:-120}"
GRACE_SECONDS="${OPENCLAW_TERM_GRACE_SECONDS:-5}"
KILL_STALE="false"
HARD_KILL="false"
FAIL_ON_FINDINGS="true"
OUTPUT_JSON=""

usage() {
  cat <<'EOF'
Usage:
  run_openclaw_devserver_check.sh [options]

Checks ai-lab for stale OpenClaw Next.js development servers, reports memory/age/port
details, and can optionally terminate stale processes after a safety check.

Stale means:
  - process path matches the configured OpenClaw target workspace
  - process is a Next.js dev server (`next dev` / `next-server`)
  - process age is at least the configured threshold
  - process has no established TCP connections to its listening ports

Options:
  --remote-host <host>            ai-lab host/address (default: ai-lab)
  --remote-user <user>            ai-lab SSH user (default: jaydreyer)
  --ssh-key <path>                Optional SSH private key path
  --openclaw-root <path>          Remote OpenClaw root (default: /home/jaydreyer/.openclaw)
  --target-relative-path <path>   Path under OpenClaw root to inspect (default: workspace/mission-control)
  --min-age-minutes <int>         Minimum process age before it can be considered stale (default: 120)
  --kill-stale                    Send SIGTERM to stale processes
  --hard-kill                     After SIGTERM grace window, send SIGKILL if still alive
  --grace-seconds <int>           Wait after SIGTERM before re-checking (default: 5)
  --no-fail                       Always exit 0 (report findings without failing)
  --output-json <path>            Write machine-readable report JSON
  --help                          Show this help

Examples:
  run_openclaw_devserver_check.sh
  run_openclaw_devserver_check.sh --kill-stale
  run_openclaw_devserver_check.sh --kill-stale --hard-kill --ssh-key ~/.ssh/codex_ai_lab
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --remote-host)
      REMOTE_HOST="${2:-}"
      shift 2
      ;;
    --remote-user)
      REMOTE_USER="${2:-}"
      shift 2
      ;;
    --ssh-key)
      REMOTE_SSH_KEY="${2:-}"
      shift 2
      ;;
    --openclaw-root)
      REMOTE_OPENCLAW_ROOT="${2:-}"
      shift 2
      ;;
    --target-relative-path)
      TARGET_RELATIVE_PATH="${2:-}"
      shift 2
      ;;
    --min-age-minutes)
      MIN_AGE_MINUTES="${2:-}"
      shift 2
      ;;
    --kill-stale)
      KILL_STALE="true"
      shift 1
      ;;
    --hard-kill)
      HARD_KILL="true"
      shift 1
      ;;
    --grace-seconds)
      GRACE_SECONDS="${2:-}"
      shift 2
      ;;
    --no-fail)
      FAIL_ON_FINDINGS="false"
      shift 1
      ;;
    --output-json)
      OUTPUT_JSON="${2:-}"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if ! [[ "$MIN_AGE_MINUTES" =~ ^[0-9]+$ ]]; then
  echo "--min-age-minutes must be an integer" >&2
  exit 2
fi

if ! [[ "$GRACE_SECONDS" =~ ^[0-9]+$ ]]; then
  echo "--grace-seconds must be an integer" >&2
  exit 2
fi

if [[ -z "$OUTPUT_JSON" ]]; then
  STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
  OUTPUT_JSON="$ROOT_DIR/data/artifacts/phase4/openclaw/${STAMP}_openclaw_devserver_check.json"
fi

mkdir -p "$(dirname "$OUTPUT_JSON")"

SSH_CMD=(ssh -o BatchMode=yes -o ConnectTimeout=10)
if [[ -n "$REMOTE_SSH_KEY" ]]; then
  SSH_CMD+=(-i "$REMOTE_SSH_KEY")
fi

remote_result="$(
  "${SSH_CMD[@]}" "$REMOTE_USER@$REMOTE_HOST" \
    "python3 - '$REMOTE_OPENCLAW_ROOT' '$TARGET_RELATIVE_PATH' '$MIN_AGE_MINUTES' '$KILL_STALE' '$HARD_KILL' '$GRACE_SECONDS'" <<'PY'
import json
import os
import pathlib
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone


openclaw_root = pathlib.Path(sys.argv[1]).resolve()
target_relative_path = pathlib.Path(sys.argv[2])
min_age_minutes = int(sys.argv[3])
kill_stale = sys.argv[4].lower() == "true"
hard_kill = sys.argv[5].lower() == "true"
grace_seconds = int(sys.argv[6])
target_path = (openclaw_root / target_relative_path).resolve()


def read_text(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def parse_ports(output: str) -> dict[int, list[int]]:
    ports_by_pid: dict[int, set[int]] = {}
    for line in output.splitlines():
        match_pid = re.search(r"pid=(\d+)", line)
        if not match_pid:
            continue
        pid = int(match_pid.group(1))
        cols = line.split()
        if len(cols) < 4:
            continue
        local_address = cols[3]
        port_text = local_address.rsplit(":", 1)[-1]
        try:
            port = int(port_text)
        except ValueError:
            continue
        ports_by_pid.setdefault(pid, set()).add(port)
    return {pid: sorted(ports) for pid, ports in ports_by_pid.items()}


def parse_established(output: str) -> dict[int, int]:
    counts: dict[int, int] = {}
    for line in output.splitlines():
        if "ESTAB" not in line:
            continue
        cols = line.split()
        if len(cols) < 5:
            continue
        local_address = cols[3]
        port_text = local_address.rsplit(":", 1)[-1]
        try:
            port = int(port_text)
        except ValueError:
            continue
        counts[port] = counts.get(port, 0) + 1
    return counts


def run_command(args: list[str]) -> str:
    try:
        return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return ""


listening_ports_by_pid = parse_ports(run_command(["ss", "-ltnp"]))
established_by_port = parse_established(run_command(["ss", "-tnp", "state", "established"]))

report = {
    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "host": os.uname().nodename,
    "openclaw_root": str(openclaw_root),
    "target_path": str(target_path),
    "min_age_minutes": min_age_minutes,
    "kill_requested": kill_stale,
    "hard_kill_requested": hard_kill,
    "processes": [],
    "stale_processes": [],
    "actions": [],
    "status": "ok",
}


for proc_dir in pathlib.Path("/proc").iterdir():
    if not proc_dir.name.isdigit():
        continue
    pid = int(proc_dir.name)
    cwd_link = proc_dir / "cwd"
    try:
        cwd = pathlib.Path(os.readlink(cwd_link)).resolve()
    except Exception:
        cwd = None

    cmdline_raw = read_text(proc_dir / "cmdline").replace("\x00", " ").strip()
    environ_raw = read_text(proc_dir / "environ").replace("\x00", "\n")
    status_raw = read_text(proc_dir / "status")
    stat_raw = read_text(proc_dir / "stat")

    if not cmdline_raw:
        continue

    is_next_dev = (
        "next-server" in cmdline_raw
        or "next dev" in cmdline_raw
        or "npm_lifecycle_event=dev" in environ_raw
        or "npm_lifecycle_script=next dev" in environ_raw
    )
    if not is_next_dev:
        continue

    pwd_value = ""
    for line in environ_raw.splitlines():
        if line.startswith("PWD="):
            pwd_value = line.split("=", 1)[1].strip()
            break

    path_markers = [cmdline_raw, pwd_value]
    if cwd is not None:
        path_markers.append(str(cwd))

    if not any(str(target_path) in marker for marker in path_markers if marker):
        continue

    stat_fields = stat_raw.split()
    start_time_ticks = int(stat_fields[21]) if len(stat_fields) > 21 else 0
    clk_tck = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
    uptime_seconds = float(read_text(pathlib.Path("/proc/uptime")).split()[0])
    elapsed_seconds = max(0, int(uptime_seconds - (start_time_ticks / clk_tck)))
    age_minutes = elapsed_seconds // 60

    rss_kib = 0
    thread_count = 0
    state = ""
    for line in status_raw.splitlines():
        if line.startswith("VmRSS:"):
            parts = line.split()
            if len(parts) >= 2:
                rss_kib = int(parts[1])
        elif line.startswith("Threads:"):
            parts = line.split()
            if len(parts) >= 2:
                thread_count = int(parts[1])
        elif line.startswith("State:"):
            state = line.split(":", 1)[1].strip()

    listening_ports = listening_ports_by_pid.get(pid, [])
    established_connections = sum(established_by_port.get(port, 0) for port in listening_ports)
    stale = age_minutes >= min_age_minutes and established_connections == 0

    process_info = {
        "pid": pid,
        "cwd": str(cwd) if cwd is not None else "",
        "pwd": pwd_value,
        "cmdline": cmdline_raw,
        "state": state,
        "age_minutes": age_minutes,
        "rss_mib": round(rss_kib / 1024, 1),
        "thread_count": thread_count,
        "listening_ports": listening_ports,
        "established_connections": established_connections,
        "stale": stale,
    }
    report["processes"].append(process_info)
    if stale:
        report["stale_processes"].append(pid)


if kill_stale:
    for pid in list(report["stale_processes"]):
        action = {"pid": pid, "signal": "TERM", "result": "skipped"}
        try:
            os.kill(pid, signal.SIGTERM)
            action["result"] = "sent"
        except ProcessLookupError:
            action["result"] = "missing"
        except PermissionError:
            action["result"] = "permission_denied"
        report["actions"].append(action)

    if grace_seconds > 0 and report["stale_processes"]:
        time.sleep(grace_seconds)

    for pid in list(report["stale_processes"]):
        alive = pathlib.Path(f"/proc/{pid}").exists()
        if alive and hard_kill:
            action = {"pid": pid, "signal": "KILL", "result": "skipped"}
            try:
                os.kill(pid, signal.SIGKILL)
                action["result"] = "sent"
            except ProcessLookupError:
                action["result"] = "missing"
            except PermissionError:
                action["result"] = "permission_denied"
            report["actions"].append(action)
            if action["result"] == "sent":
                time.sleep(0.2)
                alive = pathlib.Path(f"/proc/{pid}").exists()

        for process_info in report["processes"]:
            if process_info["pid"] == pid:
                process_info["alive_after_action"] = alive
                break


if report["stale_processes"]:
    report["status"] = "stale_found"
if kill_stale and report["stale_processes"]:
    still_alive = any(item.get("alive_after_action") for item in report["processes"] if item["pid"] in report["stale_processes"])
    report["status"] = "stale_remaining" if still_alive else "cleaned"

print(json.dumps(report))
PY
)"

printf '%s\n' "$remote_result" >"$OUTPUT_JSON"

python3 - "$OUTPUT_JSON" "$REMOTE_HOST" "$REMOTE_USER" "$FAIL_ON_FINDINGS" <<'PY'
import json
import pathlib
import sys


report_path = pathlib.Path(sys.argv[1])
remote_host = sys.argv[2]
remote_user = sys.argv[3]
fail_on_findings = sys.argv[4].lower() == "true"

report = json.loads(report_path.read_text(encoding="utf-8"))
processes = report.get("processes", [])
stale_pids = report.get("stale_processes", [])

print(f"OpenClaw dev server report: {report_path}")
print(f"Remote target: {remote_user}@{remote_host}:{report.get('target_path')}")

if not processes:
    print("No matching OpenClaw Next.js dev servers found.")
    sys.exit(0)

print("Matching processes:")
for process in processes:
    ports = ",".join(str(port) for port in process.get("listening_ports", [])) or "-"
    line = (
        f"  - pid={process['pid']} stale={str(process['stale']).lower()} "
        f"age_min={process['age_minutes']} rss_mib={process['rss_mib']} "
        f"ports={ports} established={process['established_connections']} "
        f"state={process['state']}"
    )
    print(line)

for action in report.get("actions", []):
    print(f"Action: pid={action['pid']} signal={action['signal']} result={action['result']}")

if not stale_pids:
    print("No stale OpenClaw dev servers detected.")
    sys.exit(0)

print(f"Stale OpenClaw dev servers: {', '.join(str(pid) for pid in stale_pids)}")

status = report.get("status")
if status == "cleaned":
    print("Stale processes were terminated successfully.")
    sys.exit(0)

if fail_on_findings:
    sys.exit(1)

sys.exit(0)
PY
