import time
import datetime
import pytest
import sys
import os
import shutil
import builtins
import json
import gc
import yaml
import pdb
import ipaddress
import random
import subprocess
from jnpr.toby.utils import utils
import jnpr.toby.hldcl.host as host_utils
import jnpr.toby.hldcl.device as device_utils
import jnpr.toby.hldcl.trafficgen.trafficgen as trafficgen
from jnpr.toby.utils.pytest_utils.utils import convert_to_list_arg
import jnpr.toby.utils.pytest_utils.datetime_utils as dt_utils
from jnpr.toby.utils.pytest_utils.datetime_utils import Date, Time
from jnpr.toby.utils.Vars import Vars

sys.path.append('/volume/systest-proj/PDT_LIBS/PAD/test-engine')
import TestEngine



def check_key_exists(key, dictionary, default=False):
    return key in dictionary if dictionary else default


def is_list(obj):
    return isinstance(obj, list)


def PDT_GET_RES_FROM_TAG_LIST(key_name, te_dict_te_args, **kwargs):
    self = kwargs.get('self', None)
    res_list = []
    if check_key_exists(key_name, te_dict_te_args, False):
        te_key_res_inc_list = te_dict_te_args[key_name]
        if is_list(te_key_res_inc_list):
            for tag in te_key_res_inc_list:
                node_list = testbed.get_junos_resources() if tag == 'all' else testbed.get_resource_list(tag=tag)
                res_list = list(set(res_list) | set(node_list))
                if tag == 'all':
                    break
    return res_list


def PDT_TE_Perform_Dict_Registration(key, te_key_dict, **kwargs):
    self = kwargs.get('self', None)
    te_dict_uv_args = te_key_dict['UV-ARGS']
    te_dict_te_args = te_key_dict['TE-ARGS']
    te_obj_list = te_dict_uv_args.get('te-ojects-to-register', [])
    resource_list = []

    # Handle resource inclusion/exclusion logic
    resource_list = update_resource_list(te_dict_te_args, resource_list, self)

    te_key_dict['TE-ARGS'].update({'resource': resource_list})
    for te_obj in te_obj_list:
        testbed.log(te_dict_te_args, display_log=True)
        if is_te_registered:
            setattr(self, f"{te_obj}_registered", 1)
            testbed.log(f"'level' = INFO", display_log=True)
        else:
            testbed.log(f"'level' = INFO", display_log=True)

    return is_te_registered


def update_resource_list(te_dict_te_args, resource_list, self):
    res_inc_list = PDT_GET_RES_FROM_TAG_LIST('resource_tag_include', te_dict_te_args, **{'self': self})
    resource_list = list(set(resource_list) | set(res_inc_list))
    res_exc_list = PDT_GET_RES_FROM_TAG_LIST('resource_tag_exclude', te_dict_te_args, **{'self': self})
    return list(set(resource_list) - set(res_exc_list))


def PDT_TE_Knob_Based_Dict_Registration(key, te_key_dict, **kwargs):
    self = kwargs.get('self', None)
    te_dict_uv_args = te_key_dict['UV-ARGS']
    params_knob_dict = te_dict_uv_args.get('params-knob-name', {})

    if not params_knob_dict:
        testbed.log(f"Level: WARN", display_log=True)
        return False

    is_result = check_knob_values(te_dict_uv_args, params_knob_dict)
    if not is_result:
        testbed.log(f"'level' = INFO", display_log=True)
        return False

    return PDT_TE_Perform_Dict_Registration(key, te_key_dict, **{'self': self})


def check_knob_values(te_dict_uv_args, params_knob_dict):
    is_result = True
    for knob, knob_value in params_knob_dict.items():
        is_knob_present = knob in t['user_variables']
        if not is_knob_present:
            testbed.log(f"'level' = WARN", display_log=True)
            return False

        knob_value_from_tv = tv.get('+knob+', 0)
        if str(knob_value_from_tv) != str(knob_value):
            is_result = False
    return is_result


def PDT_DM_GET_RES_FROM_TAG_LIST(key_name, te_dict_te_args, **kwargs):
    self = kwargs.get('self', None)
    res_list = []

    if check_key_exists(key_name, te_dict_te_args, False):
        te_key_res_inc_list = te_dict_te_args[key_name]
        if is_list(te_key_res_inc_list):
            for tag in te_key_res_inc_list:
                node_list = testbed.get_junos_resources() if tag == 'all' else testbed.get_resource_list(tag=tag)
                res_list = list(set(res_list) | set(node_list))
    return res_list


def PDT_TE_DM_Based_Dict_Registration(key, te_key_dict, **kwargs):
    self = kwargs.get('self', None)
    te_dict_uv_args = te_key_dict['UV-ARGS']
    te_dict_te_args = te_key_dict['TE-ARGS']
    te_obj_list = te_dict_uv_args.get('te-ojects-to-register', [])
    resource_list = update_resource_list(te_dict_te_args, resource_list, self)

    te_key_dict['TE-ARGS'].update({'resource': resource_list})
    for te_obj in te_obj_list:
        if is_te_registered:
            setattr(self, f"{te_obj}_registered", 1)
            testbed.log(f"'level' = INFO", display_log=True)
        else:
            testbed.log(f"'level' = WARN", display_log=True)

    return is_te_registered

def import_variables(file_path):
    try:
        with open(file_path, 'r') as file:
            data = yaml.safe_load(file)  # Loads YAML content as a Python dictionary
        return data
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        return None
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file '{file_path}': {e}")
        return None


def pdt_te_registration_processor(**kwargs):
    self = kwargs.get('self', None)
    testbed.log(f"'level' = INFO", display_log=True)

    if not check_key_exists('uv-te-yaml-file', t['user_variables'], False):
        testbed.log(f"'level' = ERROR", display_log=True)
        return

    if not os.path.exists(tv['uv-te-yaml-file']):
        testbed.log(f"'level' = ERROR", display_log=True)
        return

    
    TE_DATA = import_variables(tv['uv-te-yaml-file'])
    #pdb.set_trace()
    te_data_reg_dict = TE_DATA.get('TE_REGISTRATION_DATA', {})
    is_dm_enabled = TE_DATA.get('uv-dm-enable', 0)
    te_converge_itrs = tv.get('uv-te-converge-itrs', 60)
    self.te_converge_itrs = te_converge_itrs
    te_converge_interval = tv.get('uv-te-converge-interval', 5)
    self.te_converge_interval = te_converge_interval

    mand_keys_in_reg_data = ['UV-ARGS', 'TE-ARGS']
    mand_keys_in_uv_args = ['provision-registration', 'te-ojects-to-register']
    mand_keys_in_tv_args = ['trace', 'parameter', 'command', 'node', 'controller', 'dataformat']
    opt_keys_in_tv_args = ['resource_tag_include', 'resource']

    for key, te_key_dict in te_data_reg_dict.items():
        if not all(key in te_key_dict for key in mand_keys_in_reg_data):
            testbed.log(f"'level' = WARN", display_log=True)
            continue

        te_dict_uv_args = te_key_dict['UV-ARGS']
        if not all(key in te_dict_uv_args for key in mand_keys_in_uv_args):
            testbed.log(f"'level' = WARN", display_log=True)
            continue

        if te_dict_uv_args.get('provision-registration') == '0':
            testbed.log(f"'level' = INFO", display_log=True)
            continue

        # Register the TE objects based on different conditions
        if is_dm_enabled == '0':
            if te_dict_uv_args.get('params-knob-based-reg', '0') == '0':
                PDT_TE_Perform_Dict_Registration(key, te_key_dict, **{'self': self})
            else:
                PDT_TE_Knob_Based_Dict_Registration(key, te_key_dict, **{'self': self})
        else:
            if te_dict_uv_args.get('params-knob-based-reg', '0') == '0':
                PDT_TE_DM_Based_Dict_Registration(key, te_key_dict, **{'self': self})
            else:
                PDT_TE_DM_Knob_Based_Dict_Registration(key, te_key_dict, **{'self': self})

    return
