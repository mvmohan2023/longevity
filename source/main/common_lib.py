from jnpr.toby.hldcl.host import upload_file
from jnpr.toby.hldcl.device import Device
from jnpr.toby.logger.logger import get_log_dir
import pdb

# Global Vars

test_root_dir = "/tmp/toby"
log_dir = "logs"
use_vir_env = False
local_vir_env_cmd = "source ~/test/bin/activate" # Will not be used in production - just for testing purpose
script_files_dir = "script_exec_files"
exec_log_dir = get_log_dir()


import subprocess
def generate_dashboard_html_report(server_handle, session_id, log_dir):
    cmd_prefix = "python Report_Generators/Intergated_Report_HTML/integrated_report.py --yaml validations.yaml"
    master_dashboard_file_name = f"master_dashboard_{session_id}.html"
    generate_integrated_report_cmd = f"{cmd_prefix} --dir {log_dir}/execute --output_dir {log_dir} --report_name {master_dashboard_file_name}"
    server_handle.shell(command = generate_integrated_report_cmd)
    server_handle.shell(command = "cp {log_dir}/{master_dashboard_file_name} /var/www/html/") # Copying to web server directory for easy access

def get_dir_and_file_from_path(path, return_value='file_name'):
  file_dir,file_name = path.rsplit("/", 1)
  if return_value == 'file_name':
      return file_name
  return file_dir, file_name

def execute_shell_cmd(cmd, out=subprocess.DEVNULL, err=subprocess.DEVNULL):
  subprocess.call(cmd,stdout=out, stderr=err,shell=True)

def git_setup(base_dir, server_handle):
    #pdb.set_trace()
    server_handle.shell(command = f"cd {base_dir}")
    server_handle.shell(command = 'git clone https://tester:x8buAGqcXNTD6xbQxfYe@ssd-git.juniper.net/manageability/api-publish.git')
    server_handle.shell(command = 'cd api-publish')
    server_handle.shell(command = 'git checkout beta')
    return

def write_env_file(env_content, platform_dict=None):
    import yaml
    env_content = dict(env_content)

    env_file_name = env_content.pop('env_file_tmp_name')
    local_env_file_name = f"{exec_log_dir}/{env_file_name}"
    if platform_dict is not None:
        env_content.update(platform_dict)

    with open(local_env_file_name, 'w+') as fh:
        yaml.dump(env_content, fh, default_flow_style=False, sort_keys=False)
    
    return local_env_file_name

def substitute_vars(input_file, tv):

    # Substitute all the variables inside the template and env files and create a substituted copy inside script log directory - later to be uploaded to yang-gnmi server
    import re

    # Load the YAML file
    with open(input_file, "r") as f:
        yaml_content = f.read()

    # Define your variables
    variables = tv

    # Replace placeholders with actual values
    def replace_var(match):
        var_name = match.group(1)
        return str(variables.get(var_name, match.group(0)))  # Default to original if not found
    
    updated_yaml = re.sub(r"\$\{([\w-]+)\}", replace_var, yaml_content)        
    file_name = get_dir_and_file_from_path(input_file)
    substituted_file = f"{exec_log_dir}/{file_name}"

    # Save the updated YAML
    with open(substituted_file, "w+") as f:
        f.write(updated_yaml)            
    
    return substituted_file