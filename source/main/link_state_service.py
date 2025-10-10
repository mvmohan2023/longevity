#!/usr/bin/env python3
"""
link_state_service.py

gNMI link-state monitor using gnmic with:
- per-run unique log files (run_id)
- local service (LinkStateMonitor)
- remote SSH control (RemoteMonitorManager) with singleton-per-target enforcement
- multi-target orchestration (RemoteMultiMonitor)
- periodic per-target health reporter (PeriodicHealthReporter) with optional stop_all()
- minimal CLI for local foreground runs: start/tail/check
- duplicate event suppression (dedupe) with TTL

Python 3.8+
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import shlex
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional, Pattern, Tuple, Any

# -------------------------
# Optional Paramiko
# -------------------------
try:
    import paramiko  # type: ignore
except Exception:
    paramiko = None

# -------------------------
# Run ID / filenames
# -------------------------
def _new_run_id() -> str:
    # Example: 2025-09-15_15-45-10_12345
    return datetime.now().strftime("%Y%m%d_%H-%M-%S") + f"_{os.getpid()}"

DEFAULT_RUN_ID = os.environ.get("LINKMON_RUN_ID") or _new_run_id()

def _slugify(addr: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", addr).strip("_")

# -------------------------
# Constants / regex
# -------------------------
DOWN_STATES = {"DOWN", "LOWER_LAYER_DOWN", "DORMANT", "NOT_PRESENT", "UNKNOWN", "TESTING"}

# 2025-09-15T13:50:43 | LINK-STATE | iface=et-0/0/10:0 state=DOWN (prev=None)
LOG_LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}) \| LINK-STATE \| iface=(?P<iface>[^ ]+) state=(?P<state>[A-Z_]+) \(prev=(?P<prev>[^)]*)\)$"
)

# -------------------------
# Utilities
# -------------------------
def _coerce(v: Any) -> Any:
    if isinstance(v, dict):
        for k in (
            "stringVal", "jsonIetfVal", "jsonVal", "boolVal", "intVal", "uintVal",
            "floatVal", "asciiVal", "bytesVal",
            "string_val", "json_ietf_val", "json_val", "bool_val", "int_val",
            "uint_val", "float_val", "ascii_val", "bytes_val"
        ):
            if k in v:
                return v[k]
    return v

def _parse_event_obj(obj: dict, out_format: str) -> Optional[Tuple[str, str, str]]:
    """
    Parse a gnmic output object → (iface, oper, ts_iso) or None.
    Supports --format event and --format json.
    """
    if obj.get("sync-response") or obj.get("sync_response"):
        return None

    ts = obj.get("timestamp")
    iso_ts = (
        datetime.fromtimestamp(ts / 1e9).isoformat(timespec="seconds")
        if isinstance(ts, int) and ts > 0
        else datetime.now().isoformat(timespec="seconds")
    )

    if out_format == "event":
        values = obj.get("values") or {}
        for k, v in values.items():
            if k.endswith("oper-status"):
                oper = str(v).upper()
                tags = obj.get("tags") or {}
                iface = tags.get("name")
                if not iface:
                    m = re.search(r"\[name=([^]]+)\]", k or "")
                    iface = m.group(1) if m else "unknown"
                return iface, oper, iso_ts
        return None

    # out_format == "json"
    prefix = obj.get("prefix") or ""
    for up in obj.get("updates") or []:
        path = up.get("path") or up.get("Path") or ""
        values_map = up.get("values") or {}
        oper = None
        for k, v in values_map.items():
            if k.endswith("oper-status"):
                oper = str(v).upper()
                break
        if oper is None:
            for key in ("value", "val"):
                if key in up and up[key] is not None:
                    oper = str(_coerce(up[key])).upper()
                    break
        if not oper:
            continue
        m = re.search(r"\[name=([^]]+)\]", prefix or path or "")
        iface = m.group(1) if m else "unknown"
        return iface, oper, iso_ts

    return None

def _parse_since(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    m = re.match(r"^(\d+)\s*([smhd])$", s.strip(), re.IGNORECASE)
    if m:
        n = int(m.group(1))
        unit = m.group(2).lower()
        delta = {"s": timedelta(seconds=n), "m": timedelta(minutes=n), "h": timedelta(hours=n), "d": timedelta(days=n)}[unit]
        return datetime.now() - delta
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None

def tail_log_file(log_file: str, n: int = 50) -> List[str]:
    if not os.path.isfile(log_file):
        return []
    avg_len = 140
    to_read = n * avg_len
    with open(log_file, "rb") as f:
        try:
            f.seek(-to_read, os.SEEK_END)
        except OSError:
            f.seek(0)
        data = f.read().decode("utf-8", errors="ignore")
    return data.strip().splitlines()[-n:]

def _get_events_from_log(
    log_file: str,
    since: Optional[str],
    iface_regex: Optional[str],
    states: Optional[List[str]],
    limit: Optional[int],
) -> List[Dict[str, str]]:
    cutoff = _parse_since(since) if since else None
    if_re = re.compile(iface_regex) if iface_regex else None
    states_u = set(s.upper() for s in states) if states else None
    out: List[Dict[str, str]] = []
    if not os.path.isfile(log_file):
        return out
    with open(log_file, "r", encoding="utf-8") as fh:
        for line in fh:
            m = LOG_LINE_RE.match(line.strip())
            if not m:
                continue
            ts = datetime.fromisoformat(m.group("ts"))
            if cutoff and ts < cutoff:
                continue
            iface = m.group("iface")
            state = m.group("state").upper()
            if if_re and not if_re.search(iface):
                continue
            if states_u and state not in states_u:
                continue
            out.append({
                "timestamp": m.group("ts"),
                "iface": iface,
                "state": state,
                "prev": m.group("prev"),
            })
    if limit:
        out = out[-limit:]
    return out

def check_log_for_updates_file(
    log_file: str,
    since: Optional[str] = "5m",
    iface_regex: Optional[str] = None,
    count_only: bool = True,
) -> Dict[str, object]:
    events = _get_events_from_log(log_file, since, iface_regex, None, None)
    return {
        "since": since,
        "updates": len(events) > 0,
        "count": len(events),
        "sample": events[-5:] if not count_only else None,
    }

# -------------------------
# Data model
# -------------------------
@dataclass
class MonitorConfig:
    address: str
    username: str
    password: str
    path: str = "/interfaces/interface[name=*]/state/oper-status"
    insecure: bool = True
    origin: Optional[str] = None
    out_format: str = "json"         # "json" or "event"
    updates_only: bool = True
    alert_any: bool = False
    debug: bool = False
    log_file: str = "./link_state_monitor.log"
    restart: bool = True
    if_filter: Optional[str] = None  # regex
    on_event: Optional[Callable[[str, str, str, Optional[str]], None]] = None
    # ---- dedupe controls ----
    dedupe_enabled: bool = True
    dedupe_ttl_sec: int = 600  # 10 minutes

# -------------------------
# Local monitor (gnmic runner)
# -------------------------
class LinkStateMonitor:
    def __init__(
        self,
        address: str,
        username: str,
        password: str,
        *,
        path: str = "/interfaces/interface[name=*]/state/oper-status",
        insecure: bool = True,
        origin: Optional[str] = None,
        out_format: str = "json",
        updates_only: bool = True,
        alert_any: bool = False,
        debug: bool = False,
        log_file: str = "./link_state_monitor.log",
        restart: bool = True,
        if_filter: Optional[str] = None,
        on_event: Optional[Callable[[str, str, str, Optional[str]], None]] = None,
        dedupe_enabled: bool = True,
        dedupe_ttl_sec: int = 600,
    ):
        self.address = address
        self.username = username
        self.password = password
        self.path = path
        self.insecure = insecure
        self.origin = origin
        self.out_format = out_format
        self.updates_only = updates_only
        self.alert_any = alert_any
        self.debug = debug
        self.debug_stream = True  # log raw lines when debug=True
        self.log_file = log_file
        self.restart = restart
        self.if_filter: Optional[Pattern[str]] = re.compile(if_filter) if if_filter else None
        self.on_event = on_event

        # de-dup
        self.dedupe_enabled = dedupe_enabled
        self.dedupe_ttl_sec = int(dedupe_ttl_sec)
        self._seen_events: Dict[Tuple[str, str, str], float] = {}

        self._proc: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()
        self._lock = threading.Lock()
        self._started_at: Optional[datetime] = None
        self._last_event: Optional[Tuple[str, str, str]] = None
        self._last_by_iface: Dict[str, str] = {}

    # ---- service controls ----
    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_evt.clear()
            self._thread = threading.Thread(target=self._run_loop, name="gnmic-monitor", daemon=True)
            self._thread.start()
            self._started_at = datetime.now()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop_evt.set()
        with self._lock:
            proc = self._proc
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                    proc.wait(timeout=2.0)
                except Exception:
                    pass
        if self._thread:
            self._thread.join(timeout=timeout)
        with self._lock:
            self._proc = None
            self._thread = None

    def is_running(self) -> bool:
        with self._lock:
            return bool(self._thread and self._thread.is_alive())

    def status(self) -> Dict[str, Optional[str]]:
        with self._lock:
            pid = self._proc.pid if self._proc and self._proc.poll() is None else None
            last = None
            if self._last_event:
                iface, oper, ts = self._last_event
                last = f"{ts} iface={iface} state={oper}"
        uptime = None
        if self._started_at:
            uptime = str(datetime.now() - self._started_at).split(".")[0]
        return {
            "running": True if self.is_running() else False,
            "pid": str(pid) if pid else None,
            "uptime": uptime,
            "last_event": last,
            "log_file": os.path.abspath(self.log_file),
            "format": self.out_format,
        }

    # ---- log helpers ----
    def tail_log(self, n: int = 50) -> List[str]:
        return tail_log_file(self.log_file, n)

    def get_events(self, since: Optional[str] = None, iface_regex: Optional[str] = None,
                   states: Optional[List[str]] = None, limit: Optional[int] = None) -> List[Dict[str, str]]:
        return _get_events_from_log(self.log_file, since, iface_regex, states, limit)

    def check_log_for_updates(self, since: Optional[str] = "5m", iface_regex: Optional[str] = None,
                              count_only: bool = True) -> Dict[str, object]:
        return check_log_for_updates_file(self.log_file, since, iface_regex, count_only)

    # ---- dedupe helper ----
    def _gc_seen(self, now: float):
        if not self._seen_events:
            return
        ttl = self.dedupe_ttl_sec
        for k, t in list(self._seen_events.items()):
            if now - t > ttl:
                del self._seen_events[k]

    def _maybe_log_event(self, iface: str, oper: str, ts_iso: str, prev: Optional[str]):
        """Apply dedupe, call on_event, and write LINK-STATE line if needed."""
        # store last
        self._last_by_iface[iface] = oper
        with self._lock:
            self._last_event = (iface, oper, ts_iso)

        if self.on_event:
            try:
                self.on_event(iface, oper, ts_iso, prev)
            except Exception as e:
                self._log_line(f"[WARN] on_event error: {e}", stderr=True)

        # dedupe: same (iface, oper, ts_iso) within TTL
        now = time.time()
        if self.dedupe_enabled:
            self._gc_seen(now)
            sig = (iface, oper, ts_iso)
            last = self._seen_events.get(sig)
            if last and (now - last) < self.dedupe_ttl_sec:
                if self.debug:
                    self._log_line(f"[DBG] dedup {sig}", stderr=True)
                return
            self._seen_events[sig] = now

        if self.alert_any or oper in DOWN_STATES:
            self._log_line(f"{ts_iso} | LINK-STATE | iface={iface} state={oper} (prev={prev})")

    # ---- runner ----
    def _run_loop(self):
        backoff = 1
        while not self._stop_evt.is_set():
            cmd = self._build_cmd()
            self._log_line("[INFO] starting gnmic: " + self._display_cmd(cmd), stderr=True)
            try:
                with subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                ) as proc:
                    with self._lock:
                        self._proc = proc

                    buf = ""
                    for raw in proc.stdout:
                        if self._stop_evt.is_set():
                            break
                        if raw is None:
                            continue

                        # Echo raw line when debug enabled (helps diagnose)
                        if self.debug and self.debug_stream:
                            self._log_line(f"[RAW] {raw.rstrip()}", stderr=True)

                        line = raw.strip()
                        if not line:
                            continue

                        # Fast path: NDJSON (one JSON object per line)
                        try:
                            obj = json.loads(line)
                            parsed = _parse_event_obj(obj, self.out_format)
                            if parsed:
                                iface, oper, ts_iso = parsed
                                if self.if_filter and not self.if_filter.search(iface):
                                    continue
                                prev = self._last_by_iface.get(iface)
                                self._maybe_log_event(iface, oper, ts_iso, prev)
                            else:
                                if self.debug:
                                    self._log_line(f"[DBG] parsed JSON but no oper-status: keys={list(obj.keys())}", stderr=True)
                            continue
                        except json.JSONDecodeError:
                            pass  # fall through to buffered multi-line

                        # Slow path: accumulate multi-line JSON
                        if line.startswith("{") or buf:
                            buf += (line if not buf else "\n" + line)
                            try:
                                obj = json.loads(buf)
                                buf = ""
                            except json.JSONDecodeError:
                                if self.debug and len(buf) > 200_000:
                                    self._log_line("[DBG] accumulating multiline JSON...", stderr=True)
                                continue

                            parsed = _parse_event_obj(obj, self.out_format)
                            if not parsed:
                                if self.debug:
                                    self._log_line(f"[DBG] parsed JSON (buffered) but no oper-status: keys={list(obj.keys())}", stderr=True)
                                continue

                            iface, oper, ts_iso = parsed
                            if self.if_filter and not self.if_filter.search(iface):
                                continue
                            prev = self._last_by_iface.get(iface)
                            self._maybe_log_event(iface, oper, ts_iso, prev)
                        else:
                            if self.debug:
                                self._log_line(f"[DBG] non-JSON line: {line[:160]}", stderr=True)

                    rc = proc.wait()
                    self._log_line(f"[INFO] gnmic exited with rc={rc}", stderr=True)

            except Exception as e:
                self._log_line(f"[ERROR] {e}", stderr=True)

            if self._stop_evt.is_set():
                break
            if self.restart:
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)
            else:
                break

        self._log_line("[INFO] monitor stopped.", stderr=True)

    def _build_cmd(self) -> List[str]:
        cmd = [
            "gnmic",
            "--insecure" if self.insecure else "",
            "-a", self.address,
            "-u", self.username,
            "-p", self.password,
            "subscribe",
            "--path", self.path,
            "--mode", "stream",
            "--stream-mode", "on-change",
            "--format", self.out_format,
        ]
        if self.updates_only:
            cmd.append("--updates-only")
        if self.origin:
            cmd += ["--origin", self.origin]
        return [c for c in cmd if c]

    def _display_cmd(self, cmd: List[str]) -> str:
        disp, hide = [], False
        for tok in cmd:
            if hide:
                disp.append("******")
                hide = False
                continue
            disp.append(tok)
            if tok in ("-p", "--password"):
                hide = True
        return " ".join(disp)

    def _log_line(self, line: str, *, stderr: bool = False) -> None:
        d = os.path.dirname(self.log_file)
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        with open(self.log_file, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        if stderr:
            print(line, file=sys.stderr)
        else:
            print(line)

# Programmatic helpers
def create_monitor(cfg: MonitorConfig) -> LinkStateMonitor:
    return LinkStateMonitor(**asdict(cfg))

def start_monitor(cfg: MonitorConfig) -> LinkStateMonitor:
    mon = create_monitor(cfg)
    mon.start()
    return mon

def stop_monitor(mon: LinkStateMonitor, timeout: float = 5.0) -> None:
    mon.stop(timeout=timeout)

def monitor_status(mon: LinkStateMonitor) -> Dict[str, Optional[str]]:
    return mon.status()

# -------------------------
# Remote manager (Paramiko)
# -------------------------
class RemoteMonitorManager:
    """
    Start/stop a single target on a remote host over SSH.
    Enforces singleton-per-target (by pattern) and cleans up stragglers on stop.
    """

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        *,
        port: int = 22,
        remote_python: str = "python3",
        remote_module_path: str = "/opt/linkmon/link_state_service.py",
        remote_workdir: str = "/opt/linkmon",
        remote_log: str = "/var/log/link_state_monitor.log",
        remote_pid: str = "/var/run/link_state_service.pid",
        max_log_bytes_for_check: int = 1_000_000,
        target_addr: Optional[str] = None,
    ):
        if paramiko is None:
            raise RuntimeError("paramiko is not installed. Run: pip install paramiko")
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.remote_python = remote_python
        self.remote_module_path = remote_module_path
        self.remote_workdir = remote_workdir
        self.remote_log = remote_log
        self.remote_pid = remote_pid
        self.max_log_bytes_for_check = max_log_bytes_for_check
        self.target_addr = target_addr

    def _connect(self):
        cli = paramiko.SSHClient()
        cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        cli.connect(self.host, port=self.port, username=self.username, password=self.password, timeout=15)
        return cli

    def _exec(self, cli: "paramiko.SSHClient", cmd: str):
        stdin, stdout, stderr = cli.exec_command(cmd)
        rc = stdout.channel.recv_exit_status()
        out = stdout.read().decode("utf-8", errors="ignore")
        err = stderr.read().decode("utf-8", errors="ignore")
        return rc, out, err

    # ---- process discovery/cleanup helpers ----
    def _target_pattern(self) -> Optional[str]:
        if not self.target_addr:
            return None
        return f"link_state_service.py start -a {self.target_addr} "

    def _pgrep_pids(self, cli) -> List[str]:
        pat = self._target_pattern()
        if not pat:
            return []
        cmd = f'pgrep -f {shlex.quote(pat)} || true'
        rc, out, _ = self._exec(cli, f"bash -lc {shlex.quote(cmd)}")
        return [p.strip() for p in out.splitlines() if p.strip()]

    def kill_all_for_target(self, cli) -> dict:
        pat = self._target_pattern()
        if not pat:
            return {"killed": 0, "note": "no target_addr"}
        cmd = f'pkill -TERM -f {shlex.quote(pat)} || true'
        self._exec(cli, f"bash -lc {shlex.quote(cmd)}")
        time.sleep(0.4)
        remaining = self._pgrep_pids(cli)
        return {"remaining": remaining}

    # ---- operations ----
    def deploy(self, local_module_path: str) -> None:
        cli = self._connect()
        try:
            self._exec(cli, f"mkdir -p {shlex.quote(self.remote_workdir)}")
            sftp = cli.open_sftp()
            try:
                sftp.put(local_module_path, self.remote_module_path)
            finally:
                sftp.close()
            self._exec(cli, f"chmod 755 {shlex.quote(self.remote_module_path)}")
        finally:
            cli.close()

    def start(self, cfg: MonitorConfig, singleton_mode: str = "kill") -> dict:
        """
        singleton_mode: "kill" (default) | "refuse" | "none"
        """
        cli = self._connect()
        try:
            self._exec(cli, "mkdir -p /var/log /var/run " + f"{shlex.quote(self.remote_workdir)}")

            # Singleton guard
            if singleton_mode in ("kill", "refuse"):
                pids = self._pgrep_pids(cli)
                if pids:
                    if singleton_mode == "refuse":
                        return {"error": "already_running", "pids": pids}
                    self.kill_all_for_target(cli)

            # --- Detect whether remote script supports dedupe flags ---
            # We run: python3 /opt/linkmon/link_state_service.py start --help
            help_cmd = (
                f"bash -lc {shlex.quote(self.remote_python + ' ' + self.remote_module_path + ' start --help || true')}"
            )
            rc_h, help_out, _ = self._exec(cli, help_cmd)
            dedupe_supported = ("--dedupe-ttl" in help_out) and ("--no-dedupe" in help_out)

            args = [
                shlex.quote(self.remote_python),
                shlex.quote(self.remote_module_path),
                "start",
                "-a", shlex.quote(cfg.address),
                "-u", shlex.quote(cfg.username),
                "-p", shlex.quote(cfg.password),
                "--format", shlex.quote(cfg.out_format),
            ]
            if cfg.path:
                args += ["--path", shlex.quote(cfg.path)]
            if cfg.origin:
                args += ["--origin", shlex.quote(cfg.origin)]
            if cfg.insecure:
                args += ["--insecure"]
            if cfg.updates_only:
                args += ["--updates-only"]
            if cfg.alert_any:
                args += ["--alert-any"]
            if cfg.debug:
                args += ["--debug"]
            if cfg.log_file:
                args += ["--log-file", shlex.quote(self.remote_log)]
            if cfg.if_filter:
                args += ["--if-filter", shlex.quote(cfg.if_filter)]

            # Only pass dedupe flags if the remote script supports them
            if dedupe_supported:
                if not cfg.dedupe_enabled:
                    args += ["--no-dedupe"]
                if cfg.dedupe_ttl_sec is not None:
                    args += ["--dedupe-ttl", str(int(cfg.dedupe_ttl_sec))]

            start_cmd = " ".join(args)

            # Ensure gnmic is found even in a non-login, non-interactive shell
            # (extend PATH to common locations, then nohup)
            nohup = (
                "bash -lc " +
                shlex.quote(
                    "export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH; "
                    f"nohup {start_cmd} > /var/log/link_state_service.out 2>&1 & "
                    f"echo $! > {self.remote_pid}"
                )
            )
            rc, _out, err = self._exec(cli, nohup)
            time.sleep(0.8)
            st = self.status()
            st["start_rc"] = rc
            st["stderr"] = err.strip() or None
            st["dedupe_supported"] = dedupe_supported
            return st
        finally:
            cli.close()


    def stop(self) -> dict:
        cli = self._connect()
        try:
            # kill process from PID file, if any
            rc, out, _ = self._exec(cli, f"bash -lc 'test -f {shlex.quote(self.remote_pid)} && cat {shlex.quote(self.remote_pid)}'")
            pid = out.strip() if rc == 0 and out.strip() else None
            if pid:
                self._exec(cli, f"bash -lc 'kill -TERM {shlex.quote(pid)} || true'")
                self._exec(cli, f"bash -lc 'rm -f {shlex.quote(self.remote_pid)}'")
            # ensure no stragglers
            killed = self.kill_all_for_target(cli)
            # wait a bit for them to exit
            deadline = time.time() + 5.0
            remaining = self._pgrep_pids(cli)
            while remaining and time.time() < deadline:
                time.sleep(0.3)
                remaining = self._pgrep_pids(cli)
            # escalate if still there
            if remaining:
                pat = self._target_pattern()
                if pat:
                    self._exec(cli, f"bash -lc 'pkill -KILL -f {shlex.quote(pat)} || true'")
                    time.sleep(0.3)
                    remaining = self._pgrep_pids(cli)
            return {"stopped_pidfile": bool(pid), "killed_by_pattern": killed, "remaining": remaining}
        finally:
            cli.close()

    def status(self) -> dict:
        cli = self._connect()
        try:
            rc, out, _ = self._exec(cli, f"bash -lc 'test -f {shlex.quote(self.remote_pid)} && cat {shlex.quote(self.remote_pid)}'")
            pid = out.strip() if rc == 0 and out.strip() else None

            running = False
            if pid:
                rc, _, _ = self._exec(cli, f"bash -lc 'ps -p {shlex.quote(pid)} -o pid= >/dev/null 2>&1'")
                running = (rc == 0)

            rc, last, _ = self._exec(cli, f"bash -lc 'test -f {shlex.quote(self.remote_log)} && tail -n 1 {shlex.quote(self.remote_log)}'")
            last = last.strip() or None
            return {"running": running, "pid": pid, "last_log": last, "log_path": self.remote_log}
        finally:
            cli.close()

    def tail_log(self, n: int = 50) -> List[str]:
        cli = self._connect()
        try:
            rc, out, _ = self._exec(cli, f"bash -lc 'test -f {shlex.quote(self.remote_log)} && tail -n {int(n)} {shlex.quote(self.remote_log)}'")
            lines = (out or "").splitlines()
            return lines[-n:]
        finally:
            cli.close()

    def check_updates(self, since: str = "5m") -> dict:
        cli = self._connect()
        try:
            sftp = cli.open_sftp()
            try:
                try:
                    st = sftp.stat(self.remote_log)
                except FileNotFoundError:
                    return {"since": since, "updates": False, "count": 0, "sample": None}
                size = st.st_size
                start = max(0, size - 1_000_000)
                f = sftp.open(self.remote_log, "r")
                try:
                    f.seek(start)
                    chunk = f.read().decode("utf-8", errors="ignore")
                finally:
                    f.close()
            finally:
                sftp.close()
        finally:
            cli.close()

        cutoff = _parse_since(since)
        cnt = 0
        sample = []
        for line in chunk.splitlines():
            m = LOG_LINE_RE.match(line.strip())
            if not m:
                continue
            ts = datetime.fromisoformat(m.group("ts"))
            if cutoff and ts < cutoff:
                continue
            cnt += 1
            if len(sample) < 5:
                sample.append({
                    "timestamp": m.group("ts"),
                    "iface": m.group("iface"),
                    "state": m.group("state"),
                    "prev": m.group("prev"),
                })
        return {"since": since, "updates": cnt > 0, "count": cnt, "sample": sample or None}

# -------------------------
# Remote multi-target controller
# -------------------------
class RemoteMultiMonitor:
    """
    Starts/stops one background process per target on a remote host.
    Per-run unique stream logs; stable per-target PID files; singleton per target.
    """
    def __init__(
        self,
        host: str, username: str, password: str,
        base_cfg: MonitorConfig,
        targets: List[str],
        *,
        remote_python: str = "python3",
        remote_workdir: str = "/opt/linkmon",
        remote_log_dir: str = "/var/log",
        remote_pid_dir: str = "/var/run",
        remote_module_path: str = "/opt/linkmon/link_state_service.py",
        run_id: Optional[str] = None,
    ):
        self.host = host
        self.username = username
        self.password = password
        self.base_cfg = base_cfg
        self.targets = targets
        self.remote_python = remote_python
        self.remote_workdir = remote_workdir.rstrip("/")
        self.remote_log_dir = remote_log_dir.rstrip("/")
        self.remote_pid_dir = remote_pid_dir.rstrip("/")
        self.remote_module_path = remote_module_path
        self.run_id = run_id or DEFAULT_RUN_ID
        self._managers: Dict[str, RemoteMonitorManager] = {}

    def deploy(self, local_module_path: str):
        mgr = RemoteMonitorManager(
            host=self.host, username=self.username, password=self.password,
            remote_python=self.remote_python,
            remote_module_path=self.remote_module_path,
            remote_workdir=self.remote_workdir,
            remote_log=f"{self.remote_log_dir}/link_state_monitor_master_{self.run_id}.log",
            remote_pid=f"{self.remote_pid_dir}/link_state_service_master.pid",
        )
        mgr.deploy(local_module_path)

    def start_all(self, singleton_mode: str = "kill"):
        started = []
        for addr in self.targets:
            slug = _slugify(addr)
            mgr = RemoteMonitorManager(
                host=self.host, username=self.username, password=self.password,
                remote_python=self.remote_python,
                remote_module_path=self.remote_module_path,
                remote_workdir=self.remote_workdir,
                remote_log=f"{self.remote_log_dir}/link_state_monitor_{slug}_{self.run_id}.log",
                remote_pid=f"{self.remote_pid_dir}/link_state_service_{slug}.pid",
                target_addr=addr,
            )
            cfg = copy.deepcopy(self.base_cfg)
            cfg.address = addr
            cfg.log_file = f"{self.remote_log_dir}/link_state_monitor_{slug}_{self.run_id}.log"
            started.append((addr, mgr.start(cfg, singleton_mode=singleton_mode)))
            self._managers[addr] = mgr
        return started

    def stop_all(self, preserve_managers: bool = True):
        stopped: Dict[str, dict] = {}
        for addr, mgr in list(self._managers.items()):
            stopped[addr] = mgr.stop()
        if not preserve_managers:
            self._managers.clear()
        return stopped

    def status_all(self) -> Dict[str, dict]:
        return {addr: mgr.status() for addr, mgr in self._managers.items()}

    def check_updates_all(self, since: str = "5m") -> Dict[str, dict]:
        return {addr: mgr.check_updates(since=since) for addr, mgr in self._managers.items()}

    def tail(self, addr: str, n: int = 50) -> List[str]:
        mgr = self._managers.get(addr)
        return mgr.tail_log(n) if mgr else []

    # per-target helpers (work even if managers were cleared)
    def _mgr_for(self, addr: str) -> RemoteMonitorManager:
        mgr = self._managers.get(addr)
        if mgr:
            return mgr
        slug = _slugify(addr)
        return RemoteMonitorManager(
            host=self.host, username=self.username, password=self.password,
            remote_python=self.remote_python,
            remote_module_path=self.remote_module_path,
            remote_workdir=self.remote_workdir,
            remote_log=f"{self.remote_log_dir}/link_state_monitor_{slug}_{self.run_id}.log",
            remote_pid=f"{self.remote_pid_dir}/link_state_service_{slug}.pid",
            target_addr=addr,
        )

    def status_for(self, addr: str) -> dict:
        return self._mgr_for(addr).status()

    def updates_for(self, addr: str, since: str = "5m") -> dict:
        return self._mgr_for(addr).check_updates(since=since)

    def tail_for(self, addr: str, n: int = 50) -> List[str]:
        return self._mgr_for(addr).tail_log(n)

# -------------------------
# Periodic health reporter (self-contained)
# -------------------------
class PeriodicHealthReporter:
    """
    Periodically snapshots per-target health/updates/tail using RemoteMultiMonitor,
    without stopping the monitors. Writes text/json/jsonl directly with per-run file names.
    Can optionally stop remote monitors in stop().
    """
    def __init__(
        self,
        rmm: "RemoteMultiMonitor",
        targets: List[str],
        out_dir: str = "/var/log",
        fmt: str = "jsonl",             # "jsonl" | "json" | "text"
        interval_sec: int = 60,
        since: Optional[str] = None,    # default: ~2x interval in minutes
        tail_lines: int = 20,
        truncate_first: bool = False,   # overwrite files on the first run
        also_print: bool = False,
        run_id: Optional[str] = None,   # per-run file suffix
        stop_monitors_on_stop: bool = False,  # stop rmm monitors on reporter.stop()
    ):
        self.rmm = rmm
        self.targets = targets
        self.out_dir = out_dir.rstrip("/") if out_dir else "."
        self.fmt = fmt.lower()
        self.interval = max(1, int(interval_sec))
        self.tail_lines = tail_lines
        self.truncate_first = truncate_first
        self.also_print = also_print
        if since:
            self.since = since
        else:
            mins = max(1, int(round((self.interval * 2) / 60.0)))
            self.since = f"{mins}m"
        self.run_id = run_id or getattr(rmm, "run_id", None) or DEFAULT_RUN_ID
        self.stop_monitors_on_stop = stop_monitors_on_stop

        self._t = None
        self._stop_evt = None
        self._ran_once = False

    def start(self):
        if self._t and self._t.is_alive():
            return
        import threading
        self._stop_evt = threading.Event()
        self._t = threading.Thread(target=self._loop, name="periodic-health-reporter", daemon=True)
        self._t.start()

    def stop(self, timeout: float = 5.0):
        if self._stop_evt:
            self._stop_evt.set()
        if self._t:
            self._t.join(timeout=timeout)
        if self.stop_monitors_on_stop and hasattr(self.rmm, "stop_all"):
            try:
                self.rmm.stop_all(preserve_managers=True)
            except Exception as e:
                print(f"[WARN] reporter.stop(): rmm.stop_all failed: {e}")

    def _loop(self):
        next_run = time.time()
        while self._stop_evt and not self._stop_evt.is_set():
            self._tick_once()
            self._ran_once = True
            next_run += self.interval
            remaining = next_run - time.time()
            if remaining > 0:
                self._stop_evt.wait(remaining)

    def _status_for(self, addr: str) -> dict:
        if hasattr(self.rmm, "status_for"):
            return self.rmm.status_for(addr)
        all_status = self.rmm.status_all()
        return all_status.get(addr, {})

    def _updates_for(self, addr: str, since: str) -> dict:
        if hasattr(self.rmm, "updates_for"):
            return self.rmm.updates_for(addr, since=since)
        all_updates = self.rmm.check_updates_all(since=since)
        return all_updates.get(addr, {"since": since, "updates": False, "count": 0, "sample": []})

    def _tail_for(self, addr: str, n: int) -> List[str]:
        if hasattr(self.rmm, "tail_for"):
            return self.rmm.tail_for(addr, n)
        return self.rmm.tail(addr, n) if hasattr(self.rmm, "tail") else []

    def _write_file(self, content: str, preferred_path: str, slug: str, truncate: bool) -> str:
        mode = "w" if truncate else "a"
        if not content.endswith("\n"):
            content += "\n"
        try:
            d = os.path.dirname(preferred_path) or "."
            os.makedirs(d, exist_ok=True)
            with open(preferred_path, mode, encoding="utf-8") as fh:
                fh.write(content)
            return preferred_path
        except PermissionError:
            fb_dir = os.path.join(os.path.expanduser("~"), "linkmon_admin")
            os.makedirs(fb_dir, exist_ok=True)
            ext = ".jsonl" if preferred_path.endswith(".jsonl") else ".log"
            fb_path = os.path.join(fb_dir, f"{slug}_linkmon_admin_{self.run_id}{ext}")
            with open(fb_path, mode, encoding="utf-8") as fh:
                fh.write(content)
            print(f"[WARN] Permission denied for {preferred_path}; wrote to {fb_path} instead.")
            return fb_path

    def _tick_once(self):
        truncate_now = (self.truncate_first and not self._ran_once)
        for addr in self.targets:
            slug = _slugify(addr)
            ts = datetime.now().isoformat(timespec="seconds")
            status = self._status_for(addr)
            updates = self._updates_for(addr, self.since)
            tail_out = self._tail_for(addr, self.tail_lines)

            if self.fmt == "jsonl":
                path = f"{self.out_dir}/{slug}_linkmon_admin_{self.run_id}.jsonl"
                entry = {
                    "ts": ts,
                    "since": self.since,
                    "status": status,
                    "updates": updates,
                    "tail_target": addr,
                    "tail_lines": self.tail_lines,
                    "tail": tail_out,
                }
                line = json.dumps(entry, separators=(",", ":"))
                self._write_file(line, path, slug, truncate=truncate_now)
                if self.also_print:
                    print(line)

            elif self.fmt == "json":
                path = f"{self.out_dir}/{slug}_linkmon_admin_{self.run_id}.log"
                entry = {
                    "ts": ts,
                    "target": addr,
                    "since": self.since,
                    "status": status,
                    "updates": updates,
                    "tail_last_n": self.tail_lines,
                    "tail": tail_out,
                }
                pretty = json.dumps(entry, indent=2)
                body = f"=== LINKMON [{addr}] {ts} ===\n{pretty}\n"
                self._write_file(body, path, slug, truncate=truncate_now)
                if self.also_print:
                    print(pretty)

            else:  # "text"
                path = f"{self.out_dir}/{slug}_linkmon_admin_{self.run_id}.log"
                lines = []
                lines.append(f"=== LINKMON [{addr}] {ts} ===")
                lines.append("Status:")
                lines.append(f"  running: {status.get('running')}")
                lines.append(f"  pid    : {status.get('pid')}")
                lines.append(f"  log    : {status.get('log_path')}")
                if status.get("last_log"):
                    lines.append(f"  last   : {status['last_log']}")
                lines.append(f"Updates (since {self.since}):")
                lines.append(f"  updates: {updates.get('updates')}  count: {updates.get('count')}")
                sample = updates.get("sample") or []
                if sample:
                    lines.append("  sample:")
                    for i, ev in enumerate(sample, 1):
                        lines.append(
                            f"    {i:02d}. {ev.get('timestamp')} | iface={ev.get('iface')} "
                            f"state={ev.get('state')} prev={ev.get('prev')}"
                        )
                else:
                    lines.append("  sample: <none>")
                lines.append(f"Tail (last {self.tail_lines} lines):")
                if tail_out:
                    lines.extend([f"  {ln}" for ln in tail_out])
                else:
                    lines.append("  <empty>")
                body = "\n".join(lines) + "\n"
                self._write_file(body, path, slug, truncate=truncate_now)
                if self.also_print:
                    print(body, end="")

# -------------------------
# Minimal CLI (local foreground)
# -------------------------
def _cli():
    ap = argparse.ArgumentParser(description="Link-state gnmic monitor service")
    sub = ap.add_subparsers(dest="cmd", required=True)

    # start (foreground)
    sp = sub.add_parser("start", help="start in foreground (Ctrl+C to stop)")
    sp.add_argument("-a","--address", required=True)
    sp.add_argument("-u","--username", required=True)
    sp.add_argument("-p","--password", required=True)
    sp.add_argument("--path", default="/interfaces/interface[name=*]/state/oper-status")
    sp.add_argument("--origin", default=None)
    sp.add_argument("--insecure", action="store_true", default=True)
    sp.add_argument("--format", choices=["json","event"], default="json")
    sp.add_argument("--updates-only", action="store_true", default=True)
    sp.add_argument("--alert-any", action="store_true")
    sp.add_argument("--debug", action="store_true")
    sp.add_argument("--log-file", default=f"./link_state_monitor_{DEFAULT_RUN_ID}.log")
    sp.add_argument("--if-filter", default=None)
    sp.add_argument("--no-dedupe", action="store_true", help="disable duplicate event suppression")
    sp.add_argument("--dedupe-ttl", type=int, default=600, help="dedupe window in seconds (default 600)")

    # tail
    st = sub.add_parser("tail", help="tail last N lines from a log file")
    st.add_argument("--log-file", required=True)
    st.add_argument("-n", type=int, default=50)

    # check
    su = sub.add_parser("check", help="check if log has updates since a time/window")
    su.add_argument("--log-file", required=True)
    su.add_argument("--since", default="5m", help='ISO "2025-09-15T13:50:00" or relative "5m"')
    su.add_argument("--iface", default=None, help="regex filter")
    su.add_argument("--list", action="store_true", help="print sample events")

    args = ap.parse_args()

    if args.cmd == "start":
        cfg = MonitorConfig(
            address=args.address,
            username=args.username,
            password=args.password,
            path=args.path,
            insecure=args.insecure,
            origin=args.origin,
            out_format=args.format,
            updates_only=args.updates_only,
            alert_any=args.alert_any,
            debug=args.debug,
            log_file=args.log_file,
            if_filter=args.if_filter,
            dedupe_enabled=not args.no_dedupe,
            dedupe_ttl_sec=max(1, args.dedupe_ttl),
        )
        mon = start_monitor(cfg)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            stop_monitor(mon)

    elif args.cmd == "tail":
        for line in tail_log_file(args.log_file, args.n):
            print(line)

    elif args.cmd == "check":
        res = check_log_for_updates_file(args.log_file, since=args.since, iface_regex=args.iface, count_only=not args.list)
        print(json.dumps(res, indent=2))

if __name__ == "__main__":
    _cli()
