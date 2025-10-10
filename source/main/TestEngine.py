"""
Test Engine (TE) is an API for collecting data, taking snapshots, executing events
and measuring convergence.  It is 100% generic, fully threaded and highly flexible.
It is written using object oriented python and executable via Robot keywords.

The key advantages of TE are the following:

* all TE functions are coordinated
* data collection runs in user defined thread(s)
* event execution runs in user defined thread(s) in random or sequential order
* convergence measurements are collected across 1 or 1000+ parameters in milliseconds using local data
* convergence is measured individually for each registered parameter
* ME integration provides a graphical view of convergence
* convergence data can be used to make pass/fail decisions
* data can be stored in a database which allows min/max/avg/count/sum calculations
* convergence metadata is stored in a database for use by reporting tools like ARG and PARCH
"""
import atexit
import datetime
import json
import os
import pickle
import pprint
import random
import re
import sqlite3
import threading
import time
from collections import OrderedDict

import humanfriendly
import pandas as pd
from jnpr.toby.hldcl.device import Device
from jnpr.toby.hldcl.device import add_mode
from jnpr.toby.hldcl.device import close_device_handle as close
from jnpr.toby.hldcl.device import execute_cli_command_on_device as cli
from jnpr.toby.hldcl.device import execute_command_on_device
from jnpr.toby.hldcl.device import execute_config_command_on_device as config
from jnpr.toby.hldcl.device import execute_shell_command_on_device as shell
from jnpr.toby.hldcl.device import execute_vty_command_on_device as vty
from jnpr.toby.hldcl.device import get_host_name_for_device as get_hostname
from jnpr.toby.hldcl.device import reconnect_to_device as reconnect
from jnpr.toby.hldcl.device import set_current_controller as set_ctrl
from jnpr.toby.hldcl.device import switch_to_superuser as su
from jnpr.toby.logger.logger import get_log_dir
from jsonpath_rw import parse
from lxml import etree as et
from sqlalchemy import create_engine
import pdb

try:
    from robot.libraries.BuiltIn import BuiltIn
except Exception:
    ROBOT = False

te_parameters = {'event': {}}
te_parameters['event']['label'] = None
te_parameters['event']['timestamp'] = None
te_parameters['event']['date'] = None


def _get_me_object():
    if 'framework_variables' in t:
        if t['framework_variables'] is not None:
            if 'fv-monitoring-engine' in t['framework_variables']:
                try:
                    me_object = BuiltIn().get_library_instance('MonitoringEngine')
                    return me_object
                except:
                    return None


def _get_resource_set(include, exclude):
    resources = set()
    if include is not None:
        for tag in include:
            matches = t.get_resource_list(tag=tag)
            resources.update(matches)
    if exclude is not None:
        for tag in exclude:
            matches = t.get_resource_list(tag=tag)
            for match in matches:
                resources.discard(match)
    return resources


def _get_node_and_controller_from_tag(resource, tag):
    dev = t.get_handle(resource=resource)
    for mynode in dev.nodes.keys():
        for mycontroller in dev.nodes[mynode].controllers.keys():
            if 'fv-tags' in t['resources'][resource]['system'][mynode]['controllers'][mycontroller].keys():
                tags = t['resources'][resource]['system'][mynode]['controllers'][mycontroller]['fv-tags']
                taglist = tags.split(':')
                if tag in taglist:
                    message = "get_node_and_controller_from_tag resource {} mynode {} mycontroller {}".format(resource,
                                                                                                              mynode,
                                                                                                              mycontroller)
                    t.log(level='DEBUG', message='TE: {}'.format(message))
                    return mynode, mycontroller
    message = "get_node_and_controller_from_tag resource {} mynode None mycontroller None".format(resource)
    t.log(level='DEBUG', message='TE: {}'.format(message))
    return None, None


def test_engine_clear_event():
    """
    When the Data.converge keyword is called, test engine will verify and calculate the
    convergence times for all registered parameters within the Data object if a test engine
    event has been recorded previously within the current testcase. If a test engine event
    has not been recorded prior to the Data.converge call, only verification is done. Test
    engine records an event when any of the following are executed:

    * Event.execute
    * Event.start/wait/stop
    * Event.update (prior to or following the execution of arbitrary user code)

    Use Test Engine Clear Event to clear the event label and timestamp so that all subsequent
    calls to Data.converge only do verification and do not calculate convergence times.

    :rtype: None
    """
    global te_parameters
    message = "clearing event label and timestamp"
    t.log(level='INFO', message='TE: {}'.format(message))
    te_parameters['event']['label'] = None
    te_parameters['event']['timestamp'] = None
    te_parameters['event']['date'] = None


def test_engine_test_setup():
    """
    This keyword should always be called within the Test Setup of your test suite.

    :rtype: None
    """
    test_engine_clear_event()


def test_engine_test_teardown():
    """
    This keyword should always be called within the Test Teardown of your test suite.

    :rtype: None
    """
    global te_parameters


def _is_number(s):
    try:
        float(s)
        return True
    except:
        return False


def _is_humanfriendly(s):
    try:
        humanfriendly.parse_size(s)
        return True
    except:
        return False


class Data:
    """
    The TE Data class contains methods to manipulate Data objects.  To instantiate Data
    objects use the following Robot Library commands::

        Library  /volume/systest-proj/PDT_LIBS/PAD/test-engine/TestEngine.py
        Library  TestEngine.Data  name=baseline  WITH NAME  baseline
        Library  TestEngine.Data  name=mydata    WITH NAME  mydata
        Library  TestEngine.Data  name=mydata2   WITH NAME  mydata2

    Each Data object has an internal python dictionary that looks like this::

        {
          "resources":
            {
              "r0":
                {
                  "threads":
                    {
                      "default":
                        {
                          "interval": 1,
                          "object": None,
                          "running": None,
                          "traces":
                            {
                              "route-summary":
                                {
                                  "command": "show route summary",
                                  "controller": "re1",
                                  "dataformat": "xml",
                                  "mode": "cli",
                                  "node": "primary",
                                  "parameters":
                                    {
                                      "ipv4-total":
                                        {
                                          "converged": None,
                                          "convergence": None,
                                          "current": None,
                                          "database": True,
                                          "expression": None,
                                          "snapshot": None,
                                          "tolerance": 50,
                                          "xpath": '//route-table[table-name="inet.0"]/total-route-count',
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        }
    """

    @staticmethod
    def _strip_xml_namespace(xml_string):
        xmlstring = xml_string
        xmlstring = re.sub('\sxmlns[^"]+"[^"]+"', '', xmlstring).strip()
        xmlstring = re.sub('\sjunos:[^"]+"[^"]+"', '', xmlstring).strip()
        xml = et.fromstring(xmlstring).getchildren()[0]
        query = ".//*[namespace-uri()!='']"
        for ele in xml.xpath(query):
            ele.tag = et.QName(ele).localname
        et.cleanup_namespaces(xml)
        xmlstring = et.tostring(xml).decode().strip()
        xml = et.fromstring(xmlstring)
        return xml

    ROBOT_LIBRARY_SCOPE = 'GLOBAL'

    def __init__(self, name, interval=None):
        self.name = name
        self.running = False
        self.parameters = {}
        if interval is None:
            self.interval = 1
        else:
            self.interval = float(interval)
        self.global_log_level = 'INFO'
        self.device_log_level = 'OFF'
        self.start_time = None
        self.stop_time = None
        self.converged = None
        self.convergence = None
        self.snapshot_date = None
        self.snapshot_timestamp = None
        logdir = get_log_dir()
        self.datadir = "{}/data".format(logdir)
        os.makedirs(self.datadir, exist_ok=True)
        self.db_filename = "{}/te.db".format(self.datadir)
        atexit.register(self._cleanup)

    def set_logging_level(self, log_level):
        """
        Set the global and device log level for Data threads

        :param log_level: global and device log level
        :type log_level: 'CRITICAL' | 'ERROR' | 'WARNING' | 'INFO' | 'DEBUG' | 'NOTSET' | 'OFF'
        :rtype: bool

        ::

            baseline.set logging level  log_level=DEBUG
        """
        self.set_global_log_level(log_level)
        self.set_device_log_level(log_level)
        return True

    def set_global_log_level(self, log_level):
        """
        Set the global log level for Data threads

        :param log_level: global log level
        :type log_level: 'CRITICAL' | 'ERROR' | 'WARNING' | 'INFO' | 'DEBUG' | 'NOTSET' | 'OFF'
        :rtype: bool

        ::

            baseline.set global log level  log_level=DEBUG
        """
        self.global_log_level = log_level
        return True

    def set_device_log_level(self, log_level):
        """
        Set the device log level for Data threads

        :param log_level: device log level
        :type log_level: 'CRITICAL' | 'ERROR' | 'WARNING' | 'INFO' | 'DEBUG' | 'NOTSET' | 'OFF'
        :rtype: bool

        ::

            baseline.set device log level  log_level=DEBUG
        """
        self.device_log_level = log_level
        return True

    def _cleanup(self):
        if self.running:
            self.running = False
            timeout = self.interval + 300
            if 'resources' in self.parameters:
                for resource in self.parameters['resources'].keys():
                    if 'threads' in self.parameters['resources'][resource]:
                        for thread in self.parameters['resources'][resource]['threads'].keys():
                            thread_object = self.parameters['resources'][resource]['threads'][thread]['object']
                            if thread_object is not None:
                                thread_object.join(timeout=timeout)

    def dump(self):
        """
        Log the internal TE and Data dictionaries::

            baseline.dump
        """
        #pprint.pprint(te_parameters)
        #pprint.pprint(self.parameters)
        t.log(level='DEBUG', message='TE PARAMETERS: {}'.format(te_parameters))
        t.log(level='DEBUG', message='TE PARAMETERS: {}'.format(self.parameters))

    def register(self, trace, command, parameter, thread='default', dataformat='xml', mode='cli',
                 tolerance=5, interval=None, node=None, controller=None, regexp=None, xpath=None,
                 jsonpath=None, resource=None, resource_tag_include=None, resource_tag_exclude=None,
                 controller_tag=None, expression=None, database=False, custom_mode_name=None,
                 custom_mode_enter_command=None, custom_mode_exit_command=None, custom_mode_pattern=None, label=None,
                 tag=None, **kwargs):
        """
        Register data to be collected

        :param trace: command name
        :type trace: str
        :param command: command
        :type command: str
        :param parameter: command output name
        :type parameter: str
        :param thread: thread name
        :type thread: str
        :param dataformat: data format
        :type dataformat: 'text' | 'xml' | 'json'
        :param mode: command mode
        :type mode: 'cli' | 'shell' | 'root' | 'custom' | 'fpcX'
        :param tolerance: percentage above or below the snapshot value for convergence to pass
        :type tolerance: float
        :param interval: time delay between data collection iterations
        :type interval: float
        :param node: HA state of system node for command execution
        :type node: 'master' | 'backup'
        :param controller: HA state of controller for command execution
        :type controller: 'master' | 'backup'
        :param regexp: command output filter if dataformat is 'text'
        :type regexp: str
        :param xpath: command output filter if dataformat is 'xml'
        :type xpath: str
        :param jsonpath: command output filter if dataformat is 'json'
        :type jsonpath: str
        :param resource: resource name(s)
        :type resource: str, list(str)
        :param resource_tag_include: resource tags to match and include
        :type resource_tag_include: list(str)
        :param resource_tag_exclude: resource tags to match and exclude
        :type resource_tag_exclude: list(str)
        :param controller_tag: controller tag to match for command execution
        :type controller_tag: str
        :param expression: python expression to evaluate for convergence
        :type expression: str
        :param database: save data to the database
        :type database: bool
        :param custom_mode_name: custom mode name
        :type custom_mode_name: str
        :param custom_mode_enter_command: command used to enter the custom mode (e.g. 'cli-pfe', 'vty fpc3', etc)
        :type custom_mode_enter_command: str
        :param custom_mode_exit_command: command used to exit the custom mode (e.g. 'quit', 'exit', etc)
        :type custom_mode_exit_command: str
        :param custom_mode_pattern: pattern to match the prompt for the custom mode (e.g. '>')
        :type custom_mode_pattern: str
        :param label: text label to be stored in the database
        :type label: str
        :param tag: tag(s) to be stored in the database
        :type tag: str, list(str)
        :rtype: bool

        ::

            ${include}         Create List  blue
            ${exclude}         Create List  orange  indigo
            baseline.register  resource_tag_include=${include}  resource_tag_exclude=${exclude}
            ...                trace=route-summary  parameter=ipv4-total  tolerance=${2}
            ...                command=show route summary  dataformat=xml
            ...                xpath=//route-table[table-name="inet.0"]/total-route-count
        """
        if self.running:
            message = "cannot register data while {} object is running".format(self.name)
            t.log(level='WARN', message='TE: {}'.format(message))
            return False
        if node is not None:
            node = node.lower()
        if controller is not None:
            controller = controller.lower()
        states = ['master', 'backup', None]
        if node not in states or controller not in states:
            message = "{} data registration failed, node and controller must be master or backup".format(self.name)
            t.log(level='WARN', message='TE: {}'.format(message))
            t.log_console(level='WARN', message='TE: {}'.format(message))
            return False
        dataformats = ['text', 'xml', 'json']
        dataformat = dataformat.lower()
        if dataformat not in dataformats:
            message = "{} data registration failed, dataformat must be text, xml, or json".format(self.name)
            t.log(level='WARN', message='TE: {}'.format(message))
            t.log_console(level='WARN', message='TE: {}'.format(message))
            return False
        if dataformat == 'text':
            if regexp is None:
                message = "{} data registration failed, text requires regexp".format(self.name)
                t.log(level='WARN', message='TE: {}'.format(message))
                t.log_console(level='WARN', message='TE: {}'.format(message))
                return False
        if dataformat == 'xml':
            if xpath is None:
                message = "{} data registration failed, xml requires xpath".format(self.name)
                t.log(level='WARN', message='TE: {}'.format(message))
                t.log_console(level='WARN', message='TE: {}'.format(message))
                return False
        if dataformat == 'json':
            if jsonpath is None:
                message = "{} data registration failed, json requires jsonpath".format(self.name)
                t.log(level='WARN', message='TE: {}'.format(message))
                t.log_console(level='WARN', message='TE: {}'.format(message))
                return False
        if mode == 'custom':
            if custom_mode_name is None or custom_mode_enter_command is None or custom_mode_exit_command is None or custom_mode_pattern is None:
                message = "{} data registration failed, custom mode parameters not specified".format(self.name)
                t.log(level='WARN', message='TE: {}'.format(message))
                t.log_console(level='WARN', message='TE: {}'.format(message))
                return False
        tags = set()
        if isinstance(tag, list):
            tags.update(tag)
        else:
            if tag is not None:
                tags = {tag}
        resources = set()
        if isinstance(resource, list):
            resources.update(resource)
        else:
            if resource is not None:
                resources = {resource}
        added_resources = _get_resource_set(resource_tag_include, resource_tag_exclude)
        resources.update(added_resources)
        if len(resources) == 0:
            message = "{} data registration failed, no resources specified".format(self.name)
            t.log(level='WARN', message='TE: {}'.format(message))
            t.log_console(level='WARN', message='TE: {}'.format(message))
            return False
        if 'resources' in self.parameters:
            for myresource in self.parameters['resources'].keys():
                if myresource in resources:
                    if 'threads' in self.parameters['resources'][myresource]:
                        for mythread in self.parameters['resources'][myresource]['threads'].keys():
                            if mythread == thread:
                                if 'traces' in self.parameters['resources'][myresource]['threads'][mythread]:
                                    for mytrace in self.parameters['resources'][myresource]['threads'][mythread][
                                        'traces'].keys():
                                        if mytrace == trace:
                                            if 'dataformat' in \
                                                    self.parameters['resources'][myresource]['threads'][mythread][
                                                        'traces'][mytrace]:
                                                mydataformat = \
                                                    self.parameters['resources'][myresource]['threads'][mythread][
                                                        'traces'][mytrace]['dataformat']
                                                if mydataformat == 'text':
                                                    if regexp is None:
                                                        message = "{} data registration failed, dataformat/filter mismatch".format(
                                                            self.name)
                                                        t.log(level='WARN', message='TE: {}'.format(message))
                                                        return False
                                                elif mydataformat == 'xml':
                                                    if xpath is None:
                                                        message = "{} data registration failed, dataformat/filter mismatch".format(
                                                            self.name)
                                                        t.log(level='WARN', message='TE: {}'.format(message))
                                                        return False
                                                elif mydataformat == 'json':
                                                    if jsonpath is None:
                                                        message = "{} data registration failed, dataformat/filter mismatch".format(
                                                            self.name)
                                                        t.log(level='WARN', message='TE: {}'.format(message))
                                                        return False
        for resource in resources:
            if resource not in t['resources'].keys():
                message = "{} data registration failed for resource {}".format(self.name, resource)
                t.log(level='WARN', message='TE: {}'.format(message))
                t.log_console(level='WARN', message='TE: {}'.format(message))
                continue
            resource_node = node
            resource_controller = controller
            if controller_tag:
                mynode, mycontroller = _get_node_and_controller_from_tag(resource, controller_tag)
                if mynode is not None:
                    resource_node = mynode
                if mycontroller is not None:
                    resource_controller = mycontroller
            if 'resources' not in self.parameters.keys(): self.parameters['resources'] = {}
            if resource not in self.parameters['resources'].keys(): self.parameters['resources'][resource] = {}
            if 'threads' not in self.parameters['resources'][resource].keys(): self.parameters['resources'][resource][
                'threads'] = {}
            if thread not in self.parameters['resources'][resource]['threads'].keys():
                self.parameters['resources'][resource]['threads'][thread] = {}
                self.parameters['resources'][resource]['threads'][thread][
                    'interval'] = float(interval) if interval is not None else self.interval
                self.parameters['resources'][resource]['threads'][thread]['object'] = None
                self.parameters['resources'][resource]['threads'][thread]['running'] = None
                self.parameters['resources'][resource]['threads'][thread]['traces'] = {}
            if trace not in self.parameters['resources'][resource]['threads'][thread]['traces'].keys():
                self.parameters['resources'][resource]['threads'][thread]['traces'][trace] = {}
                self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'] = {}
                self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['node'] = None
                self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['controller'] = None
            if parameter not in self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                'parameters'].keys():
                self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][parameter] = {}
                self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][parameter][
                    'current'] = None
                self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][parameter][
                    'snapshot'] = None
                self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][parameter][
                    'tolerance'] = None
                self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][parameter][
                    'converged'] = None
                self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][parameter][
                    'convergence'] = None
                self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][parameter][
                    'expression'] = None
                self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][parameter][
                    'database'] = None
                self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][parameter][
                    'label'] = None
                self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][parameter][
                    'tag'] = None
            if dataformat == 'text':
                self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][parameter][
                    'regexp'] = regexp
            if dataformat == 'xml':
                self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][parameter][
                    'xpath'] = xpath
            if dataformat == 'json':
                self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][parameter][
                    'jsonpath'] = jsonpath
            self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['command'] = command
            self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['dataformat'] = dataformat
            self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['mode'] = mode
            if mode == 'custom':
                self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                    'custom_mode_name'] = custom_mode_name
                self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                    'custom_mode_enter_command'] = custom_mode_enter_command
                self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                    'custom_mode_exit_command'] = custom_mode_exit_command
                self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                    'custom_mode_pattern'] = custom_mode_pattern
            self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][parameter][
                'tolerance'] = tolerance
            if interval is not None: self.parameters['resources'][resource]['threads'][thread]['interval'] = float(
                interval)
            if resource_node is not None:
                self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['node'] = resource_node
            if resource_controller is not None:
                self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                    'controller'] = resource_controller
            self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][parameter][
                'expression'] = expression
            self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][parameter][
                'database'] = database
            if label is not None:
                self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][parameter][
                    'label'] = label
            if tag is not None:
                self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][parameter][
                    'tag'] = tags
        self.dump()
        return True

    def delete_parameter(self, trace, parameter, thread='default', resource=None, resource_tag_include=None,
                         resource_tag_exclude=None, **kwargs):
        """
        Delete a parameter

        :param trace: command name
        :type trace: str
        :param parameter: command output name
        :type parameter: str
        :param thread: thread name
        :type thread: str
        :param resource: resource name(s)
        :type resource: str, list(str)
        :param resource_tag_include: resource tags to match and include
        :type resource_tag_include: list(str)
        :param resource_tag_exclude: resource tags to match and exclude
        :type resource_tag_exclude: list(str)
        :rtype: bool

        ::

            ${include}  Create List  blue
            ${exclude}  Create List  orange  indigo
            baseline.delete parameter  resource_tag_include=${include}  resource_tag_exclude=${exclude}
            ...                        trace=route-summary  parameter=ipv4-total
            baseline.delete parameter  resource=r4  trace=route-summary  parameter=ipv4-total
        """
        if self.running:
            message = "cannot delete data while {} object is running".format(self.name)
            t.log(level='WARN', message='TE: {}'.format(message))
            return False
        resources = set()
        if isinstance(resource, list):
            resources.update(resource)
        else:
            if resource is not None:
                resources = {resource}
        added_resources = _get_resource_set(resource_tag_include, resource_tag_exclude)
        resources.update(added_resources)
        if len(resources) == 0:
            message = "{} delete parameter failed, no resources specified".format(self.name)
            t.log(level='WARN', message='TE: {}'.format(message))
            t.log_console(level='WARN', message='TE: {}'.format(message))
            return False
        for resource in resources:
            if resource in self.parameters['resources'].keys():
                if thread in self.parameters['resources'][resource]['threads'].keys():
                    if trace in self.parameters['resources'][resource]['threads'][thread]['traces'].keys():
                        if parameter in self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                            'parameters'].keys():
                            self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                                'parameters'].pop(parameter)
        self.dump()
        return True

    def delete_trace(self, trace, thread='default', resource=None, resource_tag_include=None,
                     resource_tag_exclude=None, **kwargs):
        """
        Delete a trace and all of its parameters

        :param trace: command name
        :type trace: str
        :param thread: thread name
        :type thread: str
        :param resource: resource name(s)
        :type resource: str, list(str)
        :param resource_tag_include: resource tags to match and include
        :type resource_tag_include: list(str)
        :param resource_tag_exclude: resource tags to match and exclude
        :type resource_tag_exclude: list(str)
        :rtype: bool

        ::

            ${include}  Create List  blue
            ${exclude}  Create List  orange  indigo
            baseline.delete trace  resource_tag_include=${include}  resource_tag_exclude=${exclude}
            ...                    trace=route-summary
            baseline.delete trace  resource=r4  trace=route-summary
        """
        if self.running:
            message = "cannot delete data while {} object is running".format(self.name)
            t.log(level='WARN', message='TE: {}'.format(message))
            return False
        resources = set()
        if isinstance(resource, list):
            resources.update(resource)
        else:
            if resource is not None:
                resources = {resource}
        added_resources = _get_resource_set(resource_tag_include, resource_tag_exclude)
        resources.update(added_resources)
        if len(resources) == 0:
            message = "{} delete trace failed, no resources specified".format(self.name)
            t.log(level='WARN', message='TE: {}'.format(message))
            t.log_console(level='WARN', message='TE: {}'.format(message))
            return False
        for resource in resources:
            if resource in self.parameters['resources'].keys():
                if thread in self.parameters['resources'][resource]['threads'].keys():
                    if trace in self.parameters['resources'][resource]['threads'][thread]['traces'].keys():
                        self.parameters['resources'][resource]['threads'][thread]['traces'].pop(trace)
        self.dump()
        return True

    def delete_thread(self, thread, resource=None, resource_tag_include=None, resource_tag_exclude=None, **kwargs):
        """
        Delete a thread and all of its traces and parameters

        :param thread: thread name
        :type thread: str
        :param resource: resource name(s)
        :type resource: str, list(str)
        :param resource_tag_include: resource tags to match and include
        :type resource_tag_include: list(str)
        :param resource_tag_exclude: resource tags to match and exclude
        :type resource_tag_exclude: list(str)
        :rtype: bool

        ::

            ${include}  Create List  blue
            ${exclude}  Create List  orange  indigo
            baseline.delete thread  resource_tag_include=${include}  resource_tag_exclude=${exclude}
            ...                     thread=default
            baseline.delete thread  resource=r4  thread=default
        """
        if self.running:
            message = "cannot delete data while {} object is running".format(self.name)
            t.log(level='WARN', message='TE: {}'.format(message))
            return False
        resources = set()
        if isinstance(resource, list):
            resources.update(resource)
        else:
            if resource is not None:
                resources = {resource}
        added_resources = _get_resource_set(resource_tag_include, resource_tag_exclude)
        resources.update(added_resources)
        if len(resources) == 0:
            message = "{} delete thread failed, no resources specified".format(self.name)
            t.log(level='WARN', message='TE: {}'.format(message))
            t.log_console(level='WARN', message='TE: {}'.format(message))
            return False
        for resource in resources:
            if resource in self.parameters['resources'].keys():
                if thread in self.parameters['resources'][resource]['threads'].keys():
                    self.parameters['resources'][resource]['threads'].pop(thread)
        self.dump()
        return True

    def delete_resource(self, resource=None, resource_tag_include=None, resource_tag_exclude=None, **kwargs):
        """
        Delete a resource and all of its threads, traces, and parameters

        :param resource: resource name(s)
        :type resource: str, list(str)
        :param resource_tag_include: resource tags to match and include
        :type resource_tag_include: list(str)
        :param resource_tag_exclude: resource tags to match and exclude
        :type resource_tag_exclude: list(str)
        :rtype: bool

        ::

            ${include}  Create List  blue
            ${exclude}  Create List  orange  indigo
            baseline.delete resource  resource_tag_include=${include}  resource_tag_exclude=${exclude}
            baseline.delete resource  resource=r4
        """
        if self.running:
            message = "cannot delete data while {} object is running".format(self.name)
            t.log(level='WARN', message='TE: {}'.format(message))
            return False
        resources = set()
        if isinstance(resource, list):
            resources.update(resource)
        else:
            if resource is not None:
                resources = {resource}
        added_resources = _get_resource_set(resource_tag_include, resource_tag_exclude)
        resources.update(added_resources)
        if len(resources) == 0:
            message = "{} delete resource failed, no resources specified".format(self.name)
            t.log(level='WARN', message='TE: {}'.format(message))
            t.log_console(level='WARN', message='TE: {}'.format(message))
            return False
        for resource in resources:
            if resource in self.parameters['resources'].keys():
                self.parameters['resources'].pop(resource)
        self.dump()
        return True

    def delete(self):
        """
        Delete all resources, threads, traces and parameters

        :rtype: bool

        ::

            baseline.delete
        """
        if self.running:
            message = "cannot delete data while {} object is running".format(self.name)
            t.log(level='WARN', message='TE: {}'.format(message))
            return False
        self.parameters = {}
        self.dump()
        return True

    def update(self, tolerance=None, expression=None, trace=None, parameter=None, resource=None,
               resource_tag_include=None, resource_tag_exclude=None, **kwargs):
        """
        Update the tolerance and/or expression for registered parameters

        :param tolerance: percentage above or below the snapshot value for convergence to pass
        :type tolerance: float
        :param expression: python expression to evaluate for convergence
        :type expression: str
        :param trace: command name
        :type trace: str
        :param parameter: command output name
        :type parameter: str
        :param resource: resource name(s)
        :type resource: str, list(str)
        :param resource_tag_include: resource tags to match and include
        :type resource_tag_include: list(str)
        :param resource_tag_exclude: resource tags to match and exclude
        :type resource_tag_exclude: list(str)
        :rtype: bool

        ::

            ${include}       Create List  blue
            ${exclude}       Create List  orange  indigo
            baseline.update  resource_tag_include=${include}  resource_tag_exclude=${exclude}
            ...              trace=route-summary  parameter=ipv4-total  tolerance=${10}
            ${expression}    Set Variable  current == snapshot
            baseline.update  resource=r4
            ...              trace=route-summary  parameter=ipv4-total  expression=${expression}
        """
        if tolerance is None and expression is None:
            message = "{} update failed, no tolerance or expression specified".format(self.name)
            t.log(level='WARN', message='TE: {}'.format(message))
            t.log_console(level='WARN', message='TE: {}'.format(message))
            return False
        resources = set()
        if isinstance(resource, list):
            resources.update(resource)
        else:
            if resource is not None:
                resources = {resource}
        added_resources = _get_resource_set(resource_tag_include, resource_tag_exclude)
        resources.update(added_resources)
        if len(resources) == 0:
            message = "{} update failed, no resources specified".format(self.name)
            t.log(level='WARN', message='TE: {}'.format(message))
            t.log_console(level='WARN', message='TE: {}'.format(message))
            return False
        for te_resource in self.parameters['resources'].keys():
            if te_resource not in resources:
                continue
            for te_thread in self.parameters['resources'][te_resource]['threads'].keys():
                for te_trace in self.parameters['resources'][te_resource]['threads'][te_thread]['traces'].keys():
                    if trace is not None:
                        if te_trace != trace:
                            continue
                    for te_parameter in \
                            self.parameters['resources'][te_resource]['threads'][te_thread]['traces'][te_trace][
                                'parameters'].keys():
                        if parameter is not None:
                            if te_parameter != parameter:
                                continue
                        if tolerance is not None:
                            self.parameters['resources'][te_resource]['threads'][te_thread]['traces'][te_trace][
                                'parameters'][te_parameter]['tolerance'] = tolerance
                        if expression is not None:
                            self.parameters['resources'][te_resource]['threads'][te_thread]['traces'][te_trace][
                                'parameters'][te_parameter]['expression'] = expression
        self.dump()
        return True

    def _save_snapshot(self):
        date = self.snapshot_date
        timestamp = self.snapshot_timestamp
        filename = "{}/{}_snapshot_{}.pickle".format(self.datadir, self.name, timestamp)
        file = open(filename, 'wb')
        snapshot_data = {'metadata': {}, 'resources': {}}
        for resource in self.parameters['resources'].keys():
            snapshot_data['resources'][resource] = {}
            snapshot_data['resources'][resource]['threads'] = {}
            for thread in self.parameters['resources'][resource]['threads'].keys():
                snapshot_data['resources'][resource]['threads'][thread] = {}
                snapshot_data['resources'][resource]['threads'][thread]['traces'] = {}
                for trace in self.parameters['resources'][resource]['threads'][thread]['traces'].keys():
                    snapshot_data['resources'][resource]['threads'][thread]['traces'][trace] = {}
                    snapshot_data['resources'][resource]['threads'][thread]['traces'][trace]['parameters'] = {}
                    for parameter in self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                        'parameters'].keys():
                        snapshot_data['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][
                            parameter] = {'snapshot': None, 'label': None, 'tag': None}
                        snapshot_data['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][
                            parameter]['snapshot'] = \
                            self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][
                                parameter]['snapshot']
                        snapshot_data['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][
                            parameter]['label'] = \
                            self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][
                                parameter]['label']
                        snapshot_data['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][
                            parameter]['tag'] = \
                            self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][
                                parameter]['tag']
        snapshot_data['metadata']['date'] = date
        snapshot_data['metadata']['timestamp'] = timestamp
        snapshot_data['metadata']['instance'] = self.name
        pickle.dump(snapshot_data, file)
        file.close()

    def snapshot(self, annotate=True):
        """
        Copy current value to snapshot value for all parameters

        :param annotate: add annotation to ME graphs
        :type annotate: bool
        :rtype: bool

        ::

            baseline.snapshot
        """
        date = datetime.datetime.now()
        timestamp = datetime.datetime.timestamp(date)
       
        for resource in self.parameters['resources'].keys():
            # hostname = t['resources'][resource]['system']['primary']['name']
            for thread in self.parameters['resources'][resource]['threads'].keys():
                for trace in self.parameters['resources'][resource]['threads'][thread]['traces'].keys():
                    for parameter in self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                        'parameters'].keys():
                        current = \
                            self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][
                                parameter]['current']
                        # if current is None:
                        #     for myresource in self.parameters['resources'].keys():
                        #         for mythread in self.parameters['resources'][myresource]['threads'].keys():
                        #             for mytrace in self.parameters['resources'][myresource]['threads'][mythread][
                        #                 'traces'].keys():
                        #                 for myparameter in \
                        #                         self.parameters['resources'][myresource]['threads'][mythread]['traces'][
                        #                             mytrace]['parameters'].keys():
                        #                     self.parameters['resources'][myresource]['threads'][mythread]['traces'][
                        #                         mytrace]['parameters'][myparameter]['snapshot'] = None
                        #     self.snapshot_timestamp = None
                        #     message = "{} snapshot failed {}/{} {} {} {} current value is None".format(self.name,
                        #                                                                                resource,
                        #                                                                                hostname, thread,
                        #                                                                                trace, parameter)
                        #     t.log(level='ERROR', message='TE: {}'.format(message))
                        #     t.log_console(level='ERROR', message='TE: {}'.format(message))
                        #     self.dump()
                        #     raise Exception('TE: {}'.format(message))
                        self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                            'parameters'][parameter]['snapshot'] = current
        message = "{} snapshot saved at {}".format(self.name, date)
        if annotate:
            me_object = _get_me_object()
            if me_object is not None:
                me_object.monitoring_engine_annotate(annotation='TE: {}'.format(message))
        t.log(level='INFO', message='TE: {}'.format(message))
        t.log_console(level='INFO', message='TE: {}'.format(message))
        self.snapshot_date = date
        self.snapshot_timestamp = timestamp
        self._save_snapshot()
        self.dump()
        return True

    def _insert_convergence_data(self):
        engine = create_engine("sqlite:///{}".format(self.db_filename))
        convergence_df = pd.DataFrame()
        event_label = te_parameters['event']['label']
        if event_label is None:
            message = "{} convergence data not updated, no event label set".format(self.name)
            t.log(level='INFO', message='TE: {}'.format(message))
            return
        event_timestamp = te_parameters['event']['timestamp']
        if event_timestamp is None:
            message = "{} convergence data not updated, no event timestamp set".format(self.name)
            t.log(level='INFO', message='TE: {}'.format(message))
            return
        event_date = te_parameters['event']['date']
        if event_date is None:
            message = "{} convergence data not updated, no event date set".format(self.name)
            t.log(level='INFO', message='TE: {}'.format(message))
            return
        for resource in self.parameters['resources'].keys():
            hostname = t['resources'][resource]['system']['primary']['name']
            for thread in self.parameters['resources'][resource]['threads'].keys():
                for trace in self.parameters['resources'][resource]['threads'][thread]['traces'].keys():
                    for parameter in self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                        'parameters'].keys():
                        convergence = \
                            self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][
                                parameter]['convergence']
                        expression = \
                            self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][
                                parameter]['expression']
                        tolerance = \
                            self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][
                                parameter]['tolerance']
                        label = \
                            self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][
                                parameter]['label']
                        tag = self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][
                            parameter]['tag']
                        if tag is not None:
                            tag = ":".join(tag)
                        df = pd.DataFrame(
                            [[self.name, event_label, event_timestamp, event_date, resource, hostname, trace, parameter,
                              convergence, expression, tolerance, label, tag]],
                            columns=['INSTANCE', 'EVENT_LABEL', 'EVENT_TIMESTAMP', 'EVENT_DATE', 'RESOURCE', 'HOSTNAME',
                                     'TRACE', 'PARAMETER', 'CONVERGENCE', 'EXPRESSION', 'TOLERANCE', 'LABEL', 'TAG'])
                        convergence_df = convergence_df.append(df)
        success = False
        for i in range(1, 11):
            try:
                message = "updating {} convergence data".format(self.name)
                t.log(level='INFO', message='TE: {}'.format(message))
                convergence_df.to_sql('convergence', engine, if_exists='append')
                success = True
                break
            except:
                message = "database error updating {} convergence data in attempt {}".format(self.name, i)
                t.log(level='WARN', message='TE: {}'.format(message))
                time.sleep(1)
        if not success:
            message = "{} convergence data update failed".format(self.name)
            t.log(level='WARN', message='TE: {}'.format(message))

    def converge(self, iterations=600, annotate=True, log_mod=1, expected_result=True, interval=None, **kwargs):
        """
        Check for convergence across all registered data parameters

        :param iterations: number of checks to execute
        :type iterations: int
        :param annotate: add annotation to ME graphs
        :type annotate: bool
        :param log_mod: only log for iterations that are divisible by log_mod
        :type log_mod: int
        :param expected_result: expected result for convergence
        :type expected_result: bool
        :param interval: time delay between convergence checking iterations
        :type interval: int
        :rtype: bool

        ::

            baseline.converge  iterations=${180}  expected_result=${false}  annotate=${false}
            baseline.converge  iterations=${3600}  log_mod=${10}
        """
        if not _is_number(iterations):
            raise Exception("TE: iterations not specified as a number")
        if interval is None:
            converge_interval = self.interval
        else:
            converge_interval = float(interval)
        # if self.snapshot_timestamp is None:
        #     raise Exception("TE: snapshot does not exist")
        for resource in self.parameters['resources'].keys():
            for thread in self.parameters['resources'][resource]['threads'].keys():
                for trace in self.parameters['resources'][resource]['threads'][thread]['traces'].keys():
                    for parameter in self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                        'parameters'].keys():
                        self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][
                            parameter]['converged'] = None
                        self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][
                            parameter]['convergence'] = None
        self.converged = None
        self.convergence = None
        message = "checking {} convergence".format(self.name)
        t.log(level='INFO', message='TE: {}'.format(message))
        iteration = 0
        converged = not expected_result
        event_label = te_parameters['event']['label']
        event_timestamp = te_parameters['event']['timestamp']
        while converged != expected_result:
            iteration += 1
            converged = True
            date = datetime.datetime.now()
            timestamp = datetime.datetime.timestamp(date)
            for resource in self.parameters['resources'].keys():
                hostname = t['resources'][resource]['system']['primary']['name']
                for thread in self.parameters['resources'][resource]['threads'].keys():
                    for trace in self.parameters['resources'][resource]['threads'][thread]['traces'].keys():
                        for parameter in self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                            'parameters'].keys():
                            current = self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                                'parameters'][parameter]['current']
                            # if current is None:
                            #     converged = False
                            #     self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                            #         'parameters'][parameter]['converged'] = None
                            #     self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                            #         'parameters'][parameter]['convergence'] = None
                            #     message = "{}/{} {} {} {} is None iteration {} of {}".format(
                            #         resource, hostname, thread, trace, parameter, iteration, iterations)
                            #     if iteration % log_mod == 0:
                            #         t.log(level='WARN', message='TE: {}'.format(message))
                            #         t.log_console(level='WARN', message='TE: {}'.format(message))
                            #     continue
                            snapshot = \
                                self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                                    'parameters'][parameter]['snapshot']
                            # if snapshot is None:
                            #     self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                            #         'parameters'][parameter]['converged'] = None
                            #     self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                            #         'parameters'][parameter]['convergence'] = None
                            #     message = "{}/{} {} {} {} snapshot is None".format(resource, hostname, thread, trace,
                            #                                                        parameter)
                            #     raise Exception('TE: {}'.format(message))
                            tolerance = self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                                'parameters'][parameter]['tolerance']
                            if isinstance(snapshot, list):
                                if len(snapshot) == 0:
                                    expression = 'snapshot == current'
                                elif _is_number(snapshot[0]):
                                    expression = '((100 - float(tolerance)) / 100) * snapshot <= current <= ((100 + float(tolerance)) / 100) * snapshot'
                                elif snapshot[0] is None or snapshot[0] == '':
                                    expression = 'snapshot == current'
                                else:
                                    expression = 'snapshot <= current'
                            elif _is_number(snapshot):
                                expression = '((100 - float(tolerance)) / 100) * snapshot <= current <= ((100 + float(tolerance)) / 100) * snapshot'
                            elif snapshot is None or snapshot == '':
                                expression = 'snapshot == current'
                            else:
                                expression = 'snapshot <= current'
                            if self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                                'parameters'][parameter]['expression'] is not None:
                                expression = self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                                    'parameters'][parameter]['expression']
                            status = True
                            snapshot_dependency = True
                            if "snapshot" not in expression:
                                snapshot_dependency = False
                            if snapshot_dependency:
                                if type(current) != type(snapshot):
                                    status = False
                                elif isinstance(current, list):
                                    if len(current) != len(snapshot):
                                        status = False
                                    else:
                                        currentlist = current
                                        snapshotlist = snapshot
                                        for item in range(len(currentlist)):
                                            current = currentlist[item]
                                            snapshot = snapshotlist[item]
                                            item_status = eval(expression)
                                            if not item_status:
                                                status = False
                                        current = \
                                            self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                                                'parameters'][parameter]['current']
                                        snapshot = \
                                            self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                                                'parameters'][parameter]['snapshot']
                                else:
                                    status = eval(expression)
                            else:
                                if isinstance(current, list):
                                    currentlist = current
                                    for item in range(len(currentlist)):
                                        current = currentlist[item]
                                        item_status = eval(expression)
                                        if not item_status:
                                            status = False
                                    current = \
                                        self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                                            'parameters'][parameter]['current']
                                else:
                                    status = eval(expression)
                            if not status:
                                converged = False
                                self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                                    'parameters'][parameter]['converged'] = None
                                self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                                    'parameters'][parameter]['convergence'] = None
                                if iteration % log_mod == 0:
                                    message = "{}/{} {} {} {} converging with snapshot {} current {} tolerance {} expression {} iteration {} of {}".format(
                                        resource, hostname, thread, trace, parameter, snapshot, current, tolerance,
                                        expression, iteration, iterations)
                                    t.log(level='INFO', message='TE: {}'.format(message))
                                    t.log_console(level='INFO', message='TE: {}'.format(message))
                            else:
                                if self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                                    'parameters'][parameter]['converged'] is None:
                                    self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                                        'parameters'][parameter]['converged'] = timestamp
                                    if event_timestamp is None:
                                        message = "{}/{} {} {} {} converged at {} with snapshot {} current {} tolerance {} expression {}".format(
                                            resource, hostname, thread, trace, parameter, date, snapshot, current,
                                            tolerance, expression)
                                    else:
                                        parameter_convergence_time = round((timestamp - event_timestamp), 1)
                                        self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                                            'parameters'][parameter]['convergence'] = parameter_convergence_time
                                        message = "{}/{} {} {} {} converged at {} with snapshot {} current {} tolerance {} expression {} in {}s after {}".format(
                                            resource, hostname, thread, trace, parameter, date, snapshot, current,
                                            tolerance, expression, parameter_convergence_time, event_label)
                                    t.log(level='INFO', message='TE: {}'.format(message))
                                    t.log_console(level='INFO', message='TE: {}'.format(message))
            if iteration == iterations or converged == expected_result:
                break
            time.sleep(converge_interval)
        date = datetime.datetime.now()
        end_timestamp = datetime.datetime.timestamp(date)
        if converged:
            if expected_result:
                self.converged = end_timestamp
                if event_timestamp is None:
                    message = "{} converged at {}".format(self.name, date)
                else:
                    global_convergence_time = round((end_timestamp - event_timestamp), 1)
                    message = "{} converged at {} in {}s after {}".format(self.name, date, global_convergence_time,
                                                                          event_label)
                    self.convergence = global_convergence_time
            else:
                message = "{} converged but expected result is false".format(self.name)
        else:
            message = "{} not converged at {}".format(self.name, date)
        if annotate:
            me_object = _get_me_object()
            if me_object is not None:
                me_object.monitoring_engine_annotate(annotation='TE: {}'.format(message))
        if converged != expected_result:
            t.log(level='ERROR', message='TE: {}'.format(message))
            t.log_console(level='ERROR', message='TE: {}'.format(message))
            if not converged:
                for resource in self.parameters['resources'].keys():
                    hostname = t['resources'][resource]['system']['primary']['name']
                    for thread in self.parameters['resources'][resource]['threads'].keys():
                        for trace in self.parameters['resources'][resource]['threads'][thread]['traces'].keys():
                            for parameter in self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                                'parameters'].keys():
                                is_converged = \
                                    self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                                        'parameters'][parameter]['converged']
                                if is_converged is None:
                                    failure_message = "{} {}/{} {} {} {} not converged at {}".format(self.name,
                                                                                                     resource, hostname,
                                                                                                     thread, trace,
                                                                                                     parameter, date)
                                    t.log(level='ERROR', message='TE: {}'.format(failure_message))
                                    t.log_console(level='ERROR', message='TE: {}'.format(failure_message))
        else:
            t.log(level='INFO', message='TE: {}'.format(message))
            t.log_console(level='INFO', message='TE: {}'.format(message))
        self.dump()
        if expected_result:
            self._insert_convergence_data()
        if converged != expected_result:
            raise Exception("TE: convergence result is not equal to expected result")
        return converged

    def get_parameter_convergence(self, resource, trace, parameter, thread='default', **kwargs):
        """
        Get the convergence time for a given parameter

        :param resource: resource name(s)
        :type resource: str, list(str)
        :param trace: command name
        :type trace: str
        :param parameter: command output name
        :type parameter: str
        :param thread: thread name
        :type thread: str
        :rtype: float, list(float)

        ::

            ${pc}  baseline.get parameter convergence  resource=r4  trace=route-summary
            ...    parameter=ipv4-total
        """
        parameter_convergence = None
        if resource in self.parameters['resources'].keys():
            if thread in self.parameters['resources'][resource]['threads'].keys():
                if trace in self.parameters['resources'][resource]['threads'][thread]['traces'].keys():
                    if parameter in self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                        'parameters'].keys():
                        parameter_convergence = \
                            self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                                'parameters'][parameter]['convergence']
        hostname = t['resources'][resource]['system']['primary']['name']
        message = "{} parameter convergence for {}/{} {} {} {} is {}s".format(
            self.name, resource, hostname, thread, trace, parameter, parameter_convergence)
        t.log(level='INFO', message='TE: {}'.format(message))
        return parameter_convergence

    def get_convergence(self):
        """
        Get the convergence time for the entire Data object

        :rtype: float

        ::

            ${gc}  baseline.get convergence
        """
        global_convergence = self.convergence
        if global_convergence is None:
            message = "{} convergence is None".format(self.name)
        else:
            message = "{} convergence is {}s".format(self.name, global_convergence)
        t.log(level='INFO', message='TE: {}'.format(message))
        return global_convergence

    def get_current_data(self, resource, trace, parameter, thread='default', **kwargs):
        """
        Get the current value for a given parameter

        :param resource: resource name(s)
        :type resource: str, list(str)
        :param trace: command name
        :type trace: str
        :param parameter: command output name
        :type parameter: str
        :param thread: thread name
        :type thread: str
        :rtype: float, list(float)

        ::

            ${current}  baseline.get current data  resource=r4  trace=route-summary  parameter=ipv4-total
        """
        current_data = None
        if resource in self.parameters['resources'].keys():
            if thread in self.parameters['resources'][resource]['threads'].keys():
                if trace in self.parameters['resources'][resource]['threads'][thread]['traces'].keys():
                    if parameter in self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                        'parameters'].keys():
                        current_data = self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                            'parameters'][parameter]['current']
        hostname = t['resources'][resource]['system']['primary']['name']
        message = "current data for {}/{} {} {} {} is {}".format(resource, hostname, thread,
                                                                 trace, parameter, current_data)
        t.log(level='INFO', message='TE: {}'.format(message))
        return current_data

    def get_snapshot_data(self, resource, trace, parameter, thread='default', **kwargs):
        """
        Get the snapshot value for a given parameter

        :param resource: resource name(s)
        :type resource: str, list(str)
        :param trace: command name
        :type trace: str
        :param parameter: command output name
        :type parameter: str
        :param thread: thread name
        :type thread: str
        :rtype: float, list(float)

        ::

            ${snapshot}  baseline.get snapshot data  resource=r4  trace=route-summary
            ...          parameter=ipv4-total
        """
        snapshot_data = None
        if resource in self.parameters['resources'].keys():
            if thread in self.parameters['resources'][resource]['threads'].keys():
                if trace in self.parameters['resources'][resource]['threads'][thread]['traces'].keys():
                    if parameter in self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                        'parameters'].keys():
                        snapshot_data = self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                            'parameters'][parameter]['snapshot']
        hostname = t['resources'][resource]['system']['primary']['name']
        message = "snapshot data for {}/{} {} {} {} is {}".format(resource, hostname, thread,
                                                                  trace, parameter, snapshot_data)
        t.log(level='INFO', message='TE: {}'.format(message))
        return snapshot_data

    def get_data(self):
        """
        Get the internal TE and Data dictionaries

        :rtype: dict, dict

        ::

            ${te}  ${data}  baseline.get data
        """
        return te_parameters, self.parameters

    def _start_data_thread(self, resource, thread):
        hostname = t['resources'][resource]['system']['primary']['name']
        sys = dict(t['resources'][resource]['system'])
        sys.pop('dh')
        global_log = True
        device_log = True
        global_log_level = str(self.global_log_level).upper()
        device_log_level = str(self.device_log_level).upper()
        if global_log_level == 'OFF':
            global_log = False
        if device_log_level == 'OFF':
            device_log = False
        message = "dev for resource {} thread {} starting".format(resource, thread)
        t.log_console(level='DEBUG', message='TE: {}'.format(message))
        try:
            dev = Device(system=sys, global_logger=global_log, device_logger=device_log)
        except:
            self.parameters['resources'][resource]['threads'][thread]['error'] = True
            raise
        message = "dev for resource {} thread {} started".format(resource, thread)
        t.log_console(level='DEBUG', message='TE: {}'.format(message))
        for node in dev.nodes.keys():
            for controller_name in dev.nodes[node].controllers.keys():
                if global_log_level != 'OFF':
                    dev.nodes[node].controllers[controller_name].global_logger.setLevel(global_log_level)
                if device_log_level != 'OFF':
                    dev.nodes[node].controllers[controller_name].device_logger.setLevel(device_log_level)
        engine = create_engine("sqlite:///{}".format(self.db_filename))
        while self.running:
            interval = self.parameters['resources'][resource]['threads'][thread]['interval']
            for trace in self.parameters['resources'][resource]['threads'][thread]['traces'].keys():
                command = self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['command']
                mode = self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['mode']
                dataformat = self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['dataformat']
                if dataformat == 'xml':
                    command = command + ' | display xml'
                elif dataformat == 'json':
                    command = command + ' | display json'
                node = self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['node']
                controller = self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['controller']
                if node or controller:
                    if not node:
                        node = 'master'
                    if not controller:
                        controller = 'master'
                    nodes = len(dev.nodes.keys())
                    try:
                        if nodes == 1:
                            for mynode in dev.nodes.keys():
                                set_ctrl(device=dev, system_node=mynode, controller=controller)
                        elif nodes > 1:
                            set_ctrl(device=dev, system_node=node, controller=controller)
                    except:
                        message = "{} cannot set node {} and controller {} on {}/{}".format(self.name, node, controller,
                                                                                            resource, hostname)
                        t.log(level='INFO', message='TE: {}'.format(message))
                        for parameter in self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                            'parameters'].keys():
                            self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][
                                parameter]['current'] = None
                        continue
                if mode.lower() == 'cli':
                    try:
                        result = cli(device=dev, command=command)
                    except:
                        message = "no result for cli command {} on {}/{}".format(command, resource, hostname)
                        t.log(level='INFO', message='TE: {}'.format(message))
                        for parameter in self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                            'parameters'].keys():
                            self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][
                                parameter]['current'] = None
                        try:
                            message = "reconnecting to {}/{}".format(resource, hostname)
                            t.log(level='INFO', message='TE: {}'.format(message))
                            reconnect(device=dev, interval=interval)
                            message = "reconnected to {}/{}".format(resource, hostname)
                            t.log(level='INFO', message='TE: {}'.format(message))
                            continue
                        except:
                            message = "reconnect to {}/{} failed".format(resource, hostname)
                            t.log(level='ERROR', message='TE: {}'.format(message))
                            return
                elif mode.lower() == 'shell':
                    try:
                        result = shell(device=dev, command=command)
                    except:
                        message = "no result for shell command {} on {}/{}".format(command, resource, hostname)
                        t.log(level='INFO', message='TE: {}'.format(message))
                        for parameter in self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                            'parameters'].keys():
                            self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][
                                parameter]['current'] = None
                        try:
                            message = "reconnecting to {}/{}".format(resource, hostname)
                            t.log(level='INFO', message='TE: {}'.format(message))
                            reconnect(device=dev, interval=interval)
                            message = "reconnected to {}/{}".format(resource, hostname)
                            t.log(level='INFO', message='TE: {}'.format(message))
                            continue
                        except:
                            message = "reconnect to {}/{} failed".format(resource, hostname)
                            t.log(level='ERROR', message='TE: {}'.format(message))
                            return
                elif mode.lower() == 'root':
                    try:
                        su(device=dev)
                        result = shell(device=dev, command=command)
                    except:
                        message = "no result for root command {} on {}/{}".format(command, resource, hostname)
                        t.log(level='INFO', message='TE: {}'.format(message))
                        for parameter in self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                            'parameters'].keys():
                            self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][
                                parameter]['current'] = None
                        try:
                            message = "reconnecting to {}/{}".format(resource, hostname)
                            t.log(level='INFO', message='TE: {}'.format(message))
                            reconnect(device=dev, interval=interval)
                            message = "reconnected to {}/{}".format(resource, hostname)
                            t.log(level='INFO', message='TE: {}'.format(message))
                            continue
                        except:
                            message = "reconnect to {}/{} failed".format(resource, hostname)
                            t.log(level='ERROR', message='TE: {}'.format(message))
                            return
                elif mode.lower() == 'custom':
                    try:
                        custom_mode_name = self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                            'custom_mode_name']
                        custom_mode_enter_command = \
                            self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                                'custom_mode_enter_command']
                        custom_mode_exit_command = \
                            self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                                'custom_mode_exit_command']
                        custom_mode_pattern = \
                            self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                                'custom_mode_pattern']
                        if custom_mode_name not in dev.current_node.current_controller.custom_modes:
                            add_mode(device=dev,
                                     mode=custom_mode_name,
                                     command=custom_mode_enter_command,
                                     exit_command=custom_mode_exit_command,
                                     pattern=custom_mode_pattern)
                        result = execute_command_on_device(device=dev, mode=custom_mode_name, command=command)
                    except:
                        message = "no result for custom command {} on {}/{}".format(command, resource, hostname)
                        t.log(level='INFO', message='TE: {}'.format(message))
                        for parameter in self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                            'parameters'].keys():
                            self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][
                                parameter]['current'] = None
                        try:
                            message = "reconnecting to {}/{}".format(resource, hostname)
                            t.log(level='INFO', message='TE: {}'.format(message))
                            reconnect(device=dev, interval=interval)
                            message = "reconnected to {}/{}".format(resource, hostname)
                            t.log(level='INFO', message='TE: {}'.format(message))
                            continue
                        except:
                            message = "reconnect to {}/{} failed".format(resource, hostname)
                            t.log(level='ERROR', message='TE: {}'.format(message))
                            return
                else:
                    try:
                        result = vty(device=dev, command=command, destination=mode)
                    except:
                        message = "no result for vty command {} on {}/{}".format(command, resource, hostname)
                        t.log(level='INFO', message='TE: {}'.format(message))
                        for parameter in self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                            'parameters'].keys():
                            self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][
                                parameter]['current'] = None
                        try:
                            message = "reconnecting to {}/{}".format(resource, hostname)
                            t.log(level='INFO', message='TE: {}'.format(message))
                            reconnect(device=dev, interval=interval)
                            message = "reconnected to {}/{}".format(resource, hostname)
                            t.log(level='INFO', message='TE: {}'.format(message))
                            continue
                        except:
                            message = "reconnect to {}/{} failed".format(resource, hostname)
                            t.log(level='ERROR', message='TE: {}'.format(message))
                            return
                if result is None:
                    message = "result is None for command {} on {}/{}".format(command, resource, hostname)
                    t.log(level='INFO', message='TE: {}'.format(message))
                    for parameter in self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                        'parameters'].keys():
                        self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][
                            parameter]['current'] = None
                    continue
                for parameter in self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                    'parameters'].keys():
                    database = \
                        self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][
                            parameter][
                            'database']
                    if dataformat == 'text':
                        regexp = \
                            self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][
                                parameter]['regexp']
                        filtered_result = re.findall(regexp, result)
                        # if not filtered_result:
                        #     message = "no filtered result for command {} regexp {} on {}/{}".format(command, regexp,
                        #                                                                             resource, hostname)
                        #     t.log(level='WARN', message='TE: {}'.format(message))
                        #     self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][
                        #         parameter]['current'] = None
                        #     continue
                        processed_result = [i[0] if isinstance(i, tuple) else i for i in filtered_result]
                        results = []
                        result_df = pd.DataFrame()
                        for item in processed_result:
                            is_num = _is_number(item)
                            is_human = _is_humanfriendly(item)
                            is_string = isinstance(item, str)
                            if is_string:
                                if is_human:
                                    te_result = float(humanfriendly.parse_size(item))
                                else:
                                    te_result = item
                            elif is_num:
                                te_result = float(item)
                            else:
                                message = "non valid result {} for command {} regexp {} on {}/{}".format(
                                    item, command, regexp, resource, hostname)
                                t.log(level='INFO', message='TE: {}'.format(message))
                                self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                                    'parameters'][parameter]['current'] = None
                                continue
                            try:
                                if database and is_num:
                                    date = datetime.datetime.now()
                                    redf = pd.DataFrame(
                                        [[self.name, resource, hostname, command, regexp, te_result, date, trace,
                                          parameter]],
                                        columns=['INSTANCE', 'RESOURCE', 'HOSTNAME', 'COMMAND', 'FILTER', 'DATA',
                                                 'DATETIME', 'TRACE', 'PARAMETER'])
                                    result_df = result_df.append(redf)
                            except:
                                message = "dataframe error for command {} regexp {} on {}/{} with result {}".format(
                                    command, regexp, resource, hostname, te_result)
                                t.log(level='INFO', message='TE: {}'.format(message))
                            results.append(te_result)
                        try:
                            if database and (len(result_df.index) > 0):
                                result_df.to_sql('data', engine, if_exists='append')
                        except:
                            message = "database error for command {} regexp {} on {}/{}".format(
                                command, regexp, resource, hostname)
                            t.log(level='INFO', message='TE: {}'.format(message))
                        if len(results) >= 1:
                            self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][
                                parameter]['current'] = results
                    elif dataformat == 'xml':
                        xpath = \
                            self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][
                                parameter]['xpath']
                        try:
                            result_object = self._strip_xml_namespace(result)
                        except:
                            message = "error stripping namespace for command {} xpath {} on {}/{}".format(command,
                                                                                                          xpath,
                                                                                                          resource,
                                                                                                          hostname)
                            t.log(level='INFO', message='TE: {}'.format(message))
                            self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][
                                parameter]['current'] = None
                            continue
                        if result_object is None:
                            message = "no response for command {} xpath {} on {}/{}".format(command,
                                                                                            xpath, resource,
                                                                                            hostname)
                            t.log(level='INFO', message='TE: {}'.format(message))
                            self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][
                                parameter]['current'] = None
                            continue
                        try:
                            filtered_result = result_object.xpath(xpath)
                        except:
                            message = "xpath error for command {} xpath {} on {}/{}".format(command,
                                                                                            xpath, resource,
                                                                                            hostname)
                            t.log(level='INFO', message='TE: {}'.format(message))
                            self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][
                                parameter]['current'] = None
                            continue
                        # if not filtered_result:
                        #     message = "no result for command {} xpath {} on {}/{}".format(command,
                        #                                                                   xpath, resource,
                        #                                                                   hostname)
                        #     t.log(level='WARN', message='TE: {}'.format(message))
                        #     self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][
                        #         parameter]['current'] = None
                        #     continue
                        results = []
                        if isinstance(filtered_result, list):
                            result_df = pd.DataFrame()
                            for item in filtered_result:
                                is_num = _is_number(item.text)
                                is_human = _is_humanfriendly(item.text)
                                is_string = isinstance(item.text, str)
                                if is_string:
                                    if is_human:
                                        te_result = float(humanfriendly.parse_size(item.text))
                                    else:
                                        te_result = item.text
                                elif is_num:
                                    te_result = float(item.text)
                                else:
                                    message = "non valid result {} for command {} xpath {} on {}/{}".format(
                                        item.text, command, xpath, resource, hostname)
                                    t.log(level='INFO', message='TE: {}'.format(message))
                                    self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                                        'parameters'][parameter]['current'] = None
                                    continue
                                try:
                                    if database and is_num:
                                        date = datetime.datetime.now()
                                        redf = pd.DataFrame(
                                            [[self.name, resource, hostname, command, xpath, te_result, date, trace,
                                              parameter]],
                                            columns=['INSTANCE', 'RESOURCE', 'HOSTNAME', 'COMMAND', 'FILTER', 'DATA',
                                                     'DATETIME', 'TRACE', 'PARAMETER'])
                                        result_df = result_df.append(redf)
                                except:
                                    message = "dataframe error for command {} xpath {} on {}/{} with list result {}".format(
                                        command, xpath, resource, hostname, te_result)
                                    t.log(level='INFO', message='TE: {}'.format(message))
                                results.append(te_result)
                            try:
                                if database and (len(result_df.index) > 0):
                                    result_df.to_sql('data', engine, if_exists='append')
                            except:
                                message = "database error for command {} xpath {} on {}/{}".format(
                                    command, xpath, resource, hostname)
                                t.log(level='INFO', message='TE: {}'.format(message))
                        else:
                            is_num = _is_number(filtered_result)
                            is_human = _is_humanfriendly(filtered_result)
                            is_string = isinstance(filtered_result, str)
                            if is_string:
                                if is_human:
                                    te_result = float(humanfriendly.parse_size(filtered_result))
                                else:
                                    te_result = filtered_result
                            elif is_num:
                                te_result = float(filtered_result)
                            else:
                                message = "non valid result {} for command {} xpath {} on {}/{}".format(
                                    filtered_result, command, xpath, resource, hostname)
                                t.log(level='INFO', message='TE: {}'.format(message))
                                self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                                    'parameters'][parameter]['current'] = None
                                continue
                            try:
                                if database and is_num:
                                    date = datetime.datetime.now()
                                    redf = pd.DataFrame(
                                        [[self.name, resource, hostname, command, xpath, te_result, date, trace,
                                          parameter]],
                                        columns=['INSTANCE', 'RESOURCE', 'HOSTNAME', 'COMMAND', 'FILTER', 'DATA',
                                                 'DATETIME',
                                                 'TRACE', 'PARAMETER'])
                                    redf.to_sql('data', engine, if_exists='append')
                            except:
                                message = "database error for command {} xpath {} on {}/{} with result {}".format(
                                    command, xpath, resource, hostname, te_result)
                                t.log(level='INFO', message='TE: {}'.format(message))
                            results.append(te_result)
                        if len(results) == 1:
                            self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][
                                parameter]['current'] = results[0]
                        elif len(results) > 1:
                            self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][
                                parameter]['current'] = results
                    elif dataformat == 'json':
                        jsonpath = \
                            self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][
                                parameter]['jsonpath']
                        try:
                            jsonpath_expr = parse(jsonpath)
                        except:
                            message = "error parsing jsonpath {} for parameter {} on {}/{}".format(jsonpath, parameter,
                                                                                                   resource, hostname)
                            t.log(level='INFO', message='TE: {}'.format(message))
                            self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                                'parameters'][parameter]['current'] = None
                            continue
                        try:
                            json_data = json.loads(result)
                        except:
                            message = "error loading JSON data for parameter {} on {}/{}".format(parameter, resource,
                                                                                                 hostname)
                            t.log(level='INFO', message='TE: {}'.format(message))
                            self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                                'parameters'][parameter]['current'] = None
                            continue
                        try:
                            matches = jsonpath_expr.find(json_data)
                        except:
                            message = "error finding JSON data for parameter {} on {}/{}".format(parameter, resource,
                                                                                                 hostname)
                            t.log(level='INFO', message='TE: {}'.format(message))
                            self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                                'parameters'][parameter]['current'] = None
                            continue
                        if not matches:
                            message = "no matches for command {} jsonpath {} on {}/{}".format(command, jsonpath,
                                                                                              resource, hostname)
                            t.log(level='INFO', message='TE: {}'.format(message))
                            self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][
                                parameter]['current'] = None
                            continue
                        results = []
                        result_df = pd.DataFrame()
                        for item in matches:
                            is_num = _is_number(item.value)
                            is_human = _is_humanfriendly(item.value)
                            is_string = isinstance(item.value, str)
                            if is_string:
                                if is_human:
                                    te_result = float(humanfriendly.parse_size(item.value))
                                else:
                                    te_result = item.value
                            elif is_num:
                                te_result = float(item.value)
                            else:
                                message = "non valid result {} for command {} jsonpath {} on {}/{}".format(
                                    item, command, jsonpath, resource, hostname)
                                t.log(level='INFO', message='TE: {}'.format(message))
                                self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                                    'parameters'][parameter]['current'] = None
                                continue
                            try:
                                if database and is_num:
                                    date = datetime.datetime.now()
                                    redf = pd.DataFrame(
                                        [[self.name, resource, hostname, command, jsonpath, te_result, date, trace,
                                          parameter]],
                                        columns=['INSTANCE', 'RESOURCE', 'HOSTNAME', 'COMMAND', 'FILTER', 'DATA',
                                                 'DATETIME', 'TRACE', 'PARAMETER'])
                                    result_df = result_df.append(redf)
                            except:
                                message = "dataframe error for command {} jsonpath {} on {}/{} with result {}".format(
                                    command, jsonpath, resource, hostname, te_result)
                                t.log(level='INFO', message='TE: {}'.format(message))
                            results.append(te_result)
                        try:
                            if database and (len(result_df.index) > 0):
                                result_df.to_sql('data', engine, if_exists='append')
                        except:
                            message = "database error for command {} jsonpath {} on {}/{}".format(
                                command, jsonpath, resource, hostname)
                            t.log(level='INFO', message='TE: {}'.format(message))
                        if len(results) >= 1:
                            self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][
                                parameter]['current'] = results
            self.parameters['resources'][resource]['threads'][thread]['running'] = True
            time.sleep(interval)
        self.parameters['resources'][resource]['threads'][thread]['running'] = False
        close(device=dev)

    def start(self):
        """
        Start data collection

        :rtype: bool

        ::

            baseline.start
        """
        date = datetime.datetime.now()
        message = "{} data collection starting at {}".format(self.name, date)
        t.log(level='INFO', message='TE: {}'.format(message))
        t.log_console(level='INFO', message='TE: {}'.format(message))
        if not self.running:
            self.running = True
        else:
            message = "{} data collection already started".format(self.name)
            t.log(level='INFO', message='TE: {}'.format(message))
            t.log_console(level='INFO', message='TE: {}'.format(message))
            return True
        if 'resources' not in self.parameters:
            raise Exception("TE: data object not started, no resources registered")
        for resource in self.parameters['resources'].keys():
            osname = t['resources'][resource]['system']['primary']['osname']
            if osname.lower() != 'junos': continue
            name = t['resources'][resource]['system']['primary']['name']
            for thread in self.parameters['resources'][resource]['threads'].keys():
                thread_object = threading.Thread(target=self._start_data_thread, args=(resource, thread))
                threadname = self.name + "_" + resource + "_" + name + "_" + thread
                thread_object.name = threadname
                thread_object.daemon = True
                thread_object.start()
                self.parameters['resources'][resource]['threads'][thread]['object'] = thread_object
        for resource in self.parameters['resources'].keys():
            for thread in self.parameters['resources'][resource]['threads'].keys():
                while not self.parameters['resources'][resource]['threads'][thread]['running']:
                    if 'error' in self.parameters['resources'][resource]['threads'][thread].keys():
                        raise Exception("Device error raised")
                    time.sleep(1)
        date = datetime.datetime.now()
        timestamp = datetime.datetime.timestamp(date)
        self.start_time = timestamp
        message = "{} data collection started at {}".format(self.name, date)
        t.log(level='INFO', message='TE: {}'.format(message))
        t.log_console(level='INFO', message='TE: {}'.format(message))
        #self.dump()
        return True

    def stop(self):
        """
        Stop data collection

        :rtype: bool

        ::

            baseline.stop
        """
        date = datetime.datetime.now()
        message = "{} data collection stopping at {}".format(self.name, date)
        t.log(level='INFO', message='TE: {}'.format(message))
        t.log_console(level='INFO', message='TE: {}'.format(message))
        self.running = False
        if 'resources' in self.parameters.keys():
            for resource in self.parameters['resources'].keys():
                for thread in self.parameters['resources'][resource]['threads'].keys():
                    interval = self.parameters['resources'][resource]['threads'][thread]['interval']
                    timeout = interval + 3600
                    thread_object = self.parameters['resources'][resource]['threads'][thread]['object']
                    if thread_object is not None:
                        thread_object.join(timeout=timeout)
                        if thread_object.is_alive():
                            message = "{} resource {} thread {} timed out after {} sec".format(self.name, resource,
                                                                                               thread, timeout)
                            t.log(level='ERROR', message='TE: {}'.format(message))
                            t.log_console(level='ERROR', message='TE: {}'.format(message))
                        self.parameters['resources'][resource]['threads'][thread]['object'] = None
                    for trace in self.parameters['resources'][resource]['threads'][thread]['traces'].keys():
                        for parameter in self.parameters['resources'][resource]['threads'][thread]['traces'][trace][
                            'parameters'].keys():
                            self.parameters['resources'][resource]['threads'][thread]['traces'][trace]['parameters'][
                                parameter]['current'] = None
        date = datetime.datetime.now()
        timestamp = datetime.datetime.timestamp(date)
        self.stop_time = timestamp
        message = "{} data collection stopped at {}".format(self.name, date)
        t.log(level='INFO', message='TE: {}'.format(message))
        t.log_console(level='INFO', message='TE: {}'.format(message))
        #self.dump()
        return True

    def min(self, trace, parameter, resource=None, **kwargs):
        """
        Get the minimum value for a given parameter

        :param trace: command name
        :type trace: str
        :param parameter: command output name
        :type parameter: str
        :param resource: resource name(s)
        :type resource: str, list(str)
        :rtype: float

        ::

            ${min}  baseline.min  resource=r4  trace=route-summary  parameter=ipv4-total
            ${min}  baseline.min  trace=route-summary  parameter=ipv4-total
        """
        database = sqlite3.connect(self.db_filename)
        sql = 'select min(DATA) from data where instance="{}" and trace="{}" and parameter="{}"'.format(self.name,
                                                                                                        trace,
                                                                                                        parameter)
        if resource is not None:
            add = ' and resource="{}"'.format(resource)
            sql = sql + add
        df = pd.read_sql_query(sql, database)
        result = round((df.iloc[0]['min(DATA)']), 1)
        if resource is not None:
            hostname = t['resources'][resource]['system']['primary']['name']
            message = "minimum for {}/{} {} {} is {}".format(resource, hostname, trace, parameter, result)
        else:
            message = "minimum for {} {} is {}".format(trace, parameter, result)
        t.log(level='INFO', message='TE: {}'.format(message))
        return result

    def max(self, trace, parameter, resource=None, **kwargs):
        """
        Get the maximum value for a given parameter

        :param trace: command name
        :type trace: str
        :param parameter: command output name
        :type parameter: str
        :param resource: resource name(s)
        :type resource: str, list(str)
        :rtype: float

        ::

            ${max}  baseline.max  resource=r4  trace=route-summary  parameter=ipv4-total
            ${max}  baseline.max  trace=route-summary  parameter=ipv4-total
        """
        database = sqlite3.connect(self.db_filename)
        sql = 'select max(DATA) from data where instance="{}" and trace="{}" and parameter="{}"'.format(self.name,
                                                                                                        trace,
                                                                                                        parameter)
        if resource is not None:
            add = ' and resource="{}"'.format(resource)
            sql = sql + add
        df = pd.read_sql_query(sql, database)
        result = round((df.iloc[0]['max(DATA)']), 1)
        if resource is not None:
            hostname = t['resources'][resource]['system']['primary']['name']
            message = "maximum for {}/{} {} {} is {}".format(resource, hostname, trace, parameter, result)
        else:
            message = "maximum for {} {} is {}".format(trace, parameter, result)
        t.log(level='INFO', message='TE: {}'.format(message))
        return result

    def avg(self, trace, parameter, resource=None, **kwargs):
        """
        Get the average value for a given parameter

        :param trace: command name
        :type trace: str
        :param parameter: command output name
        :type parameter: str
        :param resource: resource name
        :type resource: str
        :rtype: float

        ::

            ${avg}  baseline.avg  resource=r4  trace=route-summary  parameter=ipv4-total
            ${avg}  baseline.avg  trace=route-summary  parameter=ipv4-total
        """
        database = sqlite3.connect(self.db_filename)
        sql = 'select avg(DATA) from data where instance="{}" and trace="{}" and parameter="{}"'.format(self.name,
                                                                                                        trace,
                                                                                                        parameter)
        if resource is not None:
            add = ' and resource="{}"'.format(resource)
            sql = sql + add
        df = pd.read_sql_query(sql, database)
        result = round((df.iloc[0]['avg(DATA)']), 1)
        if resource is not None:
            hostname = t['resources'][resource]['system']['primary']['name']
            message = "average for {}/{} {} {} is {}".format(resource, hostname, trace, parameter, result)
        else:
            message = "average for {} {} is {}".format(trace, parameter, result)
        t.log(level='INFO', message='TE: {}'.format(message))
        return result

    def sum(self, trace, parameter, resource=None, **kwargs):
        """
        Get the sum of values for a given parameter

        :param trace: command name
        :type trace: str
        :param parameter: command output name
        :type parameter: str
        :param resource: resource name(s)
        :type resource: str, list(str)
        :rtype: float

        ::

            ${sum}  baseline.sum  resource=r4  trace=route-summary  parameter=ipv4-total
            ${sum}  baseline.sum  trace=route-summary  parameter=ipv4-total
        """
        database = sqlite3.connect(self.db_filename)
        sql = 'select sum(DATA) from data where instance="{}" and trace="{}" and parameter="{}"'.format(self.name,
                                                                                                        trace,
                                                                                                        parameter)
        if resource is not None:
            add = ' and resource="{}"'.format(resource)
            sql = sql + add
        df = pd.read_sql_query(sql, database)
        result = round((df.iloc[0]['sum(DATA)']), 1)
        if resource is not None:
            hostname = t['resources'][resource]['system']['primary']['name']
            message = "sum for {}/{} {} {} is {}".format(resource, hostname, trace, parameter, result)
        else:
            message = "sum for {} {} is {}".format(trace, parameter, result)
        t.log(level='INFO', message='TE: {}'.format(message))
        return result

    def count(self, trace, parameter, resource=None, **kwargs):
        """
        Get the count of values for a given parameter

        :param trace: command name
        :type trace: str
        :param parameter: command output name
        :type parameter: str
        :param resource: resource name
        :type resource: str
        :rtype: float

        ::

            ${count}  baseline.count  resource=r4  trace=route-summary  parameter=ipv4-total
            ${count}  baseline.count  trace=route-summary  parameter=ipv4-total
        """
        database = sqlite3.connect(self.db_filename)
        sql = 'select count(DATA) from data where instance="{}" and trace="{}" and parameter="{}"'.format(self.name,
                                                                                                          trace,
                                                                                                          parameter)
        if resource is not None:
            add = ' and resource="{}"'.format(resource)
            sql = sql + add
        df = pd.read_sql_query(sql, database)
        result = df.iloc[0]['count(DATA)']
        if resource is not None:
            hostname = t['resources'][resource]['system']['primary']['name']
            message = "count for {}/{} {} {} is {}".format(resource, hostname, trace, parameter, result)
        else:
            message = "count for {} {} is {}".format(trace, parameter, result)
        t.log(level='INFO', message='TE: {}'.format(message))
        return result

    def clear(self, resource=None, resource_tag_include=None, resource_tag_exclude=None, **kwargs):
        """
        Delete data from the TE database

        :param resource: resource name(s)
        :type resource: str, list(str)
        :param resource_tag_include: resource tags to match and include
        :type resource_tag_include: list(str)
        :param resource_tag_exclude: resource tags to match and exclude
        :type resource_tag_exclude: list(str)
        :rtype: bool

        ::

            ${include}      Create List  blue
            ${exclude}      Create List  orange  indigo
            baseline.clear  resource_tag_include=${include}  resource_tag_exclude=${exclude}
            baseline.clear  resource=r4
            baseline.clear
        """
        database = sqlite3.connect(self.db_filename)
        sql = 'delete from data where instance="{}"'.format(self.name)
        resources = set()
        if isinstance(resource, list):
            resources.update(resource)
        else:
            if resource is not None:
                resources = {resource}
        added_resources = _get_resource_set(resource_tag_include, resource_tag_exclude)
        resources.update(added_resources)
        if len(resources) > 0:
            for resource in resources:
                if resource not in t['resources'].keys():
                    message = "{} data deletion failed, resource {} does not exist".format(self.name, resource)
                    t.log(level='WARN', message='TE: {}'.format(message))
                    continue
                add = ' and resource="{}"'.format(resource)
                newsql = sql + add
                cur = database.cursor()
                cur.execute(newsql)
                database.commit()
                message = "{} data deleted for resource {}".format(self.name, resource)
                t.log(level='INFO', message='TE: {}'.format(message))
        else:
            cur = database.cursor()
            cur.execute(sql)
            database.commit()
            message = "{} data deleted".format(self.name)
            t.log(level='INFO', message='TE: {}'.format(message))
        return True


class Event:
    """
    The TE Event class contains methods to manipulate Event objects. To instantiate
    Event objects use the following Robot Library commands::

        Library  /volume/systest-proj/PDT_LIBS/PAD/test-engine/TestEngine.py
        Library  TestEngine.Event  name=myevents   WITH NAME  myevents
        Library  TestEngine.Event  name=myevents2  WITH NAME  myevents2
        Library  TestEngine.Event  name=myevents3  WITH NAME  myevents3

    Each Event object has an internal python dictionary that looks like this::

        {
          "resources":
            {
              "r4":
                {
                  "threads":
                    {
                      "default":
                        {
                          "events":
                            {
                              "clear-bgp-neighbor":
                                {
                                  "command": "clear bgp neighbor all",
                                  "controller": "master",
                                  "mode": "cli",
                                  "node": "master",
                                  "wait": 1,
                                },
                              "clear-isis-adjacency":
                                {
                                  "command": "clear isis adjacency all",
                                  "controller": None,
                                  "mode": "cli",
                                  "node": None,
                                  "wait": 0,
                                },
                              "clear-mpls-autobandwidth":
                                {
                                  "command": "clear mpls lsp autobandwidth optimize-aggressive all",
                                  "controller": None,
                                  "mode": "cli",
                                  "node": None,
                                  "wait": 0,
                                },
                              "config-aggregate":
                                {
                                  "command":
                                    [
                                      "set interfaces ae66 aggregated-ether-options link-speed 1g",
                                      "set interfaces ae66 stacked-vlan-tagging",
                                    ],
                                  "controller": None,
                                  "mode": "config",
                                  "node": None,
                                  "wait": 0,
                                },
                              "delete-aggregate":
                                {
                                  "command":
                                    [
                                      "delete interfaces ae66 aggregated-ether-options link-speed 1g",
                                      "delete interfaces ae66",
                                    ],
                                  "controller": None,
                                  "mode": "config",
                                  "node": None,
                                  "wait": 0,
                                },
                            },
                          "interval": 2,
                          "object": None,
                          "running": None,
                          "shuffle": None,
                        },
                    },
                },
            },
        }
    """

    ROBOT_LIBRARY_SCOPE = 'GLOBAL'

    def __init__(self, name):
        self.name = name
        self.running = False
        self.parameters = {}
        self.interval = 1
        self.wait_time = 0
        self.global_log_level = 'ERROR'
        self.device_log_level = 'OFF'
        self.start_time = None
        self.stop_time = None
        self.event_count = 0
        atexit.register(self._cleanup)
        logdir = get_log_dir()
        self.datadir = "{}/data".format(logdir)
        os.makedirs(self.datadir, exist_ok=True)

    def set_logging_level(self, log_level):
        """
        Set the global and device log level for Event threads

        :param log_level: global and device log level
        :type log_level: 'CRITICAL' | 'ERROR' | 'WARNING' | 'INFO' | 'DEBUG' | 'NOTSET' | 'OFF'
        :rtype: bool

        ::

            event.set logging level  log_level=DEBUG
        """
        self.set_global_log_level(log_level)
        self.set_device_log_level(log_level)
        return True

    def set_global_log_level(self, log_level):
        """
        Set the global log level for Event threads

        :param log_level: global log level
        :type log_level: 'CRITICAL' | 'ERROR' | 'WARNING' | 'INFO' | 'DEBUG' | 'NOTSET' | 'OFF'
        :rtype: bool

        ::

            event.set global log level  log_level=DEBUG
        """
        self.global_log_level = log_level
        return True

    def set_device_log_level(self, log_level):
        """
        Set the device log level for Event threads

        :param log_level: device log level
        :type log_level: 'CRITICAL' | 'ERROR' | 'WARNING' | 'INFO' | 'DEBUG' | 'NOTSET' | 'OFF'
        :rtype: bool

        ::

            event.set device log level  log_level=DEBUG
        """
        self.device_log_level = log_level
        return True

    def _cleanup(self):
        if self.running:
            self.running = False
            timeout = self.interval + 300
            if 'resources' in self.parameters:
                for resource in self.parameters['resources'].keys():
                    if 'threads' in self.parameters['resources'][resource]:
                        for thread in self.parameters['resources'][resource]['threads'].keys():
                            thread_object = self.parameters['resources'][resource]['threads'][thread]['object']
                            if thread_object is not None:
                                thread_object.join(timeout=timeout)

    def dump(self):
        """
        Log the internal TE and Event dictionaries::

            event.dump
        """
        #pprint.pprint(te_parameters)
        #pprint.pprint(self.parameters)
        t.log(level='DEBUG', message='TE PARAMETERS: {}'.format(te_parameters))
        t.log(level='DEBUG', message='TE PARAMETERS: {}'.format(self.parameters))

    def get_data(self):
        """
        Get the internal TE and Event dictionaries

        :rtype: dict, dict

        ::

            ${te}  ${event}  event.get data
        """
        return te_parameters, self.parameters

    def get_event_count(self):
        """
        Get the current number of events executed since Event.start

        :rtype: int

        ::

            ${ec}  event.get event count
        """
        return self.event_count

    def register(self, event, command, thread='default', mode='cli', interval=None, node=None, controller=None,
                 wait=None, resource=None, resource_tag_include=None, resource_tag_exclude=None, controller_tag=None,
                 shuffle=None, custom_mode_name=None, custom_mode_enter_command=None,
                 custom_mode_exit_command=None, custom_mode_pattern=None, **kwargs):
        """
        Register events to be executed

        :param event: event name
        :type event: str
        :param command: command(s) to execute
        :type command: str, list(str)
        :param thread: thread name
        :type thread: str
        :param mode: mode for command execution
        :type mode: 'cli' | 'shell' | 'root' | 'custom' | 'fpcx' | 'config'
        :param interval: time delay after event thread executions
        :type interval: float
        :param node: HA state of system node for command execution
        :type node: 'master' | ''backup'
        :param controller: HA state of controller for command execution
        :type controller: 'master' | ''backup'
        :param wait: time delay after event execution
        :type wait: float
        :param resource: resource name(s)
        :type resource: str, list(str)
        :param resource_tag_include: resource tags to match and include
        :type resource_tag_include: list(str)
        :param resource_tag_exclude: resource tags to match and exclude
        :type resource_tag_exclude: list(str)
        :param controller_tag: controller tag to match for command execution
        :type controller_tag: str
        :param shuffle: execute events in random order
        :type shuffle: bool
        :param custom_mode_name: custom mode name
        :type custom_mode_name: str
        :param custom_mode_enter_command: command used to enter the custom mode (e.g. ‘cli-pfe’, ‘vty fpc3’, etc)
        :type custom_mode_enter_command: str
        :param custom_mode_exit_command: command used to exit the custom mode (e.g. ‘quit’, ‘exit’, etc)
        :type custom_mode_exit_command: str
        :param custom_mode_pattern: pattern to match the prompt for the custom mode (e.g. ‘>’)
        :type custom_mode_pattern: str
        :rtype: bool

        ::

            ${include}      Create List  yellow
            ${exclude}      Create List  orange  red
            event.register  resource_tag_include=${include}  resource_tag_exclude=${exclude}
            ...             event=clear-bgp-neighbor  interval=${2}  wait=${1}
            ...             command=clear bgp neighbor all  mode=cli
            ...             controller_tag=brown  node=master  controller=master
        """
        if self.running:
            message = "cannot register events while {} object is running".format(self.name)
            t.log(level='WARN', message='TE: {}'.format(message))
            return False
        if node is not None:
            node = node.lower()
        if controller is not None:
            controller = controller.lower()
        states = ['master', 'backup', None]
        if node not in states or controller not in states:
            message = "{} event registration failed, node and controller must be master or backup".format(self.name)
            t.log(level='WARN', message='TE: {}'.format(message))
            t.log_console(level='WARN', message='TE: {}'.format(message))
            return False
        if mode == 'custom':
            if custom_mode_name is None or custom_mode_enter_command is None or custom_mode_exit_command is None or custom_mode_pattern is None:
                message = "{} event registration failed, custom mode parameters not specified".format(self.name)
                t.log(level='WARN', message='TE: {}'.format(message))
                t.log_console(level='WARN', message='TE: {}'.format(message))
                return False
        if shuffle is not None:
            if not isinstance(shuffle, bool):
                message = "{} event registration failed, shuffle must be boolean".format(self.name)
                t.log(level='WARN', message='TE: {}'.format(message))
                t.log_console(level='WARN', message='TE: {}'.format(message))
                return False
        resources = set()
        if isinstance(resource, list):
            resources.update(resource)
        else:
            if resource is not None:
                resources = {resource}
        added_resources = _get_resource_set(resource_tag_include, resource_tag_exclude)
        resources.update(added_resources)
        if len(resources) == 0:
            message = "{} event registration failed, no resources specified".format(self.name)
            t.log(level='WARN', message='TE: {}'.format(message))
            t.log_console(level='WARN', message='TE: {}'.format(message))
            return False
        for resource in resources:
            if resource not in t['resources'].keys():
                message = "{} event registration failed for resource {}".format(self.name, resource)
                t.log(level='WARN', message='TE: {}'.format(message))
                t.log_console(level='WARN', message='TE: {}'.format(message))
                continue
            resource_node = node
            resource_controller = controller
            if controller_tag:
                mynode, mycontroller = _get_node_and_controller_from_tag(resource, controller_tag)
                if mynode is not None:
                    resource_node = mynode
                if mycontroller is not None:
                    resource_controller = mycontroller
            if 'resources' not in self.parameters.keys(): self.parameters['resources'] = {}
            if resource not in self.parameters['resources'].keys(): self.parameters['resources'][
                resource] = {}
            if 'threads' not in self.parameters['resources'][resource].keys(): self.parameters['resources'][resource][
                'threads'] = {}
            if thread not in self.parameters['resources'][resource]['threads'].keys():
                self.parameters['resources'][resource]['threads'][thread] = {}
                self.parameters['resources'][resource]['threads'][thread][
                    'interval'] = float(interval) if interval is not None else self.interval
                self.parameters['resources'][resource]['threads'][thread]['object'] = None
                self.parameters['resources'][resource]['threads'][thread]['running'] = None
                self.parameters['resources'][resource]['threads'][thread][
                    'shuffle'] = shuffle if shuffle is not None else True
                self.parameters['resources'][resource]['threads'][thread]['events'] = OrderedDict()
            if event not in self.parameters['resources'][resource]['threads'][thread]['events'].keys():
                self.parameters['resources'][resource]['threads'][thread]['events'][event] = {}
                self.parameters['resources'][resource]['threads'][thread]['events'][event]['node'] = None
                self.parameters['resources'][resource]['threads'][thread]['events'][event]['controller'] = None
                self.parameters['resources'][resource]['threads'][thread]['events'][event][
                    'wait'] = float(wait) if wait is not None else self.wait_time
            self.parameters['resources'][resource]['threads'][thread]['events'][event]['command'] = command
            self.parameters['resources'][resource]['threads'][thread]['events'][event]['mode'] = mode
            if mode == 'custom':
                self.parameters['resources'][resource]['threads'][thread]['events'][event][
                    'custom_mode_name'] = custom_mode_name
                self.parameters['resources'][resource]['threads'][thread]['events'][event][
                    'custom_mode_enter_command'] = custom_mode_enter_command
                self.parameters['resources'][resource]['threads'][thread]['events'][event][
                    'custom_mode_exit_command'] = custom_mode_exit_command
                self.parameters['resources'][resource]['threads'][thread]['events'][event][
                    'custom_mode_pattern'] = custom_mode_pattern
            if interval is not None: self.parameters['resources'][resource]['threads'][thread]['interval'] = float(
                interval)
            if shuffle is not None: self.parameters['resources'][resource]['threads'][thread]['shuffle'] = shuffle
            if wait is not None: self.parameters['resources'][resource]['threads'][thread]['events'][event][
                'wait'] = float(wait)
            if resource_node is not None:
                self.parameters['resources'][resource]['threads'][thread]['events'][event]['node'] = resource_node
            if resource_controller is not None:
                self.parameters['resources'][resource]['threads'][thread]['events'][event][
                    'controller'] = resource_controller
        self.dump()
        return True

    def delete_event(self, event, thread='default', resource=None, resource_tag_include=None,
                     resource_tag_exclude=None, **kwargs):
        """
        Delete an event

        :param event: event name
        :type event: str
        :param thread: thread name
        :type thread: str
        :param resource: resource name(s)
        :type resource: str, list(str)
        :param resource_tag_include: resource tags to match and include
        :type resource_tag_include: list(str)
        :param resource_tag_exclude: resource tags to match and exclude
        :type resource_tag_exclude: list(str)
        :rtype: bool

        ::

            ${include}          Create List  yellow
            ${exclude}          Create List  orange  red
            event.delete event  resource_tag_include=${include}  resource_tag_exclude=${exclude}
            ...                 event=clear-bgp-neighbor
        """
        if self.running:
            message = "cannot delete events while {} object is running".format(self.name)
            t.log(level='WARN', message='TE: {}'.format(message))
            return False
        resources = set()
        if isinstance(resource, list):
            resources.update(resource)
        else:
            if resource is not None:
                resources = {resource}
        added_resources = _get_resource_set(resource_tag_include, resource_tag_exclude)
        resources.update(added_resources)
        if len(resources) == 0:
            message = "{} delete event failed, no resources specified".format(self.name)
            t.log(level='WARN', message='TE: {}'.format(message))
            t.log_console(level='WARN', message='TE: {}'.format(message))
            return False
        for resource in resources:
            if resource in self.parameters['resources'].keys():
                if thread in self.parameters['resources'][resource]['threads'].keys():
                    if event in self.parameters['resources'][resource]['threads'][thread]['events'].keys():
                        self.parameters['resources'][resource]['threads'][thread]['events'].pop(event)
        self.dump()
        return True

    def delete_thread(self, thread='default', resource=None, resource_tag_include=None, resource_tag_exclude=None,
                      **kwargs):
        """
        Delete a thread and all of its events

        :param thread: thread name
        :type thread: str
        :param resource: resource name(s)
        :type resource: str, list(str)
        :param resource_tag_include: resource tags to match and include
        :type resource_tag_include: list(str)
        :param resource_tag_exclude: resource tags to match and exclude
        :type resource_tag_exclude: list(str)
        :rtype: bool

        ::

            ${include}  Create List  yellow
            ${exclude}  Create List  orange  red
            event.delete thread  resource_tag_include=${include}  resource_tag_exclude=${exclude}
            ...                  thread=default
        """
        if self.running:
            message = "cannot delete events while {} object is running".format(self.name)
            t.log(level='WARN', message='TE: {}'.format(message))
            return False
        resources = set()
        if isinstance(resource, list):
            resources.update(resource)
        else:
            if resource is not None:
                resources = {resource}
        added_resources = _get_resource_set(resource_tag_include, resource_tag_exclude)
        resources.update(added_resources)
        if len(resources) == 0:
            message = "{} delete thread failed, no resources specified".format(self.name)
            t.log(level='WARN', message='TE: {}'.format(message))
            t.log_console(level='WARN', message='TE: {}'.format(message))
            return False
        for resource in resources:
            if resource in self.parameters['resources'].keys():
                if thread in self.parameters['resources'][resource]['threads'].keys():
                    self.parameters['resources'][resource]['threads'].pop(thread)
        self.dump()
        return True

    def delete_resource(self, resource=None, resource_tag_include=None, resource_tag_exclude=None, **kwargs):
        """
        Delete a resource and all of its threads and events

        :param resource: resource name(s)
        :type resource: str, list(str)
        :param resource_tag_include: resource tags to match and include
        :type resource_tag_include: list(str)
        :param resource_tag_exclude: resource tags to match and exclude
        :type resource_tag_exclude: list(str)
        :rtype: bool

        ::

            ${include}  Create List  yellow
            ${exclude}  Create List  orange  red
            event.delete resource  resource_tag_include=${include}  resource_tag_exclude=${exclude}
        """
        if self.running:
            message = "cannot delete events while {} object is running".format(self.name)
            t.log(level='WARN', message='TE: {}'.format(message))
            return False
        resources = set()
        if isinstance(resource, list):
            resources.update(resource)
        else:
            if resource is not None:
                resources = {resource}
        added_resources = _get_resource_set(resource_tag_include, resource_tag_exclude)
        resources.update(added_resources)
        if len(resources) == 0:
            message = "{} delete resource failed, no resources specified".format(self.name)
            t.log(level='WARN', message='TE: {}'.format(message))
            t.log_console(level='WARN', message='TE: {}'.format(message))
            return False
        for resource in resources:
            if resource in self.parameters['resources'].keys():
                self.parameters['resources'].pop(resource)
        self.dump()
        return True

    def delete(self):
        """
        Delete all resources, threads, and events

        :rtype:bool

        ::

            event.delete
        """
        if self.running:
            message = "cannot delete events while {} object is running".format(self.name)
            t.log(level='WARN', message='TE: {}'.format(message))
            return False
        self.parameters = {}
        self.dump()
        return True

    def _process_event(self, dev, mode, command, wait=0, custom_mode_name=None,
                       custom_mode_enter_command=None, custom_mode_exit_command=None, custom_mode_pattern=None):
        name = get_hostname(device=dev)
        if mode.lower() == 'cli':
            try:
                cli(device=dev, command=command)
            except:
                message = "error for cli command {} on {}".format(command, name)
                t.log(level='INFO', message='TE: {}'.format(message))
                try:
                    message = "reconnecting to {}".format(name)
                    t.log(level='INFO', message='TE: {}'.format(message))
                    reconnect(device=dev, interval=self.interval)
                    message = "reconnected to {}".format(name)
                    t.log(level='INFO', message='TE: {}'.format(message))
                except:
                    message = "reconnect failed to {}".format(name)
                    t.log(level='ERROR', message='TE: {}'.format(message))
                    return
        elif mode.lower() == 'shell':
            try:
                shell(device=dev, command=command)
            except:
                message = "error for shell command {} on {}".format(command, name)
                t.log(level='INFO', message='TE: {}'.format(message))
                try:
                    message = "reconnecting to {}".format(name)
                    t.log(level='INFO', message='TE: {}'.format(message))
                    reconnect(device=dev, interval=self.interval)
                    message = "reconnected to {}".format(name)
                    t.log(level='INFO', message='TE: {}'.format(message))
                except:
                    message = "reconnect failed to {}".format(name)
                    t.log(level='ERROR', message='TE: {}'.format(message))
                    return
        elif mode.lower() == 'root':
            try:
                su(device=dev)
                shell(device=dev, command=command)
            except:
                message = "error for root command {} on {}".format(command, name)
                t.log(level='INFO', message='TE: {}'.format(message))
                try:
                    message = "reconnecting to {}".format(name)
                    t.log(level='INFO', message='TE: {}'.format(message))
                    reconnect(device=dev, interval=self.interval)
                    message = "reconnected to {}".format(name)
                    t.log(level='INFO', message='TE: {}'.format(message))
                except:
                    message = "reconnect failed to {}".format(name)
                    t.log(level='ERROR', message='TE: {}'.format(message))
                    return
        elif mode.lower() == 'config':
            try:
                config(device=dev, command=command, commit=True)
                # if dev.current_node.controllers.keys().len() > 1:
                #     commit(device=dev, sync=True)
                # else:
                #     commit(device=dev)
            except:
                message = "error for config command {} on {}".format(command, name)
                t.log(level='INFO', message='TE: {}'.format(message))
                try:
                    message = "reconnecting to {}".format(name)
                    t.log(level='INFO', message='TE: {}'.format(message))
                    reconnect(device=dev, interval=self.interval)
                    message = "reconnected to {}".format(name)
                    t.log(level='INFO', message='TE: {}'.format(message))
                except:
                    message = "reconnect failed to {}".format(name)
                    t.log(level='ERROR', message='TE: {}'.format(message))
                    return
        elif mode.lower() == 'custom':
            try:
                if custom_mode_name not in dev.current_node.current_controller.custom_modes:
                    add_mode(device=dev,
                             mode=custom_mode_name,
                             command=custom_mode_enter_command,
                             exit_command=custom_mode_exit_command,
                             pattern=custom_mode_pattern)
                execute_command_on_device(device=dev, mode=custom_mode_name, command=command)
            except:
                message = "error for custom command {} on {}".format(command, name)
                t.log(level='INFO', message='TE: {}'.format(message))
                try:
                    message = "reconnecting to {}".format(name)
                    t.log(level='INFO', message='TE: {}'.format(message))
                    reconnect(device=dev, interval=self.interval)
                    message = "reconnected to {}".format(name)
                    t.log(level='INFO', message='TE: {}'.format(message))
                except:
                    message = "reconnect failed to {}".format(name)
                    t.log(level='ERROR', message='TE: {}'.format(message))
                    return
        else:
            try:
                vty(device=dev, command=command, destination=mode)
            except:
                message = "error for vty command {} on {}".format(command, name)
                t.log(level='INFO', message='TE: {}'.format(message))
                try:
                    message = "reconnecting to {}".format(name)
                    t.log(level='INFO', message='TE: {}'.format(message))
                    reconnect(device=dev, interval=self.interval)
                    message = "reconnected to {}".format(name)
                    t.log(level='INFO', message='TE: {}'.format(message))
                except:
                    message = "reconnect failed to {}".format(name)
                    t.log(level='ERROR', message='TE: {}'.format(message))
                    return
        if wait != 0: time.sleep(wait)

    def wait(self, duration, annotate=False):
        """
        Wait

        :param duration: time to wait in sec
        :type duration: float
        :param annotate: add annotation to ME graphs
        :type annotate: bool
        :rtype: bool

        ::

            event.wait  duration=${30}
        """
        global te_parameters
        message = "{} waiting for {}s".format(self.name, duration)
        t.log(level='INFO', message='TE: {}'.format(message))
        t.log_console(level='INFO', message='TE: {}'.format(message))
        if annotate:
            me_object = _get_me_object()
            if me_object is not None:
                me_object.monitoring_engine_annotate(annotation='TE: {}'.format(message))
        time.sleep(duration)
        date = datetime.datetime.now()
        timestamp = datetime.datetime.timestamp(date)
        message = "{} waited for {}s".format(self.name, duration)
        t.log(level='INFO', message='TE: {}'.format(message))
        t.log_console(level='INFO', message='TE: {}'.format(message))
        te_parameters['event']['label'] = message
        te_parameters['event']['timestamp'] = timestamp
        te_parameters['event']['date'] = date
        self.dump()
        return True

    def update(self, label, annotate=True):
        """
        Update event label and timer

        :param label: description of custom processing being executed
        :type label: str
        :param annotate: add annotation to ME graphs
        :type annotate: bool
        :rtype: bool

        ::

            event.update  label=restart routing
        """
        global te_parameters
        date = datetime.datetime.now()
        timestamp = datetime.datetime.timestamp(date)
        message = "{} executed at {}".format(label, date)
        if annotate:
            me_object = _get_me_object()
            if me_object is not None:
                me_object.monitoring_engine_annotate(annotation='TE: {}'.format(message))
        t.log(level='INFO', message='TE: {}'.format(message))
        te_parameters['event']['label'] = label
        te_parameters['event']['timestamp'] = timestamp
        te_parameters['event']['date'] = date
        self.dump()
        return True

    def execute(self, command, label=None, resource=None, mode='cli', node=None, controller=None, annotate=True,
                resource_tag_include=None, resource_tag_exclude=None, controller_tag=None, custom_mode_name=None,
                custom_mode_enter_command=None, custom_mode_exit_command=None, custom_mode_pattern=None,
                pre_event_timing=True, **kwargs):
        """
        Execute an event

        :param command: command(s) to execute
        :type command: str, list(str)
        :param label: description of event being executed
        :type label: str
        :param resource: resource name(s)
        :type resource: str, list(str)
        :param mode: mode for command execution
        :type mode: 'cli' | 'shell' | 'root' | 'custom' | 'fpcx' | 'config'
        :param node: HA state of system node for command execution
        :type node: 'master' | 'backup'
        :param controller: HA state of controller for command execution
        :type controller: 'master' | 'backup'
        :param annotate: add annotation to ME graphs
        :type annotate: bool
        :param resource_tag_include: resource tags to match and include
        :type resource_tag_include: list(str)
        :param resource_tag_exclude: resource tags to match and exclude
        :type resource_tag_exclude: list(str)
        :param controller_tag: controller tag to match for command execution
        :type controller_tag: str
        :param custom_mode_name: custom mode name
        :type custom_mode_name: str
        :param custom_mode_enter_command: command used to enter the custom mode (e.g. ‘cli-pfe’, ‘vty fpc3’, etc)
        :type custom_mode_enter_command: str
        :param custom_mode_exit_command: command used to exit the custom mode (e.g. ‘quit’, ‘exit’, etc)
        :type custom_mode_exit_command: str
        :param custom_mode_pattern: pattern to match the prompt for the custom mode (e.g. ‘>’)
        :type custom_mode_pattern: str
        :param pre_event_timing: set event timer prior to execution of event
        :type pre_event_timing: bool
        :rtype: bool

        ::

            event.execute  resource=r0  command=restart routing  label=restart routing
            ...            controller_tag=brown
        """
        global te_parameters
        if label is None:
            if isinstance(command, list):
                label = command[0]
            else:
                label = command
        if pre_event_timing:
            date = datetime.datetime.now()
            timestamp = datetime.datetime.timestamp(date)
            message = "{} executed at {}".format(label, date)
            te_parameters['event']['label'] = label
            te_parameters['event']['timestamp'] = timestamp
            te_parameters['event']['date'] = date
            if annotate:
                me_object = _get_me_object()
                if me_object is not None:
                    me_object.monitoring_engine_annotate(annotation='TE: {}'.format(message))
            t.log(level='INFO', message='TE: {}'.format(message))
            t.log_console(level='INFO', message='TE: {}'.format(message))
        resources = set()
        if isinstance(resource, list):
            resources.update(resource)
        else:
            if resource is not None:
                resources = {resource}
        added_resources = _get_resource_set(resource_tag_include, resource_tag_exclude)
        resources.update(added_resources)
        if len(resources) == 0:
            message = "{} execute failed, no resources specified".format(self.name)
            t.log(level='WARN', message='TE: {}'.format(message))
            t.log_console(level='WARN', message='TE: {}'.format(message))
            return False
        if node is not None:
            node = node.lower()
        if controller is not None:
            controller = controller.lower()
        states = ['master', 'backup', None]
        if node not in states or controller not in states:
            message = "{} execute failed, node and controller must be master or backup".format(self.name)
            t.log(level='WARN', message='TE: {}'.format(message))
            t.log_console(level='WARN', message='TE: {}'.format(message))
            return False
        if mode == 'custom':
            if custom_mode_name is None or custom_mode_enter_command is None or custom_mode_exit_command is None or custom_mode_pattern is None:
                message = "{} execute failed, custom mode parameters not specified".format(self.name)
                t.log(level='WARN', message='TE: {}'.format(message))
                t.log_console(level='WARN', message='TE: {}'.format(message))
                return False
        threads = []
        for resource in resources:
            dev = t.get_handle(resource=resource)
            hostname = t['resources'][resource]['system']['primary']['name']
            if resource not in t['resources'].keys():
                message = "{} execute failed for resource {}".format(self.name, resource)
                t.log(level='WARN', message='TE: {}'.format(message))
                t.log_console(level='WARN', message='TE: {}'.format(message))
                continue
            resource_node = node
            resource_controller = controller
            if controller_tag:
                mynode, mycontroller = _get_node_and_controller_from_tag(resource, controller_tag)
                if mynode is not None:
                    resource_node = mynode
                if mycontroller is not None:
                    resource_controller = mycontroller
            if resource_node or resource_controller:
                if not resource_node:
                    resource_node = 'master'
                if not resource_controller:
                    resource_controller = 'master'
                nodes = len(dev.nodes.keys())
                try:
                    if nodes == 1:
                        for mynode in dev.nodes.keys():
                            set_ctrl(device=dev, system_node=mynode, controller=resource_controller)
                    elif nodes > 1:
                        set_ctrl(device=dev, system_node=resource_node, controller=resource_controller)
                except:
                    message = "{} cannot set node {} and controller {} on {}/{}".format(self.name, resource_node,
                                                                                        resource_controller,
                                                                                        resource, hostname)
                    t.log(level='WARN', message='TE: {}'.format(message))
                    continue
            wait = 0
            thread = threading.Thread(target=self._process_event, args=(
                dev, mode, command, wait, custom_mode_name, custom_mode_enter_command, custom_mode_exit_command,
                custom_mode_pattern))
            thread.start()
            threads.append(thread)
            message = "{} executed on {}/{}".format(label, resource, hostname)
            t.log(level='INFO', message='TE: {}'.format(message))
        for thread in threads:
            thread.join()
        if not pre_event_timing:
            date = datetime.datetime.now()
            timestamp = datetime.datetime.timestamp(date)
            message = "{} executed at {}".format(label, date)
            te_parameters['event']['label'] = label
            te_parameters['event']['timestamp'] = timestamp
            te_parameters['event']['date'] = date
            if annotate:
                me_object = _get_me_object()
                if me_object is not None:
                    me_object.monitoring_engine_annotate(annotation='TE: {}'.format(message))
            t.log(level='INFO', message='TE: {}'.format(message))
            t.log_console(level='INFO', message='TE: {}'.format(message))
        self.dump()
        return True

    def _start_event_thread(self, resource, thread, shuffle):
        hostname = t['resources'][resource]['system']['primary']['name']
        sys = dict(t['resources'][resource]['system'])
        sys.pop('dh')
        global_log = True
        device_log = True
        global_log_level = str(self.global_log_level).upper()
        device_log_level = str(self.device_log_level).upper()
        if global_log_level == 'OFF':
            global_log = False
        if device_log_level == 'OFF':
            device_log = False
        message = "dev for resource {} thread {} starting".format(resource, thread)
        t.log_console(level='DEBUG', message='TE: {}'.format(message))
        try:
            dev = Device(system=sys, global_logger=global_log, device_logger=device_log)
        except:
            self.parameters['resources'][resource]['threads'][thread]['error'] = True
            raise
        message = "dev for resource {} thread {} started".format(resource, thread)
        t.log_console(level='DEBUG', message='TE: {}'.format(message))
        for node in dev.nodes.keys():
            for controller_name in dev.nodes[node].controllers.keys():
                if global_log_level != 'OFF':
                    dev.nodes[node].controllers[controller_name].global_logger.setLevel(global_log_level)
                if device_log_level != 'OFF':
                    dev.nodes[node].controllers[controller_name].device_logger.setLevel(device_log_level)
        interval = self.parameters['resources'][resource]['threads'][thread]['interval']
        events = self.parameters['resources'][resource]['threads'][thread]['events'].keys()
        if shuffle:
            random.shuffle(list(events))
        while self.running:
            for event in events:
                command = self.parameters['resources'][resource]['threads'][thread]['events'][event]['command']
                mode = self.parameters['resources'][resource]['threads'][thread]['events'][event]['mode']
                if mode == 'custom':
                    custom_mode_name = self.parameters['resources'][resource]['threads'][thread]['events'][event][
                        'custom_mode_name']
                    custom_mode_enter_command = \
                        self.parameters['resources'][resource]['threads'][thread]['events'][event][
                            'custom_mode_enter_command']
                    custom_mode_exit_command = \
                        self.parameters['resources'][resource]['threads'][thread]['events'][event][
                            'custom_mode_exit_command']
                    custom_mode_pattern = self.parameters['resources'][resource]['threads'][thread]['events'][event][
                        'custom_mode_pattern']
                else:
                    custom_mode_name = None
                    custom_mode_enter_command = None
                    custom_mode_exit_command = None
                    custom_mode_pattern = None
                node = self.parameters['resources'][resource]['threads'][thread]['events'][event]['node']
                controller = self.parameters['resources'][resource]['threads'][thread]['events'][event]['controller']
                wait = self.parameters['resources'][resource]['threads'][thread]['events'][event]['wait']
                if node or controller:
                    if not node:
                        node = 'master'
                    if not controller:
                        controller = 'master'
                    nodes = len(dev.nodes.keys())
                    try:
                        if nodes == 1:
                            for mynode in dev.nodes.keys():
                                set_ctrl(device=dev, system_node=mynode, controller=controller)
                        elif nodes > 1:
                            set_ctrl(device=dev, system_node=node, controller=controller)
                    except:
                        message = "{} cannot set node {} and controller {} on {}/{}".format(self.name, node, controller,
                                                                                            resource, hostname)
                        t.log(level='WARN', message='TE: {}'.format(message))
                        continue
                self._process_event(dev, mode, command, wait=wait, custom_mode_name=custom_mode_name,
                                    custom_mode_enter_command=custom_mode_enter_command,
                                    custom_mode_exit_command=custom_mode_exit_command,
                                    custom_mode_pattern=custom_mode_pattern)
                self.event_count += 1
            if not self.parameters['resources'][resource]['threads'][thread]['running']:
                self.parameters['resources'][resource]['threads'][thread]['running'] = True
            time.sleep(interval)
        if self.parameters['resources'][resource]['threads'][thread]['running']:
            self.parameters['resources'][resource]['threads'][thread]['running'] = False
        close(device=dev)

    def start(self, annotate=True, shuffle=True):
        """
        Start event execution

        :param annotate: add annotation to ME graphs
        :type annotate: bool
        :param shuffle: execute events in random order
        :type shuffle: bool
        :rtype: bool

        ::

            event.start
        """
        date = datetime.datetime.now()
        self.event_count = 0
        message = "{} execution starting at {}".format(self.name, date)
        t.log(level='INFO', message='TE: {}'.format(message))
        t.log_console(level='INFO', message='TE: {}'.format(message))
        if not self.running:
            self.running = True
        else:
            message = "{} execution already started".format(self.name, date)
            t.log(level='INFO', message='TE: {}'.format(message))
            t.log_console(level='INFO', message='TE: {}'.format(message))
            return True
        if annotate:
            me_object = _get_me_object()
            if me_object is not None:
                me_object.monitoring_engine_annotate(annotation='TE: {}'.format(message))
        if 'resources' not in self.parameters:
            raise Exception("TE: event object not started, no resources registered")
        for resource in self.parameters['resources'].keys():
            osname = t['resources'][resource]['system']['primary']['osname']
            if osname.lower() != 'junos': continue
            name = t['resources'][resource]['system']['primary']['name']
            for thread in self.parameters['resources'][resource]['threads'].keys():
                mix = self.parameters['resources'][resource]['threads'][thread]['shuffle']
                if mix != shuffle:
                    shuffle = mix
                thread_object = threading.Thread(target=self._start_event_thread, args=(resource, thread, shuffle))
                threadname = self.name + "_" + resource + "_" + name + "_" + thread
                thread_object.name = threadname
                thread_object.daemon = True
                thread_object.start()
                self.parameters['resources'][resource]['threads'][thread]['object'] = thread_object
        for resource in self.parameters['resources'].keys():
            for thread in self.parameters['resources'][resource]['threads'].keys():
                while not self.parameters['resources'][resource]['threads'][thread]['running']:
                    if 'error' in self.parameters['resources'][resource]['threads'][thread].keys():
                        raise Exception("Device error raised")
                    time.sleep(1)
        date = datetime.datetime.now()
        timestamp = datetime.datetime.timestamp(date)
        self.start_time = timestamp
        message = "{} execution started at {}".format(self.name, date)
        t.log(level='INFO', message='TE: {}'.format(message))
        t.log_console(level='INFO', message='TE: {}'.format(message))
        self.dump()
        return True

    def _save_events(self):
        date = te_parameters['event']['date']
        timestamp = te_parameters['event']['timestamp']
        filename = "{}/{}_commands_{}.pickle".format(self.datadir, self.name, timestamp)
        file = open(filename, 'wb')
        event_data = {'metadata': {}, 'resources': {}}
        for resource in self.parameters['resources'].keys():
            event_data['resources'][resource] = {}
            event_data['resources'][resource]['threads'] = {}
            for thread in self.parameters['resources'][resource]['threads'].keys():
                event_data['resources'][resource]['threads'][thread] = {}
                event_data['resources'][resource]['threads'][thread] = {'interval': None, 'shuffle': None}
                event_data['resources'][resource]['threads'][thread]['interval'] = \
                    self.parameters['resources'][resource]['threads'][thread]['interval']
                event_data['resources'][resource]['threads'][thread]['shuffle'] = \
                    self.parameters['resources'][resource]['threads'][thread]['shuffle']
                event_data['resources'][resource]['threads'][thread]['events'] = {}
                for event in self.parameters['resources'][resource]['threads'][thread]['events'].keys():
                    event_data['resources'][resource]['threads'][thread]['events'][event] = {}
                    event_data['resources'][resource]['threads'][thread]['events'][event] = {'command': None,
                                                                                             'controller': None,
                                                                                             'mode': None, 'node': None,
                                                                                             'wait': None}
                    event_data['resources'][resource]['threads'][thread]['events'][event]['command'] = \
                        self.parameters['resources'][resource]['threads'][thread]['events'][event]['command']
                    event_data['resources'][resource]['threads'][thread]['events'][event]['controller'] = \
                        self.parameters['resources'][resource]['threads'][thread]['events'][event]['controller']
                    event_data['resources'][resource]['threads'][thread]['events'][event]['mode'] = \
                        self.parameters['resources'][resource]['threads'][thread]['events'][event]['mode']
                    event_data['resources'][resource]['threads'][thread]['events'][event]['node'] = \
                        self.parameters['resources'][resource]['threads'][thread]['events'][event]['node']
                    event_data['resources'][resource]['threads'][thread]['events'][event]['wait'] = \
                        self.parameters['resources'][resource]['threads'][thread]['events'][event]['wait']
        event_data['metadata']['date'] = date
        event_data['metadata']['timestamp'] = timestamp
        event_data['metadata']['instance'] = self.name
        pickle.dump(event_data, file)
        file.close()

    def stop(self, annotate=True):
        """
        Stop event execution

        :param annotate: add annotation to ME graphs
        :type annotate: bool
        :rtype: bool

        ::

            event.stop
        """
        global te_parameters
        date = datetime.datetime.now()
        message = "{} execution stopping at {}".format(self.name, date)
        t.log(level='INFO', message='TE: {}'.format(message))
        t.log_console(level='INFO', message='TE: {}'.format(message))
        self.running = False
        if annotate:
            me_object = _get_me_object()
            if me_object is not None:
                me_object.monitoring_engine_annotate(annotation='TE: {}'.format(message))
        if 'resources' in self.parameters.keys():
            for resource in self.parameters['resources'].keys():
                if 'threads' in self.parameters['resources'][resource]:
                    for thread in self.parameters['resources'][resource]['threads'].keys():
                        interval = self.parameters['resources'][resource]['threads'][thread]['interval']
                        timeout = interval + 3600
                        thread_object = self.parameters['resources'][resource]['threads'][thread]['object']
                        if thread_object is not None:
                            thread_object.join(timeout=timeout)
                            if thread_object.is_alive():
                                message = "{} resource {} thread {} timed out after {} sec".format(self.name, resource,
                                                                                                   thread, timeout)
                                t.log(level='ERROR', message='TE: {}'.format(message))
                                t.log_console(level='ERROR', message='TE: {}'.format(message))
                            self.parameters['resources'][resource]['threads'][thread]['object'] = None
        date = datetime.datetime.now()
        timestamp = datetime.datetime.timestamp(date)
        event_label = "{} execution stopped".format(self.name)
        te_parameters['event']['label'] = event_label
        te_parameters['event']['timestamp'] = timestamp
        te_parameters['event']['date'] = date
        self.stop_time = timestamp
        message = "{} execution stopped at {} after {} events".format(self.name, date, self.event_count)
        t.log(level='INFO', message='TE: {}'.format(message))
        t.log_console(level='INFO', message='TE: {}'.format(message))
        self._save_events()
        #self.dump()
        return True
