import time
import datetime
import re
import pytest
import sys
import copy
import os
import shutil
import builtins
import json
import pdb
import gc
import ipaddress
import random
import inspect
import subprocess
import jnpr.toby.utils.junos.system_time as system_time
import jnpr.toby.hldcl.host as host_utils
import jnpr.toby.hldcl.device as device_utils
from jnpr.toby.utils import utils
import jnpr.toby.hldcl.trafficgen.trafficgen as trafficgen
from jnpr.toby.utils.pytest_utils.utils import convert_to_list_arg
import jnpr.toby.utils.pytest_utils.datetime_utils as dt_utils
from jnpr.toby.utils.pytest_utils.datetime_utils import Date, Time, _SecsToTimestrHelper
from itertools import zip_longest
from jnpr.toby.utils.Vars import Vars
from jnpr.toby.utils.pytest_utils.pytest_utils import topology_init
from  LongevityTelemetry import LongevityTelemetry
topology_init()
#from PDT_LONGEVITY_LIB import *
from jnpr.jpytest import Jpytest

class Testlongevity_ipclos(Jpytest):
    @classmethod
    def setup_class(cls):
        self = cls
        try:
            testbed.log(f"Seting up...", display_log=True)
            testbed.toby_suite_setup()
        except Exception as e:
            testbed.log(f"Setup Failed {e}", display_log=True)
            cls.teardown_class(self)
            raise e
    @classmethod
    def teardown_class(self):
        builtins.TEST_STATUS = Vars().get_global_variable("TEST_STATUS")
        builtins.TEST_MESSAGE = 'Running test teardown'
        #self = cls    
        testbed.toby_suite_teardown()

    def setup_method(self, method):
        testbed.toby_test_setup() 
        
    def teardown_method(self, method):
        #pdb.set_trace()
        #te_longevity_stop()
        testbed.toby_test_teardown()
    
    def test_telemetry001(self):
        yang_gnmi_server = testbed.get_handle(resource='h0')
        hostname = tv.get(f"r2__re0__hostname")
        lng_tel = LongevityTelemetry(yang_gnmi_server,hostname) 
        #pdb.set_trace()
        lng_tel.run_oc_paths()
          
    def test_active_longevity(self):
        #builtins.TEST_NAME = inspect.currentframe().f_code.co_name
        longevity_test(test_type='Active', steady_state_keyword='Baseline Check',**{'self':self})

    #def test_passive_longevity(self):
    #    #builtins.TEST_NAME = inspect.currentframe().f_code.co_name
    #    longevity_test(test_type='Passive', steady_state_keyword='Baseline Check',**{'self':self})

    def __getattr__(self, name):
        # First, check in the instance's __dict__
        name = name.lower()
        if name in self.__dict__:
            return self.__dict__[name]

        # Then, check in the class's __dict__ (for class-level variables)
        if name in self.__class__.__dict__:
            return self.__class__.__dict__[name]

        # Then, check in globals()
        if name in globals():
            return globals()[name]

        # Then, check in locals()
        if name in locals():
            return locals()[name]

        # If the attribute is not found in any of the above, raise an AttributeError
        raise AttributeError(f"Attribute '{name}' not found!")

