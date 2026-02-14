import time
import datetime
import re
import pytest
import sys
import copy
import os
import ast
import shutil
import builtins
import json
import gc
import ipaddress
import random
import inspect
from lxml import etree
from typing import Tuple
from datetime import datetime
import time
import subprocess
import jnpr.toby.utils.junos.system_time as system_time
import jnpr.toby.hldcl.host as host_utils
import jnpr.toby.hldcl.device as device_utils
from jnpr.toby.utils import utils
import jnpr.toby.hldcl.trafficgen.trafficgen as trafficgen
from jnpr.toby.utils.pytest_utils.utils import convert_to_list_arg
import jnpr.toby.utils.pytest_utils.datetime_utils as dt_utils
from jnpr.toby.utils.pytest_utils.datetime_utils import Date, Time, _SecsToTimestrHelper
from jnpr.toby.engines.verification.verifyEngine import verifyEngine
sys.path.insert(0, '/volume/regressions/toby/test-suites/MTS/resources/yang_gnmi_validator/openconfig')
import yang_validator_test_mts
#from device_utils import execute_shell_command_on_device, set_current_controller
from itertools import zip_longest
from jnpr.toby.utils.Vars import Vars
from datetime import datetime
from PDT_TE_PROCESSOR import *
# Import the class
sys.path.append('brcm_snapshot.py')
from brcm_snapshot import BRCMDataCollector
#from tv import get as tv.get
sys.path.append('LongevityDashboard.py')
from LongevityDataCollection import LongevityDataCollection
from LongevityReportGen import LongevityReportOrchestrator
from  LongevityTelemetry import LongevityTelemetry
import LongevityDashboard
#sys.path.append('/volume/tide-toby-scripts/test-suites-svn/pdt/lib/pad')
#import TestEngine
from TestEngine import Data, Event
import datetime
import pdb
baseline = Data(name="baseline")
evomemory = Data(name="evomemory")
lrm_baseline = Data(name="lrm_baseline")
te_longevity_test = Data(name="longevity_test")
failed_apps_not_enabled_memory_profiling = {}
# Importing the main LongevityDashboard module

# Importing Dashboard class from LongevityDashboard and assigning aliases
from LongevityDashboard import Dashboard
if 'LongevityDashboard' not in sys.path:
    sys.path.append('LongevityDashboard')
# Creating instances similar to WITH NAME usage in Robot Framework
lng_evo_global = Dashboard()
lng_junos_global = Dashboard()
lng_common = Dashboard()
eo = Event(name="eo")

from typing import Tuple  # <-- Python < 3.9: use typing.Tuple

sys.path.append('link_state_service.py')
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
    "10.83.6.21:50051",
]
#ipclos
TARGETS_DICT = {
    "10.83.6.3": "10.83.6.3:60063",
    "10.83.6.4": "10.83.6.4:60064",
    "10.83.6.30": "10.83.6.30:60065",
    "10.83.6.28": "10.83.6.28:60061",
    "10.83.6.5": "10.83.6.5:60062",
    "10.83.6.25": "10.83.6.25:60066",
    "10.83.6.32": "10.83.6.32:60069",
    "10.83.6.21": "10.83.6.21:60067",
    "10.83.6.9": "10.83.6.9:60068"
}

#yucen setup
#TARGETS_DICT= {
#    "10.48.41.78": "10.48.41.78:60051",
#    "10.48.42.213": "10.48.42.213:50051",
#    "10.48.42.113": "10.48.42.113:60053",
#    "10.48.40.164": "10.48.40.164:60054"
#}

SAMPLES = 3                   # run 3 samples
SAMPLE_DURATION_SEC = 300     # 5 minutes per sample
SAMPLE_GAP_SEC = 5            # <-- REQUIRED: gap between samples

REPORT_INTERVAL_SEC = 60
REPORT_FMT = "html"          # better for parsing snapshots
REPORT_OUT_DIR = "/tmp"
DEPLOY_MODULE = True
TEST_ID = "longevity_run"
REPORT_TAIL_LINES = 0

DEPLOY_MODULE = True
TEST_ID = "longevity_run"

# -------------------------
# Helpers
# -------------------------
def make_run_id(sample_idx: int) -> str:
    #ts = datetime.now().strftime("%Y%m%d_%H-%M-%S")
    ts = datetime.datetime.now().strftime("%Y%m%d_%H-%M-%S")
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
    time.sleep(1.0)  # small settle time

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


def LLOG(message, level='INFO', console='True',**kwargs):

    self = kwargs.get('self', None)
    current_time =  datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if f'{level}' == 'INFO':
        testbed.log(f"'level' = {level}", display_log=True)
    else:
        testbed.log(f"'level' = {level}", display_log=True)
        
    print(f"[{level}]: {message}") 
    pass

def detect_longevity_devices(**kwargs):
    self = kwargs.get('self', None)

    is_dm_enable = tv.get('uv-dm-enable', 0)
    longevity_tag = tv.get('uv-longevity-tag', 'longevity')

    longevity_dut_list = testbed.get_resource_list(tag=longevity_tag) if is_dm_enable == 0 else []
    
    # Initialize attributes
    self.LONGEVITY_OUTPUT_DIR = ''
    self.evo_lng_rtr_list = []
    self.junos_lng_rtr_list = []
    self.longevity_dut_handles = {}
    self.hostname_to_rtr_map = {}

    for rtr in longevity_dut_list:
        rh = testbed.get_handle(resource=rtr)
        h_name = tv.get(f"{rtr}__name", rtr)
        
        self.longevity_dut_handles[h_name] = rh
        self.hostname_to_rtr_map[h_name] = rtr

        
        if rh.is_evo():
            setattr(self, f"isEvo_{rtr}", True)  # Dynamically create attribute if needed
            self.evo_lng_rtr_list.append(rtr)
        else:
            setattr(self, f"isEvo_{rtr}", False)  # Optional: Explicitly mark non-EVO routers
            self.junos_lng_rtr_list.append(rtr)

    
    self.evo_lng_global_flag = len(self.evo_lng_rtr_list) > 0
    self.junos_lng_global_flag = len(self.junos_lng_rtr_list) > 0
    self.evo_lng_rtr_list_len = len(self.evo_lng_rtr_list)
    self.junos_lng_rtr_list_len = len(self.junos_lng_rtr_list)
    self.combined_lng_rtr_list = self.evo_lng_rtr_list + self.junos_lng_rtr_list


def lrm_baseline_config_check(lrm_config_check_list, **kwargs):
    self = kwargs.get('self', None)

    for lrm_dut in lrm_config_check_list:
        LLOG(message=f"Checking LRM Baseline config on router {lrm_dut}...", **{"self": self})
        lrm_dut_handle = testbed.get_handle(resource=lrm_dut)
        resp = device_utils.execute_shell_command_on_device(
            lrm_dut_handle, 
            command='ls /var/tmp/baseline-config.conf', 
            pattern='Toby.*%$'
        )
        
        if 'No such file or directory' in resp:
            raise FileNotFoundError(f"Baseline config missing on {lrm_dut}")


def te_longevity_stop():
    
   
    lrm_baseline.stop()
    te_longevity_test.stop()
    
def set_default_longevity_test_scenarios(**kwargs):
    self = kwargs.get('self', None)
    
    LLOG(message='Longevity Test Timers:\n', **{"self": self})

    duration_in_hrs = int(tv.get("uv-longevity-test-duration", 1))
    duration_in_secs = duration_in_hrs * 60 * 60

    test_scenario_1_percentage = int(tv.get('uv-longevity-test-scenario-1-duration-percent', 90))
    test_scenario_2_percentage = int(tv.get('uv-longevity-test-scenario-2-duration-percent', 10))

    LLOG(message=f"Longevity Test Duration: {duration_in_secs} Seconds\n", **{"self": self})

    for id, percentage in enumerate([test_scenario_1_percentage, test_scenario_2_percentage], start=1):
        longevity_test_duration = int((duration_in_secs * percentage) / 100)
        self.longevity_test_scenarios[str(id)] = longevity_test_duration
        LLOG(message=f"Test Scenario {id} Duration: {longevity_test_duration} Seconds\n", **{"self": self})


def set_customized_longevity_test_scenarios(customized_test_percent_list, **kwargs):
    self = kwargs.get('self', None)

    LLOG(message='Longevity Test Timers:\n', **{"self": self})

    duration_in_hrs = float(tv.get("uv-longevity-test-duration", 1))
    duration_in_secs = duration_in_hrs * 60 * 60

    LLOG(message=f"Longevity Test Duration: {duration_in_secs} Seconds\n", **{"self": self})

    for id, percentage in enumerate(customized_test_percent_list, start=1):
        longevity_test_duration = int((duration_in_secs * int(percentage)) / 100)
        self.longevity_test_scenarios[str(id)] = longevity_test_duration
        LLOG(message=f"Test Scenario {id} Duration: {longevity_test_duration} Seconds\n", **{"self": self})
  

def set_longevity_test_scenarios(**kwargs):
    self = kwargs.get('self', None)
    test_duration_list = tv.get('uv-longevity-customized-test-scenario-duration-percent', 0)
    
    if str(test_duration_list) == 0:
        set_default_longevity_test_scenarios(**{"self": self})
    else:
        set_customized_longevity_test_scenarios(test_duration_list, **{"self": self})


def data_preprocessing(**kwargs):
    self = kwargs.get('self', None)
    
    keys = list(t['resources'].keys())
    event_routers = [gen_item for gen_item in keys if re.match(r'r\d+', gen_item)]
    self.event_routers = event_routers
    
    self.events_hosts = {}
    
    for dut in self.event_routers:
        dh = testbed.get_handle(resource=dut)
        hostname = t['resources'][dut]['system']['primary']['name']
        self.events_hosts[dut] = hostname

        LLOG(message=f"*** HALT PRE-SETUP - Device: {dut} / hostname: {hostname}\n", **{'self': self})

        # Store is_evo flag properly
        setattr(self, f"is_evo_{dut}", dh.current_node.current_controller.is_evo())

        # Correct boolean condition
        if getattr(self, f"is_evo_{dut}", False):
            LLOG(message=f"** hostname: {hostname} is running EVO\n", **{'self': self})
        else:
            LLOG(message=f"** hostname: {hostname} is running JUNOS\n", **{'self': self})

        # Initialize processed list
        setattr(self, f"processed_list_{dut}", [])

    # Check if `is_replay` is already defined
    is_replay = globals().get("is_replay", True)

    try:
        assert 'replay' in tv["uv-active-longevity-events-file"]
    except Exception:
        is_replay = False

    self.is_replay = is_replay

    # Read commands from file
    with open(tv["uv-active-longevity-events-file"], 'r', encoding='UTF-8', errors='strict') as f:
        cmd_str = f.read()

    # Process command list
    tmp_cmd_list = cmd_str.split('\n')
    cmd_list = [item for item in tmp_cmd_list if not item.startswith('#') and item]

    testbed.log(f"\ncmd_list = {cmd_list}", display_log=True)

    # Initialize processing variables
    total_duration = 0
    self.events_hosts_temp = []
    self.sample_size = len(cmd_list)
    event_routers = set(event_routers) 
    for num, cmd in enumerate(cmd_list):
        
        val = convert_to_list_arg(cmd.split('|'))
        d = val[0]
        
        # non router tag present in event_routers.
        if d not in event_routers:
            continue
        self.events_hosts_temp.append(d)

        length = len(val)
        line_num = num + 1

        if length != 6:
            LLOG(level='WARN', message=f"CHECK FORMAT LINE#{line_num} / Number args:{length} in place, need 6 args with a | in between each arg.\n", **{'self': self})
            continue  # Instead of breaking, continue to process remaining lines

        # Store values in processed list
        if not hasattr(self, f"processed_list_{d}"):
            setattr(self, f"processed_list_{d}", [])

        getattr(self, f"processed_list_{d}").append(val[1:])
        duration = int(float(val[2])) * 60
        total_duration += duration

    # Calculate iterations
    #total_time = int(float(tv['uv-longevity-test-duration'])) * 3600

    #if total_duration > 0:
    #    number_of_iterations = int(total_time / total_duration)
    #else:
    #    number_of_iterations = 1

    #self.number_of_iterations = number_of_iterations if number_of_iterations > 0 else 1

    # Adjust for replay mode
    #if self.is_replay:
    #    self.number_of_iterations = 1

    # Final log
    #if not self.is_replay:
    #    LLOG(message=f"*** TOTAL HALT DURATION: {self.number_of_iterations} hrs ***\n", **{'self': self})
    

def LONGEVITY_ANNOTATE(annotate_string, **kwargs):
    MonitoringEngine.monitoring_engine_annotate(annotation=f'"{annotate_string}"')


def te_object_control(te_data_object, action, **kwargs):
    testbed.log(f"{te_data_object} {action}", display_log=True)


def LSLEEP(sleep_time=10, reason='', **kwargs):
    LLOG(message=f"Sleep Timer of {sleep_time} Seconds in progress... {reason}", self=kwargs.get('self', None))
    testbed.log(reason, display_log=True)
    testbed.log(f"Sleeping for {sleep_time} seconds", display_log=True)
    time.sleep(int(re.sub(r'\D', '', str(sleep_time))))
    LLOG(message=f"Sleep Timer of {sleep_time} Seconds completed.", self=kwargs.get('self', None))


def process_user_te_objects(te_objects_list, action, **kwargs):
    for te_obj in te_objects_list:
        te_object_control(te_obj, action, self=kwargs.get('self', None))
    #LSLEEP(120, self=kwargs.get('self', None))


def junos_get_node_list(rtr, **kwargs):
    rh = testbed.get_handle(resource=rtr)
    cmd_timeout = tv.get('uv-cmd-timeout-fpc-online-slot-list', 600)
    xml_out = device_utils.execute_cli_command_on_device(device=rh, command='show chassis fpc | display xml', timeout=cmd_timeout, pattern='Toby.*>$')
    junos_fpc_list = xml_utils.get_elements_texts(xml_out, "fpc-information/fpc[state='Online']/slot")
    return {'fpc_list': junos_fpc_list}


def get_pfe_instances_from_junos_qfx_fpc(rtr, fpc, **kwargs):
    return [0, '1', '2', '3', '4', '5']




def get_pfe_instances_from_junos_fpc(rtr, fpc, **kwargs):
    """Fetch PFE instances from a Junos FPC."""
    self = kwargs.get("self", None)
    rh = testbed.get_handle(resource=rtr)
    cmd_timeout = tv.get("uv-cmd-timeout-fpc-online-slot-list", 600)
    xml_out = device_utils.execute_cli_command_on_device(
        device=rh, command="show chassis fabric fpcs | display xml", 
        timeout=cmd_timeout, pattern="Toby.*>$"
    )
    return xml_utils.get_elements_texts(
        xml_out, f'fm-fpc-state-information/fm-fpc-ln[slot="{fpc}"]/fm-pfe-ln/pfe-slot'
    )

def build_pfe_instances_data_for_fpc_on_junos_rtr(rtr, **kwargs):
    """Build PFE instances data for a Junos router."""
    self = kwargs.get("self", None)
    setattr(self, f"pfe_instances_of_fpc_{rtr}", {})

    nodes_data = junos_get_node_list(rtr, **{"self": self})
    fpc_list = nodes_data["fpc_list"]
    rh = testbed.get_handle(resource=rtr)
    rtr_model = device_utils.get_model_for_device(device=rh).lower()

    is_rtr_qfx = "qfx" in rtr_model
    is_rtr_ex = "ex" in rtr_model

    for fpc in fpc_list:
        pfe_instances = (
            get_pfe_instances_from_junos_qfx_fpc(rtr, fpc, **{"self": self}) 
            if is_rtr_qfx or is_rtr_ex 
            else get_pfe_instances_from_junos_fpc(rtr, fpc, **{"self": self})
        )
        getattr(self, f"pfe_instances_of_fpc_{rtr}")[f"{rtr}.{fpc}"] = pfe_instances

def junos_preparation_helper(rtr_list, **kwargs):
    """Prepare Junos routers before testing."""
    self = kwargs.get("self", None)
    self.junos_aft_cards = {}

    for rtr in rtr_list:
        rh = testbed.get_handle(resource=rtr)
        rtr_model = device_utils.get_model_for_device(device=rh).lower()
        
        is_load_lrm_config = tv.get("uv-longevity-skip-lrm-baseline-step", 0) == 0
        is_rtr_mx = "mx" in rtr_model

        if is_load_lrm_config and is_rtr_mx:
            device_utils.execute_config_command_on_device(
                rh, command_list="set groups global chassis network-services enhanced-ip", 
                commit=True, pattern="Toby.*#$"
            )

        build_pfe_instances_data_for_fpc_on_junos_rtr(rtr, **{"self": self})

def longevity_save_rtr_test_config(rtr_list, **kwargs):
    """Save the test configuration for routers."""
    self = kwargs.get("self", None)
    self.rtr_saved_cfg = {}
    tasks = []
    time_stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    result =''
    for rtr in rtr_list:
        rtr_name = tv[f"{rtr}__name"]
        file_name = f"/var/tmp/{rtr_name}_{time_stamp}.config"
        cmd = f"save {file_name}"
        self.rtr_saved_cfg[rtr] = file_name
        rh = testbed.get_handle(resource=rtr)
        #parallel.append_to_task(f"task={rtr}_save_config")
        parallel.create_task(f"task={rtr}_save_config", "Run Event", "ON CONFIG", f"command={cmd}", f"device={rh}", f"timeout={600}")
        tasks.append(f"{rtr}_save_config")
        
    try:
        
        parallel.run_in_parallel(f"tasks={','.join(tasks)}")
        LLOG(message=f"Test Configuration of Routers {rtr_list} saved.\n", **{"self": self})
    except Exception as e:
        LLOG(
            level="ERROR",
            message=f"Failed to save test configuration on {rtr_list}. Aborting the Longevity Test. Error: {str(e)}\n",
            **{"self": self}
        )
        raise RuntimeError(f"[ Fail ] Failed to save test configuration on {rtr_list}. Aborting the Longevity Test.") from e

def longevity_load_rtr_test_config(**kwargs):
    
    
    """Load the saved test configuration onto routers."""
    self = kwargs.get("self", None)
   
    rtr_list = list(self.rtr_saved_cfg.keys())

    task_list1 = []
    task_list2 = []

    for rtr in rtr_list:
        rh = testbed.get_handle(resource=rtr)
        
        # Task for loading config
        #parallel.create_task(
        #    task=f"{rtr}_load_config",
        #    action="Execute Config Command On Device",|
        #    target=rh,
        #    command_list=f"load override {self.rtr_saved_cfg[rtr]}",
        #    timeout=720
        #)
        cmds = [f"load override {self.rtr_saved_cfg[rtr]}",'commit']
        parallel.create_task(f"task={rtr}_load_config", "Run Event", "ON CONFIG", f"command={cmds}", f"device={rh}", f"timeout={400}")
        task_list1.append(f"{rtr}_load_config")


    LLOG(message=f"Loading Longevity Routers {rtr_list} with Test Configuration\n", **{"self": self})

    try:
        parallel.run_in_parallel(f"tasks={','.join(task_list1)}")
    except Exception as e:
        LLOG(
            level="ERROR",
            message=f"Failed to load test configuration on {rtr_list}. Error: {str(e)}\n",
            **{"self": self}
        )
        raise RuntimeError(f"[ Fail ] Failed to load and commit the test configuration on {rtr_list}. Aborting the Longevity Test.") from e

    LLOG(message=f"Loaded Routers {rtr_list} with Test Configuration\n", **{"self": self})

def longevity_load_lrm_baseline_config(rtr_list, **kwargs):
    self = kwargs.get('self')
    task_list = []
    LLOG(message=f"Loading LRM Baseline Config /var/tmp/baseline-config.conf on the routers: {rtr_list}\n", **{"self": self})
    
    
    tasks = []

    for rtr in rtr_list:
        rh = testbed.get_handle(resource=rtr)
        task_name = f"{rtr}_clean_config"
        cmds =["load override /var/tmp/baseline-config.conf",'commit']
        parallel.create_task(f"task={rtr}_clean_config", "Run Event", "ON CONFIG", f"command={cmds}", f"device={rh}", f"timeout={400}")
        tasks.append(task_name)

    try:
        parallel.run_in_parallel(f"tasks={tasks}")
    except Exception as e:
        LLOG(
            level="ERROR",
            message=f"Failed to load the LRM configuration on {rtr_list}: {str(e)}\nAborting the Longevity Test.\n",
            **{"self": self}
        )
        longevity_load_rtr_test_config(**{"self": self})
        raise RuntimeError(f"[ Fail ] Failed to load the LRM configuration on {rtr_list}: {str(e)}. Aborting the Longevity Test.") from e

    LLOG(message=f"LRM Baseline Config loaded on {rtr_list}\n", **{"self": self})



def LONGEVITY_REBOOT_ROUTERS(rtr_list, **kwargs):
    self = kwargs.get("self")
    tasks = [f"task_{rtr}_reboot" for rtr in rtr_list]
    
    for rtr, task_name in zip(rtr_list, tasks):
        rh = testbed.get_handle(resource=rtr)
        parallel.append_to_task(f"task={task_name}")
        parallel.create_task(f"task={task_name}", "Reboot Device", rh, f"wait={540}")

    LLOG(message=f"Rebooting Longevity Routers: {', '.join(rtr_list)}\n", **{"self": self})

    try:
        parallel.run_in_parallel(f"tasks={tasks}")
    except Exception:
        LLOG(message=f"Failed to reboot routers: {', '.join(rtr_list)}.\n", level="ERROR", **{"self": self})
        raise

    LLOG(message=f"Routers {', '.join(rtr_list)} rebooted successfully.\n", **{"self": self})



def longevity_test_preparation(rtr_list, **kwargs):
    self = kwargs.get('self')
    
    if not rtr_list:
        LLOG(level='WARN', message=f"No Routers defined with 'longevity_tag'. Skipping Passive Longevity Test Case\n", **{"self": self})
        return
    
    LLOG(message=f"**** STEP#1: Longevity DUT List: {rtr_list}\n", **{"self": self})
    LLOG(message=f"**** STEP#2: Save Current Router Test Configuration\n", **{"self": self})
    longevity_save_rtr_test_config(rtr_list, **{"self": self})
    LSLEEP(15, **{"self": self})
    
    is_load_lrm_config = tv.get('uv-longevity-skip-lrm-baseline-step', 0) == 0
    lrm_pre_kw = locals().get('run_kw_before_lrm_load_config', [])
    
    if lrm_pre_kw and is_load_lrm_config:
        try:
            pass  # Placeholder for executing lrm_pre_kw
            kw1_result = 'PASS'
        except Exception as e:
            kw1_result = 'FAIL'
            LLOG(level='WARN', message=f"Failure Reason for {lrm_pre_kw}: {str(e)}\n", **{"self": self})
    
    self.is_load_lrm_config = is_load_lrm_config
    if self.is_load_lrm_config:
        LLOG(message=f"**** STEP#3: Load LRM Baseline Config On {rtr_list}\n", **{"self": self})
        longevity_load_lrm_baseline_config(rtr_list, **{"self": self})
    
    lrm_post_kw = locals().get('run_kw_after_lrm_load_config', [])
    
    if lrm_post_kw and self.is_load_lrm_config:
        try:
            pass  # Placeholder for executing lrm_post_kw
            kw2_result = 'PASS'
        except Exception as e:
            kw2_result = 'FAIL'
            LLOG(level='WARN', message=f"Failure Reason for {lrm_post_kw}: {str(e)}\n", **{"self": self})
    
    if self.is_load_lrm_config:
        LSLEEP(tv.get('uv-longevity-post-lrm-baseline-wait-time', 1800), **{"self": self})
    
  
    if tv.get('uv-longevity-skip-reboot-router', 0) == 0:
        LLOG(message=f"**** STEP#4: Rebooting Routers: {rtr_list}\n", **{"self": self})
        LONGEVITY_REBOOT_ROUTERS(rtr_list, **{"self": self})
        LSLEEP(tv.get('uv-longevity-post-reboot-router-wait-time', 1800), **{"self": self})


def longevity_get_task_block_names(rtr, **kwargs):
    self = kwargs.get('self')
    return mts.get(
        info='get_task_block_names', 
        devices=rtr, 
        file='/volume/regressions/toby/test-suites/pdt/lib/longevity/dev_branch/longevity.ve.yaml'
    )


def longevity_get_task_malloc_names(rtr, **kwargs):
    self = kwargs.get('self')
    return mts.get(
        info='get_task_malloc_names', 
        devices=rtr, 
        file='/volume/regressions/toby/test-suites/pdt/lib/longevity/dev_branch/longevity.ve.yaml'
    )


def longevity_te_reg_task_memory_detail(rtr_list, **kwargs):
    self = kwargs.get('self')
    for rtr in rtr_list:
        longevity_te_reg_task_memory_detail_on_rtr(rtr, **{"self": self})


def longevity_te_reg_task_memory_detail_on_rtr(rtr, **kwargs):
    """
    Registers task memory detail telemetry for a given router.

    Arguments:
        rtr - Router tag

    Return: None
    """
    self = kwargs.get('self')
    # -----------------------------------------------
    # Get the list of task block names
    # -----------------------------------------------
    tb_names = longevity_get_task_block_names(rtr, **kwargs)
    

    # -----------------------------------------------
    # Get the task block threshold values
    # -----------------------------------------------
    tb_alloc_bytes_thld = tv.get('uv-tb-alloc-bytes-threshold', 20000000)
    re_tb_alloc_bytes = f"current is not None and ((current - snapshot) < {tb_alloc_bytes_thld})"

    # ------------------------------------------------------
    # Perform TE Registrations for task-block alloc-bytes
    # ------------------------------------------------------        
    te_dict = {
        "trace": f"{rtr}-show-task-memory-detail",
        "command": "show task memory detail",
        "dataformat": "xml",
        "node": "master",
        "controller": "master",
        "expression": re_tb_alloc_bytes,
        "resource": rtr,
        "database": True
    }

    # -----------------------------------------------
    # Register Per Task Block Parameter
    # -----------------------------------------------        
    for tb_name in tb_names:
        testbed.log(level="INFO", message=f"[INFO] Registering task block tb-alloc-bytes for {tb_name} on {rtr}", console=True)
        
        te_dict.update({
            "parameter": f"{tb_name}-tb-alloc-bytes",
            "xpath": f"//task-memory-allocator-report/task-block-list/task-block[tb-name='{tb_name}']/tb-alloc-bytes"
        })

        #lrm_baseline.register(**te_dict)
        
        #te_longevity_test.register(**te_dict)

        testbed.log(level="INFO", message=f"[INFO] Registered task block tb-alloc-bytes for {tb_name} on {rtr}", console=True)

    # -----------------------------------------------
    # Get the list of task malloc names
    # -----------------------------------------------
    tm_names = longevity_get_task_malloc_names(rtr)

    # -----------------------------------------------
    # Get the task malloc threshold values
    # -----------------------------------------------
    tm_alloc_bytes_thld = tv.get('uv-tm-alloc-bytes-threshold', 20000000)
    re_tm_alloc_bytes = f"current is not None and ((current - snapshot) < {tm_alloc_bytes_thld})"
    te_dict["expression"] = re_tm_alloc_bytes  

    # -----------------------------------------------
    # Register Per Task Malloc Parameter
    # -----------------------------------------------        
    for tm_name in tm_names:
        testbed.log(level="INFO", message=f"[INFO] Registering task malloc tm-alloc-bytes for {tm_name} on {rtr}", console=True)
        
        te_dict.update({
            "parameter": f"{tm_name}-tm-alloc-bytes",
            "xpath": f"//task-memory-malloc-usage-report/task-malloc-list/task-malloc[tm-name='{tm_name}']/tm-alloc-bytes"
        })

        #lrm_baseline.register(**te_dict)
        #te_longevity_test.register(**te_dict)

        testbed.log(level="INFO", message=f"[INFO] Registered task malloc tm-alloc-bytes for {tm_name} on {rtr}", console=True)
        


 

def evo_get_node_list(rtr, **kwargs):
    self = kwargs.get('self')
    rh = testbed.get_handle(resource=rtr)
    xml_out = device_utils.execute_cli_command_on_device(device=rh, command='show system nodes | display xml', pattern='Toby.*>$')
    return xml_utils.get_elements_texts(xml_out, 'system-nodes-info/system-nodes-info-entry[system-node-info-node-status="online, apps-ready"]/system-node-info-node-name')


def evo_is_chassis_form_factor_fixed(rtr, **kwargs):
    self = kwargs.get('self')
    rh = testbed.get_handle(resource=rtr)
    cmd_resp = device_utils.execute_shell_command_on_device(device=rh, timeout=600, command='/usr/sbin/nodeinfo --getSystemType', pattern='Toby.*%$')
    return str(cmd_resp) == 'SingleNode'

def longevity_te_reg_re_system_memory(rtr, node, **kwargs):
    self = kwargs.get('self', None)
    sys_mem_def_tol = tv.get('uv-evo-system-mem-def-tol', 10)
    parameter_list = ['system-memory-used', 'system-memory-free']
    rh = testbed.get_handle(resource=rtr)
    
    for parameter in parameter_list:
        tolerance = tv.get(f'uv-evo-re-{parameter}-tol', sys_mem_def_tol)
        sys_dict = {
            'resource': rtr,
            'trace': f"{node}-show-sys-mem",
            'parameter': f"{node}-{parameter}",
            'command': f"show system memory node {node}",
            'dataformat': 'xml',
            'xpath': f"//system-memory-summary-information/{parameter}",
            'node': 'master',
            'controller': 'master',
            'database': True
        }
        if parameter == 'system-memory-free':
            sys_dict['expression'] = 'current >= snapshot'
        if parameter == 'system-memory-used':
            sys_dict['tolerance'] = tolerance
        
        testbed.log("INFO: Processing system memory stats", display_log=True)
        #lrm_baseline.register(**sys_dict)  
        #te_longevity_test.register(**sys_dict)
        testbed.log(f"INFO: [${rtr}] [${node}] Registered show system memory - ${parameter}",  display_log=True)

def EVO_Get_Anomalies_Check_App_List(rtr, node, **kwargs):
    self = kwargs.get('self', None)
    rh = testbed.get_handle(resource=rtr)
    xml_out = device_utils.execute_cli_command_on_device(
        device=rh, 
        command=f"show platform object-info anomalies node {node} summary | display xml", 
        pattern='Toby.*>$'
    )
    return []  # TODO: Parse xml_out to extract app_list

def longevity_te_reg_platform_anomalies(rtr, node, **kwargs):
    """
    Keyword that makes TE Registrations for Anomalies summary for the given node.

    Arguments:
        rtr - Router Tag, Ex: r0
        node - RE node name, Ex: re0 
    Return: None

    Keyword Usage:
        longevity_te_reg_platform_anomalies("r0", "re1", self)
    """
    
    self = kwargs.get('self', None)
    
    #----------------
    # Get Handle
    #----------------        
    rh = testbed.get_handle(resource=rtr)

    #------------------------------
    # Get App list on the node
    #------------------------------
    app_list = EVO_Get_Anomalies_Check_App_List(rtr, node)

    #--------------------------------
    # Perform app-wise registration.
    #--------------------------------    
    exp = "current == 0"
    
    te_dict = {
        "resource": rtr,
        "trace": f"{rtr}-{node}-anomalies",
        "command": f"show platform object-info anomalies summary node {node}",
        "dataformat": "xml",
        "node": "master",
        "controller": "master",
        "expression": exp,
        "database": True
    }

    #--------------------------------
    # TE Registrations
    #--------------------------------    
    for app in app_list:
        testbed.log(f"INFO: [{rtr}] [{node}] Registering {app} for Anomalies BQ complete-deleted", display_log=True)
        
        te_dict.update({
            "parameter": f"{node}-{app}-anomalies-complete-deleted",
            "xpath": f'//object-info-anomalies-summaries/object-info-anomalies-summary[object-application="{app}"]/object-complete-deleted'
        })

        #lrm_baseline.register(**te_dict)
        #te_longevity_test.register(**te_dict)

        testbed.log(f"INFO: [{rtr}] [{node}] Registered {app} for Anomalies BQ complete-deleted", display_log=True)
        testbed.log(f"INFO: [{rtr}] [{node}] Registering {app} for Anomalies Publish publish-deleted", display_log=True)

        te_dict.update({
            "parameter": f"{node}-{app}-anomalies-unpublist-undeleted",
            "xpath": f'//object-info-anomalies-summaries/object-info-anomalies-summary[object-application="{app}"]/object-unpublish-undeleted'
        })

        #lrm_baseline.register(**te_dict)
        #te_longevity_test.register(**te_dict)

        testbed.log(f"INFO: [{rtr}] [{node}] Registered {app} for Anomalies Publish publish-deleted", display_log=True)


def evo_re_memory_used_te_registration(rtr, node, **kwargs):
    """
    Keyword to register memory used from 'show system process extensive' for RE.

    Arguments:
        rtr - Router tag, e.g., "r0"
        node - Node ID of the RE, e.g., "re0"

    Return: None

    Keyword Usage:
        evo_re_memory_used_te_registration("r0", "re1", self)
    """
    
    self = kwargs.get('self', None)
    
    #----------------------------------------------------
    # Get Router Handle
    #----------------------------------------------------    
    rh = testbed.get_handle(resource=rtr)

    #----------------------------------------------------
    # Get the tolerance
    #----------------------------------------------------    
    tolerance = tv.get('uv-evo-re-system-mem-used-tol', 15)

    #------------------------------------------------
    # Perform Registration Per Parameter
    #------------------------------------------------    
    testbed.log(f"INFO: [{rtr}] [{node}] Registering with system memory used", display_log=True)

    te_dict = {
        "resource": rtr,
        "trace": f"top-{node}-sys-mem-used",
        "parameter": f"{node}-sys-mem-used",
        "command": f'show system processes extensive node {node} | match "iB Mem"',
        "dataformat": "text",
        "regexp": r"(\d+)\s+used",
        "node": "master",
        "controller": "master",
        "tolerance": tolerance,
        "database": True
    }

    #lrm_baseline.register(**te_dict)
    #te_longevity_test.register(**te_dict)

    testbed.log(f"INFO: [{rtr}] [{node}] Registered with system memory used", display_log=True)


def evo_get_re_slot_ha_state(rtr, node, **kwargs):
    self = kwargs.get('self', None)
    rh = testbed.get_handle(resource=rtr)
    slot_id = [match.group(1) for match in re.finditer(r're(\d+)', node)] or []
    if not slot_id:
        return None  # No slot found
    
    xml_out = device_utils.execute_cli_command_on_device(
        device=rh, 
        command=f"show chassis routing-engine {slot_id[0]} | display xml", 
        pattern='Toby.*>$'
    )
    return xml_utils.get_element_text(xml_out, f"route-engine-information/route-engine[slot='{slot_id[0]}']/mastership-state").lower()

def evo_re_proc_meminfo_te_registration(rtr, node, **kwargs):
    """
    Keyword to register 'cat /proc/meminfo' parameters for RE.

    Arguments:
        rtr - Router tag, e.g., "r0"
        node - Node ID of the RE, e.g., "re0"

    Return: None

    Keyword Usage:
        evo_re_proc_meminfo_te_registration("r0", "re1", self)
    """
    
    self = kwargs.get('self', None)
    
    #--------------------------------------
    # Default Tolerance Values
    #--------------------------------------
    sys_mem_def_tol = tv.get('uv-evo-system-mem-def-tol', 10)

    #----------------------------------------------------
    # Create a list of parameters to be registered    
    #----------------------------------------------------
    parameter_list = ["MemFree"]

    #----------------------------------------------------
    # Get Router Handle
    #----------------------------------------------------
    rh = testbed.get_handle(resource=rtr)

    #----------------------------------------------------
    # Connect to the Node Controller
    #----------------------------------------------------
    device_utils.set_current_controller(rh, controller=node)

    #----------------------------------------------------
    # Get the node state
    #----------------------------------------------------
    node_state = evo_get_re_slot_ha_state(rtr, node)

    #------------------------------------------------
    # Perform Registration Per Parameter
    #------------------------------------------------
    for parameter in parameter_list:
        testbed.log(f"INFO: [{rtr}] [{node}] Registering cat /proc/meminfo - {parameter}", display_log=True)

        expression = "current >= snapshot"

        te_dict = {
            "resource": rtr,
            "trace": f"{node}-proc-meminfo",
            "parameter": f"{node}-{parameter}",
            "mode": "shell",
            "command": "cat /proc/meminfo",
            "dataformat": "text",
            "regexp": fr"{parameter}:\s+(\d+)",
            "node": node_state,
            "controller": node_state,
            "expression": expression,
            "database": True
        }

        #lrm_baseline.register(**te_dict)
        #te_longevity_test.register(**te_dict)

        testbed.log(f"INFO: [{rtr}] [{node}] Registered cat /proc/meminfo - {parameter}", display_log=True)

    #----------------------------------------------------
    # Connect to the Master
    #----------------------------------------------------
    device_utils.set_current_controller(rh, controller="master")


def longevity_te_reg_sys_mem_stats_jemalloc_stats_on_rtr(rtr, node, **kwargs):
    """
    Registers system memory statistics (jemalloc stats) on a router if version check passes.

    Arguments:
        rtr - Router tag, e.g., "r0"
        node - Node ID, e.g., "re0"

    Return: None
    """

    self = kwargs.get('self', None)
    
    #-----------------------------------------------
    # Get the router handle
    #-----------------------------------------------
    rh = testbed.get_handle(resource=rtr)

    #-----------------------------------------------
    # Check the software version
    #-----------------------------------------------
    rtr_ver_chk = utils.check_version(device=rh, version="22.3")

    if not rtr_ver_chk:
        testbed.log(f"INFO: Minimum version check not matched, skipping LONGEVITY SYS MEM STATS JEMALLOC STATS ON RTR registration", display_log=True)
        return

    #-----------------------------------------------
    # Get the list of applications
    #-----------------------------------------------
    xml_out = device_utils.execute_cli_command_on_device(
        device=rh,
        command=f"show system memory statistics jemalloc-stats node {node} | display xml",
        timeout=600,
        pattern="Toby.*>$"
    )

    app_list = xml_utils.get_elements_texts(xml_out, ".//system-memory-statistics-jemalloc/system-memory-statistics-jemalloc-summary/app-name")

    #-----------------------------------------------
    # Get the jemalloc stats threshold
    #-----------------------------------------------
    tol = tv.get("uv-longevity-sys-mem-jemelloc-thr", 20)

    #------------------------------------------------------
    # Prepare TE dictionary for registration
    #------------------------------------------------------
    te_dict = {
        "trace": f"{rtr}-show-sys-mem-stat-jem-{node}",
        "command": f"show system memory statistics jemalloc-stats node {node}",
        "dataformat": "xml",
        "node": "master",
        "controller": "master",
        "tolerance": tol,
        "expression": "current <= ((100 + float(tolerance)) / 100) * snapshot",
        "resource": rtr,
        "database": True
    }

    #-----------------------------------------------
    # Register Per Parameter
    #-----------------------------------------------
    for app in app_list:
        testbed.log(f"INFO: Registering jemalloc stats for {app} on {rtr} {node}", display_log=True)

        te_dict.update({
            "parameter": f"{app}-{node}-jemalloc-stat-total_allocated",
            "xpath": f'//system-memory-statistics-jemalloc/system-memory-statistics-jemalloc-summary[app-name="{app}"]/jemalloc-stat-total_allocated'
        })

        #lrm_baseline.register(**te_dict)
        #te_longevity_test.register(**te_dict)

        testbed.log(f"INFO: Registered jemalloc stats for {app} on {rtr} {node}", display_log=True)


def evo_top_re_te_registration(rtr, node, evo_process_dict, tolerance, **kwargs):
    """
    Registers top parameters for a process on the router, including PID, SHR, RES, CPU, and memory.

    Arguments:
        rtr - Router tag, e.g., "r0"
        node - Node ID of the RE, e.g., "re0" or "re1"
        evo_process_dict - Dictionary of processes and their associated tolerance values
        tolerance - Default tolerance value

    Return: None
    """

    self = kwargs.get('self', None)
    
    cmd_timeout = tv.get('uv-cmd-timeout', '100')
    #---------------------
    # Get Router Handle
    #---------------------
    rh = testbed.get_handle(resource=rtr)

    # Set the Controller to the state
    device_utils.set_current_controller(rh, controller=node)


    # Get RE Slot State
    slot_state = evo_get_re_slot_ha_state(rtr, node)

    # Get Process List from evo_process_dict keys
    process_list = evo_process_dict.keys()

    #------------------------------------------------------------------
    # Get CPU Utilization threshold for RE Processes and expression
    #------------------------------------------------------------------
    re_process_cpu_util_thr = tv.get("uv-evo-re-process-cpu-util-thr", 50)
    re_process_cpu_util_exp = f"current <= {re_process_cpu_util_thr}"

    # Start Registering Per Process
    for process in process_list:
        # Get the Tolerance value from the dictionary
        tol_from_proc = evo_process_dict.get(process)
        tolerance1 = tol_from_proc if tol_from_proc else tolerance

        # Ensure process runs on the shell
        shell_out = device_utils.execute_shell_command_on_device(
            device=rh,
            timeout=cmd_timeout,
            command=f"top -b -n 1 | grep -w \"{process}\"$",
            pattern=r"Toby.*%$"
        )

        is_process_running = bool(re.search(f"{process}$", shell_out))

        expression1 = "current == snapshot"

        if is_process_running:
            # Register RES for the process
            testbed.log(level="INFO", message=f"\n[INFO] [{rtr}] [{node}] Registering with top RES for {process}", console=True)
            lrm_baseline.register(
                resource=rtr,
                trace=f"top-{node}-{process}",
                parameter=f"{node}-{process}-RES",
                command=f"top -b -n 1 | grep -w \"{process}\"$",
                mode="shell",
                dataformat="text",
                regexp=r"[.|\\n]*\\s*\\d+\\s+\\S+\\s+\\d+\\s+\\d+\\s+[0-9\\w+.]+\\s+([0-9.\\w+]+)\\s+[0-9\\w+.]+\\s+\\S+\\s+[0-9.]+\\s+[0-9.]+\\s+[0-9:.]+\\s+${process}$",
                node=slot_state,
                controller=slot_state,
                tolerance=tolerance1,
                thread=node,
                database=True
            )

            te_longevity_test.register(
                resource=rtr,
                trace=f"top-{node}-{process}",
                parameter=f"{node}-{process}-RES",
                command=f"top -b -n 1 | grep -w \"{process}\"$",
                mode="shell",
                dataformat="text",
                regexp=r"[.|\\n]*\\s*\\d+\\s+\\S+\\s+\\d+\\s+\\d+\\s+[0-9\\w+.]+\\s+([0-9.\\w+]+)\\s+[0-9\\w+.]+\\s+\\S+\\s+[0-9.]+\\s+[0-9.]+\\s+[0-9:.]+\\s+${process}$",
                node=slot_state,
                controller=slot_state,
                tolerance=tolerance1,
                thread=node,
                database=True
            )

            testbed.log(level="INFO", message=f"\n[INFO] [{rtr}] [{node}] Registered with top RES for {process}", console=True)

            # Register SHR for the process (Repeat similar process for SHR, PID, CPU, and MEM)
            testbed.log(level="INFO", message=f"\n[INFO] [{rtr}] [{node}] Registering with top SHR for {process}", console=True)
            lrm_baseline.register(
                resource=rtr,
                trace=f"top-{node}-{process}",
                parameter=f"{node}-{process}-SHR",
                command=f"top -b -n 1 | grep -w \"{process}\"$",
                mode="shell",
                dataformat="text",
                regexp=r"[.|\\n]*\\s*\\d+\\s+\\S+\\s+\\d+\\s+\\d+\\s+[0-9\\w+.]+\\s+[0-9.\\w+]+\\s+([0-9\\w+.]+)\\s+\\S+\\s+[0-9.]+\\s+[0-9.]+\\s+[0-9:.]+\\s+${process}$",
                node=slot_state,
                controller=slot_state,
                tolerance=tolerance1,
                thread=node,
                database=True
            )

            te_longevity_test.register(
                resource=rtr,
                trace=f"top-{node}-{process}",
                parameter=f"{node}-{process}-SHR",
                command=f"top -b -n 1 | grep -w \"{process}\"$",
                mode="shell",
                dataformat="text",
                regexp=r"[.|\\n]*\\s*\\d+\\s+\\S+\\s+\\d+\\s+\\d+\\s+[0-9\\w+.]+\\s+[0-9.\\w+]+\\s+([0-9\\w+.]+)\\s+\\S+\\s+[0-9.]+\\s+[0-9.]+\\s+[0-9:.]+\\s+${process}$",
                node=slot_state,
                controller=slot_state,
                tolerance=tolerance1,
                thread=node,
                database=True
            )

            testbed.log(level="INFO", message=f"\n[INFO] [{rtr}] [{node}] Registered with top SHR for {process}", console=True)

            # Similarly register PID, CPU, and MEM using the same steps...

    # Set the controller to master
    device_utils.set_current_controller(rh, controller="master")

def longevity_te_reg_sdb_live_objects_on_rtr(rtr, node, **kwargs):
    """
    Registers SDB Live Objects statistics on the router.

    Arguments:
        rtr - Router tag, e.g., "r0"
        node - Node ID, e.g., "re0"

    Return: None
    """
    self = kwargs.get('self', None)
    #-----------------------------------------------
    # Get the SDB Live Objects Threshold
    #-----------------------------------------------
    tol = tv.get("uv-longevity-sdb-live-obj-thr", 20)

    #------------------------------------------------------
    # Prepare TE dictionary for registration
    #------------------------------------------------------
    te_dict = {
        "trace": f"{rtr}-sh-plat-dist-stat-sum-{node}",
        "command": f"show platform distributor statistics summary {node}",
        "parameter": f"{rtr}-{node}-sdb-live-objs",
        "dataformat": "xml",
        "xpath": "//distributor_statistics_summary_list/distributor_statistics_summary/dist_stats_sdb_live_objs",
        "node": "master",
        "controller": "master",
        "tolerance": tol,
        "expression": "current <= ((100 + float(tolerance)) / 100) * snapshot",
        "resource": rtr,
        "database": True
    }

    #------------------------------------------------------
    # Perform TE Registration
    #------------------------------------------------------
    lrm_baseline.register(**te_dict)
    te_longevity_test.register(**te_dict)




def evo_re_process_fd_te_registration(rtr, node, evo_process_dict, tolerance, **kwargs):
    """
    Registers FD for a process on the router, checking if the process is running and registering 
    its file descriptor count for monitoring.

    Arguments:
        rtr - Router tag, e.g., "r0"
        node - Node ID of the RE, e.g., "re0" or "re1"
        evo_process_dict - Dictionary of processes and their associated tolerance values
        tolerance - Default tolerance value

    Return: None
    """

    self = kwargs.get('self', None)
    
    cmd_timeout = tv.get('uv-cmd-timeout', '100')
    # Get Router Handle
    rh = testbed.get_handle(resource=rtr)

    # Set the Controller to the state
    device_utils.set_current_controller(rh, controller=node)

    # Get RE Slot State
    slot_state = evo_get_re_slot_ha_state(rtr, node)

    # Get Process List from evo_process_dict keys
    process_list = list(evo_process_dict.keys())

    # Start Registering Per Process
    for process in process_list:
        # Get the Tolerance value from the dictionary
        tol_from_proc = evo_process_dict.get(process)
        tolerance1 = tol_from_proc if tol_from_proc else tolerance

        # Ensure process runs on the shell
        shell_out = device_utils.execute_shell_command_on_device(
            device=rh,
            timeout=cmd_timeout,
            command=f"top -b -n 1 | grep -w \"{process}\"$",
            pattern=r"Toby.*%$"
        )

        # Extract PID using regex
        pid_matches = re.findall(r"^\s*(\d+).*?\s+" + re.escape(process) + r"$", shell_out, re.MULTILINE)
        
        # Check if PID is found
        is_process_running = bool(pid_matches)

        if is_process_running:
            pid = pid_matches[0]

            # Log registration of FD
            testbed.log(level="INFO", message=f"\n[INFO] [{rtr}] [{node}] Registering FD for {process} pid {pid}", console=True)
            
            # Register FD for the process
            lrm_baseline.register(
                resource=rtr,
                trace=f"{node}-{process}-fd",
                parameter=f"{node}-{process}-fd",
                command=f"ls /proc/{pid}/fd | wc -l",
                mode="root",
                dataformat="text",
                regexp=r"(\d+)",
                node=slot_state,
                controller=slot_state,
                tolerance=tolerance1,
                thread=node,
                database=True
            )

            te_longevity_test.register(
                resource=rtr,
                trace=f"{node}-{process}-fd",
                parameter=f"{node}-{process}-fd",
                command=f"ls /proc/{pid}/fd | wc -l",
                mode="root",
                dataformat="text",
                regexp=r"(\d+)",
                node=slot_state,
                controller=slot_state,
                tolerance=tolerance1,
                thread=node,
                database=True
            )

            # Log completion of FD registration
            testbed.log(level="INFO", message=f"\n[INFO] [{rtr}] [{node}] Registered FD for {process} pid {pid}", console=True)

    # Set the controller to master
    device_utils.set_current_controller(rh, controller="master")

    

import re

def evo_re_ps_mem_te_registration(rtr, node, evo_process_dict, ps_mem_def_tol, **kwargs):
    """
    Registers ps_mem with TE, ensuring processes are running and monitoring memory usage.

    Arguments:
        rtr - Router tag, e.g., "r0"
        node - Node ID of the RE, e.g., "re0" or "re1"
        evo_process_dict - Dictionary of processes and their associated tolerance values
        ps_mem_def_tol - Default tolerance for memory usage

    Return: None
    """

    self = kwargs.get('self', None)
    
    cmd_timeout = tv.get('uv-cmd-timeout', '100')
    
    
    # Set the Controller to the current RE
    rh = testbed.get_handle(resource=rtr)

    # Connect to current controller
   
    device_utils.set_current_controller(rh, controller=node)

    # Get RE Slot State
    slot_state = evo_get_re_slot_ha_state(rtr, node)

    # Copy ps_mem.py file to the router
    ps_mem_loc = tv.get('uv-evo-ps-mem-location', "/volume/regressions/toby/test-suites/pdt/lib/longevity/ps_mem.py")
    cmd_resp = host_utils.upload_file(rh, local_file=ps_mem_loc, remote_file="~regress/ps_mem.py", protocol="scp", user="regress", password="MaRtInI")

    if not cmd_resp:
        testbed.log(level="WARN", message=f"\nFailed to copy ps_mem.py file to {rtr}\n", console=True)
        device_utils.set_current_controller(rh, controller="master")
        return

    # Register for total memory used
    ps_mem_tot_tol = tv.get('uv-evo-psmem-total-mem-tol', 10)
    testbed.log(level="INFO", message=f"\n[INFO] [{rtr}] [{node}] Registering with ps_mem total memory used", console=True)

    lrm_baseline.register(
        resource=rtr,
        trace=f"psmem-{node}-total-mem",
        parameter=f"psmem-{node}-total-mem",
        command="python3 /var/home/regress/ps_mem.py -t",
        mode="root",
        dataformat="text",
        regexp=r"(\d+)",
        node=slot_state,
        controller=slot_state,
        tolerance=ps_mem_tot_tol,
        database=True
    )

    te_longevity_test.register(
        resource=rtr,
        trace=f"psmem-{node}-total-mem",
        parameter=f"psmem-{node}-total-mem",
        command="python3 /var/home/regress/ps_mem.py -t",
        mode="root",
        dataformat="text",
        regexp=r"(\d+)",
        node=slot_state,
        controller=slot_state,
        tolerance=ps_mem_tot_tol,
        database=True
    )

    testbed.log(level="INFO", message=f"\n[INFO] [{rtr}] [{node}] Registered with ps_mem total memory used", console=True)

    # Get Process List
    process_list = list(evo_process_dict.keys())

    # Start registering per process
    for process in process_list:
        # Get the tolerance value for the process
        tol_from_proc = evo_process_dict.get(process)
        tolerance1 = tol_from_proc if tol_from_proc else ps_mem_def_tol

        # Ensure process runs on the shell
        shell_out = device_utils.execute_shell_command_on_device(
            device=rh,
            timeout=cmd_timeout,
            command=f"top -b -n 1 | grep -w \"{process}\"$",
            pattern=r"Toby.*%$"
        )

        # Check if process is running using regex
        is_process_running = bool(re.search(rf"{process}$", shell_out))

        if is_process_running:
            # Log registration of memory used for process
            testbed.log(level="INFO", message=f"\n[INFO] [{rtr}] [{node}] Registering with ps_mem RAM Used for {process}", console=True)

            lrm_baseline.register(
                resource=rtr,
                trace=f"psmem-{node}-{process}",
                parameter=f"psmem-{node}-{process}",
                command=f"python3 /var/home/regress/ps_mem.py -d",
                mode="root",
                dataformat="text",
                regexp=r"(\?m)^\\s*\\d+.\\d+\\s+\\w+\\s+\\+\\s+\\d+.\\d+\\s+\\w+\\s+=\\s+(\\d+.\\d+\\s+\\w+)\\s+{process}\\s+\\S+",
                node=slot_state,
                controller=slot_state,
                tolerance=tolerance1,
                database=True
            )

            te_longevity_test.register(
                resource=rtr,
                trace=f"psmem-{node}-{process}",
                parameter=f"psmem-{node}-{process}",
                command=f"python3 /var/home/regress/ps_mem.py -d",
                mode="root",
                dataformat="text",
                regexp=r"(\?m)^\\s*\\d+.\\d+\\s+\\w+\\s+\\+\\s+\\d+.\\d+\\s+\\w+\\s+=\\s+(\\d+.\\d+\\s+\\w+)\\s+{process}\\s+\\S+",
                node=slot_state,
                controller=slot_state,
                tolerance=tolerance1,
                database=True
            )

            testbed.log(level="INFO", message=f"\n[INFO] [{rtr}] [{node}] Registered with ps_mem RAM Used for {process}", console=True)

    # Move the Controller Back to Master
    device_utils.set_current_controller(rh, controller=node)
    #device_utils.set_current_controller(rh, controller="master")


def evo_re_top_command_te_registration(rtr, node, **kwargs):
    """
    Registers the `top` command to monitor total zombie and stopped processes for a given RE.

    Arguments:
        rtr (str): Router tag, e.g., "r0"
        node (str): Node ID of the RE, e.g., "re0" or "re1"

    Returns:
        None
    """

    self = kwargs.get('self', None)
    
    cmd_timeout = tv.get('uv-cmd-timeout', '100')
    
    # Create a list of parameters to be registered
    parameter_list = ["zombie", "stopped"]

    # Get Router Handle
    rh = testbed.get_handle(resource=rtr)

    # Connect to the Node Controller
    device_utils.set_current_controller(rh, controller=node)
    #device_utils.set_current_controller(rh, controller=node)

    # Get the node state
    node_state = evo_get_re_slot_ha_state(rtr, node)

    # Perform Registration Per Parameter
    for parameter in parameter_list:
        testbed.log(level="INFO", message=f"\n[INFO] [{rtr}] [{node}] Registering top - {parameter}", console=True)

        # Define the expression for evaluation
        expression = "current <= snapshot"

        lrm_baseline.register(
            resource=rtr,
            trace=f"{node}-top",
            parameter=f"{node}-{parameter}",
            mode="shell",
            command="top -bn1 | head -n 7",
            dataformat="text",
            regexp=rf"(\d+)\s+{parameter}",
            node=node_state,
            controller=node_state,
            expression=expression,
            database=True
        )

    # Connect back to the Master Controller
    device_utils.set_current_controller(rh, controller="master")

def evo_fpc_show_system_memory_te_registration(rtr, node, **kwargs):
    """Checks system memory usage and free space using show system memory command."""
    
    self = kwargs.get('self', None)
    sys_mem_def_tol = tv.get('uv-evo-system-mem-def-tol', 10)
    parameter_list = ['system-memory-used', 'system-memory-free']
    rh = testbed.get_handle(resource=rtr)

    testbed.log("INFO: Checking system memory parameters.", display_log=True)

    for parameter in parameter_list:
        tolerance = tv.get(f'uv-evo-fpc-{parameter}-tol', sys_mem_def_tol)
        expression = 'current >= snapshot'
        
        sys_dict = {
            'resource': rtr,
            'trace': f"{node}-show-sys-mem",
            'parameter': f"{node}-{parameter}",
            'command': f"show system memory node {node}",
            'dataformat': 'xml',
            'xpath': f"//system-memory-summary-information/{parameter}",
            'node': 'master',
            'controller': 'master',
            'database': True
        }

        if parameter == 'system-memory-free':
            sys_dict.update({'expression': expression})
        else:
            sys_dict.update({'tolerance': tolerance})

        # TODO: Implement system memory evaluation based on sys_dict
        
        testbed.log(f"INFO: Completed memory check for {parameter}.", display_log=True)


def evo_fpc_memory_used_te_registration(rtr, node, **kwargs):
    """Checks FPC memory usage tolerance."""
    
    self = kwargs.get('self', None)
    rh = testbed.get_handle(resource=rtr)
    tolerance = tv.get('uv-evo-fpc-system-mem-used-tol', 15)

    testbed.log("INFO: Checking FPC memory usage.", display_log=True)

    # TODO: Implement logic for checking memory usage

    testbed.log("INFO: FPC memory usage check completed.", display_log=True)


def evo_fpc_proc_meminfo_te_registration(rtr, node):
    """
    Registers `cat /proc/meminfo` parameters for an FPC.

    Arguments:
        rtr (str): Router tag, e.g., "r0"
        node (str): Node ID of the FPC, e.g., "fpc0" or "fpc1"

    Returns:
        None
    """

    # Default Tolerance Value
    sys_mem_def_tol = tv.get("uv-evo-system-mem-def-tol", default=10)

    # List of parameters to be registered
    parameter_list = ["MemFree"]

    # Get Router Handle
    rh = testbed.get_handle(resource=rtr)

    # Perform Registration Per Parameter
    for parameter in parameter_list:
        testbed.log(level="INFO", message=f"\n[INFO] [{rtr}] [{node}] Registering cat /proc/meminfo - {parameter}", console=True)

        # Get Tolerance Value
        tolerance = tv.get(f"uv-evo-fpc-{parameter}-tol", sys_mem_def_tol)

        # Expression for evaluation
        expression = "current >= snapshot"

        # Command to fetch memory info from the FPC
        command = f"chvrf iri ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR root@{node} cat /proc/meminfo"

        # Register with lrm_baseline
        lrm_baseline.register(
            resource=rtr,
            trace=f"{node}-proc-meminfo",
            parameter=f"{node}-{parameter}",
            mode="root",
            command=command,
            dataformat="text",
            regexp=rf"{parameter}:\s+(\d+)",
            node="master",
            controller="master",
            expression=expression,
            database=True
        )

        # Register with longevity_test
        te_longevity_test.register(
            resource=rtr,
            trace=f"{node}-proc-meminfo",
            parameter=f"{node}-{parameter}",
            mode="root",
            command=command,
            dataformat="text",
            regexp=rf"{parameter}:\s+(\d+)",
            node="master",
            controller="master",
            expression=expression,
            database=True
        )

        testbed.log(level="INFO", message=f"\n[INFO] [{rtr}] [{node}] Registered cat /proc/meminfo - {parameter}", console=True)



def evo_top_fpc_te_registration(rtr, node, evo_process_dict, tolerance, **kwargs):
    """
    Registers top parameters for a process from a given FPC, including PID, SHR, RES, CPU, and memory.

    Arguments:
        rtr - Router tag, e.g., "r0"
        node - Node ID of the FPC, e.g., "fpc0"
        evo_process_dict - Dictionary of processes and their associated tolerance values
        tolerance - Default tolerance value

    Return: None
    """

    self = kwargs.get('self', None)
    # Get Router Handle
    rh = testbed.get_handle(resource=rtr)

    # Get FPC Slot ID
    fpc_id_match = re.findall(r"fpc(\d+)", node)
    fpc_id = fpc_id_match[0] if fpc_id_match else None

    # Get Process List from evo_process_dict keys
    process_list = list(evo_process_dict.keys())

    # Get CPU Utilization threshold for FPC Processes and expression
    fpc_process_cpu_util_thr = tv.get("uv-evo-fpc-process-cpu-util-thr", 50)
    fpc_process_cpu_util_exp = "current <= snapshot"

    # Start Registering Per Process
    for process in process_list:
        # Get the Tolerance value from the dictionary
        tol_from_proc = evo_process_dict.get(process)
        tolerance1 = tol_from_proc if tol_from_proc else tolerance

        # Ensure process runs on the shell
        shell_out = device_utils.execute_shell_command_on_device(
            device=rh,
            timeout=cmd_timeout,
            command=f"chvrf iri ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
                    f"-o LogLevel=ERROR -t root@{node} top -b -n 1 | grep -w \"{process}\" | grep -v \"closed\"",
            pattern=r"Toby.*%$"
        )

        is_process_running = bool(re.search(fr"{process}$", shell_out))

        expression1 = "current == snapshot"

        if is_process_running:
            testbed.log(f"\n[INFO] [{rtr}] [{node}] Registering PID of {process}", console=True)

            # Register PID
            for registry in (lrm_baseline, longevity_test):
                registry.register(
                    resource=rtr,
                    trace=f"top-{node}-{process}",
                    parameter=f"{node}-{process}-PID",
                    command=f"chvrf iri ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
                            f"-o LogLevel=ERROR -t root@fpc{fpc_id} top -b -n 1 | grep -w \"{process}\" | grep -v \"closed\"",
                    mode="shell",
                    dataformat="text",
                    regexp=r"[.|\n]*\s*(\d+)\s+\S+\s+\d+\s+\d+\s+[0-9.\w+]+\s+[0-9.\w+]+\s+[0-9.\w+]+\s+\S+\s+\d+.\d+\s+\d+.\d+\s+[0-9.:]+\s+" + process,
                    node="master",
                    controller="master",
                    expression=expression1,
                    interval=te_interval,
                    database=True
                )

            testbed.log(f"\n[INFO] [{rtr}] [{node}] Registered PID of {process}", console=True)

            # Register RES, SHR, CPU, MEM
            for param, regex, exp in [
                ("RES", r"[.|\n]*\s*\d+\s+\S+\s+\d+\s+\d+\s+[0-9.\w+]+\s+([0-9.\w+]+)\s+[0-9.\w+]+\s+\S+\s+\d+.\d+\s+\d+.\d+\s+[0-9.:]+\s+" + process, None),
                ("SHR", r"[.|\n]*\s*\d+\s+\S+\s+\d+\s+\d+\s+[0-9.\w+]+\s+[0-9.\w+]+\s+([0-9.\w+]+)\s+\S+\s+\d+.\d+\s+\d+.\d+\s+[0-9.:]+\s+" + process, None),
                ("CPU", r"[.|\n]*\s*\d+\s+\S+\s+\d+\s+\d+\s+[0-9\w+.]+\s+[0-9.\w+]+\s+[0-9\w+.]+\s+\S+\s+([\d+.]+)\s+[0-9.]+\s+[0-9:.]+\s+" + process, fpc_process_cpu_util_exp),
                ("MEM", r"[.|\n]*\s*\d+\s+\S+\s+\d+\s+\d+\s+[0-9\w+.]+\s+[0-9.\w+]+\s+[0-9\w+.]+\s+\S+\s+[\d+.]+\s+([\d+.]+)\s+[0-9:.]+\s+" + process, None),
            ]:
                testbed.log(f"\n[INFO] [{rtr}] [{node}] Registering top {param} of {process}", console=True)

                for registry in (lrm_baseline, longevity_test):
                    registry.register(
                        resource=rtr,
                        trace=f"top-{node}-{process}",
                        parameter=f"{node}-{process}-{param}",
                        command=f"chvrf iri ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
                                f"-o LogLevel=ERROR -t root@fpc{fpc_id} top -b -n 1 | grep -w \"{process}\" | grep -v \"closed\"",
                        mode="shell",
                        dataformat="text",
                        regexp=regex,
                        node="master",
                        controller="master",
                        expression=exp if param == "CPU" else None,
                        tolerance=tolerance1 if param in ["RES", "SHR", "MEM"] else None,
                        interval=te_interval,
                        database=True
                    )

                testbed.log(f"\n[INFO] [{rtr}] [{node}] Registered top {param} of {process}", console=True)



def evo_fpc_process_fd_te_registration(rtr, node, evo_process_dict, tolerance, **kwargs):
    """
    Registers FD for a process on the FPC, checking if the process is running and registering 
    its file descriptor count for monitoring.

    Arguments:
        rtr - Router tag, e.g., "r0"
        node - Node ID of the FPC, e.g., "fpc0"
        evo_process_dict - Dictionary of processes and their associated tolerance values
        tolerance - Default tolerance value

    Return: None
    """

    self = kwargs.get('self', None)
    
    # Get Router Handle
    rh = testbed.get_handle(resource=rtr)

    # Get Process List from evo_process_dict keys
    process_list = list(evo_process_dict.keys())

    # Start Registering Per Process
    for process in process_list:
        # Get the Tolerance value from the dictionary
        tol_from_proc = evo_process_dict.get(process)
        tolerance1 = tol_from_proc if tol_from_proc else tolerance

        # Ensure process runs on the shell
        device_utils.switch_to_superuser(rh)

        shell_out = device_utils.execute_shell_command_on_device(
            device=rh,
            timeout=cmd_timeout,
            command=f"chvrf iri ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
                    f"-o LogLevel=ERROR -t root@{node} top -b -n 1 | grep -w \"{process}\" | grep -v \"closed\"",
            pattern=r"Toby.*%$"
        )

        # Extract PID using regex
        pid_matches = re.findall(r"^\s*(\d+).*?\s+" + re.escape(process) + r"$", shell_out, re.MULTILINE)

        # Check if PID is found
        is_process_running = bool(pid_matches)

        if is_process_running:
            pid = pid_matches[0]

            # Log registration of FD
            testbed.log(f"\n[INFO] [{rtr}] [{node}] Registering FD for {process} pid {pid}", console=True)

            # Register FD for the process
            for registry in (lrm_baseline, longevity_test):
                registry.register(
                    resource=rtr,
                    trace=f"{node}-{process}-fd",
                    parameter=f"{node}-{process}-fd",
                    command=f"ls /proc/{pid}/fd | wc -l",
                    mode="root",
                    dataformat="text",
                    regexp=r"(\d+)",
                    node="master",
                    controller="master",
                    tolerance=tolerance1,
                    database=True
                )

            # Log completion of FD registration
            testbed.log(f"\n[INFO] [{rtr}] [{node}] Registered FD for {process} pid {pid}", console=True)


import re

def evo_fpc_ps_mem_te_registration(rtr, node, evo_process_dict, ps_mem_def_tol, **kwargs):
    """
    Registers ps_mem with TE for monitoring memory usage of processes on an FPC.

    Arguments:
        rtr - Router tag, e.g., "r0"
        node - Node ID of the FPC, e.g., "fpc0"
        evo_process_dict - Dictionary of processes and their associated tolerance values
        ps_mem_def_tol - Default tolerance value

    Return: None
    """

    self = kwargs.get('self', None)
    
    # Get Router Handle
    rh = testbed.get_handle(resource=rtr)

    # Switch to Superuser
    device_utils.switch_to_superuser(rh)

    # Get File Location
    ps_mem_loc = tv.get("uv-evo-ps-mem-location", "/volume/regressions/toby/test-suites/pdt/lib/longevity/ps_mem.py")

    # Upload file to the router
    cmd_resp = Upload_File(rh, local_file=ps_mem_loc, remote_file="~regress/ps_mem.py",
                           protocol="scp", user="regress", password="MaRtInI")

    if not cmd_resp:
        testbed.log(f"\n[WARN] Failed to copy ps_mem.py file to {rtr}\n", console=True)
        device_utils.set_current_controller(rh, controller="master")
        return

    # Copy File from RE to FPC
    device_utils.execute_shell_command_on_device(
        device=rh,
        timeout=cmd_timeout,
        command=f"chvrf iri scp-internal -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
                f"-o LogLevel=ERROR /var/home/regress/ps_mem.py root@{node}:",
        pattern=r"Toby.*%$"
    )

    # Register for total memory used
    ps_mem_tot_tol = tv.get("uv-evo-psmem-total-mem-tol", 10)
    testbed.log(f"\n[INFO] [{rtr}] [{node}] Registering with ps_mem total memory used", console=True)

    for registry in (lrm_baseline, longevity_test):
        registry.register(
            resource=rtr,
            trace=f"psmem-{node}-total-mem",
            parameter=f"psmem-{node}-total-mem",
            command=f"chvrf iri ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
                    f"-o LogLevel=ERROR root@{node} python3 ps_mem.py -t",
            mode="root",
            dataformat="text",
            regexp=r"(\d+)",
            node="master",
            controller="master",
            tolerance=ps_mem_tot_tol,
            database=True
        )

    testbed.log(f"\n[INFO] [{rtr}] [{node}] Registered with ps_mem total memory used", console=True)

    # Get Process List
    process_list = list(evo_process_dict.keys())

    # Start Registering Per Process
    for process in process_list:
        # Get the Tolerance value from the dictionary
        tol_from_proc = evo_process_dict.get(process)
        tolerance1 = tol_from_proc if tol_from_proc else ps_mem_def_tol

        # Switch to Superuser
        device_utils.switch_to_superuser(rh)

        # Ensure process runs on the shell
        shell_out = device_utils.execute_shell_command_on_device(
            device=rh,
            timeout=cmd_timeout,
            command=f"chvrf iri ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
                    f"-o LogLevel=ERROR -t root@{node} top -b -n 1 | grep -w \"{process}\" | grep -v \"closed\"",
            pattern=r"Toby.*%$"
        )

        # Check if process is running
        is_process_running = bool(re.search(fr"{process}$", shell_out))

        if is_process_running:
            testbed.log(f"\n[INFO] [{rtr}] [{node}] Registering with ps_mem RAM Used for {process}", console=True)

            for registry in (lrm_baseline, longevity_test):
                registry.register(
                    resource=rtr,
                    trace=f"psmem-{node}-{process}",
                    parameter=f"psmem-{node}-{process}",
                    command=f"chvrf iri ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
                            f"-o LogLevel=ERROR -t root@{node} python3 ps_mem.py -d",
                    mode="root",
                    dataformat="text",
                    regexp=rf"^\s*\d+.\d+\s+\w+\s+\+\s+\d+.\d+\s+\w+\s+=\s+(\d+.\d+\s+\w+)\s+{process}\s+\S+",
                    node="master",
                    controller="master",
                    tolerance=tolerance1,
                    database=True
                )

            testbed.log(f"\n[INFO] [{rtr}] [{node}] Registered with ps_mem RAM Used for {process}", console=True)


def evo_fpc_top_command_te_registration(rtr, node, **kwargs):
    """
    Registers the top command to monitor total zombie and stopped processes for an FPC.

    Arguments:
        rtr - Router tag, e.g., "r0"
        node - Node ID of the FPC, e.g., "fpc1"

    Return: None
    """

    self = kwargs.get('self', None)
    
    # Create a list of parameters to be registered
    parameter_list = ["zombie", "stopped"]

    # Get Router Handle
    rh = testbed.get_handle(resource=rtr)

    # Perform Registration Per Parameter
    for parameter in parameter_list:
        testbed.log(f"\n[INFO] [{rtr}] [{node}] Registering top - {parameter}", console=True)

        # Define expression
        expression = "current <= snapshot"

        # Register the parameter with TE
        lrm_baseline.register(
            resource=rtr,
            trace=f"{node}-top",
            parameter=f"{node}-{parameter}",
            mode="shell",
            command=f"chvrf iri ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
                    f"-o LogLevel=ERROR root@{node} top -bn1 | head -n 7",
            dataformat="text",
            regexp=fr"(\d+)\s+{parameter}",
            expression=expression,
            database=True
        )



def evo_node_wise_te_registrations(rtr, evo_process_dict, node_list, **kwargs):

    self = kwargs.get('self', None)
    
    process_mem_def_tol = tv.get('uv-evo-process-mem-def-tol', 10)
    ps_mem_def_tol = tv.get('uv-evo-ps-mem-def-tol', 10)

    for node in node_list:
        tolerance = process_mem_def_tol

        is_node_re = 're' in node
        is_node_fpc = 'fpc' in node
        
        if is_node_re:
            longevity_te_reg_re_system_memory(rtr, node,**{'self':self}) # done 
            longevity_te_reg_platform_anomalies(rtr, node,**{'self':self}) # done 
            evo_re_memory_used_te_registration(rtr, node,**{'self':self})
            evo_re_proc_meminfo_te_registration(rtr, node,**{'self':self})
            #longevity_te_reg_sys_mem_stats_jemalloc_stats_on_rtr(rtr, node,**{'self':self})
            longevity_te_reg_sdb_live_objects_on_rtr(rtr, node,**{'self':self})
            evo_top_re_te_registration(rtr, node, evo_process_dict, tolerance,**{'self':self})
            evo_re_process_fd_te_registration(rtr, node, evo_process_dict, tolerance,**{'self':self})
            evo_re_ps_mem_te_registration(rtr, node, evo_process_dict, ps_mem_def_tol,**{'self':self})
            evo_re_top_command_te_registration(rtr, node,**{'self':self})
        if is_node_fpc:
            evo_fpc_show_system_memory_te_registration(rtr, node,**{'self':self})
            longevity_te_reg_platform_anomalies(rtr, node,**{'self':self})
            evo_fpc_memory_used_te_registration(rtr, node,**{'self':self})
            evo_fpc_proc_meminfo_te_registration(rtr, node,**{'self':self})
            #longevity_te_reg_sys_mem_stats_jemalloc_stats_on_rtr(rtr, node,**{'self':self})
            longevity_te_reg_sdb_live_objects_on_rtr(rtr, node,**{'self':self})
            evo_top_fpc_te_registration(rtr, node, evo_process_dict, tolerance,**{'self':self})
            evo_fpc_process_fd_te_registration(rtr, node, evo_process_dict, tolerance,**{'self':self})
            evo_fpc_ps_mem_te_registration(rtr, node, evo_process_dict, tolerance,**{'self':self})
            evo_fpc_top_command_te_registration(rtr, node,**{'self':self})
        
       

def evo_memory_te_registrations(evo_router_list, process_dict=None, **kwargs):


    """
    Registers top process SHR & RES Memory Usage for EVO routers.

    Arguments:
        evo_router_list - List of EVO routers
        process_dict - Optional dictionary of processes and their tolerances

    Return: None
    """
    self = kwargs.get('self', None)
    
    
    default_process_dict = {
        'rpd': 5, 'rpd-agent': 10, 'fibd': 5, 'arpd': 10, 'picd': 20, 'distributord': 20
    }

    for rtr in evo_router_list:
        rh = testbed.get_handle(resource=rtr)

        # Determine the source of process dictionary
        resource_data = testbed.resources.get('r0', {}).get('system', {}).get('primary', {})
        evo_process_dict = process_dict or resource_data.get('uv-processes') or \
                           resource_data.get('fv-properties', {}).get('processes'), {} or \
                           default_process_dict
                           
        

        if isinstance(evo_process_dict, tuple):
            testbed.log(level="WARN", message=f"[WARN] [{rtr}] process_dict is a tuple. Attempting to convert.", console=True)
            try:
                # Try parsing the first element if it's a valid dictionary string
                parsed_dict = ast.literal_eval(evo_process_dict[0]) if isinstance(evo_process_dict[0], str) else {}
                process_dict = parsed_dict if isinstance(parsed_dict, dict) else default_process_dict
            except (SyntaxError, ValueError):
                testbed.log(level="ERROR", message=f"[ERROR] [{rtr}] Failed to parse process_dict. Using default.", console=True)
                process_dict = default_process_dict
        elif not isinstance(evo_process_dict, dict):
            testbed.log(level="WARN", message=f"[WARN] [{rtr}] Invalid process_dict type: {type(evo_process_dict)}. Using default.", console=True)
            process_dict = default_process_dict

        evo_process_dict = process_dict.copy() if process_dict else default_process_dict
            
        evo_process_list = list(evo_process_dict.keys())
        testbed.log(level="INFO", message=f"[INFO] [{rtr}] List Of Processes Used in Data Registration = {evo_process_list}", console=True)

        # Get node list and chassis type
        node_list = evo_get_node_list(rtr, **kwargs)
        
        # Register telemetry per node
        print(f"here...{rtr}->{node_list}")
        evo_node_wise_te_registrations(rtr, evo_process_dict, node_list, **kwargs)



def get_npu_list_from_fpc(rtr, fpc, npu_to_be_monitor_list, **kwargs):
    self = kwargs.get('self', None)
    
    # Initialize and fetch resources
    testbed.log(rtr, display_log=True)
    rh = testbed.get_handle(resource=rtr)
    
    # Execute CLI command and parse the output
    cmd_out = device_utils.execute_cli_command_on_device(
        device=rh, 
        timeout=600, 
        command=f"request pfe execute target {fpc} command \"show npu memory info\"",
        pattern='Toby.*>$'
    )
    
    # Process NPU information
    fpc = fpc.upper()
    matches = re.findall(f"{fpc}:NPU\d+", cmd_out)
    npu_list = list(set(convert_to_list_arg(matches)))
    
    # Initialize NPU parameter size dictionary
    npu_parameter_size = {}

    # Monitor each parameter and update size information
    for para in npu_to_be_monitor_list:
        matches = re.findall(f"{para}\s+(\d+)", cmd_out)
        
        # Handle empty matches gracefully
        if not matches:
            testbed.log(f"'level' = WARN: {para} not found", display_log=True)
            continue
        
        # Extract and log parameter size
        size = int(float(re.findall(r'\d+$', matches[0])[0]))
        npu_parameter_size[para] = size
        testbed.log(f"{para} size converted to integer: {size}", display_log=True)
    
    testbed.log(f"NPU Parameter Sizes: {npu_parameter_size}", display_log=True)
    
    return npu_list, npu_parameter_size


def longevity_te_reg_fpc_npu_memory_info_helper(rtr, node, npu_instance, evo_npu_memory_dict, size_dict, **kwargs):
    """
    Helper function to register NPU MEMORY usage for LONGEVITY TE REG FPC NPU MEMORY INFO.

    Arguments:
        rtr - Router tag, e.g., "r0"
        node - Node ID.
        npu_instance - NPU instance name.
        evo_npu_memory_dict - Dictionary containing NPU memory utilization values.
        size_dict - Dictionary containing size-related information for NPUs.

    Return: None
    """
    self = kwargs.get('self', None)
    
    
    # Default Tolerance Value
    npu_mem_size_tol = tv.get("uv-evo-system-npu-mem-size-tol", 5)

    # Get NPU memory parameters
    evo_npu_memory_list = list(evo_npu_memory_dict.keys())

    # Get Router Handle
    rh = testbed.get_handle(resource=rtr)

    # Iterate over each parameter in the memory list
    for parameter in evo_npu_memory_list:
        testbed.log(f"\n[INFO] [{rtr}] [{node}] Registering show npu memory info - {parameter}", console=True)

        # Skip if parameter not in size_dict
        if parameter not in size_dict:
            continue

        # Get threshold value for the parameter
        threshold = evo_npu_memory_dict.get(parameter)
        expression = f"current <= {threshold} + {npu_mem_size_tol}"

        # Create TE Registration Dictionary
        sys_dict = {
            "resource": rtr,
            "trace": f"{node}-{npu_instance}-show-npu-memory-info",
            "parameter": f"{node}-{npu_instance}-{parameter}",
            "command": f'request pfe execute command "show npu memory info" target {node}',
            "dataformat": "text",
            "regexp": rf"{npu_instance}\s+{parameter}\s+(\d+)",
            "node": "master",
            "controller": "master",
            "database": True,
            "expression": expression
        }

        # Register the parameter
        te_longevity_test.register(**sys_dict)

        testbed.log(f"\n[INFO] [{rtr}] [{node}] Registered show npu memory info - {parameter}", console=True)



def evo_pfe_instance_wise_npu_memory_te_registrations(rtr, npu_list, fpc, evo_npu_memory_dict, size_dict, **kwargs):
    """
    Registers NPU MEMORY usage under a node with individual PFE instances.

    Arguments:
        rtr - Router tag, e.g., "r0"
        npu_list - List of NPUs for the given FPC.
        fpc - FPC node ID.
        evo_npu_memory_dict - Dictionary containing NPU memory utilization values.
        size_dict - Dictionary containing size-related information for NPUs.

    Return: None
    """

    # Perform Registration Per NPU
    for npu in npu_list:
        longevity_te_reg_fpc_npu_memory_info_helper(rtr, fpc, npu, evo_npu_memory_dict, size_dict, **kwargs)


def evo_node_wise_npu_memory_te_registrations(rtr, evo_npu_memory_dict, node_list, **kwargs):
    """
    Registers NPU MEMORY usage on a node-wise basis.

    Arguments:
        rtr - Router tag, e.g., "r0"
        evo_npu_memory_dict - Dictionary containing NPU memory utilization values.
        node_list - List of nodes (FPCs) for which the NPU memory usage is to be registered.

    Return: None
    """

    self = kwargs.get('self', None)
    
    # Extract FPC list from node list
    fpc_list = [node for node in node_list if node.startswith("fpc")]

    # Extract NPU memory keys
    evo_npu_memory_list = list(evo_npu_memory_dict.keys())

    for fpc in fpc_list:
        # Get NPU list and size dictionary from FPC
        npu_list, size_dict = get_npu_list_from_fpc(rtr, fpc, evo_npu_memory_list, **kwargs)

        # If size_dict is empty, return from function
        if not size_dict:
            return

        # Perform PFE instance-wise NPU Memory TE Registrations
        evo_pfe_instance_wise_npu_memory_te_registrations(rtr, npu_list, fpc, evo_npu_memory_dict, size_dict, **kwargs)




def longevity_te_reg_fpc_npu_memory_info(evo_router_list, npu_memory_dict=None, **kwargs):
    """
    Registers NPU MEMORY usage for the specified routers.

    Arguments:
        
        evo_router_list - List of routers to register NPU memory usage for.
        npu_memory_dict - Dictionary containing NPU memory utilization values. Defaults to None.

    Return: None
    """
    self = kwargs.get('self', None)
    # Define default NPU memory utilization list
    default_npu_memory_utilization_list = {
        'mem-util-kht-epp-mapid-utilization': '80',
        'mem-util-kht-l2domain-utilization': '99',
        'mem-util-kht-slu-my-mac-utilization': '80',
        'mem-util-kht-dlu-idb-utilization': '75',
        'mem-util-jnh-mm-global-utilization': '50',
        'mem-util-jnh-mm-private-utilization': '100',
        'mem-util-jnh-loadbal-utilization': '100',
        'mem-util-epp-total-mem-utilization': '50',
        'mem-util-flt-vfilter-utilization': '100',
        'mem-util-flt-phyfilter-utilization': '100',
        'mem-util-flt-alpha-0-kht-peak-utilization': '90',
        'mem-util-flt-alpha-0-kht-utilization': '90',
        'mem-util-policer-id-utilization': '100',
        'mem-util-plct-utilization': '90'
    }

    for rtr in evo_router_list:
        rh = testbed.get_handle(resource=rtr)
    
        rtr_model = device_utils.get_model_for_device(device=rh).lower()
        
        if 'qfx' in rtr_model:
            continue
        
        # Check if NPU memory list is defined in parameters
        is_npu_memory_dict_in_params = "uv-longevity-npu-memory-utilization-list" in t['resources'][rtr]['system']['primary']

        # Check if NPU memory list is defined under fv-properties
        is_npu_memory_dict_in_fv_prop = "longevity-npu-memory-utilization-list" in t['resources'][rtr]['system']['primary'].get('fv-properties', {})

        tmp_var = t['resources'][rtr]['system']['primary']['fv-properties'].get('longevity-npu-memory-utilization-list') if is_npu_memory_dict_in_fv_prop else None

        # Check if user provided a dictionary for NPU memory
        is_npu_memory_dict_in_robot = bool(npu_memory_dict)

        if is_npu_memory_dict_in_robot:
            evo_npu_memory_dict = npu_memory_dict.copy()
        elif is_npu_memory_dict_in_params:
            evo_npu_memory_dict = eval(t['resources'][rtr]['system']['primary']['uv-longevity-npu-memory-utilization-list'])
        elif is_npu_memory_dict_in_fv_prop:
            evo_npu_memory_dict = eval(tv[tmp_var])
        else:
            evo_npu_memory_dict = default_npu_memory_utilization_list

        # Extract NPU memory keys
        evo_npu_memory_list = list(evo_npu_memory_dict.keys())

        # Log the list of NPU Memory being registered
        testbed.log(f"\n[INFO] [{rtr}] List Of NPU Memory Used in Data Registration = {evo_npu_memory_list}", console=True)

        # Get the node list from the router
        node_list = evo_get_node_list(rtr, **kwargs)

        # Check if the chassis is fixed form factor
        is_fixed_form_factor = evo_is_chassis_form_factor_fixed(rtr, **kwargs)

        if is_fixed_form_factor:
            node_list.append("fpc0")

        # Perform Node-wise NPU Memory TE Registrations
        evo_node_wise_npu_memory_te_registrations(rtr, evo_npu_memory_dict, node_list, **kwargs)


def get_npu_memory_dict(rtr, default_npu_memory_utilization_list, **kwargs):

    self = kwargs.get('self', None)
    try:
        is_npu_memory_dict_in_params = 'uv-longevity-npu-memory-utilization-list' in t['resources'][rtr]['system']['primary']
        if is_npu_memory_dict_in_params:
            return eval(str(t['resources'][rtr]['system']['primary']['uv-longevity-npu-memory-utilization-list']))
    except Exception:
        pass

    try:
        is_npu_memory_dict_in_fv_prop = 'longevity-npu-memory-utilization-list' in t['resources'][rtr]['system']['primary']['fv-properties']
        if is_npu_memory_dict_in_fv_prop:
            return eval(str(tv['+tmp_var+']))
    except Exception:
        pass
    
    return default_npu_memory_utilization_list



def evo_longevity_data_registration(rtr_list, process_dict=None, npu_memory_dict=None, rtag=None, **kwargs):


    self = kwargs.get('self', None)
    cmd_timeout = tv.get('uv-cmd-timeout', '900')
  
    self.cmd_timeout = cmd_timeout
    te_interval = tv.get('uv-te-interval', f"{5_0}")
    self.te_interval = te_interval
    
    # Determine tag state (True/False)
    tag_state = 'True' if 'tag_state' in globals() else 'True'
    try:
        tag_state = True if len(rtag) != 0 else False
    except Exception:
        tag_state = False
        
        
    ltag =  rtag if tag_state else 'evo'
    
    evo_longevity_rtr_tag = tv.get('uv-evo-longevity-rtr-tag', ltag)
    self.evo_longevity_rtr_tag = evo_longevity_rtr_tag
    
    # Identify EVO routers from the list
    evo_router_list = [rtr for rtr in rtr_list if (testbed.get_handle(resource=rtr).is_evo())]
    
    len__val = len(evo_router_list)
    self.is_router_evo_based = 1 if len__val > 0 else 0
    
    if len__val == 0:
        testbed.log("'level' = INFO", display_log=True)
        return EMPTY
    
    skip_fpc_checks = tv.get('uv-skip-fpc-level-checks-and-collection', 0)
    self.skip_fpc_checks = skip_fpc_checks
    testbed.log("'level' = INFO", display_log=True)
    
    # Call respective functions for memory and FPC checks
    longevity_te_reg_task_memory_detail(evo_router_list, **{'self': self})
    evo_memory_te_registrations(evo_router_list, process_dict, **{'self': self})
    longevity_te_reg_fpc_npu_memory_info(evo_router_list, npu_memory_dict, **{'self': self})

def longevity_chk_is_fpc_aft(fpc_model, **kwargs):
    self = kwargs.get('self', None)
    list_of_aft_linecards = ['MPC11E 3D MRATE-40xQSFPP', 'JNP10K-LC9600', 'JNP10K-LC4800', 'MPC10E 3D MRATE-15xQSFPP', 'MPC10E 3D MRATE-10xQSFPP', 'FPC-BUILTIN']
    
    new_aft_lc = tv.get('uv-longevity-aft-linecard-name', EMPTY)
    tmp_status = len(new_aft_lc) == 0
    
    if not tmp_status:
        list_of_aft_linecards.append(new_aft_lc)
    
    is_lc_aft = any(fpc_model in card for card in list_of_aft_linecards)
    return is_lc_aft

def longevity_get_junos_fpc_heap_block_names(rtr, fpc_slot, **kwargs):
    self = kwargs.get('self', None)
    rh = testbed.get_handle(resource=rtr)
    
    # Checking if it's an EVO router
    if not rh_is_evo(rh):
        return False, []
    
    rtr_model = device_utils.get_model_for_device(device=rh).lower()
    device_types = ['mx', 'ptx', 'acx', 'qfx', 'srx']
    device_flags = {device: device in rtr_model for device in device_types}
    
    xml_out = device_utils.execute_cli_command_on_device(device=rh, command='show chassis fpc pic-status | display xml', pattern='Toby.*>$')
    fpc_desc = xml_utils.get_element_text(xml_out, f".//fpc-information/fpc[slot=\"{fpc_slot}\"]/description")
    
    LLOG(message=f"[{rtr}] FPC{fpc_slot} Model = {fpc_desc}", **{'self': self})
    
    is_aft_card = longevity_chk_is_fpc_aft(fpc_desc, **{'self': self})
    
    if is_aft_card:
        junos_aft_cards.update({f"{rtr}.{fpc_slot}": '1'})
        
    # Select appropriate template name based on device type and AFT status
    ve_tmpl_name = 'get_junos_mx_ptx_aft_heap_block_names' if is_aft_card else 'get_junos_mx_ptx_heap_block_names'
    args = {'fpc_slot': fpc_slot}
    
    temp_block_names = mts.get(info=ve_tmpl_name, devices=rtr, args=args, file='/volume/regressions/toby/test-suites/pdt/lib/longevity/dev_branch/longevity.ve.yaml')
    block_names = [temp_block_names] if isinstance(temp_block_names, list) else [temp_block_names]
    
    result = bool(block_names)
    return result, block_names


def longevity_te_register_fpc_heap_blocks_on_fpc(rtr, fpc, block_names, **kwargs):
    """
    Registers FPC heap blocks for the given router and FPC.

    Arguments:
        rtr - Router tag
        fpc - FPC slot number
        block_names - List of heap block names

    Return: None
    """

    self = kwargs.get('self', None)
    # ------------------------------------------------------
    # Get Router Handle
    # ------------------------------------------------------
    rh = testbed.get_handle(resource=rtr)

    # ------------------------------------------------------
    # Create TE Dictionary
    # ------------------------------------------------------            
    te_dict = {
        "trace": f"{rtr}-fpc{fpc}-show-heap",
        "mode": "shell",
        "dataformat": "text",
        "node": "master",
        "controller": "master",
        "resource": rtr,
        "database": True
    }

    # ------------------------------------------------------
    # Get the FPC Model
    # ------------------------------------------------------   
    xml_out = device_utils.execute_cli_command_on_device(
        device=rh,
        command="show chassis fpc pic-status | display xml",
        pattern=r"Toby.*>$"
    )
    
    fpc_desc = xml_utils.get_element_text(xml_out, f".//fpc-information/fpc[slot='{fpc}']/description")
    testbed.log(level="INFO", message=f"[{rtr}] FPC{fpc} Model = {fpc_desc}")

    # ------------------------------------------------------
    # Check whether the model is aft or nonaft
    # ------------------------------------------------------       
    is_aft_card = longevity_chk_is_fpc_aft(fpc_desc, **kwargs)
    if is_aft_card:
        te_dict["command"] = f"cprod -A fpc{fpc}.0 -c \"show heap\""
    else:
        te_dict["command"] = f"cprod -A fpc{fpc} -c \"show heap\""
    
    # -----------------------------------------------
    # Get the task malloc threshold values
    # -----------------------------------------------
    fpc_heap_block_thr = tv.get('uv-fpc-heap-block-mem-used-threshold', 10)
    te_dict["tolerance"] = fpc_heap_block_thr
    te_dict["expression"] = "current <= ((100 + float(tolerance)) / 100) * snapshot"
    
    # ------------------------------------------------------
    # Perform Per Block Registration
    # ------------------------------------------------------            
    for block in block_names:
        testbed.log(level="INFO", message=f"[ {rtr} ] [ {tv.get(f'{rtr}__name', '')} ] [ fpc{fpc} ] Registering {block} memory used")
        
        # ------------------------------------------------------
        # Replace space for parameter name
        # ------------------------------------------------------
        param_name = block.replace(" ", "")
        te_dict.update({
            "parameter": f"{rtr}-fpc{fpc}-heap-block-{param_name}-memory-used",
            "regexp": rf"\d+\s+\w+\s+\d+\s+\d+\s+(\d+)\s+\d+\s+{block}"
        })
        
        #lrm_baseline.register(**te_dict)
        #te_longevity_test.register(**te_dict)
        testbed.log(level="INFO", message=f"[ {rtr} ] [ {tv.get(f'{rtr}__name', '')} ] [ fpc{fpc} ] Registered {block} memory used")


def longevity_te_register_fpc_heap_blocks_on_rtr(rtr, **kwargs):
    self = kwargs.get('self', None)
    rh = testbed.get_handle(resource=rtr)
    cmd_timeout = tv.get('uv-cmd-timeout-fpc-online-slot-list', 600)
    
    xml_out = device_utils.execute_cli_command_on_device(device=rh, command='show chassis fpc | display xml', timeout=self.cmd_timeout, pattern='Toby.*>$')
    fpc_list = xml_utils.get_elements_texts(xml_out, "fpc-information/fpc[state='Online']/slot")
    
    if not fpc_list:
        LLOG(message=f"[ {rtr} ] [ {tv[rtr+'__name']} ] No FPCs are online", **{'self': self})
        return
    
    self.fpc_list = fpc_list
    LLOG(message=f"[ {rtr} ] [ {tv[rtr+'__name']} ] Online FPC List = {self.fpc_list}", **{'self': self})
    
    for fpc in self.fpc_list:
        result, block_names = longevity_get_junos_fpc_heap_block_names(rtr, fpc, **{'self': self})
        if not result:
            continue
        LLOG(message=f"[ {rtr} ] [ {tv[rtr+'__name']} ] [ fpc{fpc} ] Block Name List = {block_names}", **{'self': self})
        longevity_te_register_fpc_heap_blocks_on_fpc(rtr, fpc, block_names, **{'self': self})

def longevity_te_register_fpc_heap_blocks_on_rtr_list(rtr_list, **kwargs):
    """
    Registers FPC heap blocks for each router in the given list.

    Arguments:
        rtr_list - List of router tags

    Return: None
    """

    self = kwargs.get('self', None)
    # -------------------------------------------------------
    # Skip if the list is empty
    # -------------------------------------------------------
    if not rtr_list:
        testbed.log("WARN: Router List is Empty. Skipping the Heap Block Registrations.\n")
        return

    # -------------------------------------------------------
    # Perform Per-router registration
    # -------------------------------------------------------
    for rtr in rtr_list:
        longevity_te_register_fpc_heap_blocks_on_rtr(rtr, **kwargs)




def longevity_te_register_fpc_heap_blocks_on_rtr(rtr, **kwargs):
    """
    Registers FPC heap blocks for the given router.

    Arguments:
        rtr - Router tag

    Return: None
    """
    self = kwargs.get('self', None)
    # ------------------------------------------------------
    # Get Router Handle
    # ------------------------------------------------------
    rh = testbed.get_handle(resource=rtr)

    # ------------------------------------------------------
    # Get List of online FPCs
    # ------------------------------------------------------
    cmd_timeout = tv.get('uv-cmd-timeout-fpc-online-slot-list', 600)
    xml_out = device_utils.execute_cli_command_on_device(
        device=rh,
        command="show chassis fpc | display xml",
        timeout=cmd_timeout,
        pattern=r"Toby.*>$"
    )

    self.fpc_list = get_elements_texts(xml_out, "fpc-information/fpc[state='Online']/slot")
    self.fpc_list_len = len(self.fpc_list)

    # Store variables globally
    #testbed.suite_variables["fpc_list"] = fpc_list
    #testbed.suite_variables["fpc_list_len"] = fpc_list_len

    if self.fpc_list_len == 0:
        testbed.log(f"[ {rtr} ] [ {tv.get(f'{rtr}__name')} ] No FPCs are online\n")
        return

    testbed.log(f"[ {rtr} ] [ {tv.get(f'{rtr}__name')} ] Online FPC List = {self.fpc_list}\n")

    # ------------------------------------------------------
    # Perform Per FPC Registration
    # ------------------------------------------------------    
    for fpc in self.fpc_list:
        # -------------------------------------------------
        # Get the Heap block names
        # -------------------------------------------------    
        result, block_names = longevity_get_junos_fpc_heap_block_names(rtr, fpc, **kwargs)

        # -------------------------------------------------
        # Skip FPC if the results are false
        # -------------------------------------------------    
        if not result:
            continue

        testbed.log(f"[ {rtr} ] [ {tv.get(f'{rtr}__name')} ] [ fpc{fpc} ] Block Name List = {block_names}")

        # -------------------------------------------------
        # Perform Registration For each block
        # -------------------------------------------------    
        longevity_te_register_fpc_heap_blocks_on_fpc(rtr, fpc, block_names, **kwargs)



def junos_is_chassis_dual_re(rtr, **kwargs):
    self = kwargs.get('self', None)
    rh = testbed.get_handle(resource=rtr)
    cmd_out = device_utils.execute_cli_command_on_device(device=rh, command='show chassis routing-engine | match "Current State" | match "Master|Backup" | count', pattern='Toby.*>$')
    
    tmp_re_count = [match.group(1) for match in re.finditer(r'Count:\s+(\d+)\s+lines', cmd_out)] or []
    re_count = int(tmp_re_count[0]) if tmp_re_count else 0
    
    result = re_count == 2
    return result

def JunOS_Get_RE_Slot_HA_State(rtr, node, **kwargs):
    self = kwargs.get('self', None)
    rh = testbed.get_handle(resource=rtr)
    slot_id = [match.group(1) for match in re.finditer(r're(\d+)', node)] or []
    
    if not slot_id:
        LLOG(level='ERROR', message=f"Invalid RE slot id for {node}", **{'self': self})
        return None
    
    xml_out = device_utils.execute_cli_command_on_device(device=rh, command=f"show chassis routing-engine {slot_id[0]} | display xml", pattern='Toby.*>$')
    slot_state = xml_utils.get_element_text(xml_out, f"route-engine-information/route-engine[slot='{slot_id[0]}']/mastership-state")
    return slot_state.lower()

def Check_Processing_Is_Running_In_Shell(rtr='', command='top -n | grep \"rpd\"', process='rpd', **kwargs):
    self = kwargs.get('self', None)
    dut_handle = testbed.get_handle(resource=rtr)
    
    shell_out = device_utils.execute_shell_command_on_device(device=dut_handle, timeout=60, command=command, pattern='Toby.*%$')
    
    gen_match_obj = re.search(rf"{process}$", shell_out)
    is_process_running = gen_match_obj.group(0) if gen_match_obj else False
    if not is_process_running:
        LLOG(level='ERROR', message=f"Process {process} not running on {rtr}", **{'self': self})
    
    return is_process_running


def JunOS_Top_RPD_Dual_RE_TE_Registration(rtr='', node='', junos_process_dict=None, **kwargs):
    """
    Registers telemetry for the 'rpd' process in dual RE configurations.
    Registers CPU and memory usage details for 'rpd' on a specific RE node (RE0 or RE1).
    """
    self = kwargs.get('self', None)
    assert rtr, "'ERROR: rtr should not be empty'"
    assert node, "'ERROR: Node should not be empty'"
    
    rpd_cpu_tol = tv.get('uv-junos-rpd-cpu-tolerance', 5)
    slot_state = JunOS_Get_RE_Slot_HA_State(rtr=rtr, node=node, **{'self': self})
    process_list = list(junos_process_dict.keys())
    
    search_string = '^rpd$'
    rh = testbed.get_handle(resource=rtr)
    device_utils.set_current_controller(rh, controller=node)
    
    kwargs = {
        'trace': 'top-rpd-cpu',
        'parameter': 'top-rpd-cpu-size',
        'command': 'top -n | grep "rpd"',
        'dataformat': 'text',
        'regexp': '\\d+\\s+\\w+\\s+\\w+\\s+\\w+\\s+\\w+\\s+(\\w+\\.*\\w*)\\s+\\w+\\.*\\w*.*\\s+rpd$',
        'node': slot_state,
        'controller': slot_state,
        'tolerance': rpd_cpu_tol,
        'resource': rtr,
        'database': True,
        'mode': 'shell'
    }
    
    is_process_running = Check_Processing_Is_Running_In_Shell(rtr=rtr, command='top -n | grep "rpd"', process='rpd', **{'self': self})
    
    if is_process_running:
        testbed.log(f"Started Registering the Command top -n | grep 'rpd' for {rtr} for node:{node} for rpd-cpu-size and rpd-cpu-res", display_log=True)
        kwargs.update({'parameter': 'top-rpd-cpu-res'})
        kwargs.update({'regexp': '\\d+\\s+\\w+\\s+\\w+\\s+\\w+\\s+\\w+\\s+\\w+\\.*\\w*\\s+(\\w+\\.*\\w*).*\\s+rpd$'})
        # Register the telemetry for CPU and memory resource usage
        pass
        testbed.log(f"Completed Registering the Command top -n | grep 'rpd' for {rtr} for node:{node} for rpd-cpu-size and rpd-cpu-res", display_log=True)
    else:
        testbed.log(f"RPD is not running on node {node} for {rtr}. Skipping TE registration for TOP RPD command", display_log=True)


    device_utils.set_current_controller(rh, controller='master')


def JunOS_Top_RPD_TE_Registration(rtr='', junos_process_dict=None, **kwargs):
    """
    Registers telemetry for 'rpd' process CPU and memory usage for a single or dual RE setup.
    Handles the case where the router has dual REs (RE0 and RE1).
    """
    self = kwargs.get('self', None)
    is_dual_re = junos_is_chassis_dual_re(rtr, **{'self': self})
    
    if is_dual_re:
        testbed.log('Register for RE0', display_log=True)
        JunOS_Top_RPD_Dual_RE_TE_Registration(rtr=rtr, node='re0', junos_process_dict=junos_process_dict, **{'self': self})
        testbed.log('Register for RE1', display_log=True)
        JunOS_Top_RPD_Dual_RE_TE_Registration(rtr=rtr, node='re1', junos_process_dict=junos_process_dict, **{'self': self})
        return
    
    rpd_cpu_tol = tv.get('uv-junos-rpd-cpu-tolerance', 5)
    kwargs = {
        'trace': 'top-rpd-cpu',
        'parameter': 'top-rpd-cpu-size',
        'command': 'top -n | grep "rpd"',
        'dataformat': 'text',
        'regexp': '\\d+\\s+\\w+\\s+\\w+\\s+\\w+\\s+\\w+\\s+(\\w+\\.*\\w*)\\s+\\w+\\.*\\w*.*\\s+rpd$',
        'node': 'master',
        'controller': 'master',
        'tolerance': rpd_cpu_tol,
        'resource': rtr,
        'database': True,
        'mode': 'shell'
    }
    
    kwargs.update({'parameter': 'top-rpd-cpu-res'})
    kwargs.update({'regexp': '\\d+\\s+\\w+\\s+\\w+\\s+\\w+\\s+\\w+\\s+\\w+\\.*\\w*\\s+(\\w+\\.*\\w*).*\\s+rpd$'})
    # Register the telemetry for CPU and memory resource usage
    pass


def JunOS_Show_System_Process_Extensive_TE_Registrations(rtr='', junos_process_dict=None, **kwargs):
    """
    Registers extensive system process telemetry for a list of processes on the router.
    Handles CPU and memory details for each process.
    """
    self = kwargs.get('self', None)
    sys_prc_tol = tv.get('uv-junos-show-system-processes-extensive-tolerance', 20)
    kwargs = {
        'dataformat': 'text',
        'node': 'master',
        'controller': 'master',
        'tolerance': sys_prc_tol,
        'resource': rtr,
        'database': True,
        'mode': 'cli'
    }
    
    process_list = list(junos_process_dict.keys())
    for process in process_list:
        is_match = False
        try:
            gen_match_obj = re.search(f"^{process}$", process)
            is_match = gen_match_obj.group(0) if gen_match_obj else None
            if not is_match:
                assert False, 'Does not match with given regex'
        except Exception:
            is_match = False
        
        if is_match:
            JunOS_Top_RPD_TE_Registration(rtr=rtr, junos_process_dict=junos_process_dict, **{'self': self})
        
        if not is_match:
            kwargs.update({'trace': f"show-system-processes-extensive-{process}"})
            kwargs.update({'parameter': f"show-system-processes-extensive-{process}-size"})
            kwargs.update({'command': f"show system processes extensive | grep {process}"})
            kwargs.update({'regexp': f"\\d+\\s+\\w+\\s+\\-*\\w+\\s+\\w+\\s+(\\w+\\.*\\w*)\\s+\\w+\\.*\\w*.*\\s+{process}"})
            # Register process-specific telemetry for CPU and memory usage
            #lrm_baseline.register(**kwargs)  
            #te_longevity_test.register(**kwargs)

            kwargs.update({'parameter': f"show-system-processes-extensive-{process}-res"})
            kwargs.update({'regexp': f"\\d+\\s+\\w+\\s+\\-*\\w+\\s+\\w+\\s+\\w+\\.*\\w*\\s+(\\w+\\.*\\w*).*\\s+{process}"})
            #lrm_baseline.register(**kwargs)  
            #te_longevity_test.register(**kwargs)

            
 


def junos_memory_te_registrations(junos_router_list, process_dict=None, **kwargs):
    """
    Registers memory usage for JunOS processes.

    Arguments:
        junos_router_list - List of JunOS routers
        process_dict - Optional dictionary of processes to monitor

    Return: None
    """
    self = kwargs.get('self', None)
    
    for rtr in junos_router_list:
        # Get Router Handle
        rh = testbed.get_handle(resource=rtr)
        
        # Define Default Process List
        default_process_list = {
            "rpd": "5",
            "ppmd": "20",
            "bfdd": "20",
            "dfwd": "20",
            "chassisd": "20",
            "dcd": "20"
        }
        
        # Check if process list is defined in system parameters
        is_process_dict_in_params = "uv-processes" in t["resources"][rtr]["system"]["primary"]
        #is_process_dict_in_params=
        # Check if process list is defined under fv-properties
        #is_process_dict_in_fv_prop = "processes" in t["resources"][rtr]["system"]["primary"]["fv-properties"]
        #tmp_var = (
        #    t["resources"][rtr]["system"]["primary"]["fv-properties"]["processes"]
        #    if is_process_dict_in_fv_prop else None
        #)
        
        # Check if user has provided process dictionary
        #is_process_dict_in_robot = process_dict is not None
        
        #junos_process_dict = (
        #    process_dict.copy() if is_process_dict_in_robot else
        #    t["resources"][rtr]["system"]["primary"].get("uv-processes") if is_process_dict_in_params else
        #    tv.get(tmp_var) if is_process_dict_in_fv_prop else
        #    default_process_list
        #)
        junos_process_dict_str = t["resources"][rtr]["system"]["primary"].get("uv-processes") 
        import re
        str_m = re.compile(r"'(\w+)':\s*'(\d+)'")
        junos_process_dict={}
        for line in junos_process_dict_str.split('\n'):
            match = str_m.search(line)
            if match:
                (app,threshold) = match.group(1), int(match.group(2))
                junos_process_dict[app]=int(threshold)
        junos_process_list = list(junos_process_dict.keys())
        testbed.log(level="INFO", message=f"\n[INFO] [{rtr}] List Of Processes Used in Data Registration = {junos_process_list}", console=True)
        
        # Register processes
        junos_show_system_process_extensive_te_registrations(rtr, junos_process_dict, **kwargs)

def junos_show_system_process_extensive_te_registrations(rtr, junos_process_dict, **kwargs):
    """
    Registers show system processes extensive for JunOS.

    Arguments:
        rtr - Router tag
        junos_process_dict - Dictionary of process names and their tolerances

    Return: None
    """
    
    self = kwargs.get('self', None)
    
    sys_prc_tol = tv.get('uv-junos-show-system-processes-extensiv-tolerance', 20)
    kwargs = {
        "dataformat": "text",
        "node": "master",
        "controller": "master",
        "tolerance": sys_prc_tol,
        "resource": rtr,
        "database": True,
        "mode": "cli"
    }
    
    # Get Process List
    process_list = list(junos_process_dict.keys())
    search_string = "^rpd$"
    
    for process in process_list:
        # Check if process is rpd 
        is_match = re.match(search_string, process)
        
        if is_match:
            junos_top_rpd_te_registration(rtr=rtr, junos_process_dict=junos_process_dict, **kwargs)
            continue
        
        # ---------------------------------------------------------
        # Register for Process Size
        # ---------------------------------------------------------    
        kwargs.update({
            "trace": f"show-system-processes-extensive-{process}",
            "parameter": f"show-system-processes-extensive-{process}-size",
            "command": f"show system processes extensive | grep {process}",
            "regexp": rf"\\d+\\s+\\w+\\s+\\-*\\w+\\s+\\w+\\s+(\\w+\\.*\\w*)\\s+\\w+\\.*\\w*.*\\s+{process}"
        })
        
        #lrm_baseline.register(**kwargs)
        #te_longevity_test.register(**kwargs)
        
        # ---------------------------------------------------------
        # Register for Process RES Memory 
        # ---------------------------------------------------------    
        kwargs.update({
            "parameter": f"show-system-processes-extensive-{process}-res",
            "regexp": rf"\\d+\\s+\\w+\\s+\\-*\\w+\\s+\\w+\\s+\\w+\\.*\\w*\\s+(\\w+\\.*\\w*).*\\s+{process}"
        })
        
        #lrm_baseline.register(**kwargs)
        #te_longevity_test.register(**kwargs)
        
        testbed.log(level="INFO", message=f"[INFO] [{rtr}] Registered show system processes extensive for {process}", console=True)

def junos_top_rpd_te_registration(rtr, junos_process_dict, **kwargs):
    """
    Registers top -n | grep "rpd" for JunOS.
    
    Arguments:
        rtr - Router tag
        junos_process_dict - Dictionary of process names and their tolerances
    
    Return: None
    """
    self = kwargs.get('self', None)
    is_dual_re = junos_is_chassis_dual_re(rtr)
    
    if is_dual_re:
        testbed.log(level="INFO", message="Registering for RE0")
        junos_top_rpd_dual_re_te_registration(rtr=rtr, node="re0", junos_process_dict=junos_process_dict)
        
        testbed.log(level="INFO", message="Registering for RE1")
        junos_top_rpd_dual_re_te_registration(rtr=rtr, node="re1", junos_process_dict=junos_process_dict)
        return
    
    rpd_cpu_tol = tv.get('uv-junos-rpd-cpu-tolerance', 5)
    kwargs = {
        "trace": "top-rpd-cpu",
        "parameter": "top-rpd-cpu-size",
        "command": "top -n | grep \"rpd\"",
        "dataformat": "text",
        "regexp": r"\\d+\\s+\\w+\\s+\\w+\\s+\\w+\\s+\\w+\\s+(\\w+\\.*\\w*)\\s+\\w+\\.*\\w*.*\\s+rpd$",
        "node": "master",
        "controller": "master",
        "tolerance": rpd_cpu_tol,
        "resource": rtr,
        "database": True,
        "mode": "shell"
    }
    
    #te_longevity_test.register(**kwargs)
    #lrm_baseline.register(**kwargs)
    
    kwargs.update({
        "parameter": "top-rpd-cpu-res",
        "regexp": r"\\d+\\s+\\w+\\s+\\w+\\s+\\w+\\s+\\w+\\s+\\w+\\.*\\w*\\s+(\\w+\\.*\\w*).*\\s+rpd$"
    })
    
    #te_longevity_test.register(**kwargs)
    #lrm_baseline.register(**kwargs)


def junos_is_chassis_dual_re(rtr):
    """
    Checks if the router has dual REs.

    Arguments:
        rtr - Router tag

    Return:
        True if router has dual REs, otherwise False.
    """
    rh = testbed.get_handle(resource=rtr)
    cmd_out = device_utils.execute_cli_command_on_device(
        device=rh,
        command="show chassis routing-engine | match 'Current State' | match 'Master|Backup' | count",
        pattern=r"Toby.*>$"
    )
    match = re.search(r"Count:\s+(\d+)\s+lines", cmd_out)
    if match:
        re_count = int(match.group(1))
        return re_count == 2
    return False
    
    
def junos_top_rpd_dual_re_te_registration(rtr, node, junos_process_dict):
    """
    Registers top -n | grep "rpd" for dual RE setups.
    
    Arguments:
        rtr - Router tag
        node - Node name (re0 or re1)
        junos_process_dict - Dictionary of JunOS processes
    
    Return: None
    """
    if not rtr or not node:
        raise ValueError("ERROR: rtr and node should not be empty")
    
    rpd_cpu_tol = tv.get('uv-junos-rpd-cpu-tolerance', 5)
    slot_state = junos_get_re_slot_ha_state(rtr, node)
    rh = testbed.get_handle(resource=rtr)
    device_utils.set_current_controller(rh, controller=node)
    
    kwargs = {
        "trace": "top-rpd-cpu",
        "parameter": "top-rpd-cpu-size",
        "command": "top -n | grep 'rpd'",
        "dataformat": "text",
        "regexp": r"\\d+\\s+\\w+\\s+\\w+\\s+\\w+\\s+\\w+\\s+(\\w+\\.*\\w*)\\s+\\w+\\.*\\w*.*\\s+rpd$",
        "node": slot_state,
        "controller": slot_state,
        "tolerance": rpd_cpu_tol,
        "resource": rtr,
        "database": True,
        "mode": "shell"
    }
    
    is_process_running = check_processing_is_running_in_shell(rtr, command="top -n | grep 'rpd'", process="rpd")
    if is_process_running:
        testbed.log(level="INFO", message=f"[INFO] Started Registering the Command top -n | grep 'rpd' for {rtr} node:{node}", console=True)
        #te_longevity_test.register(**kwargs)
        #lrm_baseline.register(**kwargs)
        kwargs.update({
            "parameter": "top-rpd-cpu-res",
            "regexp": r"\\d+\\s+\\w+\\s+\\w+\\s+\\w+\\s+\\w+\\s+\\w+\\.*\\w*\\s+(\\w+\\.*\\w*).*\\s+rpd$"
        })
        #te_longevity_test.register(**kwargs)
        #lrm_baseline.register(**kwargs)
        testbed.log(level="INFO", message=f"[INFO] Completed Registering the Command top -n | grep 'rpd' for {rtr} node:{node}", console=True)
    else:
        testbed.log(level="INFO", message=f"[INFO] RPD is not running on node {node} for {rtr}. Skipping TE registration for TOP RPD command", console=True)
    
 
    device_utils.set_current_controller(rh, controller="master")


def junos_get_re_slot_ha_state(rtr, node):
    """
    Returns the current HA state of the RE, master or backup.
    
    Arguments:
        rtr - Router tag
        node - re0 or re1
    
    Return: master or backup based on the RE state.
    """
    rh = testbed.get_handle(resource=rtr)
    slot_id_match = re.match(r"re(\\d+)", node)
    if not slot_id_match:
        return None
    slot_id = slot_id_match.group(1)
    xml_out = device_utils.execute_cli_command_on_device(
        device=rh,
        command=f"show chassis routing-engine {slot_id} | display xml",
        pattern=r"Toby.*>$"
    )
    slot_state = xml_utils.get_elements_texts(xml_out, f"route-engine-information/route-engine[slot='{slot_id}']/mastership-state")
    return slot_state.lower() if slot_state else None

def check_processing_is_running_in_shell(rtr, command="top -n | grep 'rpd'", process="rpd"):
    """
    Checks if the given process is running in the shell.
    
    Arguments:
        rtr - Router tag
        command - Shell command to check the process
        process - Process name to match
    
    Return: True if the process is running, otherwise False.
    """
    dut_handle = testbed.get_handle(resource=rtr)
    shell_out = device_utils.execute_shell_command_on_device(
        device=dut_handle,
        timeout=60,
        command=command,
        pattern=r"Toby.*%$"
    )
    return bool(re.search(rf"{process}$", shell_out))


def junos_longevity_data_registration(rtr_list, process_dict=None, rtag=None, **kwargs):
    """
    Keyword that registers all the TE JunOS related checks.

    Arguments:
        rtr_list - List of router tags
        process_dict - Optional dictionary provided via function argument
        rtag - Optional tag for user-defined processing

    Return: None
    """

    # ----------------------------------------------------------------------
    # Global Timeout
    # ----------------------------------------------------------------------
    cmd_timeout = tv.get("uv-cmd-timeout", 600)

    # ----------------------------------------------------------------------
    # TE Interval
    # ----------------------------------------------------------------------
    te_interval = tv.get("uv-te-interval", 5.0)

    # ----------------------------------------------------------------------
    # Skip FPC level Checks
    # ----------------------------------------------------------------------
    skip_fpc_checks = tv.get("uv-skip-fpc-level-checks-and-collection", 0)

    # ----------------------------------------------------------------------
    # Perform off the file registrations
    # ----------------------------------------------------------------------
    testbed.log("\n[INFO] Starting JunOS Data Registration Process", console=True)

    # Register required tasks
    #
    longevity_te_reg_task_memory_detail(rtr_list, **kwargs)
    longevity_te_register_fpc_heap_blocks_on_rtr_list(rtr_list, **kwargs)
    junos_memory_te_registrations(rtr_list, process_dict, **kwargs)



def longevity_start_te_registrations(**kwargs):
    """
    Starts telemetry registration for longevity data on routers.
    Registers telemetry based on the global flags for EVO and JunOS data.
    """
    self = kwargs.get('self', None)
    
    
    pdt_te_registration_processor(**{'self': self})
    
   
    
    # Checking if EVO or JunOS longevity data should be registered
    if self.evo_lng_global_flag:
        evo_longevity_data_registration(rtr_list=self.evo_lng_rtr_list, **{'self': self})
        
    
    
    if self.junos_lng_global_flag:
        junos_longevity_data_registration(rtr_list=self.junos_lng_rtr_list, **kwargs)
    

  


    


def pdt_get_app_status_on_all_nodes(rtr, app_name, **kwargs):
    """
    Retrieves the application status on all nodes for a given router.
    """
    self = kwargs.get('self', None)
    app_status_list = []  # Initialize empty list for storing status
    
    rh = testbed.get_handle(resource=rtr)
    cli_cmd_exec_timeout = tv.get('uv-cmd-timeout', '900')
    self.cli_cmd_exec_timeout = cli_cmd_exec_timeout
    
    # Executing CLI command to retrieve app status
    xml_cmd_response = device_utils.execute_cli_command_on_device(device=rh, command=f"show system applications app {app_name} | display xml", timeout=self.cli_cmd_exec_timeout, pattern='Toby.*>$')
    app_status_list = get_elements_texts(xml_cmd_response, ".//system-applications-info/system-applications-info-entry/system-application-state")
    # Populating app_status_list based on the response (example logic)
    app_status_list_len = len(app_status_list)
    return app_status_list_len, app_status_list


def pdt_start_memory_profiling_on_rtr(rtr, app_list, **kwargs):
    """
    Starts memory profiling on the router for a given list of applications.
    """
    self = kwargs.get('self', None)
    mem_pro_enable_status = []  # List to track status of memory profiling for each app
    return_value = True  # Default return value for success
    
    rh = testbed.get_handle(resource=rtr)
    
    for app in app_list:
        # Get the application status on the router nodes
        app_status_list_len, app_status_list = pdt_get_app_status_on_all_nodes(rtr, app, **{'self': self})
        
        if app_status_list_len < 1:
            testbed.log(f"Warning: No status found for application {app} on router {rtr}", display_log=True)
            continue
        
        online_count = len([gen_item for gen_item in app_status_list if re.search(r'\bonline\b', gen_item)])
        
        if online_count == 0:
            testbed.log(f"Warning: Application {app} is not online on router {rtr}", display_log=True)
            
            # Ensure the attribute is a list before appending
            attr_name = f"{rtr}_lrm_memory_profiling_disabled_apps"
            
            # Retrieve existing value, ensuring it's a list
            existing_value = getattr(self, attr_name, [])
            if not isinstance(existing_value, list):
                existing_value = []  # Reset to empty list if it's not a list
            
            # Append the app and update the attribute
            existing_value.append(app)
            setattr(self, attr_name, existing_value)
            continue

        
        cli_cmd_exec_timeout = tv.get('uv-cmd-timeout', '900')
        self.cli_cmd_exec_timeout = cli_cmd_exec_timeout
        
        # Log the profiling initiation
        testbed.log(f"Info: Starting memory profiling for application {app} on router {rtr}", display_log=True)
        
        # Command to enable memory profiling based on application
        cmd = 'set task memory-leak-detector on' if app == 'routing' else f"request system memory-profiling node all application {app} enable"
        
        # Execute the memory profiling command
        cmd_response = device_utils.execute_cli_command_on_device(device=rh, command=cmd, timeout=self.cli_cmd_exec_timeout)
        
        # Check for success or failure in enabling profiling
        # Normalize cmd_response by stripping spaces and handling quotes
        normalized_response = cmd_response.strip().strip("'\"").rstrip(".")

        # Define valid success messages
        success_messages = {
            "Profiling started for the application",
            "Profiling is enabled successfully for the application",
            "Task memory leak detection enabled",
        }
        # Check if cmd_response is in the success messages set
        is_profiling_enabled = "True" if normalized_response in success_messages else "False"

        
        if str(is_profiling_enabled).lower() == 'false':
            testbed.log(f"Warning: Memory profiling failed to enable for application {app} on router {rtr}", display_log=True)
            mem_pro_enable_status.append(False)
        else:
            testbed.log(f"Info: Memory profiling enabled for application {app} on router {rtr}", display_log=True)
            mem_pro_enable_status.append(True)

            # Ensure the attribute is a list before appending
            attr_name = f"{rtr}_memory_profiled_enabled_apps"

            # Check if the attribute exists and is a list
            if not hasattr(self, attr_name) or not isinstance(getattr(self, attr_name), list):
                setattr(self, attr_name, [])  # Initialize as an empty list

            # Now safely append to the list
            getattr(self, attr_name).append(app)

    
    # Return the overall status of memory profiling
    return_value = str(eval(f"any({mem_pro_enable_status})"))
   
    return return_value

def pdt_start_memory_profiling(mode, rtr_list=None, **kwargs):
    """
    Starts memory profiling on routers based on the mode and the provided router list.
    """
    self = kwargs.get('self', None)
    
    # Use 'longevity' as the default router tag if not defined
    rtr_tag = evo_longevity_rtr_tag if 'evo_longevity_rtr_tag' in locals() else 'longevity'
    
    # If no routers are provided, fetch them from the testbed based on the tag
    if rtr_list is None:
        rtrs = testbed.get_resource_list(tag=rtr_tag)
    else:
        rtrs = rtr_list
    
    mem_pro_en_status = {'status': '1'}
    self.mem_pro_en_status = mem_pro_en_status
    
    # Check if we have any routers in the list
    if len(rtrs) < 1:
        testbed.log(f"'level' = WARN: No routers found for memory profiling", display_log=True)

    self.evo_rtr_list = [rtr for rtr in rtrs if testbed.get_handle(resource=rtr).is_evo()]
    
    if len(self.evo_rtr_list) < 1:
        testbed.log(f"'level' = WARN: No EVO routers found for memory profiling", display_log=True)

    # Iterate over each EVO router and start profiling
    for rtr in self.evo_rtr_list:
        is_key_exist = f"{rtr}__uv-evo-mem-profile-app-list" in tv
        if not is_key_exist:
            testbed.log(f"'level' = WARN: Memory profiling app list not found for {rtr}", display_log=True)
            continue
        
        
        # Set the application list based on the mode
        if mode == 'lrm_config':
            app_list = tv.get(f"{rtr}__uv-evo-mem-profile-app-list").split(',')
            
            hostname = tv.get(f"{rtr}__re0__hostname")
            #
            if failed_apps_not_enabled_memory_profiling:
                if hostname in failed_apps_not_enabled_memory_profiling:
                    app_list.extend(failed_apps_not_enabled_memory_profiling[hostname])
                    app_list = list(set(app_list)) 
        else:
            app_list = getattr(self, f"{rtr}_lrm_memory_profiling_disabled_apps", [])
        

    
        
        
        return_value = pdt_start_memory_profiling_on_rtr(rtr, app_list, **{'self': self})
        if return_value:
            mem_pro_en_status.update({'status': 0})
    
    return mem_pro_en_status


def get_proc_collector_to_evo_re(rtr, node, **kwargs):
    """
    Uploads the proc_collector.py script to the EVO router in the RE node.
    """
    self = kwargs.get('self', None)
    testbed.log(f"'level' = INFO: Uploading proc_collector to RE node", display_log=True)
    
    rh = testbed.get_handle(resource=rtr)
    device_utils.set_current_controller(device=rh, controller=node)
    device_utils.switch_to_superuser(rh)

    proc_collector_loc = tv.get('uv-evo-proc-collector-profile-tools-path', '/volume/regressions/toby/test-suites/pdt/lib/longevity/dev_branch')
    
    # Upload the proc_collector script
    cmd_resp = host_utils.upload_file(rh, local_file=f"{proc_collector_loc}/proc_collector.py", remote_file='/var/home/regress/proc_collector.py', protocol='scp', user='regress', password='MaRtInI')
    
    if not cmd_resp:
        testbed.log(f"'level' = WARN: Failed to upload proc_collector.py to {rtr}", display_log=True)

      
        device_utils.set_current_controller(device=rh, controller='master')
        return  # Exit the function if upload failed

    device_utils.set_current_controller(device=rh, controller='master')


def get_proc_collector_to_evo_fpc(rtr, node, **kwargs):
    """
    Uploads the proc_collector.py script to the EVO router in the FPC node.
    """
    self = kwargs.get('self', None)
    rh = testbed.get_handle(resource=rtr)
    device_utils.switch_to_superuser(rh)

    proc_collector_loc = tv.get('uv-evo-proc-collector-profile-tools-path', '/volume/regressions/toby/test-suites/pdt/lib/longevity/dev_branch')
    
    # Upload the proc_collector script
    cmd_resp = host_utils.upload_file(rh, local_file=f"{proc_collector_loc}/proc_collector.py", remote_file='/var/home/regress/proc_collector.py', protocol='scp', user='regress', password='MaRtInI')
    
    if not cmd_resp:
        testbed.log(f"'level' = WARN: Failed to upload proc_collector.py to {rtr} (FPC node)", display_log=True)
       
        device_utils.set_current_controller(device=rh, controller='master')
        return  # Exit the function if upload failed
    
    # Execute command on device after upload
    device_utils.execute_shell_command_on_device(device=rh, timeout=self.cmd_timeout, command=f"chvrf iri scp-internal -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR /var/home/regress/proc_collector.py root@{node}:", pattern='Toby.*%$')


def Get_Proc_Collector(rtr, node_list, **kwargs):
    """
    Iterates through a list of nodes and uploads proc_collector to each node (RE or FPC).
    """
    self = kwargs.get('self', None)
    
    # Loop through each node and upload proc_collector.py accordingly
    for node in node_list:
        is_node_re = 're' in node
        is_node_fpc = 'fpc' in node
        
        if is_node_re:
            get_proc_collector_to_evo_re(rtr, node, **{'self': self})
        if is_node_fpc:
            get_proc_collector_to_evo_fpc(rtr, node, **{'self': self})
            
            

def initialize_proc_collector_data_structure_on_rtr_for_cleanup(rtr, node_list, **kwargs):
    """
    Initializes the proc_collector cleanup structure on the router for the given node list.
    """
    self = kwargs.get('self')
    if self is None:
        raise ValueError("Missing 'self' in kwargs")

    # Initialize cleanup attributes for each node in the node_list
    for node in node_list:
        setattr(self, f"proc_collector_cleanup_{rtr}_{node}_list", [])

def get_elements_texts(xml_response, xpath):
    """
    Function to extract text from elements in the XML response based on the provided XPath.
    """
    tree = etree.fromstring(xml_response)
    elements = tree.xpath(xpath)
    return [element.text for element in elements]

def pdt_get_app_node_list(rtr, app_name, **kwargs):
    """
    Retrieves the application node list for the given router and application name.
    """
    self = kwargs.get('self', None)
    testbed.log(f"'level' = INFO: Fetching app node list for {app_name} on {rtr}", display_log=True)
    
    rh = testbed.get_handle(resource=rtr)
    cli_cmd_exec_timeout = tv.get('uv-cmd-timeout', '900')
    self.cli_cmd_exec_timeout = cli_cmd_exec_timeout
    
    # Execute the command to fetch the application node list
    xml_cmd_response = device_utils.execute_cli_command_on_device(
        device=rh, 
        command=f"show system applications app {app_name} | display xml", 
        timeout=self.cli_cmd_exec_timeout, 
        pattern='Toby.*>$'
    )

    
    # Initialize the app node list (assumed to be populated by the XML response parsing)
    app_node_list =  get_elements_texts(xml_cmd_response, ".//system-applications-info/system-applications-info-entry/system-application-node")
    
    return len(app_node_list), app_node_list

def initialize_proc_collector_data_structure_on_rtr_for_node_list(rtr, app, node_list, **kwargs):
    """
    Initializes the proc_collector data structure for each node in the node list.
    """
    self = kwargs.get('self')
    if not self:
        raise ValueError("Missing 'self' in kwargs")  # Error handling for missing 'self'

    # Iterate over each node in the list and initialize the attribute
    for node in node_list:
        attribute_name = f"dict_rtr_{node}_{app}"
        setattr(self, attribute_name, {})  # Set the attribute to an empty string for each node-app pair


def evo_proc_collector_init_on_rtr(rtr, app_list, mode, **kwargs):
    """
    Initializes the proc collector on the router for the given application list and mode.
    """
    self = kwargs.get('self')
    if self is None:
        raise ValueError("Missing 'self' in kwargs")

    rh = testbed.get_handle(resource=rtr)
    node_list = evo_get_node_list(rtr, **{"self": self})

    # Handle mode-specific initialization
    if mode == 'lrm_config':
        Get_Proc_Collector(rtr, node_list, **{"self": self})
        initialize_proc_collector_data_structure_on_rtr_for_cleanup(rtr, node_list, **{"self": self})

    # Initialize proc collector data structure for each application
    for app in app_list:
        node_list_len, _ = pdt_get_app_node_list(rtr, app, **{"self": self})

        if node_list_len == 0:
            # Ensure the attribute is initialized as a list, converting it if necessary
            attr_name = f"{rtr}_lrm_disabled_apps"
            existing_value = getattr(self, attr_name, None)

            if existing_value is None or isinstance(existing_value, str):
                setattr(self, attr_name, [])  # Initialize or convert to a list

            getattr(self, attr_name).append(app)



def evo_proc_collector_init(mode, **kwargs):
    """
    Initializes the proc collector across all EVO routers and apps for the given mode.
    """
    self = kwargs.get('self', None)
    proc_collector_profile_tools_path = tv.get('uv-evo-proc-collector-profile-tools-path', '/volume/regressions/toby/test-suites/pdt/lib/longevity/dev_branch')
    self.proc_collector_profile_tools_path = proc_collector_profile_tools_path
    
    for rtr in self.evo_lng_rtr_list:
        # Initialize the tracking list for each router
        setattr(self, f"proc_collector_track_{rtr}_list", '')
        
        # Check if the app list exists for the current router
        is_key_exist = 'uv-evo-mem-profile-app-list' in t['resources'].get(rtr, {}).get('system', {}).get('primary', {})
        
        hostname = tv.get(f"{rtr}__re0__hostname")
        
        if not is_key_exist:
            testbed.log(f"'level' = WARN: No memory profile app list for {rtr}", display_log=True)
            continue
        
        # Get the app list based on the mode
        if mode == 'lrm_config':
            app_list = tv.get(f"{rtr}__uv-evo-mem-profile-app-list").split(',')
            if failed_apps_not_enabled_memory_profiling:
                if hostname in failed_apps_not_enabled_memory_profiling:
                    app_list.extend(failed_apps_not_enabled_memory_profiling[hostname])
                    app_list = list(set(app_list)) 
        else:
            app_list = getattr(self, f"{rtr}_lrm_disabled_apps", None)
        
        # Initialize proc collector for each router and app
        return_value = evo_proc_collector_init_on_rtr(rtr, app_list, mode, **{'self': self})

def pdt_get_file_from_re(rtr, node, src_file, dst_location, **kwargs):
    """
    Retrieves a file from a remote device to a local destination.
    """
    
    self = kwargs.get('self', None)
    rh = testbed.get_handle(resource=rtr)
    _h_name = device_utils.get_host_name_for_device(rh)
  
    device_utils.set_current_controller(rh, controller=node)

    # Check if the source file exists
    resp_from_cmd = device_utils.execute_cli_command_on_device(device=rh, 
                                                               command=f"file list {src_file}", 
                                                               timeout=600, 
                                                               pattern='Toby.*>$')
    
    is_file_exist = 'No such file or directory' not in resp_from_cmd
    
    if not is_file_exist:
        testbed.log(f"'level' = WARN: File not found at {src_file} on {rtr}", display_log=True)
        device_utils.set_current_controller(rh, controller='master')
        return  # Exit if the file doesn't exist
    
    # Ensure the destination directory exists
    if not os.path.exists(dst_location):
        try:
            os.makedirs(dst_location, exist_ok=True)
            testbed.log(f"'level' = INFO: Created destination directory {dst_location}", display_log=True)
        except Exception as e:
            testbed.log(f"'level' = WARN: Failed to create directory {dst_location}. Error: {e}", display_log=True)
            device_utils.set_current_controller(rh, controller='master')
            return  # Exit if directory creation fails

    # Extract the file name from the source path using regex
    file_name_matches = [match.group(1) for match in re.finditer(r'\S+\/(\S+)', src_file)]
    file_name = file_name_matches[0] if file_name_matches else "unknown_file"
    
    # Download the file
    dwnd_status = host_utils.download_file(rh, 
                                           remote_file=src_file, 
                                           local_file=f"{dst_location}/{_h_name}.{node}.{file_name}")
    
    if dwnd_status:
        testbed.log(f"'level' = INFO: File {src_file} downloaded to {dst_location}/{_h_name}.{node}.{file_name}", display_log=True)
    else:
        testbed.log(f"'level' = WARN: Failed to download {src_file} to {dst_location}/{_h_name}.{node}.{file_name}", display_log=True)
    
    # Set the controller back to 'master'
    device_utils.set_current_controller(rh, controller='master')


def pdt_get_file_from_fpc(rtr, node, src_file, dst_location, **kwargs):
    """
    Retrieves a file from an FPC node on a router via SCP and places it in the destination directory.
    """
    self = kwargs.get('self', None)
    rh = testbed.get_handle(resource=rtr)
    _h_name = device_utils.get_host_name_for_device(rh)
    device_utils.switch_to_superuser(device=rh)

    # Check if the source file exists on the node
    resp_from_cmd = device_utils.execute_shell_command_on_device(device=rh,
                                                                command=f"chvrf iri ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR root@{node} ls {src_file}",
                                                                timeout=600, pattern='Toby.*%$')

    if 'No such file or directory' in resp_from_cmd:
        testbed.log(f"'level' = WARN: File {src_file} not found on {node}", display_log=True)
        return

    # Extract the file name using regex
    file_name_matches = [match.group(1) for match in re.finditer(r'\S+\/(\S+)', src_file)]
    if not file_name_matches:
        testbed.log(f"'level' = WARN: Failed to extract file name from {src_file}", display_log=True)
        return

    new_file_name = f"{node}.{file_name_matches[0]}"

    # Perform SCP file transfer
    resp_from_cp_cmd = device_utils.execute_shell_command_on_device(device=rh,
                                                                   command=f"chvrf iri scp-internal -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR root@{node}:{src_file} /var/home/regress/{new_file_name}",
                                                                   timeout=600, pattern='Toby.*%$')

    if '100%' not in resp_from_cp_cmd:
        testbed.log(f"'level' = WARN: Failed to copy file {src_file} from {node}", display_log=True)
        return

    # Change permissions on the copied file
    resp_from_chmod_cmd = device_utils.execute_shell_command_on_device(device=rh,
                                                                      command=f"chmod 777 /var/home/regress/{new_file_name}",
                                                                      timeout=600, pattern='Toby.*%$')

    # Ensure the destination directory exists
    if not os.path.exists(dst_location):
        try:
            os.makedirs(dst_location, exist_ok=True)
            testbed.log(f"'level' = INFO: Created destination directory {dst_location}", display_log=True)
        except Exception as e:
            testbed.log(f"'level' = WARN: Failed to create directory {dst_location}. Error: {e}", display_log=True)
            return

    # Download the file to the local machine
    dwnd_status = host_utils.download_file(rh,
                                           remote_file=f"/var/home/regress/{new_file_name}",
                                           local_file=f"{dst_location}/{_h_name}.{new_file_name}")
    
    if dwnd_status:
        testbed.log(f"'level' = INFO: File downloaded successfully to {dst_location}/{_h_name}.{new_file_name}", display_log=True)
    else:
        testbed.log(f"'level' = WARN: Failed to download {new_file_name}", display_log=True)


def pdt_dump_memory_profile_on_rtr_for_node_list(rtr, app, node_list, itr_tag, **kwargs):
    """
    Dumps the memory profile for each node in the node list and retrieves the dump files.
    """
    self = kwargs.get('self', None)
    rh = testbed.get_handle(resource=rtr)

    for node in node_list:
        cmd_response = device_utils.execute_cli_command_on_device(device=rh,
                                                                  command=f"request system memory-profiling node {node} application {app} dump",
                                                                  timeout=self.cli_cmd_exec_timeout, pattern='Toby.*>$')

        # Check if the dump file location is included in the response
        if f"/var/log/{app}." not in cmd_response:
            testbed.log(f"'level' = WARN: Memory profile dump for {node} not found", display_log=True)
            continue

        # Extract the dump file location
        
        dump_file_location = [match.group(1) for match in re.finditer(r'location (\S+)', cmd_response)]
        if not dump_file_location:
            testbed.log(f"'level' = WARN: Failed to extract dump file location for {node}", display_log=True)
            continue

        # Log the file location and update the dictionary with the file location
        testbed.log(f"'level' = INFO: Dump file location for {node}: {dump_file_location[0]}", display_log=True)
        
        matches = [match.group(1) for match in re.finditer(r'test_config_itr_(\d+)', itr_tag)] or []
        key = itr_tag if not matches else matches[0]
        
        # Construct the attribute name
        attr_name = f"dict_{rtr}_{node}_{app}"

        # Get the dictionary using getattr() and update it
        existing_dict = getattr(self, attr_name, None)
        if existing_dict is None:
            existing_dict = {}  # Initialize if attribute doesn't exist
            setattr(self, attr_name, existing_dict)  # Assign it to self

        # Update the dictionary
        if dump_file_location and isinstance(dump_file_location, list):  # Ensure dump_file_location is valid
            existing_dict.update({key: dump_file_location[0]})


        #eval(f"{'dict_' + rtr + '_' + node + '_' + app}").update({key: dump_file_location[0]})

        # Check if the node is a RE node and handle accordingly
        if 're' in node:
            pdt_get_file_from_re(rtr, node, dump_file_location[0], f"{self.LONGEVITY_OUTPUT_DIR}/{itr_tag}", **{'self': self})
        else:
            pdt_get_file_from_fpc(rtr, node, dump_file_location[0], f"{self.LONGEVITY_OUTPUT_DIR}/{itr_tag}", **{'self': self})



def pdt_move_file(rtr, node, src_file, dst_path, **kwargs):
    """
    Move a file from the source to the destination path on a router. Handles both RE and FPC nodes.
    """
    self = kwargs.get('self', None)
    rh = testbed.get_handle(resource=rtr)
    if 're' in node:
        # For RE node
      
        device_utils.set_current_controller(rh, controller=node)
        device_utils.switch_to_superuser(rh)
        device_utils.execute_shell_command_on_device(device=rh, timeout=self.cmd_timeout,
                                                     command=f"cp {src_file} {dst_path}", pattern='Toby.*%$')
        device_utils.set_current_controller(rh, controller='master')
    else:
        # For FPC node
        device_utils.switch_to_superuser(rh)
        device_utils.execute_shell_command_on_device(device=rh, timeout=self.cmd_timeout,
                                                     command=f"chvrf iri ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR root@{node} \"cp {src_file} {dst_path}\"", pattern='Toby.*%$')
    testbed.log(f"'level' = INFO: Moved file {src_file} to {dst_path}", display_log=True)


def pdt_dump_rpd_memory_profile(rtr, app, node_list, itr_tag, **kwargs):
    """
    Dumps the memory profile for the RPD application on the router for each node in node_list.
    """
    self = kwargs.get('self', None)
    rh = testbed.get_handle(resource=rtr)
    #
    for node in node_list:
        # Get the PID of the application
        pid_xml_resp = device_utils.execute_cli_command_on_device(device=rh, command=f"show system applications app {app} detail node {node} | display xml", 
                                                                  timeout=self.cli_cmd_exec_timeout, pattern='Toby.*>$')
        app_pid = xml_utils.get_element_text(pid_xml_resp, ".//system-applications-info/system-applications-info-entry/system-application-mainpid")
        
        # Delete any old heap files
        del_response = device_utils.execute_cli_command_on_device(device=rh, command=f"file delete /var/core/jeprof.{app_pid}.*", 
                                                                  timeout=self.cli_cmd_exec_timeout, pattern='Toby.*>$')
        
        # Trigger the memory leak detector dump
        cmd_response = device_utils.execute_cli_command_on_device(device=rh, command='set task memory-leak-detector dump', 
                                                                  timeout=self.cli_cmd_exec_timeout, pattern='Toby.*>$')

        if 'Task memory leak detection profile dumped' not in cmd_response:
            testbed.log(f"'level' = WARN: Memory leak dump failed on {node} for app {app}", display_log=True)
            continue
        
        LSLEEP('15', **{'self': self})

        # List the newly generated heap file
        cmd_response1 = device_utils.execute_cli_command_on_device(device=rh, command=f"file list /var/core/jeprof.{app_pid}.* | last 1 | no-more", 
                                                                   timeout=self.cli_cmd_exec_timeout, pattern='Toby.*>$')

        if 'No such file or directory' in cmd_response1:
            testbed.log(f"'level' = WARN: No heap file generated for {node}", display_log=True)
            continue
        
        dump_file_location = [match.group(1) for match in re.finditer(r'(\S+)', cmd_response1)] or []
        
        # Move the heap file to the appropriate location
        rpd_heap_file = re.sub(r'/var/core/jeprof', '/var/log/routing', dump_file_location[0], -1)
        rpd_heap_file = re.sub(r'.f', '', rpd_heap_file, -1)

        pdt_move_file(rtr, node, dump_file_location[0], rpd_heap_file, **{'self': self})

        # Retrieve the heap file and store it locally
        if 'fpc' in node:
            pdt_get_file_from_fpc(rtr, node, rpd_heap_file, f"{self.LONGEVITY_OUTPUT_DIR}/{itr_tag}", **{'self': self})

        # Update the dictionary with the dump file location
        matches = [match.group(1) for match in re.finditer(r'test_config_itr_(\d+)', itr_tag)] or []
        key = itr_tag if not matches else matches[0]
        #
        # Construct the attribute name
        attr_name = f"dict_{rtr}_{node}_{app}"

        # Get the dictionary using getattr() and update it
        existing_dict = getattr(self, attr_name, None)
        if existing_dict is None:
            existing_dict = {}  # Initialize if attribute doesn't exist
            setattr(self, attr_name, existing_dict)  # Assign it to self

        # Update the dictionary
        
        #
        if rpd_heap_file:  # Ensure dump_file_location is valid
            existing_dict.update({key: rpd_heap_file})

        
        #eval(f"{'dict_' + rtr + '_' + node + '_' + app}").update({key: rpd_heap_file})

    testbed.log(f"'level' = INFO: Completed RPD memory dump for {app} on nodes: {', '.join(node_list)}", display_log=True)


def pdt_dump_memory_profile_on_rtr(rtr, app_list, itr_tag, **kwargs):
    """
    Dumps memory profiles for the specified application list on the router.
    """
    self = kwargs.get('self', None)
    rh = testbed.get_handle(resource=rtr)
    
    for app in app_list:
        _,node_list = pdt_get_app_node_list(rtr, app, **{'self': self})
        
        if app != 'routing':
            pdt_dump_memory_profile_on_rtr_for_node_list(rtr, app, node_list, itr_tag, **{'self': self})
        else:
            #
            pdt_dump_rpd_memory_profile(rtr, app, node_list, itr_tag, **{'self': self})
            #


def pdt_dump_memory_profile(itr_tag, rtr_list, **kwargs):
    """
    Dumps memory profiles for the list of routers.
    """
    self = kwargs.get('self', None)
    testbed.log(f"'level' = INFO: Starting memory dump for routers: {', '.join(rtr_list)}", display_log=True)
    
    for rtr in rtr_list:
        hostname = tv.get(f"{rtr}__re0__hostname")
        if 'uv-evo-mem-profile-app-list' not in t['resources'][rtr]['system']['primary']:
            testbed.log(f"'level' = WARN: No memory profile app list found for {rtr}", display_log=True)
            continue
           
            #
          
        app_list = tv.get(f"{rtr}__uv-evo-mem-profile-app-list").split(',')
        if failed_apps_not_enabled_memory_profiling:
            if hostname in failed_apps_not_enabled_memory_profiling:
                app_list.extend(failed_apps_not_enabled_memory_profiling[hostname])
                app_list = list(set(app_list)) 
        
        pdt_dump_memory_profile_on_rtr(rtr, app_list, itr_tag, **{'self': self})
    
    testbed.log(f"'level' = INFO: Completed memory profile dump for all routers", display_log=True)


def pdt_get_jemelloc_mem_prof_from_rtr_for_fpc(rtr, fpc, jemelloc_app_list, position, itr_tag, **kwargs):
    """
    Retrieves jemalloc memory profile from the FPC on the router for each application in jemelloc_app_list.
    """
    self = kwargs.get('self', None)
    rh = testbed.get_handle(resource=rtr)
    is_fixed_form_factor = evo_is_chassis_form_factor_fixed(rtr, **{'self': self})

    for app in jemelloc_app_list:
        current_timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        host_name = device_utils.get_host_name_for_device(rh)
        file_name = f"{rtr}.{position}.{app}.mem_prof.{current_timestamp}"

        # Log the operation
        testbed.log(f"'level' = INFO: Requesting memory profile for app {app} on {rtr} ({position})", display_log=True)

        # Execute command on FPC
        command_response = device_utils.execute_cli_command_on_device(device=rh, 
            command=f"request pfe execute command \"test mem-prof {app} {file_name}\" target fpc{fpc}", timeout=600, pattern='Toby.*>$')

        # Check if the response is valid
        if f"Memory dump created as /var/tmp/.jemalloc/{file_name}" not in command_response:
            testbed.log(f"'level' = WARN: Invalid response for app {app} on {rtr}", display_log=True)
            continue

        # Extract file location from the response
        file_location = re.search(r'Memory dump created as (\S+).', command_response)
        if file_location:
            file1_name = file_location.group(1).rstrip('_')

            # Retrieve files based on the chassis form factor
            if is_fixed_form_factor:
                pdt_get_file_from_re(rtr, 're0', file1_name, f"{self.LONGEVITY_OUTPUT_DIR}/{itr_tag}", **{'self': self})
            else:
                pdt_get_file_from_fpc(rtr, f"fpc{fpc}", file1_name, f"{self.LONGEVITY_OUTPUT_DIR}/{itr_tag}", **{'self': self})

            # Retrieve additional memory stats file
            file2_name = f"{file1_name}-memstats.txt"
            if is_fixed_form_factor:
                pdt_get_file_from_re(rtr, 're0', file2_name, f"{self.LONGEVITY_OUTPUT_DIR}/{itr_tag}", **{'self': self})
            else:
                pdt_get_file_from_fpc(rtr, f"fpc{fpc}", file2_name, f"{self.LONGEVITY_OUTPUT_DIR}/{itr_tag}", **{'self': self})

    testbed.log(f"'level' = INFO: Memory profiling completed for applications: {', '.join(jemelloc_app_list)} on FPC {fpc}", display_log=True)


def pdt_get_jemelloc_mem_prof_from_rtr(rtr, jemelloc_app_list, position, itr_tag, **kwargs):
    """
    Iterates over FPCs of a router and retrieves jemalloc memory profiles for each application in jemelloc_app_list.
    """
    self = kwargs.get('self', None)
    rh = testbed.get_handle(resource=rtr)

    # Fetch the list of online FPCs
    xml_out = device_utils.execute_cli_command_on_device(device=rh, command='show chassis fpc | display xml', timeout=600, pattern='Toby.*>$')
    fpc_list = xml_utils.get_elements_texts(xml_out, ".//fpc-information/fpc[state='Online']/slot")

    if not fpc_list:
        testbed.log(f"'level' = WARN: No online FPCs found for {rtr}", display_log=True)

    # Retrieve memory profiles for each FPC
    for fpc in fpc_list:
        pdt_get_jemelloc_mem_prof_from_rtr_for_fpc(rtr, fpc, jemelloc_app_list, position, itr_tag, **{'self': self})


def pdt_get_jemelloc_mem_prof(itr_tag, position='PRE', rtr_list=None, **kwargs):
    """
    Iterates over a list of routers and retrieves jemalloc memory profiles for each.
    """
    self = kwargs.get('self', None)
    rtr_tag = evo_longevity_rtr_tag if 'evo_longevity_rtr_tag' in locals() else 'evo'

    # Determine the router list
    rtrs = rtr_list if rtr_list else testbed.get_resource_list(tag=rtr_tag)

    if not rtrs:
        testbed.log(f"'level' = WARN: No routers found for tag {rtr_tag}", display_log=True)

    # Process each router
    for rtr in rtrs:
        rh = testbed.get_handle(resource=rtr)
    
        if rh.is_evo():
            
            # Ensure list of apps is defined for the given router
            jemelloc_app_list_string = tv.get(
                f"{rtr}__uv-evo-jemelloc-mem-prof-app-list",
                "cda,packetio"
            )
            jemelloc_app_list = jemelloc_app_list_string.split(',')
            pdt_get_jemelloc_mem_prof_from_rtr(rtr, jemelloc_app_list, position, itr_tag, **{'self': self})

    testbed.log(f"'level' = INFO: Memory profiling completed for routers: {', '.join(rtrs)}", display_log=True)


def Get_Current_Time_Of_Device(_rtr, **kwargs):
    """
    Retrieves the current time of a device by checking its system uptime.
    """
    self = kwargs.get('self', None)
    _rh = testbed.get_handle(resource=_rtr)
    rtr_model = device_utils.get_model_for_device(device=_rh).lower()

    # Check device type
    is_rtr_mx = 'mx' in rtr_model
    is_rtr_ptx = 'ptx' in rtr_model
    is_rtr_acx = 'acx' in rtr_model
    is_rtr_srx = 'srx' in rtr_model
    is_rtr_ex = 'ex' in rtr_model
    is_rtr_qfx = any(model in rtr_model for model in ['qfx5110', 'qfx5120', 'qfx5130', 'qfx52'])
    is_rtr_qfx5100 = 'qfx5100' in rtr_model

    if not any([is_rtr_ex, is_rtr_qfx5100, is_rtr_qfx]):
        device_utils.reconnect_to_device(device=_rh, all=True, timeout=300, interval=60, force=True, channel_name='all')

    local_node_type = 'fpc0' if is_rtr_ex or is_rtr_qfx5100 else 'localre'
    current_time_type1 = ''

    if not (is_rtr_ex or is_rtr_qfx5100 or is_rtr_qfx):
        try:
            current_time_type1 = system_time.get_system_time(device=_rh)
        except Exception:
            current_time_type1 = None
    
    current_time = None
    if is_rtr_ex or is_rtr_qfx5100 or is_rtr_qfx:
        xml_out = device_utils.execute_cli_command_on_device(device=_rh, command='show system uptime | display xml', pattern='Toby.*>$')
        current_time_data = xml_utils.get_elements_texts(xml_out, f"./multi-routing-engine-results/multi-routing-engine-item[re-name=\"{local_node_type}\"]/system-uptime-information/current-time/date-time")
        if current_time_data:
            current_time_match = re.findall(r'(\d+-\d+-\d+\s+\d+:\d+:\d+)', current_time_data[0])
            current_time = current_time_match[0] if current_time_match else None

    return current_time or current_time_type1



def evo_get_active_pfe_list_from_fpc(rtr, fpc, **kwargs):
    """
    Retrieves the list of active PFEs from a given FPC on the router.
    """
    self = kwargs.get('self', None)
    rh = testbed.get_handle(resource=rtr)
    
    xml_out = device_utils.execute_cli_command_on_device(
        device=rh,
        command=f"request pfe execute command \"show pfe id info | display xml\" target fpc{fpc} | except SENT",
        pattern='Toby.*>$'
    )
    
    active_pfe_list = []  # Placeholder for actual parsing of XML output
    return active_pfe_list



def Evo_Capture_Memory_Snapshot(rtr, position, itr_tag,**kwargs):

    self = kwargs.get('self', None)
    rh =  testbed.get_handle(resource=rtr)
    isEvo = rh.is_evo()
    if not isEvo:
        return EMPTY
    node_list = evo_get_node_list(rtr,**{'self':self})
    re_cmd_list =  ['show platform distributor statistics summary', 'show platform distributor statistics all-clients', 'show version', 'show chassis fpc', 'show chassis fpc pic-status', 'show chassis hardware', 'show system alarms', 'show system process extensive', 'show task memory detail', 'show route summary', 'show krt state', 'show krt queue', 'show platform object-info anomalies summary', 'show platform application-info allocations', 'show route forwarding-table family inet summary', 'show route forwarding-table family inet6 summary', 'show route forwarding-table family mpls summary', 'show platform application-info allocations', 'show platform binding-queue summary', 'show platform binding-queue incomplete', 'show platform binding-queue complete-deleted', 'show platform app-controller summary', 'show platform dependency-state', 'show platform dmf', 'show system memory statistics jemalloc-stats', 'show system storage', 'show platform object-info anomalies', 'show platform object-info anomalies app pfetokend', 'show platform application-info allocations app pfetokend', 'show platform app-controller incomplete', 'show platform app-controller incomplete app pfetokend']
    for _node in node_list:
        re_cmd_list.append(f"show system memory statistics smap-stats node {_node}")
        re_cmd_list.append(f"show system applications node {_node}")
    self.re_cmd_list = re_cmd_list
    re_shell_cmd_list =  ['top -o RES -b -n1', 'df -h /var', 'du -sh /var', 'vmstat -s', 'cat /proc/meminfo', 'netstat -np | grep 19010 | grep ESTABLISHED', 'cli -c \"set task accounting on\"', 'sleep 30', 'cli -c \"show task accounting detail | no-more\"', 'cli -c \"set task accounting off\"', 'cli -c \"show task jobs | no-more\"', 'cli -c \"show task io | no-more\"', 'cli -c \"set task accounting on\"', 'sleep 30', 'cli -c \"show task accounting detail | no-more\"', 'cli -c \"set task accounting off\"', 'cli -c \"show task jobs | no-more\"', 'cli -c \"show task io | no-more\"', 'cli -c \"set task accounting on\"', 'sleep 30', 'cli -c \"show task accounting detail | no-more\"', 'cli -c \"set task accounting off\"', 'cli -c \"show task jobs | no-more\"', 'cli -c \"show task io | no-more\"', 'top -b -n 1 | awk \'$8 == \"Z\" || $8 == \"T\"\'']
    self.re_shell_cmd_list = re_shell_cmd_list
    fpc_cmd_list =  ['show sandbox stats', 'show cda npu utilization packet-rates', 'show cda statistics server api', 'show npu utilization info', 'show npu memory info', 'show nh summary', 'show nh management', 'show route summary', 'show route all summary', 'show route ack', 'show aft transport stats', 'show jexpr unilist stats', 'show jexpr route mpls stats', 'show irp memory app usage', 'show irp memory lb usage', 'show interfaces summary', 'show host-path app wedge-detect state | grep State', 'show nh db', 'show system cpu']
    self.fpc_cmd_list = fpc_cmd_list
    fpc_pfe_cmd_list =  ['show jexpr chash pfe', 'show jexpr jtm egress-memory summary chip', 'show jexpr jtm egress-const-memory chip', 'show jexpr jtm egress-private-desc chip', 'show jexpr jtm egress-public-desc chip', 'show jexpr jtm egress-mactbl-memory chip', 'show jexpr jtm egress-tunnel-memory chip', 'show jexpr jtm ingress-main-memory chip', 'show jexpr jtm ingress-special-memory chip', 'show jexpr jtm mce-block-memory chip', 'show jexpr plct usage counter dev', 'show jexpr plct usage policer dev']
    self.fpc_pfe_cmd_list = fpc_pfe_cmd_list
    fpc_shell_cmd_list =  ['top -o RES -b -n1', 'df -h /var', 'du -sh /var', 'ls -lSR /var/log', 'vmstat -s', 'cat /proc/meminfo', 'netstat -np | grep 19010 | grep ESTABLISHED', 'top -b -n 1 | awk \'$8 == \"Z\" || $8 == \"T\"\'']
    self.fpc_shell_cmd_list = fpc_shell_cmd_list
    self.position = position
    cmd_timeout =  tv.get('uv-cmd-timeout', '900')
    self.cmd_timeout = self.cmd_timeout
    host_name =  device_utils.get_host_name_for_device(rh)
    model =  device_utils.get_model_for_device(rh)
    xml_out =  device_utils.execute_cli_command_on_device(device=rh, command='show chassis fpc | display xml', timeout=self.cmd_timeout, pattern='Toby.*>$')
    fpc_list =  xml_utils.get_elements_texts(xml_out,"fpc-information/fpc[state='\'Online\']/slot")
    testbed.log(f"'level' = INFO", display_log=True)
    curr_date =  datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    file_name =  '.'.join([host_name, self.position, curr_date, 'log'])
    fh = f"{self.LONGEVITY_OUTPUT_DIR}/{itr_tag}/{file_name}"
    os.makedirs(os.path.dirname(fh), exist_ok=True)
    with open(fh, 'w', encoding='UTF-8') as file_hdl:
        file_hdl.write('UTF-8')
    isFileCreated =  isFileCreated if 'isFileCreated' in globals() else 'True'
    try:
        assert os.path.exists(fh)
    except Exception as e:
        isFileCreated =  False
    if not isFileCreated:
        testbed.log(f"'level' = WARN", display_log=True)
        return EMPTY
    testbed.log(f"'level' = INFO", display_log=True)
    Evo_Re_Cmd_Capture(rtr, rh, fh,**{'self':self})
    Evo_RE_Shell_Cmd_Capture(rtr, rh, fh,**{'self':self})
    if self.skip_fpc_checks== str(0) :
        evo_fpc_cmd_capture(rtr, rh, fh, self.fpc_list,**{'self':self})
    if self.skip_fpc_checks== str(0) :
        Evo_PS_MEM_Cmd_Capture(rtr, rh, fh, self.fpc_list,**{'self':self})
    testbed.log(f"'level' = INFO", display_log=True)
    pass

def EVO_Memory_Snapshot(rtr_list, position, itr_tag,**kwargs):

    self = kwargs.get('self', None)
    for rtr in rtr_list:
        Evo_Capture_Memory_Snapshot(rtr, self.position, itr_tag,**{'self':self})
    pass

def evo_dump_memory_prof(itr_tag,**kwargs):

    self = kwargs.get('self', None)
    pdt_dump_memory_profile(itr_tag, self.evo_lng_rtr_list,**{'self':self})
    pdt_get_jemelloc_mem_prof(itr_tag=itr_tag, position=itr_tag, rtr_list=self.evo_lng_rtr_list,**{'self':self})
    #EVO_Memory_Snapshot(rtr_list=self.evo_lng_rtr_list, self_position=itr_tag, itr_tag=itr_tag,**{'self':self})
    pass





def longevity_junos_data_collection(itr_tag,**kwargs):

    self = kwargs.get('self', None)
    JunOS_Memory_Snapshot(rtr_list=self.junos_lng_rtr_list, self_position=itr_tag, itr_tag=itr_tag,**{'self':self})
    pass


    


    


def log_event_start(event_type, annotation, hostname, args_1=None, self=None):
    LLOG(message='-----------------------------------------------------------', **{'self': self})
    if args_1:
        LLOG(message=f"** BEGIN HALT EVENT {event_type}: {annotation} / {args_1} **", **{'self': self})
    else:
        LLOG(message=f"** BEGIN HALT EVENT {event_type}: {annotation} **", **{'self': self})
    LLOG(message='-----------------------------------------------------------\n', **{'self': self})
    if hostname:
        LLOG(message=f"@@@@ {hostname}\n", **{'self': self})

def log_event_end(event_type, annotation, self=None):
    LLOG(message='-----------------------------------------------------------', **{'self': self})
    LLOG(message=f"** END HALT EVENT {event_type}: {annotation} **", **{'self': self})
    LLOG(message='-----------------------------------------------------------\n', **{'self': self})

def process_sleep(duration, self=None):
    LLOG(message=f"** Sleep for {duration} seconds **\n", **{'self': self})
    testbed.log(f"Sleeping for {duration} seconds", display_log=True)
    sleep_secs = int(float(re.sub(r'\D', '', str(duration))))
    time.sleep(sleep_secs)

def Type_One(cmd, annotation, duration, count, args_1, hostname, **kwargs):
    self = kwargs.get('self', None)
    log_event_start("TYPE 1 (EVO APP SPECIFIC)", annotation, hostname, **{"self": self})
    
    dh = self.longevity_dut_handles[hostname]
    if not dh.is_evo():
        LLOG(message='App Restart is not applicable to JunOS Platform. Skipping app restart.\n', **{'self': self})
        return
    
    app_args = args_1.split(',')
    wait_time = int(float(app_args[1]))
    try:
        event_engine.run_event('Restart App', app=cmd, device=dh, node=app_args[0], enable_check='True', wait_for_reboot=wait_time)
    except Exception:
        pass
    
    #MonitoringEngine.monitoring_engine_annotate(annotation=f"{annotation}{count}")
    process_sleep(duration, **{"self": self})
    log_event_end("TYPE 1 (EVO APP SPECIFIC)", annotation, **{"self": self})

def Type_Two(cmd, annotation, duration, count, args_1, hostname, **kwargs):
    self = kwargs.get('self', None)
   
    log_event_start("TYPE 2", annotation, hostname, **{"self": self})
    
    dh = self.longevity_dut_handles[hostname]
    try:
        device_utils.execute_cli_command_on_device(device=dh, command=cmd, timeout=1800, pattern='Toby.*>$')
    except Exception:
        pass
    
    #MonitoringEngine.monitoring_engine_annotate(annotation=f"{annotation}{count}")
    process_sleep(duration, **{"self": self})
    log_event_end("TYPE 2", annotation, **{"self": self})

def Type_Three(cmd, annotation, duration, count, args_1, hostname, **kwargs):
    self = kwargs.get('self', None)
    log_event_start("TYPE 3", annotation, hostname, **{"self": self})
    
    dh = self.longevity_dut_handles[hostname]
    device_utils.switch_to_superuser(device=dh)
    try:
        event_engine.run_event('On SHELL', device=dh, command=cmd)
    except Exception:
        pass
    
    #MonitoringEngine.monitoring_engine_annotate(annotation=f"{annotation}{count}")
    process_sleep(duration, **{"self": self})
    log_event_end("TYPE 3", annotation, **{"self": self})

def Type_Four(cmd, annotation, duration, count, args_1, hostname, **kwargs):
    self = kwargs.get('self', None)
    log_event_start("TYPE 4", annotation, hostname, args_1=args_1, **{"self": self})
    
    dh = self.longevity_dut_handles[hostname]
    try:
        event_engine.run_event('Flap Interface', device=dh, interface=args_1, method=cmd)
        #
    except Exception:
        pass
    
    #MonitoringEngine.monitoring_engine_annotate(annotation=f"{annotation}{count}")
    process_sleep(duration, **{"self": self})
    log_event_end("TYPE 4", annotation, **{"self": self})


def get_device_handle(self, hostname):
    return self.longevity_dut_handles[hostname]

def Type_Generic(event_type, cmd, annotation, duration, count, args_1, hostname, event_name, event_kwargs=None, **kwargs):
    self = kwargs.get('self', None)
    event_kwargs = event_kwargs or {}
    log_event_start(event_type, annotation, args_1, self)
    
    dh = get_device_handle(self, hostname)
    try:
        _ = event_engine.run_event(event_name, device=dh, **event_kwargs)
    except Exception:
        pass
    
    annotation = f"{annotation}{count}"
    #MonitoringEngine.monitoring_engine_annotate(annotation=annotation)
    process_sleep(duration, self)
    log_event_end(event_type, annotation, self)

def Type_Five(cmd, annotation, duration, count, args_1, hostname, **kwargs):
    Type_Generic(5, cmd, annotation, duration, count, args_1, hostname, 'Flap Interface', 
                 {'interface': args_1, 'method': cmd}, **kwargs)

def Type_Six(cmd, annotation, duration, count, args_1, hostname, **kwargs):
    ae_args = args_1.split(',')
    Type_Generic(6, cmd, annotation, duration, count, args_1, hostname, 'Flap Interface', 
                 {'interface': ae_args[0], 'method': cmd, 'member_link_percentage': ae_args[1]}, **kwargs)

def Type_Seven(cmd, annotation, duration, count, args_1, hostname, **kwargs):
    Type_Generic(7, cmd, annotation, duration, count, args_1, hostname, 'ON CONFIG', 
                 {'command': f"{cmd}, commit, rollback 1, commit"}, **kwargs)

def Type_Eight(cmd, annotation, duration, count, args_1, hostname, **kwargs):
    Type_Generic(8, cmd, annotation, duration, count, args_1, hostname, 'ON CONFIG', 
                 {'command': f"deactivate {cmd}, commit, activate {cmd}, commit"}, **kwargs)

def Type_Nine(cmd, annotation, duration, count, args_1, hostname, **kwargs):
    Type_Generic(9, cmd, annotation, duration, count, args_1, hostname, 'Disable Enable config', 
                 {'config': cmd}, **kwargs)




def log_event(self, message, separator=False):
    """Centralized logging function."""
    if separator:
        LLOG(message='-' * 75, **{'self': self})
    LLOG(message=message, **{'self': self})

def run_event_with_handling(event_name, device, **kwargs):
    """Wrapper to run an event and handle exceptions gracefully."""
    try:
        _ = event_engine.run_event(event_name, device=device, **kwargs)
    except Exception as e:
        LLOG(message=f"Exception during event {event_name}: {e}", **{'self': kwargs.get('self', None)})

def sleep_for_duration(duration, self):
    """Handles duration parsing and sleeping."""
    sleep_secs = re.sub(r'\D', '', str(f"{duration} seconds"))
    time.sleep(int(float(sleep_secs)))
    testbed.log(f"Sleeping for {duration} seconds", display_log=True)
    log_event(self, f"** Sleep for {duration} seconds **")

def Type_Ten(cmd, annotation, duration, count, args_1, hostname, **kwargs):
    """Deletes and then sets a configuration."""
    self = kwargs.get('self', None)
    log_event(self, f"** BEGIN HALT EVENT TYPE 10: {annotation} **", separator=True)

    dh = self.longevity_dut_handles[hostname]
    run_event_with_handling('ON CONFIG', command=f"delete {cmd}, commit, set {cmd}, commit", device=dh, **{"self": self})

    #MonitoringEngine.monitoring_engine_annotate(annotation=f"{annotation}{count}")
    sleep_for_duration(duration, self)

    log_event(self, f"** END HALT EVENT TYPE 10: {annotation}{count} **", separator=True)

def Type_Eleven(cmd, annotation, duration, count, args_1, hostname, **kwargs):
    """Takes a chassis SIB offline and then brings it back online after a delay."""
    self = kwargs.get('self', None)
    log_event(self, f"** BEGIN HALT EVENT TYPE 11: {annotation} **", separator=True)

    dh = self.longevity_dut_handles[hostname]
    try:
        device_utils.execute_cli_command_on_device(device=dh, command='request chassis sib offline slot 0', pattern='Toby.*>$')
    except Exception as e:
        log_event(self, f"Exception during chassis sib offline: {e}")

    sleep_for_duration(args_1, self)

    try:
        device_utils.execute_cli_command_on_device(device=dh, command='request chassis sib online slot 0', pattern='Toby.*>$')
    except Exception as e:
        log_event(self, f"Exception during chassis sib online: {e}")

    #MonitoringEngine.monitoring_engine_annotate(annotation=f"{annotation}{count}")
    sleep_for_duration(duration, self)

    log_event(self, f"** END HALT EVENT TYPE 11: {annotation}{count} **", separator=True)


def _get_halt_event_details(self, val, dut):
    
    
    """Extract and validate event details from processed list."""
    
    val = int(val)-1
    
    #val = str(eval(str(f"{int(float(val))} - 1")))
    attr_name = f"processed_list_{dut}"
    event_list = getattr(self, attr_name, [])  # Fetches the attribute safely
    user_list =  event_list[val]

    
    if not user_list or len(user_list) < 5:
        raise ValueError(f"Invalid halt event data for DUT {dut}, val {val}")

    cmd, event_type, annotation, pre_duration, args = user_list[2], user_list[0], user_list[3], user_list[1], user_list[4]
    duration = int(float(pre_duration))
 
    # Extract 'args' parameter using regex
    match = re.search(r'args=(.+)', args)
    if not match:
        raise ValueError("Invalid args format, missing expected pattern.")

    args_1 = match.group(1)
    hostname = self.events_hosts[dut]
    return event_type, cmd, annotation, duration, args_1, hostname



def _get_halt_event_details_ddd(self, val, dut):
    
    """Extract and validate event details from processed list."""
    
    try:
        val = str(int(float(val)) - 1)  # Normalize 'val' as an integer string
    except ValueError:
        raise ValueError(f"Invalid value format: {val}")

    processed_list = locals().get(f"processed_list_{dut}", {})
    user_list = processed_list.get(val, [])

    if len(user_list) < 5:
        raise ValueError(f"Invalid halt event data for DUT {dut}, val {val}")

    event_type, pre_duration, cmd, annotation, args = user_list[:5]

    try:
        duration = int(float(pre_duration))  # Ensure duration is a valid integer
    except ValueError:
        raise ValueError(f"Invalid duration format: {pre_duration}")

    # Extract 'args' parameter using regex
    match = re.search(r'args=(.+)', args)
    if not match:
        raise ValueError("Invalid args format, missing expected pattern.")

    args_1 = match.group(1)
    hostname = self.events_hosts.get(dut, "Unknown")

    return event_type, cmd, annotation, duration, args_1, hostname

def execute_halt_event(event_type, cmd, annotation, duration, count, args_1, hostname, **kwargs):
    
    self = kwargs.get('self', None)
    
    """Execute the appropriate halt event function."""
    halt_event_map = {
        "One": Type_One,
        "Two": Type_Two,
        "Three": Type_Three,
        "Four": Type_Four,
        "Five": Type_Five,
        "Six": Type_Six,
        "Seven": Type_Seven,
        "Eight": Type_Eight,
        "Nine": Type_Nine,
        "Ten": Type_Ten,
        "Eleven": Type_Eleven,
    }
    
    if event_type in halt_event_map:
        halt_event_function = halt_event_map[event_type]
        if callable(halt_event_function):
          
            halt_event_function(cmd, annotation, duration, count, args_1, hostname, **kwargs)
            
        else:
            LLOG(message=f"** Error: {event_type} is not a callable function **", self=self)     
    else:
        LLOG(message=f"** Unsupported halt event type: {event_type} **", **{'self': self})

def log_halt_event(dut, event_type, cmd, annotation, duration, count, args_1, **kwargs):
    """Log and store halt event details."""

    self = kwargs.get('self', None)

    # Log the halt event
    LLOG(
        message=(
            f"** RUNNING HALT ITERATION ON {dut}:{self.global_iteration} ->> "
            f"Type:{event_type}/cmd:{cmd}/annotation:{annotation}/duration:{duration}/count:{count}/args:{args_1} **\n"
        ),
        self=self
    )

    # Ensure output directory exists
    output_file_path = os.path.join(self.LONGEVITY_OUTPUT_DIR, "halt-cmds-replay.txt")
    os.makedirs(os.path.dirname(output_file_path), exist_ok=True)

  

    # Write event details to file
    with open(output_file_path, 'a', encoding='UTF-8') as file_hdl:
      
        file_hdl.write(f"{dut}|{event_type}|{duration}|{annotation}|args={args_1}\n")

def Apply_Halt_Testing(halt_list, count, dut, **kwargs):
    """Applies the halt testing based on the given halt_list."""
    self = kwargs.get('self', None)


    for val in halt_list:
        try:
            event_type, cmd, annotation, duration, args_1, hostname = _get_halt_event_details(self, val, dut)
     
        except ValueError as e:
            LLOG(message=f"** Error processing halt event: {e} **", **{'self': self})
            continue
      
        if event_type == "One" and eval(f"is_evo_{dut}"):
            log_halt_event(dut, event_type, cmd, annotation, duration, count, args_1, **kwargs)
            execute_halt_event(event_type, cmd, annotation, duration, count, args_1, hostname, **kwargs)
        elif event_type == "One":
            LLOG(message='** Bypass Type One Halt Events as they are EVO-specific **\n', **{'self': self})
        else:
            log_halt_event(dut, event_type, cmd, annotation, duration, count, args_1, **kwargs)
            execute_halt_event(event_type, cmd, annotation, duration, count, args_1, hostname, **kwargs)

def Replay_Halt_Testing(**kwargs):
    """Initiates replay of halt events."""
    self = kwargs.get('self', None)
    self.global_iteration = 1

    halt_list = list(range(1, len(processed_list) + 1))
    
    LLOG(message='** BEGIN HALT REPLAY **\n', **{'self': self})
    Apply_Halt_Testing(halt_list, count=1, **{'self': self})
    LLOG(message='** END HALT REPLAY **\n', **{'self': self})



def get_time_diff_in_seconds(curr_time, start_time):  
    """
    Calculate the time difference in seconds between current time and start time.
    """
 
    curr_time = datetime.datetime.strptime(curr_time, "%Y-%m-%d %H:%M:%S")  
    start_time = datetime.datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")  
    return int((curr_time - start_time).total_seconds())  



def longevity_lrm_config_start():
    """
    Starts the longevity test configuration.
    """
    testbed.log(level="INFO", message="Starting TE Data for lrm ocnfig test")
    lrm_baseline.start()

def longevity_te_test_config_start():
    """
    Starts the longevity test configuration.
    """
    testbed.log(level="INFO", message="[INFO] Starting Longevity Test Configuration", console=True)
    te_longevity_test.start()


def longevity_te_lrm_baseline_snapshot():
    """
    Takes a snapshot of the LRM baseline.
    """
    testbed.log(level="INFO", message="[INFO] Taking LRM Baseline Snapshot", console=True)
    
    lrm_baseline.snapshot()


def longevity_te_test_config_snapshot():
    """
    Takes a snapshot of the Longevity Test Configuration.
    """
    testbed.log(level="INFO", message="[INFO] Taking Longevity Test Configuration Snapshot", console=True)
    te_longevity_test.snapshot()


def longevity_te_lrm_baseline_stop(is_load_lrm_config):
    """
    Stops the LRM Baseline if is_load_lrm_config is 0.
    
    Arguments:
        is_load_lrm_config - Indicator whether LRM baseline should be stopped.
    """
    if is_load_lrm_config:
        testbed.log(level="INFO", message="[INFO] Stopping LRM Baseline", console=True)
        lrm_baseline.stop()


def longevity_te_test_config_stop():
    """
    Stops the Longevity Test Configuration.
    """
    testbed.log(level="INFO", message="[INFO] Stopping Longevity Test Configuration", console=True)
    te_longevity_test.stop()


def longevity_te_lrm_baseline_converge():
    """
    Converges the LRM Baseline based on the configured iterations.
    """
    te_iterations = tv.get("uv-te-converge-itrs", 30)
    testbed.log(level="INFO", message=f"[INFO] LRM Baseline Converging with {te_iterations} iterations", console=True)
    lrm_baseline.converge(iterations=te_iterations, interval=5)


def longevity_te_test_config_converge(iterations=5, interval=5):
    """
    Wrapper function for test engine convergence.

    Arguments:
        iterations - Number of iterations to execute before convergence (default: 12).
        interval - Time delay between convergence checking iterations (default: 5).
    """
    te_iterations = iterations if iterations is not None else tv.get("uv-te-converge-itrs", 5)
    te_interval = interval if interval is not None else tv.get("uv-te-converge-interval", 5)

    testbed.log(
        level="INFO",
        message=f"[INFO] Longevity Test Config Converging with {te_iterations} iterations, interval {te_interval}",
        console=True
    )

    te_longevity_test.converge(iterations=te_iterations, interval=te_interval)



def get_memory_profile_http_path(**kwargs):
    """
    Generate the memory profiling HTTP path.
    """
    self = kwargs.get('self', None)
    temp = REPORT_FILE.split('/')
    
    # TODO: Missing KW implementation
    # Placeholder for any additional logic as needed
    url = f"{web_prefix}/toby_logs/{temp[-2]}/test_suite_iter_{self.global_iter}/{self.test_type}{self.test_scenario}/memory_profiling/"
    return url


def get_fpcs_from_evo_device(_rtr, **kwargs):
    """
    Get FPCs from an Evo device by executing a CLI command.
    """
    self = kwargs.get('self', None)
    _rh = testbed.get_handle(resource=_rtr)
    
    # Execute CLI command to retrieve XML data
    xml_out = device_utils.execute_cli_command_on_device(
        device=_rh, command='show chassis fpc | display xml', timeout=600, pattern='Toby.*>$'
    )
    
    # Parse XML data to extract FPC information
    fpc_list = xml_utils.get_elements_texts(xml_out, ".//fpc-information/fpc[state='Online']/slot")

    n_fpc_list = [f"fpc{fpc_num}" for fpc_num in fpc_list]
    
    return n_fpc_list

def evo_get_node_list_for_dashboard(rtr, **kwargs):
    """
    Get the node list for the dashboard from the Evo device.
    """
    self = kwargs.get('self', None)
    rh = testbed.get_handle(resource=rtr)
    xml_out = device_utils.execute_cli_command_on_device(device=rh, command='show system nodes | display xml', pattern='Toby.*>$')
    node_list = xml_utils.get_elements_texts(xml_out,"system-nodes-info/system-nodes-info-entry[system-node-info-node-status='online, apps-ready']/system-node-info-node-name")

    
    # Filtering FPC nodes from the node list
    t1_fpc_list = [gen_item for gen_item in node_list if re.match('fpc*', gen_item)]
    
    # If no FPCs found, retrieve them from Evo device
    if not t1_fpc_list:
        t2_fpc_list = get_fpcs_from_evo_device(rtr, **{'self': self})
    else:
        t2_fpc_list = []

    # Combine both node lists
    node_list.extend(t2_fpc_list)
    return node_list



def generate_longevity_dashboard_helper(_drtr, Log_Dir, host_name, node_list, out_dir, platform, version, url):
    """ Keyword that generates the longevity dashboard helper """

    
    # Extract FPC and RE lists from node_list
    fpc_list = [node for node in node_list if re.match(r'fpc.*', node)]
    re_list = [node for node in node_list if re.match(r're.*', node)]

    # Data collection from ps_mem output
    lng_common.parse_ps_mem_output(Log_Dir, host_name, "RE")

    for fpc in fpc_list:
        lng_common.parse_ps_mem_output(Log_Dir, host_name, fpc)

    # Collect Data From Jemalloc
    lng_common.collect_data_from_jemalloc(Log_Dir, host_name, node_list, "Allocated")
    lng_common.collect_data_from_jemalloc(Log_Dir, host_name, node_list, "Resident")

    # Convert FPC names to uppercase and collect NPU memory data
    for fpc in fpc_list:
        fpc = fpc.upper()
        collect_data_from_npu_mem_helper(Log_Dir, host_name, fpc, globals().get(f"npu_memory_list_{_drtr}", []))

    # Collect system process data
    for node in node_list:
        lng_common.collect_data_from_show_system_process_extensive(Log_Dir, host_name, node)

    lng_common.collect_data_from_show_system_proc_mem_info(Log_Dir, host_name)

    for fpc in fpc_list:
        lng_common.collect_data_from_show_system_proc_mem_info(Log_Dir, host_name, fpc)

    # Collect system storage data
    for node in node_list:
        lng_common.collect_data_from_show_system_storage(Log_Dir, host_name, node)

    # Collect task memory details
    lng_common.collect_data_from_show_task_memory_detail(log_dir_location=Log_Dir, host_name=host_name)

    # Collect platform distributor statistics
    lng_common.collect_show_platform_distributor_statistics(log_dir_location=Log_Dir, host_name=host_name)
    lng_common.collect_show_platform_distributor_statistics_all_clients(log_dir_location=Log_Dir, host_name=host_name)
    lng_common.collect_show_platform_distributor_statistics_sdb_current_holds(log_dir_location=Log_Dir, host_name=host_name)
    lng_common.collect_show_platform_distributor_statistics_all_clients_sdb_current_holds(log_dir_location=Log_Dir, host_name=host_name)

    # Plot Graph in Dashboard
    lng_common.plot_graph_in_dashboard(out_dir=out_dir, host_name=host_name, platform=platform, version=version, url=url)
    


def collect_data_from_npu_mem_helper(Log_Dir, host_name, fpc, collection_types):
    """ 
    Collects data from NPU memory for the given FPC and collection types. 
    """

    for collection_type in collection_types:
        lng_common.collect_data_from_npu_mem(Log_Dir, host_name, fpc, collection_type)


def generate_longevity_dashboard(check_point=None, **kwargs):
    """
    Generate the longevity dashboard.
    """
    self = kwargs.get('self', None)
    
    LLOG(message='!!!!!!!! Longevity Dashboard Creation !!!!!!!!', **{'self': self})
    
    # Set dashboard directory based on the checkpoint value
    dashboard_dir = 'lrm_config_post_test' if check_point is None else check_point
    
    # Generate memory profile HTTP path
   
    url = get_memory_profile_http_path(**{'self': self}) if check_point == 'NONE' else ''

    # Iterate over Evo routers to generate the dashboard
    _host_info = {}
    _nodes_data = {}
    for lrtr in self.evo_lng_rtr_list:
        host_name = t['resources'][lrtr]['system']['primary']['name']
        platform = tv.get(f'{lrtr}__model')
        version = tv.get(f'{lrtr}__os-ver')
        
        # Create output directory
        os.makedirs(f"{self.LONGEVITY_OUTPUT_DIR}/dashboard/{host_name}/{dashboard_dir}", exist_ok=True)
        out_dir = f"{self.LONGEVITY_OUTPUT_DIR}/dashboard/{host_name}/{dashboard_dir}"
        
        # Get node list for the current router
        node_list = evo_get_node_list_for_dashboard(lrtr, **{'self': self})
        
        # Generate the longevity dashboard
        # Run Dashboard Helper
        if 'qfx' in platform:
            node_list = ['re0']
        try:
            
            generate_longevity_dashboard_helper(
                lrtr, self.LONGEVITY_OUTPUT_DIR, host_name, node_list, out_dir, platform, version, url
            )
        except Exception as e:
            LLOG(message=f"Error generating dashboard for {lrtr}: {e}")
        
        
        _host_info[host_name]={'platform':f'{platform}', 'version':f'{version}'}
        _nodes_data[host_name] = node_list
    
   
    if _nodes_data:
        if lng_common.longevity_report_data:
                for _host_name in _host_info.keys():
                    if _host_name in self.brcm_host_names:
                        lng_common.longevity_report_data[f"brcm_inspect_on_re0-{_host_name}.html"]={'lrm_config_post_test':True, 'test_config_post_test':False}
                
                scenario_execution_secs = self.duration_in_sec
                host_info = _host_info
                nodes_data = _nodes_data
                scenario = f"{self.test_type}{self.test_scenario}"
                #log_dir = "/volume/regressions/results/JUNOS/HEAD/mmahadevaswa/longevity/IPCLOS/conversion/converted/jpytest_logs/longevity_ipclos_20250331-200749/test_suite_iter_0/ActiveTest_Scenario1"
                log_dir = self.LONGEVITY_OUTPUT_DIR
                #
                orchestrator = LongevityReportOrchestrator(
                    nodes_data=nodes_data,
                    global_data_dict=lng_common.longevity_report_data,
                    scenario=scenario,
                    scenario_execution_secs=scenario_execution_secs,
                    host_info=host_info,
                    log_dir=log_dir
                )
                import traceback
                try:
                    #
                    orchestrator.run()
                    
                    #failed_apps_not_enabled_memory_profiling =[]
                    global failed_apps_not_enabled_memory_profiling
                    #problem is here...
                    if _host_name in orchestrator.failed_memory_apps_dict:
                        for k, v in orchestrator.failed_memory_apps_dict[_host_name].items():
                            if v:
                                if _host_name not in failed_apps_not_enabled_memory_profiling:
                                    failed_apps_not_enabled_memory_profiling[_host_name] = []
                                failed_apps_not_enabled_memory_profiling[_host_name].extend(v)
                        
                        
                except Exception as e:
                    traceback.print_exc()
            
    
    
        
    
def generate_longevity_junos_dashboard_helper(Log_Dir, host_name, junos_nodes, out_dir, platform, version):
    """ 
    Keyword that generates the Longevity Junos Dashboard Helper.
    
    Arguments:
    - Log_Dir: Directory where logs are stored
    - host_name: Hostname of the device
    - junos_nodes: Dictionary containing Junos node details
    - out_dir: Output directory for the dashboard
    - platform: Device platform
    - version: Junos version

    Returns:
    - None
    """

    # Extract FPC list from Junos nodes dictionary
    fpc_list = junos_nodes.get("fpc_list", [])

    # Log FPC list
    print(f"FPC List: {fpc_list}")

    # Data collection from 'show heap'
    for fpc in fpc_list:
        lng_common.parse_junos_show_heap_output(Log_Dir, host_name, f"FPC{fpc}")

    # Data collection from process and memory details
    lng_common.parse_junos_show_process_extensive(log_dir_location=Log_Dir, host_name=host_name)
    lng_common.collect_data_from_show_task_memory_detail(log_dir_location=Log_Dir, host_name=host_name)

    # Plot Graph in Dashboard
    lng_common.plot_graph_in_dashboard(out_dir=out_dir, host_name=host_name, platform=platform, version=version, url=None)


def generate_longevity_junos_dashboard(check_point=None, **kwargs):
    
    """ 
    Keyword that generates the Longevity Junos Dashboard.
    
    Mandatory Arguments:
    - None

    Optional Arguments:
    - check_point: Determines which dashboard directory to use (default: None)

    Returns:
    - None
    """
    self = kwargs.get('self', None)
    LLOG(message="!!!!!!!! Longevity Dashboard Creation !!!!!!!!")

    # Determine the dashboard directory based on check_point
    if check_point is None:
        dashboard_dir = "lrm_config_post_test"
    else:
        dashboard_dir = check_point

    for lrtr in self.junos_lng_rtr_list:
        host_name = t['resources'][lrtr]['system']['primary']['name']
        platform = tv[f"{lrtr}__model"]
        version = tv[f"{lrtr}__os-ver"]

        # Create dashboard directory
        out_dir = os.path.join(self.LONGEVITY_OUTPUT_DIR, "dashboard", host_name, dashboard_dir)
        os.makedirs(out_dir, exist_ok=True)

        # Get Junos node list
        junos_nodes = junos_get_node_list(lrtr)

        # Run Dashboard Helper
        try:
            generate_longevity_junos_dashboard_helper(
                LONGEVITY_OUTPUT_DIR, host_name, junos_nodes, out_dir, platform, version
            )
        except Exception as e:
            LLOG(message=f"Error generating Junos dashboard for {lrtr}: {e}")



def randomize_halt_testing(steady_state_keyword, event_keyword, **kwargs):
    """
    Randomize halt testing based on events and steady state keywords.
    """
    self = kwargs.get('self', None)
    events_hosts_temp = convert_to_list_arg(self.events_hosts_temp)
    events_nodes_list = list(set(events_hosts_temp))
    events_nodes_list_len = len(events_nodes_list)
    
    j = 0
    for_every_itr_dash = tv.get('uv-for-every-test-itr-dashboard-generation', 2)
   
    
    time_to_wait_post_iteration = tv.get('uv-longevity-test-itr-interval', 1800)
    min_duration_in_sec = int(0.9 * int(time_to_wait_post_iteration))
    #
    test_start_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    for number in range(0, 999999):
        
        # Ensure nodes list is correctly processed
        dut = events_nodes_list[int(j)]
        testbed.log(f"***************Selected {dut} ******************", display_log=True)
        
        # Update index
        j = str((int(j) + 1) % events_nodes_list_len)
        
        # Get current time difference
        current_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        diff_time_in_sec = get_time_diff_in_seconds(curr_time=current_date, start_time=test_start_time)
        time_left_in_sec = self.duration_in_sec-diff_time_in_sec
       
        # Break if duration exceeded
        #if diff_time_in_sec >= self.duration_in_sec or diff_time_in_sec < min_duration_in_sec:
        if min_duration_in_sec > time_left_in_sec:
            LLOG(message=f"Longevity Test Duration of {self.duration_in_sec} is completed. Exiting the Test Iterations.\n", **{'self': self})
            break
        else:
            LLOG(message=f"Longevity Test Duration of {self.duration_in_sec} is not completed. Continuing to the next iteration.\n", **{'self': self})
        
        # Perform halt testing and other actions
        global_iteration = str(int(number) + 1)
        self.global_iteration = global_iteration
        LLOG(message=f"** Performing Events on {dut} **\n", **{'self': self})
        
        # Handle processed list and randomize
        
        attr_name = f"processed_list_{dut}"

        # Check if the attribute exists in self before accessing it
        if hasattr(self, attr_name):
            processed_list = getattr(self, attr_name)

            if isinstance(processed_list, list):
                asample_size = len(processed_list)
                
                if asample_size == 0:
                    raise ValueError(f"Error: {attr_name} is an empty list.")
            else:
                raise TypeError(f"Error: {attr_name} exists but is not a list (found {type(processed_list).__name__}).")
        else:
            raise AttributeError(f"Error: {attr_name} does not exist in self.")
            
        #asample_size = len(self.eval(f"{'processed_list_' + dut}"))
        random_list = random.sample(range(1, asample_size + 1), asample_size)
        
        #
        
        LLOG(message=f"** BEGIN HALT ITERATION: {self.global_iteration} - RANDOM LIST {random_list} **\n", **{'self': self})
    
        try:
       
            _ = Apply_Halt_Testing(halt_list=random_list, count=number, dut=dut, **{'self': self})
        except Exception:
            pass
        
        LLOG(message=f"** END HALT ITERATION: {self.global_iteration} - RANDOM LIST {random_list} **\n", **{'self': self})
        
        if event_keyword:
            try:
                event_keyword()
            except Exception as e:
                LLOG(message=f"Error executing Event Keyword: {str(e)}", **{'self': self})



        
        LLOG(message=f"** Waiting for {time_to_wait_post_iteration} seconds after the events execution **\n", **{'self': self})
        time.sleep(time_to_wait_post_iteration)
        LLOG(message=f"** Waiting for {time_to_wait_post_iteration} seconds after the events execution is completed **\n", **{'self': self})

        #check_for_link_down_events(dut, f'test_config_itr_{number}', **kwargs)
        #try:
            
        #    longevity_te_test_config_converge()
            
        #except Exception as e:
        #    LLOG(message=f"Error during TE Test Config Convergence: {str(e)}", **{'self': self})

        #if steady_state_keyword:
        #    try:
        #        steady_state_keyword()
        #    except Exception as e:
        #        LLOG(message=f"Error executing Steady State Keyword: {str(e)}", **{'self': self})

        # Data Collection at Convergence
        is_evo_dump_enabled = tv.get('uv-evo-system-dump-at-convergence', 0)
        is_junos_collection_needed = tv.get('uv-data-collection-dump-at-convergence', 0)

        '''
        if is_evo_dump_enabled and evo_lng_global_flag:
            try:
                longevity_data_collection(f"test_config_itr_{number}")
            except Exception as e:
                LLOG(message=f"Error during EVO Data Collection: {str(e)}", **{'self': self})

        if is_junos_collection_needed and junos_lng_global_flag:
            try:
                longevity_junos_data_collection(f"test_config_itr_{number}")
            except Exception as e:
                LLOG(message=f"Error during JunOS Data Collection: {str(e)}", **{'self': self})
        '''
        collect_longevity_test_data(self, longevity_check_point=f'test_config_itr_{number}')
        # Generate dashboards at intermediate test iterations
        if (number + 1) % 5 == 0:
            try:
                LLOG(message=f"Started Creation dashboard for itr->{number}", **{'self': self})
                generate_longevity_dashboard(check_point=f"test_config_itr_{number}", **kwargs)
                generate_longevity_junos_dashboard(check_point=f"test_config_itr_{number}", **kwargs)
            except Exception as e:
                LLOG(message=f"Error during Dashboard Generation: {str(e)}", **{'self': self})

        number+=1
       


def randomize_halt_testing_bk(steady_state_keyword, event_keyword, **kwargs):
    """
    Executes randomized halt testing with event execution and steady state validation.

    Arguments:
        steady_state_keyword - Keyword or function to validate system steady state.
        event_keyword - Keyword or function to execute during the halt test.
        events_hosts_temp - List of event nodes.
        halt_start_time - Start time of the halt testing.
        duration_in_sec - Total duration for the halt testing.
        processed_list_dict - Dictionary containing processed list per device.
        combined_lng_rtr_list - List of routers for longevity testing.
        data_collect_nodes - Nodes involved in data collection.
        longevity_output_dir - Output directory for longevity data collection.

    Returns:
        None
    """

    # Ensure unique event nodes list
    self = kwargs.get('self', None)
    events_hosts_temp = convert_to_list_arg(self.events_hosts_temp)
    events_nodes_list = list(set(events_hosts_temp))
    events_nodes_list_len = len(events_nodes_list)
    j = 0

    # Get iteration dashboard generation frequency
    for_every_itr_dash = tv.get('uv-for-every-test-itr-dashboard-generation', 2)
    
    for number in range(999999):
        # Validate events list
        events_nodes_list = list(set(events_nodes_list))

        # Select DUT (Device Under Test) in a round-robin manner
        dut = events_nodes_list[j]
        print(f"*************** Selected {dut} ******************")

        res = (number + 1) % events_nodes_list_len
        j = 0 if res == 0 else j + 1

        # Get Current Time and Check Test Duration
        current_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        diff_time_in_sec = (datetime.datetime.strptime(current_date, '%Y-%m-%d %H:%M:%S') - datetime.datetime.strptime(halt_start_time, '%Y-%m-%d %H:%M:%S')).total_seconds()

        if diff_time_in_sec >= self.duration_in_sec:
            break

        self.global_iteration = number + 1
        print(f"** Performing Events on {dut} **\n")




        # Randomize Halt Testing
        asample_size = len(processed_list_dict.get(dut, []))
        dummy = asample_size + 1
        processed_list = processed_list_dict.get(dut, [])
        random_list = random.sample(range(1, dummy), asample_size) if asample_size > 0 else []

        print(f"** BEGIN HALT ITERATION: {global_iteration} - RANDOM LIST {random_list} **\n")
        
        try:
            apply_halt_testing(random_list=random_list, count=number, dut=dut)
        except Exception as e:
            print(f"Error executing Apply Halt Testing: {str(e)}")

        print(f"** END HALT ITERATION: {global_iteration} - RANDOM LIST {random_list} **\n")

        # Call Event Keyword if provided
        if event_keyword:
            try:
                event_keyword()
            except Exception as e:
                print(f"Error executing Event Keyword: {str(e)}")

        # Wait after events execution
        time_to_wait_post_iteration = tv.get('uv-longevity-test-itr-interval', 1800)
        print(f"** Waiting for {time_to_wait_post_iteration} seconds after the events execution **\n")
        time.sleep(time_to_wait_post_iteration)
        print(f"** Waiting for {time_to_wait_post_iteration} seconds after the events execution is completed **\n")

        # Perform TE Convergence
        #try:
            
        #    longevity_te_test_config_converge()
            
        #except Exception as e:
        #    print(f"Error during TE Test Config Convergence: {str(e)}")

        # Call Steady State Keyword if provided
        #if steady_state_keyword:
        #    try:
        #        steady_state_keyword()
        #    except Exception as e:
        #        print(f"Error executing Steady State Keyword: {str(e)}")

        # Data Collection and Longevity Processing
        is_evo_dump_at_itr_enabled = tv.get('uv-evo-system-dump-at-convergence', 0)
        is_junos_collection_needed = tv.get('uv-data-collection-dump-at-convergence', 0)

        if is_evo_dump_at_itr_enabled and evo_lng_global_flag:
            try:
                longevity_data_collection(f"test_config_itr_{number}")
            except Exception as e:
                print(f"Error in EVO Data Collection: {str(e)}")

        lng_data_obj = LongevityDataCollection.DataCollection('lngdata')
        data_collection_preparation_and_init(self.combined_lng_rtr_list, lng_data_obj)

        try:
            lng_data_obj.longevity_data_collection(self.combined_lng_rtr_list, data_collect_nodes, longevity_output_dir, f"test_config_itr_{number}")
        except Exception as e:
            print(f"Error in Longevity Data Collection: {str(e)}")

        # Generate Dashboard at specified iterations
        if (number + 1) % for_every_itr_dash == 0:
            try:
                generate_longevity_dashboard(check_point=f"test_config_itr_{number}")
                generate_longevity_junos_dashboard(check_point=f"test_config_itr_{number}")
            except Exception as e:
                print(f"Error in Dashboard Generation: {str(e)}")


def Active_Execution(steady_state_keyword, event_keyword, **kwargs):
    """
    Execute the active halt testing or replay based on the replay flag.
    """
    self = kwargs.get('self', None)
    halt_start_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    self.halt_start_time = halt_start_time

    # Perform either Replay or Randomize Halt Testing
    if self.is_replay:
        Replay_Halt_Testing(**{'self': self})
    else:
        randomize_halt_testing(steady_state_keyword, event_keyword, **{'self': self})

    # Log and wait for DUT to settle down
    settle_down_time = tv['uv-longevity-test-pre-post-settle-down-time']
    LLOG(message=f"** HALT Completed. Waiting {settle_down_time} Sec for DUT to Settle Down\n", **{"self": self})
    #LONGEVITY_ANNOTATE(f"annotate_string=Settle Down Timer Started {settle_down_time} seconds", **{'self': self})
    LSLEEP(settle_down_time, **{'self': self})


def passive_execution(steady_state_keyword, **kwargs):
    """
    Perform passive execution for longevity testing iterations.
    """
    self = kwargs.get('self', None)
    test_start_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    LLOG(message='Longevity Monitor Test Iterations Begins...\n', **{'self': self})

    # Iterative execution for longevity test
    time_to_wait_post_iteration = tv.get('uv-longevity-test-itr-interval', 1800)
    min_duration_in_sec = int(0.9 * int(time_to_wait_post_iteration))
    #
    number = 0
    while True:
        current_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        diff_time_in_sec = get_time_diff_in_seconds(curr_time=current_date, start_time=test_start_time)
        time_left_in_sec = self.duration_in_sec-diff_time_in_sec
        #if diff_time_in_sec >= self.duration_in_sec:
        #
        if min_duration_in_sec > time_left_in_sec:
        #if diff_time_in_sec < min_duration_in_sec:
            LLOG(message=f"Longevity Test Duration of {self.duration_in_sec} is completed. Exiting the Test Iterations.\n", **{'self': self})
            break
        else:
            LLOG(message=f"Longevity Test Duration of {self.duration_in_sec} is not completed. Continuing to the next iteration.\n", **{'self': self})

        # Annotate iteration start and wait for next iteration
        #LONGEVITY_ANNOTATE(f"annotate_string=\"Iteration#{diff_time_in_sec} Start\"", **{'self': self})
        LSLEEP(time_to_wait_post_iteration, **{'self': self})

        # Process steady state keyword if provided
        #is_ss_kw_empty = len(steady_state_keyword) == 0

        #if not is_ss_kw_empty:
        #    pass  # Implement steady state logic here

        # Converge test configuration
     
        #try:
            
        #    longevity_te_test_config_converge()
            
        #except Exception as e:
        #    LLOG(message=f"Error during TE Test Config Convergence: {str(e)}", **{'self': self})

        #if steady_state_keyword:
        #    try:
        #        steady_state_keyword()
        #    except Exception as e:
        #        LLOG(message=f"Error executing Steady State Keyword: {str(e)}", **{'self': self})

        
        # Data Collection at Convergence
        #is_evo_dump_enabled = tv.get('uv-evo-system-dump-at-convergence', 0)
        #is_junos_collection_needed = tv.get('uv-data-collection-dump-at-convergence', 0)

       
        collect_longevity_test_data(self, longevity_check_point=f'test_config_itr_{number}')
        
        
        
        # Generate dashboards at intermediate test iterations
        # valid = (number + 1) % for_every_itr_dash
        #if valid == 0:
        #    try:
        #        generate_longevity_dashboard(check_point=f"test_config_itr_{number}")
        #        generate_longevity_junos_dashboard(check_point=f"test_config_itr_{number}")
        #    except Exception as e:
        #        LLOG(message=f"Error during Dashboard Generation: {str(e)}", **{'self': self})

        # Generate dashboards for specific iterations
        if (number + 1) % 5 == 0:
            generate_longevity_dashboard(check_point=f"test_config_itr_{number}", **{'self': self})
            generate_longevity_junos_dashboard(check_point=f"test_config_itr_{number}", **{'self': self})
        number+=1

def longevity_post_test_preparation(rtr_list, **kwargs):
    """
    Prepare post-test actions, including saving test config, loading LRM baseline config, and waiting.
    """
    self = kwargs.get('self', None)
    LLOG(message=f"Saving Test Configuration of {rtr_list}...\n", **{'self': self})
    longevity_save_rtr_test_config(rtr_list, **{'self': self})
    LSLEEP(15, reason="Adhoc Sleep Post Saving the Test Configuration...", **{'self': self})

    # Check if pre-configuration keywords exist and execute them
    #lrm_pre_kw = run_kw_before_lrm_load_config if 'run_kw_before_lrm_load_config' in locals() else []
    #is_lrm_pre_kw_empty = len(lrm_pre_kw) == 0
    #kw1_result = 'PASS'
    #kw1_failure_reason = 'Keyword did not run'

    #if not is_lrm_pre_kw_empty and self.is_load_lrm_config:
    #    try:
    #        # Implement pre-configuration keyword execution logic here
    #        kw1_result = 'PASS'
    #    except Exception:
    #        kw1_result = 'FAIL'
    #        kw1_failure_reason = 'Pre-configuration failed'

    #if kw1_result == 'FAIL':
    #    LLOG(level='WARN', message=f"Failure Reason for {lrm_pre_kw}: {kw1_failure_reason}\n", **{'self': self})

    # Load LRM configuration if necessary
    if self.is_load_lrm_config:
        #hi
        LLOG(message=f"Loading LRM Configuration On {rtr_list}\n", **{'self': self})
        longevity_load_lrm_baseline_config(rtr_list, **{'self': self})
        wait_timer_01 = tv.get('uv-longevity-post-lrm-baseline-wait-time', 1800)
        LSLEEP(wait_timer_01, **{'self': self})
        #

    # Check if post-configuration keywords exist and execute them
    #lrm_post_kw = run_kw_after_lrm_load_config if 'run_kw_after_lrm_load_config' in locals() else []
    #is_lrm_post_kw_empty = len(lrm_post_kw) == 0
    #kw2_result = 'PASS'
    #kw2_failure_reason = 'Keyword did not run'

    #if not is_lrm_post_kw_empty and self.is_load_lrm_config:
    #    try:
            # Implement post-configuration keyword execution logic here
    #        kw2_result = 'PASS'
    #    except Exception:
    #        kw2_result = 'FAIL'
    #        kw2_failure_reason = 'Post-configuration failed'

    #if kw2_result == 'FAIL':
    #    LLOG(level='WARN', message=f"Failure Reason for {lrm_post_kw}: {kw2_failure_reason}\n", **{'self': self})

    # Wait after loading the LRM baseline config
    
       


def pdt_stop_memory_profiling_ON_RTR(rtr, app_list, **kwargs):
    self = kwargs.get('self', None)
    rh = testbed.get_handle(resource=rtr)
    mem_pro_disable_status = []

    for app in app_list:
        cli_cmd_exec_timeout = tv.get('uv-cmd-timeout', '900')
        self.cli_cmd_exec_timeout = self.cli_cmd_exec_timeout
        cmd = 'set task memory-leak-detector off' if app == 'routing' else f"request system memory-profiling node all application {app} disable"
        
        cmd_response = device_utils.execute_cli_command_on_device(device=rh, command=cmd, timeout=self.cli_cmd_exec_timeout, pattern='Toby.*>$')
        
        is_profiling_enabled = True
        try:
            assert cmd_response in ["'Profiling disabled for the application'", "'Profiling is disabled successfully for the application'", "'Task memory leak detection disabled'"]
        except Exception:
            is_profiling_enabled = False
        
        if not is_profiling_enabled:
            testbed.log(f"'level' = WARN", display_log=True)
            mem_pro_disable_status.append(False)
            continue
        testbed.log(f"'level' = INFO", display_log=True)
        mem_pro_disable_status.append(True)

    return str(any(mem_pro_disable_status))

def pdt_stop_memory_profiling(**kwargs):
    self = kwargs.get('self', None)

    for rtr in self.evo_rtr_list:
        is_key_exist = 'uv-evo-mem-profile-app-list' in t['resources'].get(rtr, {}).get('system', {}).get('primary', {})
        hostname = tv.get(f"{rtr}__re0__hostname")

        if not is_key_exist:
            testbed.log(f"'level' = WARN", display_log=True)
            continue

        app_list = tv.get(f"{rtr}__uv-evo-mem-profile-app-list").split(',')
        
        if failed_apps_not_enabled_memory_profiling:
            if hostname in failed_apps_not_enabled_memory_profiling:
                app_list.extend(failed_apps_not_enabled_memory_profiling[hostname])
                app_list = list(set(app_list)) 
            
            
        pdt_stop_memory_profiling_ON_RTR(rtr, app_list, **{'self': self})




def get_proc_collector_exec_command(rtr, node, app, **kwargs):
    """Generate the process collector execution command."""
    
    self = kwargs.get('self', None)
    if self is None:
        raise ValueError("Instance reference 'self' is required in kwargs.")

    attr_name = f"dict_{rtr}_{node}_{app}"
    existing_dict = getattr(self, attr_name, None)

    if not existing_dict or "test_config_pre_test" not in existing_dict:
        raise ValueError(f"Missing 'test_config_pre_test' in {attr_name}")

    heap_output = existing_dict["test_config_pre_test"]

    # Extract process ID using regex
    gen_match_obj = re.search(r'/var/log/(.*)\.(\d+)\.\d+\.heap', heap_output)
    if not gen_match_obj:
        raise ValueError("Regex did not match the expected heap output format")

    process_name, process_id = gen_match_obj.group(1), gen_match_obj.group(2)

    testbed.log(f"Process ID: {process_id}", display_log=True)
    return f"-p {process_id} {process_name} /var/log/{process_name}.{process_id}.*.heap"


def update_proc_collector_global_data_dictionary(rtr, data_dict, tgz_file, node, app, **kwargs):
    """Update the global data dictionary for the process collector."""
    
    self = kwargs.get('self', None)
    if self is None:
        raise ValueError("Instance reference 'self' is required in kwargs.")

    rh = testbed.get_handle(resource=rtr)
    _h_name = device_utils.get_host_name_for_device(rh)

    # Update dictionary safely
    data_dict.update({
        'tgz_name': f"{tgz_file}.tgz",
        'node': node,
        'app': app,
        'tgz_location': f"{self.LONGEVITY_OUTPUT_DIR}/memory_profiling/{_h_name}/{app}/{node}"
    })

    # Ensure tracking list exists before updating
    attr_name = f"proc_collector_track_{rtr}_list"
    tracking_list = getattr(self, attr_name, [])

    if not isinstance(tracking_list, list):
        tracking_list = []

    tracking_list.append(data_dict)
    setattr(self, attr_name, tracking_list)  # Save updated list



def execute_proc_collector_on_node_re(rtr, node, app, **kwargs):
    """Execute process collector on a Routing Engine (RE) node."""
    
    self = kwargs.get('self', None)
    if self is None:
        raise ValueError("Instance reference 'self' is required in kwargs.")

    rh = testbed.get_handle(resource=rtr)
    _h_name = device_utils.get_host_name_for_device(rh)

    # Construct attribute name dynamically
    attr_name = f"dict_{rtr}_{node}_{app}"
    existing_dict = getattr(self, attr_name, None)
    
    if not existing_dict or 'test_config_pre_test' not in existing_dict:
        testbed.log(f"'level' = WARN", display_log=True)
        return EMPTY

    # Generate process collector command
    proc_collector_exec_command = get_proc_collector_exec_command(rtr, node, app, self=self)

    # Switch to appropriate controller and superuser mode

    device_utils.set_current_controller(rh, controller=node)
    device_utils.switch_to_superuser(device=rh)

    

    # Execute process collector command on device
    cmd_resp = device_utils.execute_shell_command_on_device(
        device=rh, timeout=getattr(self, "cmd_timeout", 300),  # Default timeout
        command=f"python3 /var/home/regress/proc_collector.py {proc_collector_exec_command}"
    )

    # Extract tar file name from response
    tgz_file = [match.group(1) for match in re.finditer(r'created tar archive:\s\/var\/tmp\/(.*).tgz', cmd_resp)] or []

    if not tgz_file:
        testbed.log(f"'level' = WARN", display_log=True)
        #device_utils.set_current_controller(device=rh, controller='master')
        return EMPTY

    # Update global dictionary safely
    update_proc_collector_global_data_dictionary(rtr, existing_dict, tgz_file[0], node, app, **kwargs)

    # Restore master controller
    #device_utils.set_current_controller(rh, controller='master')

    # Ensure directories exist before saving file
    output_dir = f"{self.LONGEVITY_OUTPUT_DIR}/memory_profiling/{_h_name}/{app}"
    os.makedirs(output_dir, exist_ok=True)

    # Retrieve the generated tar file
    pdt_get_file_from_re(rtr, node, f"/var/tmp/{tgz_file[0]}.tgz", f"{output_dir}/{node}", **kwargs)
    
    # Ensure cleanup list exists and update it
    cleanup_attr = f"proc_collector_cleanup_{rtr}_{node}_list"
    cleanup_list = getattr(self, cleanup_attr, [])

    if not isinstance(cleanup_list, list):
        cleanup_list = []

    cleanup_list.append(f"/var/tmp/{tgz_file[0]}.tgz")
    setattr(self, cleanup_attr, cleanup_list)  # Save updated list



def execute_proc_collector_on_node_fpc(rtr, node, app, **kwargs):
    self = kwargs.get('self', None)
    rh = testbed.get_handle(resource=rtr)
    _h_name = device_utils.get_host_name_for_device(rh)

    if 'test_config_pre_test' not in eval('dict_' + rtr + '_' + node + '_' + app):
        testbed.log(f"'level' = WARN", display_log=True)
        return EMPTY

    proc_collector_exec_command = get_proc_collector_exec_command(rtr, node, app, **{'self': self})
    device_utils.switch_to_superuser(device=rh)

    cmd_resp = device_utils.execute_shell_command_on_device(
        device=rh, timeout=self.cmd_timeout,
        command=f"chvrf iri ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR root@{node} python3 proc_collector.py {proc_collector_exec_command}",
        pattern='Toby.*%$'
    )

    tgz_file = [match.group(1) for match in re.finditer(r'created tar archive:\s\/var\/tmp\/(.*).tgz', cmd_resp)] or []

    if not tgz_file:
        testbed.log(f"'level' = WARN", display_log=True)
        return EMPTY

    update_proc_collector_global_data_dictionary(rtr, eval(f"{'dict_' + rtr + '_' + node + '_' + app}"), tgz_file[0], node, app, **{'self': self})
    os.makedirs(f"{self.LONGEVITY_OUTPUT_DIR}/memory_profiling/{_h_name}/{app}", exist_ok=True)
    pdt_get_file_from_fpc(rtr, node, f"/var/tmp/{tgz_file[0]}.tgz", f"{self.LONGEVITY_OUTPUT_DIR}/memory_profiling/{_h_name}/{app}/{node}", **{'self': self})

    attr_name = f"proc_collector_cleanup_{rtr}_{node}_list"

    # Ensure the attribute exists and is a list
    if not hasattr(self, attr_name):
        setattr(self, attr_name, [])

    # Append the file name to the list
    getattr(self, attr_name).append(f"{tgz_file[0]}.tgz")




def execute_proc_collector_on_all_nodes(rtr, app, node_list, **kwargs):
    """
    Execute process collector on all nodes for a given router and application.
    
    Arguments:
        rtr         - Router identifier
        app         - Application name
        node_list   - List of nodes
        is_node_re  - Flag to indicate if RE nodes should be checked (default: True)
        is_node_fpc - Flag to indicate if FPC nodes should be checked (default: True)
    
    Keyword Arguments:
        self - Instance reference (if used within a class)
    """

    self = kwargs.get('self', None)  # Not needed unless function is used outside a class
    
    is_node_re = False
    is_node_fpc = False

    
    for node in node_list:
        node_is_re = node.lower().startswith('re')
        node_is_fpc = node.lower().startswith('fpc')
            

        # Check if heap data is collected for the current node safely
        heap_data_var = f'dict_{rtr}_{node}_{app}'
        is_heap_data_collected = 0
        
        
         # Retrieve the dictionary using getattr()
        existing_dict = getattr(self, heap_data_var, None)

        # Check if heap data is collected
        is_heap_data_collected = existing_dict is not None
        
        if not is_heap_data_collected:
            continue  # Skip processing if no heap data

        # Execute corresponding collector functions if conditions are met
        

        if node_is_re and is_heap_data_collected:
            execute_proc_collector_on_node_re(rtr, node, app, **kwargs)
            

        if node_is_fpc and is_heap_data_collected:
            execute_proc_collector_on_node_fpc(rtr, node, app, **kwargs)




def evo_proc_collector_execute_on_rtr(rtr, app_list, **kwargs):
    self = kwargs.get('self', None)

    rh = testbed.get_handle(resource=rtr)
    app_list = convert_to_list_arg(app_list)
    app_list = list(set(app_list))

    LLOG(message=f"**** profile app List: {app_list}\n", **{'self': self})

    for app in app_list:
        cli_cmd_exec_timeout = tv.get('uv-cmd-timeout', '900')
        self.cli_cmd_exec_timeout = self.cli_cmd_exec_timeout

        # Get the list of nodes for the app
        _, node_list = pdt_get_app_node_list(rtr, app, **{'self': self})
        

        # Execute the proc collector on nodes
        
        execute_proc_collector_on_all_nodes(rtr, app, node_list, **{'self': self})
    


def evo_proc_collector_execute(**kwargs):
    
    self = kwargs.get('self', None)

    for rtr in self.evo_rtr_list:
        # Check if the 'uv-evo-mem-profile-app-list' exists in the resources
        is_key_exist = False
        try:
            is_key_exist = 'uv-evo-mem-profile-app-list' in t['resources'][rtr]['system']['primary']
        except KeyError:
            pass

        if not is_key_exist:
            testbed.log(f"'{rtr}' level: WARN - No memory profile app list found", display_log=True)
            continue

        # Get the list of memory-profiled apps for this router
        app_list = tv.get(f"{rtr}__uv-evo-mem-profile-app-list").split(',')
        hostname = tv.get(f"{rtr}__re0__hostname")
        if failed_apps_not_enabled_memory_profiling:
            if hostname in failed_apps_not_enabled_memory_profiling:
                app_list.extend(failed_apps_not_enabled_memory_profiling[hostname])
                app_list = list(set(app_list)) 
        

        # Execute the proc collector for this router
        evo_proc_collector_execute_on_rtr(rtr, app_list, **{'self': self})
    


def generate_profiling_diff_output_data_in_pdf_helper(jeprof_script, program_symlink, unpack_dir, base_key, last_key, current_tgz_location, pdf_name, app_heap_dump_dict, base, **kwargs):
    self = kwargs.get('self', None)
    
    # Ensure both base_key and last_key are in app_heap_dump_dict
    if base_key not in app_heap_dump_dict or last_key not in app_heap_dump_dict:
        testbed.log(f"'level' = WARN", display_log=True)
        return EMPTY

    # Extract heap sample file names
    First_Heap_Sample = app_heap_dump_dict[base_key]
    Last_Heap_Sample = app_heap_dump_dict[last_key]
    
    # Extract match from the heap sample paths
    def extract_heap_sample_path(heap_sample):
        gen_match_obj = re.search(r'/var/log/(.*)$', heap_sample)
        return gen_match_obj.group(0) if gen_match_obj else None

    First_Heap_Sample = extract_heap_sample_path(First_Heap_Sample)
    Last_Heap_Sample = extract_heap_sample_path(Last_Heap_Sample)

    # Validate that we got a valid match
    if not First_Heap_Sample or not Last_Heap_Sample:
        raise ValueError('Heap sample path does not match the expected format.')

    # Run the subprocess based on the 'base' argument
    if base == '1':
        subprocess.run(f"{jeprof_script} --pdf {program_symlink} --base {unpack_dir}/{First_Heap_Sample} {unpack_dir}/{Last_Heap_Sample} > {current_tgz_location}/{pdf_name}.pd", shell=True, capture_output=True, text=True)
    else:
        subprocess.run(f"{jeprof_script} --pdf {program_symlink} {unpack_dir}/{First_Heap_Sample} > {current_tgz_location}/{pdf_name}.pd", shell=True, capture_output=True, text=True)

    # Check if PDF file is created
    pdf_path = f"{current_tgz_location}/{pdf_name}.pdf"
    if not os.path.exists(pdf_path):
        testbed.log(f"'level' = WARN", display_log=True)
        return EMPTY

    pass


def Generate_Profiling_Diff_output_data_In_Pdf(unpack_dir, jeprof_script, program_symlink, app_heap_dump_dict, heap_keys, current_tgz_location, **kwargs):
    self = kwargs.get('self', None)

    # Extract app name and node from heap dump dictionary
    app_name = app_heap_dump_dict['app']
    node = app_heap_dump_dict['node']
    len_val = len(heap_keys)
    
    # Iterate over heap keys and generate profiling diff output
    for i, key in enumerate(heap_keys):
        hash_value = (i + 1) % 4
        
        # Determine base and last keys based on heap keys and the length of heap_keys
        if len_val == 1 and i == 0:
            generate_profiling_diff_output_data_in_pdf_helper(jeprof_script, program_symlink, unpack_dir, heap_keys[0], key, current_tgz_location, f"{node}_{app_name}_test_iteration_{0}-{i}_mem", app_heap_dump_dict, 0, **{'self': self})
        elif len_val == 2 and i == 1:
            generate_profiling_diff_output_data_in_pdf_helper(jeprof_script, program_symlink, unpack_dir, heap_keys[0], key, current_tgz_location, f"{node}_{app_name}_test_iteration_{0}-{i}_mem", app_heap_dump_dict, '1', **{'self': self})
        elif len_val == 3 and i == 2:
            generate_profiling_diff_output_data_in_pdf_helper(jeprof_script, program_symlink, unpack_dir, heap_keys[0], key, current_tgz_location, f"{node}_{app_name}_test_iteration_{0}-{i}_mem", app_heap_dump_dict, '1', **{'self': self})
        elif len_val >= 4 and hash_value == 0:
            generate_profiling_diff_output_data_in_pdf_helper(jeprof_script, program_symlink, unpack_dir, heap_keys[0], key, current_tgz_location, f"{node}_{app_name}_test_iteration_{0}-{i}_mem", app_heap_dump_dict, '1', **{'self': self})

    # Generate config pre/post test outputs
    generate_profiling_diff_output_data_in_pdf_helper(jeprof_script, program_symlink, unpack_dir, 'test_config_pre_test', 'test_config_post_test', current_tgz_location, f"{node}_{app_name}_test_config_pre_test-post_test", app_heap_dump_dict, '1', **{'self': self})
    generate_profiling_diff_output_data_in_pdf_helper(jeprof_script, program_symlink, unpack_dir, 'lrm_config_pre_test', 'lrm_config_post_test', current_tgz_location, f"{node}_{app_name}_lrm_config_pre_test-post_test", app_heap_dump_dict, '1', **{'self': self})

    pass


def extract_program_symlink_and_unpack_dir(response, unpack_dir_prefix="unpack_dir:"):
    # Extract unpack directory path
    
    gen_match_obj = re.search(rf'{unpack_dir_prefix}\s+(.*).unpack', response)
    
    if gen_match_obj:
        unpack_data = gen_match_obj.group(0)
        return f"{unpack_data[1]}.unpack"
    raise ValueError("Unpack directory does not match the expected format.")

def extract_program_symlink(response, unpack_dir):
    # Extract program symlink from response
    matches = [match.group(1) for match in re.finditer(rf'program symlink:\s+<unpack_dir>\/(.*)', response)] or []
    
    if matches:
        return f"{unpack_dir}/{matches[0]}"
    raise ValueError("Program symlink not found in response.")

def run_subprocess(command):
    # Run subprocess and handle errors
    response = subprocess.run(command, shell=True, capture_output=True, text=True)
    if response.returncode != 0:
        raise subprocess.CalledProcessError(response.returncode, command, output=response.stdout, stderr=response.stderr)
    return response.stdout

def proc_collector_unpack_profiling_data_helper(_rtr, dict, **kwargs):
    self = kwargs.get('self', None)
    rh = testbed.get_handle(resource=_rtr)
    _h_name = device_utils.get_host_name_for_device(rh)

    key_list = list(dict.keys())
    heap_keys = [gen_item for gen_item in key_list if re.match(r'\d+', gen_item)]
    
    if len(key_list) < 2:
        testbed.log(f"'level' = WARN", display_log=True)
    
    current_tgz_location = dict['tgz_location']
    tgz_file_name = dict['tgz_name']
    node = dict['node']
    
    os.makedirs(f"{current_tgz_location}/dump", exist_ok=True)

    # Unpack profiling data

    #unpack_command = f"python3 {self.proc_collector_profile_tools_path}/jeprof_unpack.py {current_tgz_location}/{_h_name}.{node}.{tgz_file_name} -d {current_tgz_location}/dump"
    #response = run_subprocess(unpack_command)
    import subprocess
    
    unpack_command = [
        "python3",
        f"{self.proc_collector_profile_tools_path}/jeprof_unpack.py",
        f"{current_tgz_location}/{_h_name}.{node}.{tgz_file_name}",
        "-d",
        f"{current_tgz_location}/dump"
    ]
    folder_path = f"{current_tgz_location}/dump"
    import glob
    response = subprocess.run(unpack_command, capture_output=True, text=True)
    unpack_files = glob.glob(os.path.join(folder_path, "*.unpack"))
    if unpack_files:
        print("Found .unpack file(s):", unpack_files)
        
        return True
    else:
        print("No .unpack files found in the folder.")
        return 
    #unpack_dir = 
    #unpack_dir = extract_program_symlink_and_unpack_dir(response)

    program_symlink = extract_program_symlink(response, unpack_dir)
    jeprof_script = f"{unpack_dir}/jeprof.sh"

    Generate_Profiling_Diff_output_data_In_Pdf(unpack_dir, jeprof_script, program_symlink, dict, heap_keys, current_tgz_location, **{'self': self})

def Proc_Collector_Unpack_Profiling_Data(rtr, **kwargs):
    self = kwargs.get('self', None)
    attr_name = f"proc_collector_track_{rtr}_list"

    # Ensure the attribute exists and is a list
    if not hasattr(self, attr_name):
        setattr(self, attr_name, [])

    # Iterate over the list safely
    for item in getattr(self, attr_name):
        proc_collector_unpack_profiling_data_helper(rtr, item, **{'self': self})


def proc_collector_post_analysis(**kwargs):
    self = kwargs.get('self', None)
  
    for rtr in self.evo_lng_rtr_list:
        Proc_Collector_Unpack_Profiling_Data(rtr, **{'self': self})

def evo_proc_collector_execute_and_profile_data_collection(**kwargs):
    
    self = kwargs.get('self', None)
    evo_proc_collector_execute(**{'self': self})

    proc_collector_post_analysis(**{'self': self})

def remove_profile_files(rh, cleanup_list, process_name_regex, file_prefix, node=None, **kwargs):
    self = kwargs.get('self', None)
    for file in cleanup_list:
        process_name = [match.group(1) for match in re.finditer(process_name_regex, file)] or []
        if process_name:
            remove_command = f"rm {file}"
            device_utils.execute_shell_command_on_device(device=rh, timeout=self.cmd_timeout, command=remove_command, pattern='Toby.*%$')
            log_remove_command = f"rm {file_prefix}/{process_name[0]}.*.heap"
            device_utils.execute_shell_command_on_device(device=rh, timeout=self.cmd_timeout, command=log_remove_command, pattern='Toby.*%$')

def remove_proc_collector_profile_files_on_node_re(rtr, node, cleanup_list, **kwargs):
    
    self = kwargs.get('self', None)
    rh = testbed.get_handle(resource=rtr)
    device_utils.set_current_controller(rh, controller=node)
    device_utils.switch_to_superuser(device=rh)
    
    remove_profile_files(rh, cleanup_list, r'\/var\/tmp\/([a-zA-Z-_0-9]+)\..*\.tgz', '/var/log', node, **kwargs)
  
    device_utils.set_current_controller(rh, controller='master')

def remove_proc_collector_profile_files_on_node_fpc(rtr, node, cleanup_list, **kwargs):
    self = kwargs.get('self', None)
    rh = testbed.get_handle(resource=rtr)
    device_utils.switch_to_superuser(rh)
    
    remove_profile_files(rh, cleanup_list, r'^([a-zA-Z-_]+)\..*\.tgz', '/var/home/regress', node, **kwargs)
    
    # Remove memory profiling files specific to the node
    device_utils.execute_shell_command_on_device(device=rh, timeout=self.cmd_timeout, command=f"rm /var/home/regress/{node}.*mem_prof.*", pattern='Toby.*%$')


def process_node(node, rtr, node_cleanup_list, cleanup_func, **kwargs):
    self = kwargs.get('self', None)
    """Process the cleanup based on node type (RE or FPC)."""
    if 're' in node:
        cleanup_func(rtr, node, node_cleanup_list, **kwargs)
    elif 'fpc' in node:
        cleanup_func(rtr, node, node_cleanup_list, **kwargs)

def proc_collector_cleanup_profiling_data_helper(rtr, node_list, **kwargs):
    self = kwargs.get('self', None)
    
    for node in node_list:
        node_cleanup_list = getattr(self, f"proc_collector_cleanup_{rtr}_{node}_list", [])
        
        # Perform cleanup for RE or FPC nodes
        if 're' in node:
            process_node(node, rtr, node_cleanup_list, remove_proc_collector_profile_files_on_node_re, **{'self': self})
        #process_node(node, rtr, node_cleanup_list, remove_proc_collector_profile_files_on_node_fpc, **{'self': self})

def proc_collector_cleanup_profiling_data(**kwargs):
    self = kwargs.get('self', None)
    
    for rtr in self.evo_lng_rtr_list:
        node_list = evo_get_node_list(rtr, **{'self': self})
      
        proc_collector_cleanup_profiling_data_helper(rtr, node_list, **{'self': self})

def generate_dashboard_link(web_prefix, toby_log_folder, _global_iter, host_name, test_type, test_id_max, **kwargs):
    self = kwargs.get('self', None)
    """Generate a dashboard link for the given test iteration."""
    for id in range(1, self.test_id_max + 1):  # Start from 1 for n_id calculation
        n_id = str(id)
        return f"{web_prefix}/toby_logs/{toby_log_folder}/test_suite_iter_{_global_iter}/{test_type}Test_Scenario{n_id}/dashboard/{host_name}/lrm_config_post_test/Longevity_dashboard.html"

def embed_dashboard_links_to_report_helper_extend(rtr, host_name, web_prefix, toby_log_folder, **kwargs):
    self = kwargs.get('self', None)
    
    # Generate and return dashboard links for all test scenarios
    for _global_iter in range(0, self.global_iterations):
        dashboard_link = generate_dashboard_link(web_prefix, toby_log_folder, _global_iter, host_name, self.test_type, self.test_id_max, **kwargs)
        pass  # TODO: Further processing of the link

def embed_dashboard_links_to_report_helper(_global_iter, rtrs, **kwargs):
    self = kwargs.get('self', None)
    
    # Extract the Toby log folder name from the report file path
    toby_log_folder = REPORT_FILE.split('/')[-2]  # Assuming REPORT_FILE is a string path
    
    for rtr in rtrs:
        host_name = t['resources'][rtr]['system']['primary']['name']
        embed_dashboard_links_to_report_helper_extend(rtr, host_name, web_prefix, toby_log_folder, **{'self': self})

def embed_dashboard_links_to_report(rtrs, **kwargs):
    self = kwargs.get('self', None)
    
    for _global_iter in range(0, self.global_iterations):
        embed_dashboard_links_to_report_helper(self.global_iter, rtrs, **{'self': self})

def create_lrm_view_directory(out_dir):
    """Helper function to create LRM view directory."""
    lrm_out_dir = f"{out_dir}/lrm_view"
    os.makedirs(lrm_out_dir, exist_ok=True)
    return lrm_out_dir

def handle_evo_flag(evoFlag, **kwargs):
    """Handle the logic for EVO flag - Placeholder for missing logic."""
    if evoFlag:
        pass  # TODO: Missing KW
    else:
        pass  # TODO: Missing KW
    pass



def longevity_dashboard_consolidated_generation_helper(g_iter, dashboard_dir, **kwargs):
    """Helper to generate dashboard for each router."""
    self = kwargs.get('self', None)
    for lrtr in self.combined_lng_rtr_list:
        is_evo = getattr(self, f"isEvo_{lrtr}")
        node_list = self.evo_get_node_list_for_dashboard(lrtr) if is_evo else self.junos_get_node_list(lrtr)

        host_name = t['resources'][lrtr]['system']['primary']['name']
        out_dir = os.path.join(dashboard_dir, host_name)
        os.makedirs(out_dir, exist_ok=True)

        platform = tv[f"{lrtr}__model"]
        version = tv[f"{lrtr}__os-ver"]
        
        if 'qfx' in platform:
            node_list = ['re0']

        self.longevity_dashboard_for_global_view(
            g_iter=g_iter,
            log_dir_location=self.output_dir,
            host_name=host_name,
            node_list=node_list,
            out_dir=out_dir,
            is_evo=is_evo,
            platform=platform,
            version=version,
            lrtr=lrtr,
            **kwargs
        )

def longevity_dashboard_for_global_view(g_iter, log_dir_location, host_name, node_list, out_dir, is_evo, platform, version, lrtr, **kwargs):
    
    self = kwargs.get('self', None)
    """Generate dashboard view for each scenario under one iteration."""
    for test_id in range(self.test_id_max):
     
        n_id = test_id + 1
        scenario = f"{self.test_type}Test_Scenario{n_id}"
        sub_log_dir = f"{log_dir_location}/test_suite_iter_{g_iter}/{scenario}"
        if 'qfx' not in platform:
            try:
                collection_types = getattr(self, f"npu_memory_list_{lrtr}")
            except AttributeError:
                collection_types = None
                testbed.log(f"⚠️ Attribute 'npu_memory_list_{lrtr}' not found. Falling back to default collection types.", display_log=True)
        else:
            collection_types=None

        if is_evo:
            lng_evo_global.collect_data_for_dashboard_evo(
                log_dir_location=sub_log_dir,
                host_name=host_name,
                node_list=node_list,
                scenario=scenario,
                collection_types=collection_types
            )
        else:
            lng_junos_global.collect_data_for_dashboard_junos(
                log_dir_location=sub_log_dir,
                host_name=host_name,
                node_dict=node_list,
                scenario=scenario
            )

    # Plot graphs

    plot_dashboard(g_iter, out_dir, host_name, is_evo, platform, version, lrtr, lrm_view=False)

    # Plot LRM View
    lrm_out_dir = os.path.join(out_dir, "lrm_view")
    os.makedirs(lrm_out_dir, exist_ok=True)
    plot_dashboard(g_iter, lrm_out_dir, host_name, is_evo, platform, version, lrtr, lrm_view=True)
   

def plot_dashboard(g_iter, out_dir, host_name, is_evo, platform, version, lrtr, lrm_view=False):
    """Plot graphs based on platform."""
    if is_evo:
        lng_evo_global.plot_graph_for_single_global_iteation_dashboard(
            out_dir=out_dir,
            host_name=host_name,
            platform=platform,
            version=version,
            lrm_view=lrm_view,
            rtr=lrtr
        )
    else:
        lng_junos_global.plot_graph_for_single_global_iteation_dashboard(
            out_dir=out_dir,
            host_name=host_name,
            platform=platform,
            version=version,
            lrm_view=lrm_view,
            rtr=lrtr
        )
def longevity_dashboard_consolidated_generation(**kwargs):
    
 
    
    """Main entry for generating consolidated dashboard across iterations."""
    
    self = kwargs.get('self', None)
    
    testbed.log("Longevity Dashboard creation for consolidated view is in progress.....\n")
    

    for g_iter in range(self.global_iterations):
        dashboard_dir = f"{self.output_dir}/test_suite_iter_{g_iter}/dashboard/"
        os.makedirs(dashboard_dir, exist_ok=True)

        if self.test_type == 'Active':
            if self.junos_lng_global_flag:
                self.lng_junos_global.events_report(
                    events_log_dir_location=f"{self.output_dir}/test_suite_iter_{g_iter}",
                    test_type=self.test_type,
                    max_test_id=self.test_id_max
                )
            if self.evo_lng_global_flag:
                lng_evo_global.events_report(
                    events_log_dir_location=f"{self.output_dir}/test_suite_iter_{g_iter}",
                    test_type=self.test_type,
                    max_test_id=self.test_id_max
                )

        longevity_dashboard_consolidated_generation_helper(g_iter, dashboard_dir, **kwargs)

    testbed.log("Longevity Dashboard creation for consolidated view is completed.\n")



def longevity_test_execution(
    steady_state_keyword, event_keyword, longevity_test_duration_in_seconds,
    test_scenario, log_sub_dir_name, test_type, **kwargs
):
    """
    Executes longevity test and handles test preparation, execution, and data collection.
    """
    #brcm_hosts_info = []
    self = kwargs.get('self', None)
    self.brcm_hosts_info = []
    self.brcm_host_names = []
    if not self:
        raise ValueError("self is required in kwargs")

    # Set test type name
    TEST_TYPE_NAME = 'ACTIVE' if test_type == 'Active' else 'PASSIVE'
    self.test_scenario = test_scenario
    self.LONGEVITY_OUTPUT_DIR = log_sub_dir_name

    # Create necessary directories
    directories = [
        self.LONGEVITY_OUTPUT_DIR,
        f"{self.LONGEVITY_OUTPUT_DIR}/memory_profiling",
        f"{self.LONGEVITY_OUTPUT_DIR}/dashboard",
        f"{self.LONGEVITY_OUTPUT_DIR}/monitor"
    ]

    for rtr in self.evo_lng_rtr_list + self.junos_lng_rtr_list:
        host_name = t['resources'][rtr]['system']['primary']['name']
        is_brcm_inspect_enabled = tv.get(f"{rtr}__uv-evo-brcm-inspection-enabled",0)
        brcm_host_mgt_ip =  tv.get(f"{rtr}__re0__mgt-ip")
            
        if int(is_brcm_inspect_enabled) == 1:
            self.brcm_hosts_info.append(brcm_host_mgt_ip)
            self.brcm_host_names.append(host_name)
            
        directories.append(f"{self.LONGEVITY_OUTPUT_DIR}/dashboard/{host_name}")
        if rtr in self.evo_lng_rtr_list:
            directories.append(f"{self.LONGEVITY_OUTPUT_DIR}/memory_profiling/{host_name}")

    for directory in directories:
        os.makedirs(directory, exist_ok=True)

    # Set test duration variables
    self.duration_in_sec = longevity_test_duration_in_seconds
    self.duration_in_hrs = Time(self.duration_in_sec).convert('verbose', millis=True)
    
    is_load_lrm_config = tv.get('uv-longevity-skip-lrm-baseline-step', 0) == 0

    # Initialize logging
    LLOG(message=f"!!!!!!!! {TEST_TYPE_NAME} LONGEVITY TEST START FOR: {self.test_scenario}!!!!!!!!", **{"self": self})

    # Pre-processing if applicable
    if self.test_scenario == 'Test_Scenario1' and test_type == 'Active':
        data_preprocessing(**{"self": self})

    # Stop TE objects if applicable
    #if self.te_user_flag and self.test_scenario == 'Test_Scenario1':
    #    process_user_te_objects(self.te_data_objects_list, 'stop', **{"self": self})

    # Test preparation steps
    if self.test_scenario == 'Test_Scenario1':
        if self.junos_lng_global_flag:
            junos_preparation_helper(self.junos_lng_rtr_list, **{'self': self})
        longevity_test_preparation(self.combined_lng_rtr_list, **{'self': self})
        longevity_start_te_registrations(**{"self": self})

    # Memory Profiling if enabled
    self.is_mem_profiling_enabled = tv.get('uv-evo-enable-memory-profiling', 0)
    if self.is_mem_profiling_enabled == 1 and self.evo_lng_global_flag:
        pdt_start_memory_profiling('lrm_config', rtr_list=self.evo_lng_rtr_list, **{"self": self})

    if self.evo_lng_global_flag:
        evo_proc_collector_init('lrm_config', **{"self": self})

    collect_longevity_test_data(self, longevity_check_point='lrm_config_pre_test') #REM
    
    #Take the brcm snapshot
  
    print("Brcm Inspection is started for lrm_config_pre checkpoint")
    
    for _brcm_host in self.brcm_hosts_info:
        print(f"Brcm Inspection is started for host {_brcm_host} lrm_config_pre checkpoint")
        
        try:
            collector = BRCMDataCollector(
                host="10.83.6.47",
                user="root",
                remote_dir="/var/log/batch_cli",
                local_dir="/path/to/local/log/dir",
                qfx_switch=f"{_brcm_host}",
                root_passwd="Embe1mpls",
                longevity_dir=self.LONGEVITY_OUTPUT_DIR,
                scenario=f"{test_type}{self.test_scenario}",
                check_point="lrm_config_pre_test"
            )

            # Execute the collection process
            lrm_pre_snap_dir = collector.execute()

            if not lrm_pre_snap_dir:
                testbed.log(level="WARN", message= f"Snapshot not created for {_brcm_host}. Continuing to next host.", display_log=True)
            else:
                testbed.log(level="INFO", message= f"Snapshot created at {lrm_pre_snap_dir} for {_brcm_host}", display_log=True)
        except RuntimeError as e:
            testbed.log(level="ERROR", message=f"[{_brcm_host}] Runtime error: {e}", display_log=True)
        except Exception as e:
            testbed.log(level="ERROR", message=f"[{_brcm_host}] Unexpected failure during BRCM inspection: {e}", display_log=True)

    

    if is_load_lrm_config:
        #longevity_te_lrm_baseline_snapshot()
        longevity_load_rtr_test_config(**{"self": self})
        settle_down_time = tv['uv-longevity-post-lrm-baseline-wait-time']
        LLOG(level="INFO", message=f"Sleeping for {settle_down_time} seconds after loading test config...", **{"self": self})
        time.sleep(settle_down_time)
        #longevity_te_test_config_start()

    # Handle steady state keyword execution
    #if steady_state_keyword:
    #    try:
    #        pass  # Execute steady_state_keyword logic
    #    except Exception:
    #        pass


    # Pre-test Data Collection
    '''
    for _brcm_host in self.brcm_hosts_info:
        print(f"Brcm Inspection is started for host {_brcm_host} test_config_pre checkpoint")
        collector = BRCMDataCollector(
            host="10.83.6.47",
            user="root",
            remote_dir="/var/log/batch_cli",
            local_dir="/path/to/local/log/dir",
            qfx_switch=f"{_brcm_host}",
            root_passwd="Embe1mpls",
            longevity_dir=self.LONGEVITY_OUTPUT_DIR,
            scenario=f"{test_type}{self.test_scenario}",
            check_point="test_config_pre_test"
        )
        
        # Execute the collection process
        test_pre_snap_dir = collector.execute()
    '''
    collect_longevity_test_data(self, longevity_check_point='test_config_pre_test') 
    #
    targets=[]
    uport_n =40061
    default_port = None
    gnmi_port =0
    #for rtr in self.evo_lng_rtr_list:
    for rtr in self.combined_lng_rtr_list:
        rh = testbed.get_handle(resource=rtr)
        mgt_ip=tv.get(f"{rtr}__re0__mgt-ip")
        is_link_monitor_enabled = tv.get(f"{rtr}__uv-link-monitor-enabled", 0)
        is_gnmi_inspect_enabled = tv.get(f"{rtr}__uv-evo-gnmi-inspection-enabled",0)
       
        if is_gnmi_inspect_enabled:
            gnmi_port = 50051
        else:
            gnmi_port=uport_n
        cmd_list =[
            "set system services extension-service request-response grpc clear-text address 0.0.0.0",
            f"set system services extension-service request-response grpc clear-text port {gnmi_port}",
            "set system services extension-service request-response grpc max-connections 30",
            #"set system services extension-service request-response grpc routing-instance mgmt_junos
            "set system services extension-service request-response grpc skip-authentication",
            "set system services extension-service request-response grpc grpc-keep-alive 300"
        ]
        device_utils.execute_config_command_on_device(
                rh, command_list=cmd_list, 
                commit=True, pattern="Toby.*#$"
        )
        
        targets.append(f"{mgt_ip}:{gnmi_port}")
        uport_n+=1
        #targets.append(f"{TARGETS_DICT[mgt_ip]}")
   
    _log_dir = f"{self.LONGEVITY_OUTPUT_DIR}/monitor"
    rmm, rep, run_id = start_sample("Test_Scenario1", targets, _log_dir)
    # 
   
    ## test_config_pre_test to clear lhe logs.

    if self.test_scenario == 'Test_Scenario1':
        _model_list = []
        for rtr in self.evo_lng_rtr_list:              
            is_gnmi_inspect_enabled = tv.get(f"{rtr}__uv-evo-gnmi-inspection-enabled",0)
            if is_gnmi_inspect_enabled == 1:
                yang_gnmi_server = testbed.get_handle(resource='h0')
                hostname = tv.get(f"{rtr}__re0__hostname")
                lng_tel = LongevityTelemetry(yang_gnmi_server,hostname)
                lng_tel.run_oc_paths()
                
                
            
        #check_for_link_down_events(rtr, 'test_config_pre_test', **kwargs)
        #Check For Link Down Events     ${rtr}      test_config_pre_test
            


    # TE data snapshot for test config pre_test
    #longevity_te_test_config_snapshot() 
    
    # Test Execution
    time1 = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    LLOG(message=f"**--------------{TEST_TYPE_NAME} LONGEVITY Execution Started: {time1} ----**", **{"self": self})
    print(f"**--------------{TEST_TYPE_NAME} LONGEVITY Execution Started: {time1} ----**")

    if test_type == 'Active':
        Active_Execution(steady_state_keyword, event_keyword, **{"self": self})
    else:
        passive_execution(steady_state_keyword, **{"self": self})

    '''
    # Post-test Data Collection
    for _brcm_host in self.brcm_hosts_info:
        collector = BRCMDataCollector(
            host="10.83.6.47",
            user="root",
            remote_dir="/var/log/batch_cli",
            local_dir="/path/to/local/log/dir",
            qfx_switch=f"{_brcm_host}",
            root_passwd="Embe1mpls",
            longevity_dir=self.LONGEVITY_OUTPUT_DIR,
            scenario=f"{test_type}{self.test_scenario}",
            check_point="test_config_post_test",
            base_dir=test_pre_snap_dir
        )
        test_postsnap_dir = collector.execute()
        
        print(test_postsnap_dir)
    '''
    collect_longevity_test_data(self, longevity_check_point='test_config_post_test')
    
    # stop monitoring 
    stop_sample(rmm, rep, "test_config_post_test", run_id, targets, _log_dir)
    


    time2 = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    LLOG(message=f"**--------------{TEST_TYPE_NAME} LONGEVITY Execution Ended: {time2} ----**", **{"self": self})

    # Post-Test Preparation
    longevity_post_test_preparation(self.combined_lng_rtr_list, **{"self": self})

   
    # LRM Baseline Convergence if applicable
    if is_load_lrm_config:
        
   
        for _brcm_host in self.brcm_hosts_info:
            print(f"Brcm Inspection is started for host {_brcm_host} lrm_config_pre checkpoint")
            try:
                collector = BRCMDataCollector(
                    host="10.83.6.47",
                    user="root",
                    remote_dir="/var/log/batch_cli",
                    local_dir="/path/to/local/log/dir",
                    qfx_switch=f"{_brcm_host}",
                    root_passwd="Embe1mpls",
                    longevity_dir=self.LONGEVITY_OUTPUT_DIR,
                    scenario=f"{test_type}{self.test_scenario}",
                    check_point="lrm_config_post_test",
                    base_dir=lrm_pre_snap_dir
                )
                lrm_postsnap_dir = collector.execute()
            
                if not lrm_pre_snap_dir:
                    testbed.log(level="WARN", message= f"Snapshot not created for {_brcm_host}. Continuing to next host.", display_log=True)
                else:
                    testbed.log(level="INFO", message= f"Snapshot created at {lrm_pre_snap_dir} for {_brcm_host}", display_log=True)
            except RuntimeError as e:
                testbed.log(level="ERROR", message=f"[{_brcm_host}] Runtime error: {e}", display_log=True)
            except Exception as e:
                testbed.log(level="ERROR", message=f"[{_brcm_host}] Unexpected failure during BRCM inspection: {e}", display_log=True)



        # Post-test Data Collection
        
        collect_longevity_test_data(self, longevity_check_point='lrm_config_post_test')
        
        #try:
        #    longevity_te_lrm_baseline_converge()
        #except Exception as e:
        #    LLOG(level="WARN", message=f"LRM baseline convergence failed: {str(e)}", **{"self": self})

    # Stop Memory Profiling if applicable
    if self.evo_lng_global_flag:
        try:
            pdt_stop_memory_profiling(**{"self": self})
            evo_proc_collector_execute_and_profile_data_collection(**{"self": self})
            
            proc_collector_cleanup_profiling_data(**{"self": self})
            
            generate_longevity_dashboard(**{"self": self})
            
            
         
        except Exception as e:
            LLOG(level="WARN", message=f"Memory profiling cleanup failed: {str(e)}", **{"self": self})

    if self.junos_lng_global_flag:
        generate_longevity_junos_dashboard(**{"self": self})


    
    
    try:
        # --- Section 1: Load LRM Config & Sleep ---
        if is_load_lrm_config and test_scenario == f"Test_Scenario{self.test_id_max}":
            longevity_load_rtr_test_config(**{"self": self})
            settle_down_time = tv['uv-longevity-test-pre-post-settle-down-time']
            LLOG(level="INFO", message=f"Sleeping for {settle_down_time} seconds after loading test config...", **{"self": self})
            time.sleep(settle_down_time)

        # --- Section 2: Post Test Config Keywords Execution ---
        #test_post_kw = self.run_kw_after_test_load_config if self.run_kw_after_test_load_config else []
        #is_test_post_kw_empty = not bool(test_post_kw)

        #kw4_result = "PASS"
        #kw4_failure_reason = "Keyword did not run"

        #if not is_test_post_kw_empty and is_load_lrm_config:
        #    try:
        #        for keyword in test_post_kw:
        #            keyword()  # Assume keyword is a callable Python function
        #    except Exception as e:
        #        kw4_result = "FAIL"
        #        kw4_failure_reason = str(e)

        #if kw4_result == "FAIL":
            #logging.warning(f"Failure Reason for post test keyword(s):\n{kw4_failure_reason}\n")
        #    LLOG(level="WARN", message=f"Failure Reason for post test keyword(s):\n{kw4_failure_reason}\n", **{"self": self})

        # --- Section 3: Embed Dashboard Links ---
        
        if test_scenario == f"Test_Scenario{self.test_id_max}":
            #embed_dashboard_links_to_report(self.combined_lng_rtr_list, **kwargs)
        
            longevity_dashboard_consolidated_generation(**kwargs)

    except Exception as e:
        LLOG(level="WARN", message=f"Exception during longevity execution block: {str(e)}", **{"self": self})
        

    # Stop Longevity Test
    #longevity_te_lrm_baseline_stop(self.is_load_lrm_config)
    #longevity_te_test_config_stop()
    






def prepare_for_test(self):
    
    
    if self.te_user_flag and self.test_scenario == 'Test_Scenario1':
        process_user_te_objects(self.te_data_objects_list, 'stop', **{'self': self})
    
    if self.test_scenario == 'Test_Scenario1' and self.junos_lng_global_flag:
        junos_preparation_helper(self.junos_lng_rtr_list, **{'self': self})
    
    if self.test_scenario == 'Test_Scenario1':
        longevity_test_preparation(self.combined_lng_rtr_list, **{'self': self})

def create_router_directories(self):
    for rtr in self.evo_lng_rtr_list:
        create_router_specific_dirs(self, rtr)
    for rtr in self.junos_lng_rtr_list:
        host_name = t['resources'][rtr]['system']['primary']['name']
        os.makedirs(f"{self.LONGEVITY_OUTPUT_DIR}/dashboard/{host_name}", exist_ok=True)

def create_router_specific_dirs(self, rtr):
    setattr(self, eval(f"{rtr + '_lrm_disabled_apps'}"), '')
    setattr(self, eval(f"{rtr + '_lrm_memory_profiling_disabled_apps'}"), '')
    setattr(self, eval(f"{rtr + '_memory_profiled_enabled_apps'}"), '')
    
    host_name = t['resources'][rtr]['system']['primary']['name']
    os.makedirs(f"{self.LONGEVITY_OUTPUT_DIR}/dashboard/{host_name}", exist_ok=True)
    os.makedirs(f"{self.LONGEVITY_OUTPUT_DIR}/memory_profiling/{host_name}", exist_ok=True)

def collect_longevity_test_data(self, longevity_check_point):
    
    
    
    if self.evo_lng_global_flag:
        evo_dump_memory_prof(longevity_check_point, **{'self': self})
        
    #lng_data_obj = LongevityDataCollection.LongevityDataCollection('lngdata')
    lng_data_obj = LongevityDataCollection(name="lngdata")
    # Call the Data Collection Preparation and Init function (if it's a function or method, you may need to import it)
    Data_Collection_Preparation_and_Init(self.combined_lng_rtr_list, lng_data_obj, **{'self': self})
    # Call the evo_dump_memory_prof method on lng_data_obj
    
    lng_data_obj.longevity_data_collection(self.combined_lng_rtr_list, self.data_collect_nodes, self.LONGEVITY_OUTPUT_DIR, longevity_check_point )


def prepare_test_config(self):
    if self.is_load_lrm_config == 0:
        longevity_te_lrm_baseline_snapshot()


def execute_test(self, steady_state_keyword, event_keyword):
    test_pre_kw = get_keyword_list('run_kw_before_test_load_config')
    execute_keyword(test_pre_kw, self)
    
    if self.test_type == 'Active':
        Active_Execution(steady_state_keyword, event_keyword, **{'self': self})
    elif self.test_type == 'Passive':
        passive_execution(steady_state_keyword, **{'self': self})

    test_post_kw = get_keyword_list('run_kw_after_test_load_config')
    execute_keyword(test_post_kw, self)

def execute_keyword(keywords, self):
    for kw in keywords:
        try:
            pass  # Execute keyword logic
            kw_result = 'PASS'
        except Exception as e:
            kw_result = 'FAIL'
            LLOG(level='WARN', message=f"Failure Reason for {kw}: {str(e)}", **{'self': self})
            pass

def finalize_test(self):
    if self.evo_lng_global_flag:
        evo_dump_memory_prof('test_config_post_test', **{'self': self})
    
    if self.junos_lng_global_flag:
        longevity_junos_data_collection('test_config_post_test', **{'self': self})
    
    # Logging test completion
    time2 = dt_utils.get_time("timestamp", dt_utils.parse_time('NOW'))
    LLOG(message=f"**--------------{self.test_type} LONGEVITY Execution Ended: {time2} ----**", **{'self': self})
    
    longevity_post_test_preparation(self.combined_lng_rtr_list, **{'self': self})

    # Collecting profiling data and generating dashboards
    if self.evo_lng_global_flag:
        pdt_stop_memory_profiling(**{'self': self})
        evo_proc_collector_execute_and_profile_data_collection(**{'self': self})
        proc_collector_cleanup_profiling_data(**{'self': self})
        generate_longevity_dashboard(**{'self': self})
    
    if self.junos_lng_global_flag:
        generate_longevity_junos_dashboard(**{'self': self})

def get_keyword_list(keyword_name):
    return globals().get(keyword_name, [])

def longevity_test_execution_helper(g_iter, steady_state_keyword, event_keyword, **kwargs):
    self = kwargs.get('self', None)
    os.makedirs(f"{testbed._log_dir}/test_suite_iter_{g_iter}", exist_ok=True)
    LONGEVITY_SUITE_OUTPUT_DIR = f"{testbed._log_dir}/test_suite_iter_{self.global_iter}"
    self.output_dir = f"{testbed._log_dir}"

    
    test_ids = list(self.longevity_test_scenarios.keys())
    self.test_id_max = len(test_ids)
    
    for test_id in test_ids:
        test_id = str(int(test_id))
        log_sub_dir_name = f"{self.test_type}Test_Scenario{test_id}"
        test_duration_temp = self.longevity_test_scenarios[test_id]
        longevity_test_execution(steady_state_keyword, event_keyword, test_duration_temp, f"Test_Scenario{test_id}", f"{LONGEVITY_SUITE_OUTPUT_DIR}/{log_sub_dir_name}", self.test_type, **{'self': self})

def longevity_test(test_type, steady_state_keyword='', event_keyword='', 
                   run_kw_before_lrm_load_config='', run_kw_after_lrm_load_config='',
                   run_kw_before_test_load_config='', run_kw_after_test_load_config='', 
                   te_data_objects=None, **kwargs):

    self = kwargs.get('self', None)
    
    # Set various keyword arguments for later use
    self.run_kw_before_lrm_load_config = run_kw_before_lrm_load_config
    self.run_kw_after_lrm_load_config = run_kw_after_lrm_load_config
    self.run_kw_before_test_load_config = run_kw_before_test_load_config
    self.run_kw_after_test_load_config = run_kw_after_test_load_config

    # Validate and log test type
    valid_test_types = ['Active', 'Passive']
    
    
    if test_type not in valid_test_types:
        LLOG(message=f"Invalid Test type: {test_type}", **{'self': self})
        raise Exception("Invalid test type")
    
    LLOG(message=f"Longevity Test Type is: {test_type}", **{'self': self})
    
    # Process te_data_objects list
    self.te_data_objects_list = te_data_objects.split(',') if te_data_objects else []
    self.te_user_flag = 'True' if self.te_data_objects_list else 'False'

    # Assign test type and longevity test scenarios
    self.test_type = test_type
    self.longevity_test_scenarios = {}

    # Detect longevity devices and baseline configurations
    detect_longevity_devices(**{'self': self})
    
    
    
    # Skip LRM configuration if the flag is set
    if tv.get('uv-longevity-skip-lrm-baseline-step', 0) == 0:
        lrm_baseline_config_check(self.combined_lng_rtr_list, **{'self': self})

    # Set longevity test scenarios and timers
    set_longevity_test_scenarios(**{'self': self})
    LLOG(message='Longevity Test Timers:\n', **{'self': self})
    
    duration_in_hrs = tv.get("uv-longevity-test-duration", '1')
    self.duration_in_hrs = duration_in_hrs
    self.duration_in_secs = str(int(duration_in_hrs) * 3600)  # Convert to seconds
    
    # Set global iteration count
    self.global_iterations = tv.get('uv-longevity-global-iterations', 1)
    
    # Run longevity tests for each global iteration
    for global_iter in range(self.global_iterations):
        self.global_iter = global_iter
        longevity_test_execution_helper(self.global_iter, steady_state_keyword, event_keyword, **{'self': self})

def Data_Collection_Preparation_and_Init(_longevity_rtrs, data_collection, **kwargs):
    
    self = kwargs.get('self', None)
    
    # Fetch router list safely
    #evo_lng_rtr_list = kwargs.get('evo_lng_rtr_list', [])

    # Create data collection nodes
    self.data_collect_nodes = create_data_collection_nodes(_longevity_rtrs)

    for rtr in self.evo_lng_rtr_list:
        rh = testbed.get_handle(resource=rtr)
        ps_mem_loc = tv.get('uv-evo-ps-mem-location', 
                            '/volume/regressions/toby/test-suites/pdt/lib/longevity/ps_mem.py')

        cmd_resp = host_utils.upload_file(
            rh, local_file=ps_mem_loc, remote_file='~regress/ps_mem.py', 
            protocol='scp', user='regress', password='MaRtInI'
        )

        if not cmd_resp:
            testbed.log("Warning: File upload failed", level="WARN", display_log=True)
            return None  # Use None instead of EMPTY unless EMPTY is defined

    # Handle Junos AFT cards
    _junos_aft_cards = self.junos_aft_cards if self.junos_lng_global_flag else {'': None}

    # Initialize data collection
    if _junos_aft_cards:
        data_collection.longevity_data_collection_init(_longevity_rtrs, self.data_collect_nodes, _junos_aft_cards)
    else:
        data_collection.longevity_data_collection_init(_longevity_rtrs, self.data_collect_nodes)


def Update_Junos_fpc_List(_fpc_list,**kwargs):

    return junos_fpc_list
    junos_fpc_list =  []
    for _fp in _fpc_list:
        junos_fpc_list.append(f"fpc{_fp}")
    pass

def create_data_collection_nodes(longevity_rtrs):
    """
    Creates a dictionary mapping routers to their respective node lists for data collection.
    """
    data_collect_nodes = {}

    for r in longevity_rtrs:
        rh = testbed.get_handle(resource=r)
        is_evo = rh.is_evo()

        if is_evo:
            node_list = evo_get_node_list(r)
        else:
            junos_node_data = junos_get_node_list(r)
            jnode_list = junos_node_data.get("fpc_list", [])

            # Update Junos FPC list if necessary
            jnode_list = update_junos_fpc_list(jnode_list)

            # Append 're0' for non-EVO routers
            jnode_list.append("re0")
            
            node_list = jnode_list

        data_collect_nodes[r] = node_list

   
    return data_collect_nodes

def update_junos_fpc_list(fpc_list):
    """
    Updates the Junos FPC list by prefixing each FPC with 'fpc'.
    
    :param fpc_list: List of FPC numbers.
    :return: Updated list with 'fpc' prefixed to each entry.
    """
    return [f"fpc{fp}" for fp in fpc_list]


def check_for_link_down_events(rtr:str, snapshot:str, **kwargs)-> None:
    
    self = kwargs.get('self', None)
    rh = testbed.get_handle(resource=rtr)
    hostname = tv.get(f"{rtr}__re0__hostname")
    cmd="show log messages | grep \"SNMP_TRAP_LINK_DOWN\""
    cmd_out = device_utils.execute_cli_command_on_device(device=rh, timeout=600, command=cmd)
    result = "No Link Down Events"
    if cmd_out:
        result=cmd_out
    output_file_path = os.path.join(self.LONGEVITY_OUTPUT_DIR, "events_monitor.log")
    os.makedirs(os.path.dirname(output_file_path), exist_ok=True)

    # Write event details to file
    with open(output_file_path, 'a', encoding='UTF-8') as file_hdl:
        file_hdl.write(f"{hostname}:{snapshot}:link_down_events_check:|{result}\n")
    
 
