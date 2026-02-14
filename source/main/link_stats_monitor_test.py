#!/usr/bin/env python3
# run_linkmon_samples.py
#
# Orchestrates link_state_service.py across N samples:
# - Per-sample unique run_id → unique remote log names
# - Start remote monitors for the given targets
# - Start a periodic health reporter on the controller
# - Wait SAMPLE_DURATION_SEC, then stop reporter (and remote monitors)
# - Prints final status + remote log paths

from datetime import datetime
import time
import os
import sys
import traceback
from typing import Tuple  # for Python < 3.9

# Ensure we can import link_state_service from the same directory
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from link_state_service import (
    MonitorConfig,
    RemoteMultiMonitor,
    PeriodicHealthReporter,
)

# -------------------------
# Config (adjust as needed)
# -------------------------
REMOTE_HOST = "10.83.6.46"
REMOTE_USER = "root"
REMOTE_PASS = "Embe1mpls"

# Default target list (you can pass a subset into start_sample if needed)
TARGETS = [
    "10.83.6.3:50051",
#    "10.83.6.4:50052",
#    "10.83.6.30:50053",
#    "10.83.6.28:50054",
#    "10.83.6.5:50055",
#    "10.83.6.25:50056",
#    "10.83.6.32:50057",
#    "10.83.6.21:50058",
    "10.83.6.9:50059",
]

SAMPLES = 3                   # number of samples to run
SAMPLE_DURATION_SEC = 300     # 5 minutes per sample
SAMPLE_GAP_SEC = 5            # gap between samples (seconds)

REPORT_INTERVAL_SEC = 60      # reporter cadence on the controller
REPORT_FMT = "html"          # "jsonl" | "json" | "text"
REPORT_OUT_DIR = "/homes/mmahadevaswa/public_html"       # where snapshots are written (controller host)

# Set to 0 to avoid re-printing gnmic "starting..." lines in snapshots
REPORT_TAIL_LINES = 0

DEPLOY_MODULE = True          # deploy link_state_service.py to remote before sample #1
TEST_ID = "longevity_run"     # tag in run_id for grouping

# -------------------------
# Helpers
# -------------------------
def make_run_id(sample_idx: int) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H-%M-%S")
    return f"{TEST_ID}_sample{sample_idx}_{ts}"

def _since_from_interval(interval_sec: int) -> str:
    """Use ~2× interval as the 'since' window: expressed in minutes."""
    mins = max(1, int(round((interval_sec * 2) / 60.0)))
    return f"{mins}m"

# -------------------------
# Per-sample lifecycle
# -------------------------
def start_sample(sample_idx: int, targets, report_out_dir) -> Tuple[RemoteMultiMonitor, PeriodicHealthReporter, str]:
    run_id = make_run_id(sample_idx)

    base_cfg = MonitorConfig(
        address="unused",          # filled per-target internally
        username="root",
        password="Embe1mpls",
        out_format="json",
        updates_only=True,
        insecure=True,
        alert_any=True,
        debug=False,               # flip to True for deep diagnosis
    )

    rmm = RemoteMultiMonitor(
        host=REMOTE_HOST,
        username=REMOTE_USER,
        password=REMOTE_PASS,
        base_cfg=base_cfg,
        targets=targets,
        remote_module_path="/opt/linkmon/link_state_service.py",
        run_id=run_id,
    )

    if DEPLOY_MODULE and sample_idx == 1:
        print("[INFO] Deploying link_state_service.py to remote…", flush=True)
        rmm.deploy("link_state_service.py")

    started = rmm.start_all(singleton_mode="kill")
    print(f"[INFO] Sample {sample_idx}: started -> {started}", flush=True)

    rep = PeriodicHealthReporter(
        rmm,
        targets,
        out_dir=report_out_dir,
        fmt=REPORT_FMT,
        interval_sec=REPORT_INTERVAL_SEC,
        since=_since_from_interval(REPORT_INTERVAL_SEC),
        tail_lines=REPORT_TAIL_LINES,   # 0 keeps snapshots quiet
        truncate_first=True,
        also_print=False,
        run_id=run_id,
        stop_monitors_on_stop=True,     # reporter.stop() will stop all remote monitors
    )
    rep.start()
    return rmm, rep, run_id

def stop_sample(
    rmm: RemoteMultiMonitor,
    rep: PeriodicHealthReporter,
    sample_idx: int,
    run_id: str,
    targets: list,
    log_dir: str,
) -> None:
    # stops reporter AND remote monitors (per stop_monitors_on_stop flag)
    rep.stop()
    try:
        status = rmm.status_all()
    except Exception:
        status = {}
    print(f"[INFO] Sample {sample_idx}: final status -> {status}", flush=True)

    # Print per-target remote log paths for convenience
    for addr in targets:
        slug = addr.replace(".", "_").replace(":", "_")
        remote_log = f"{log_dir}/link_state_monitor_{slug}_{run_id}.log"
        print(f"[INFO] Remote log for {addr}: {remote_log}", flush=True)

# -------------------------
# Main orchestration
# -------------------------
def main() -> int:
    # Choose which targets to run this session
    targets = TARGETS

    for i in range(1, SAMPLES + 1):
        print(f"\n===== START SAMPLE {i}/{SAMPLES} =====", flush=True)
        rmm, rep, run_id = start_sample(i, targets, REPORT_OUT_DIR)

        try:
            end_ts = time.time() + SAMPLE_DURATION_SEC
            while time.time() < end_ts:
                time.sleep(1)
        except KeyboardInterrupt:
            print("[WARN] Interrupted by user; stopping this sample…", flush=True)
        except Exception:
            print("[ERROR] Unexpected error in sample loop:", file=sys.stderr)
            traceback.print_exc()
        finally:
            stop_sample(rmm, rep, i, run_id, targets, "/var/log")

        if i < SAMPLES and SAMPLE_GAP_SEC > 0:
            print(f"[INFO] Gap {SAMPLE_GAP_SEC}s before next sample…", flush=True)
            time.sleep(SAMPLE_GAP_SEC)

    print("\n[INFO] All samples completed.", flush=True)
    return 0

if __name__ == "__main__":
    sys.exit(main())
