import os
import sys
from pathlib import Path

# Consider using relative imports or installing the package properly
sys.path.insert(0, '/volume/regressions/toby/test-suites/MTS/resources/yang_gnmi_validator/openconfig')
import yang_validator_test_mts


class LongevityTelemetry:
    def __init__(self, yang_gnmi_server: str):
        self.yang_gnmi_server = yang_gnmi_server
        state_only_templates = ['openconfig-lldp_counters-stateonly_tc_template.yaml']
        callback_and_transform_func_files = ['lldp_callback_func.py']
        platform_annotation_file = 'openconfig-schema.xml'
        self.yang_gnmi_validator_files = {
            "state_only_templates": state_only_templates,
            "callback_and_transform_func_files": callback_and_transform_func_files,
            "platform_annotation_file": platform_annotation_file
        }
        yang_gnmi_server_setup(yang_gnmi_server, self.yang_gnmi_validator_files)

    def run_oc_paths(self):
        env_file = 'intf_xpath_env.yaml'
        oc_paths_list = [f"STATE_ONLY_LEAFS.TC_group_{i}" for i in range(1, 14)]
        for test_case in oc_paths_list:
            execute_yang_gnmi_validator(self.yang_gnmi_server, test_case, env_file)
    

if __name__ == "__main__():"


 
    
    lng_telemetry = LongevityTelemetry(state_only_templates,callback_and_transform_func_files,platform_annoation_file)