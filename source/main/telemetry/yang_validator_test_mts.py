import sys
#sys.path.append("/volume/regressions/toby/test-suites/MTS/resources/yang_gnmi_validator/lib")
import jnpr.toby.hldcl.host as host_utils
from common_lib import *
import pdb

# Global Vars
ygnmi_global_dict = {}

def configure_gnmi_in_dut(dut, gnmi_port=50051):

    command_list = [ "set system schema openconfig unhide", 
                f"set system services extension-service request-response grpc clear-text port {str(gnmi_port)}", 
                "set system services extension-service notification allow-clients address 0.0.0.0/0",
                "set system services extension-service request-response grpc skip-authentication",
                "set services analytics zero-suppression no-zero-suppression",
                "commit"]
    
    dut.config(command_list=command_list)

# Yang GNMI Setup
def configure_yang_gnmi_server(server_handle, files_dict, virtual_env_cmd=None):
    
    session_id = t.get_session_id()
    # Git clone and setting up folder structure to copy all template files and env files from script repo to tool directory in yang-gnmi server
    base_dir = f"{test_root_dir}/{session_id}"
    tool_dir = f"{base_dir}/api-publish/tools/yang_gnmi_validator"
    print(f"Tool dir: {tool_dir}")
    server_handle.shell(command = f"echo Tool-Dir: {tool_dir}")
    server_handle.shell(command = f"mkdir -p {base_dir}") 
    git_setup(base_dir, server_handle)
    #pdb.set_trace()
    ygnmi_global_dict['tool_dir'] = tool_dir
    server_handle.shell(command = f"cd {tool_dir}")
    #pdb.set_trace()
    server_handle.shell(command = f"mkdir {script_files_dir}")
    script_files_dir_path = f"{tool_dir}/{script_files_dir}"

    for file_name, file_path in files_dict.items():
        
        if file_path is not None and file_path != "None":            
            if not isinstance(file_path, list):
                file_path = [file_path]
            
            if file_name == "platform_annotation_file":
                [server_handle.upload(local_file=input_file, remote_file=script_files_dir_path) for input_file in file_path]           

            elif file_name == "callback_and_transform_func_files": # No substitution as these are python files
                callback_dir = f"{tool_dir}/callback_func"
                [server_handle.upload(local_file=input_file, remote_file=callback_dir) for input_file in file_path]
            
            elif file_name == "env_dict_list":
                if files_dict['platform_annotation_file'] not in ["None", None]:
                    platform_path = script_files_dir_path + "/" + str(files_dict['platform_annotation_file']).rsplit("/")[-1]
                    platform_dict = {"platform_annotation_file": platform_path}
                else:
                    platform_dict = None
                for env_content in file_path:
                    local_env_file = write_env_file(env_content, platform_dict)
                    server_handle.upload(local_file=local_env_file, remote_file=script_files_dir_path)
            
            else: # Template files
                for input_file in file_path:
                    substituted_file = substitute_vars(input_file, tv)
            
                    #server_handle.upload(local_file=substituted_file, remote_file=script_files_dir_path)
                    host_utils.upload_file(server_handle, local_file=substituted_file, remote_file=script_files_dir_path)
    
    # Activating virtual env - tmp-testing
    if virtual_env_cmd:
        server_handle.shell(command=virtual_env_cmd)
    elif use_vir_env is True:
        server_handle.shell(command=local_vir_env_cmd)
        
def execute_yang_gnmi_validator(server_handle, test_group_str, env_file, config_template=None, state_only_template=None):
    
    # Constructing the execution command with input template, env and test execution groups
    config_str = ""
    state_only_str = ""
    if config_template:
        config_str = f" -c {script_files_dir}/{get_dir_and_file_from_path(config_template)} "
    if state_only_template:
        space = " "
        if config_template:
            space = ""
        state_only_str = f"{space}-so {script_files_dir}/{get_dir_and_file_from_path(state_only_template)} "

    xpath_tester_cmd = f"python xpath_tester.py -env {script_files_dir}/{env_file} {config_str}{state_only_str}-teg {test_group_str} -e"
    #pdb.set_trace()
    server_handle.shell(command=xpath_tester_cmd, timeout=10000 )
    grep_cmd = f"ls -t {log_dir}/execute/*execution.log | head -n 1 | xargs grep 'Yang Validator Test Result'"
    grep_response = str(server_handle.shell(command=grep_cmd).response())
    #pdb.set_trace()
    if grep_response and "PASS" in grep_response:
        return True
    else:
        return False
    
def fetch_ygnmi_validator_logs(server_handle):
    
    session_id = t.get_session_id()
    
    tool_dir = ygnmi_global_dict['tool_dir']
    server_handle.shell(command = f"cd {tool_dir}")
    generate_dashboard_html_report(server_handle, session_id, log_dir)
    
    # Cmd to copy files with specific name pattern to tar file
    # tar_cmd = f"tar -cvzf yang_gnmi_validator_logs.tar -C {log_dir} --transform='s|^|yang_gnmi_validator_logs/|' $(find {log_dir} -maxdepth 1 -name 'openconfig*' -printf '%f ')"

    # Command to copy all files and dir from given dir => tar -cvzf yang_gnmi_validator_logs.tar -C new_logs --transform='s|^|yang_gnmi_validator_logs/|' .
    tar_cmd = f"tar -cvzf yang_gnmi_validator_logs.tar -C {log_dir} --transform='s|^|yang_gnmi_validator_logs/|' ."

    server_handle.shell(command = tar_cmd) 
    server_handle.download(local_file=f"{exec_log_dir}/yang_gnmi_validator_logs.tar", remote_file=f"{tool_dir}/yang_gnmi_validator_logs.tar")
    extract_cmd = f"tar -xvf {exec_log_dir}/yang_gnmi_validator_logs.tar -C {exec_log_dir}/"
    execute_shell_cmd(extract_cmd)
    execute_shell_cmd("rm -f {exec_log_dir}/yang_gnmi_validator_logs.tar")

