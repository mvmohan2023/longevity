#!/usr/bin/env python3
# run_linkmon_samples.py
#
# Runs the link-state monitor in 3 clean samples:
# - per-sample unique run_id → unique remote log files
# - start monitors, start reporter, wait N seconds, stop reporter (stops monitors)
# - prints final per-target status and remote log file paths for each sample

from datetime import datetime
import time
import sys
import traceback
from typing import Tuple  # <-- Python < 3.9: use typing.Tuple

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

TARGETS = [
    
    "10.83.6.3:50051",
    "10.83.6.4:50052",
    "10.83.6.30:50053",
    "10.83.6.28:50054",
    "10.83.6.5:50055",
    "10.83.6.25:50056",
    "10.83.6.32:50057",
    "10.83.6.21:50058",
    "10.83.6.9:50059",
    
]

SAMPLES = 1                # run the service 3 times
SAMPLE_DURATION_SEC = 300   # 5 minutes per sample
SAMPLE_GAP_SEC = 5          # small idle gap between samples

REPORT_INTERVAL_SEC = 60    # reporter cadence
REPORT_SINCE = "1m"         # window for "updates since"
REPORT_FMT = "text"         # "text" | "json" | "jsonl"
REPORT_OUT_DIR = "/tmp" # snapshots written on the controller host

DEPLOY_MODULE = True        # push local link_state_service.py to remote before first sample

# Optional tag to group runs by test
TEST_ID = "longevity_run"

# -------------------------
# Helpers
# -------------------------
def make_run_id(sample_idx: int) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H-%M-%S")
    return f"{TEST_ID}_sample{sample_idx}_{ts}"

def start_sample(sample_idx: int) -> Tuple[RemoteMultiMonitor, PeriodicHealthReporter, str]:
    run_id = make_run_id(sample_idx)

    # Base gnmic subscribe config; applied per target
    base_cfg = MonitorConfig(
        address="unused",                 # filled per-target internally
        username="root",
        password="Embe1mpls",
        out_format="json",
        updates_only=True,
        insecure=True,
        alert_any=True,
        debug=True,
    )

    # Remote controller for this sample (unique run_id → unique remote logs)
    rmm = RemoteMultiMonitor(
        host=REMOTE_HOST,
        username=REMOTE_USER,
        password=REMOTE_PASS,
        base_cfg=base_cfg,
        targets=TARGETS,
        remote_module_path="/opt/linkmon/link_state_service.py",
        run_id=run_id,
    )

    if DEPLOY_MODULE and sample_idx == 1:
        print("[INFO] Deploying link_state_service.py to remote…", flush=True)
        rmm.deploy("link_state_service.py")

    started = rmm.start_all(singleton_mode="kill")
    print(f"[INFO] Sample {sample_idx}: started ->", started, flush=True)

    rep = PeriodicHealthReporter(
        rmm,
        TARGETS,
        out_dir=REPORT_OUT_DIR,
        fmt=REPORT_FMT,
        interval_sec=REPORT_INTERVAL_SEC,
        since=REPORT_SINCE,
        tail_lines=20,
        truncate_first=True,     # first tick overwrites the output file for this run_id
        also_print=False,
        run_id=run_id,           # keep reporter files aligned with sample run_id
        stop_monitors_on_stop=True,
    )
    rep.start()
    return rmm, rep, run_id

def stop_sample(rmm: RemoteMultiMonitor, rep: PeriodicHealthReporter, sample_idx: int, run_id: str) -> None:
    rep.stop()  # stops reporter AND remote monitors (flag above)
    try:
        status = rmm.status_all()
    except Exception:
        status = {}
    print(f"[INFO] Sample {sample_idx}: final status -> {status}", flush=True)

    # Print per-target remote log paths (handy for fetching)
    for addr in TARGETS:
        slug = addr.replace(".", "_").replace(":", "_")
        remote_log = f"/var/log/link_state_monitor_{slug}_{run_id}.log"
        print(f"[INFO] Remote log for {addr}: {remote_log}", flush=True)

# -------------------------
# Main orchestration
# -------------------------
def main() -> int:
    for i in range(1, SAMPLES + 1):
        print(f"\n===== START SAMPLE {i}/{SAMPLES} =====", flush=True)
        rmm, rep, run_id = start_sample(i)

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
            stop_sample(rmm, rep, i, run_id)

        if i < SAMPLES and SAMPLE_GAP_SEC > 0:
            print(f"[INFO] Gap {SAMPLE_GAP_SEC}s before next sample…", flush=True)
            time.sleep(SAMPLE_GAP_SEC)

    print("\n[INFO] All samples completed.", flush=True)
    return 0

if __name__ == "__main__":
    sys.exit(main())
