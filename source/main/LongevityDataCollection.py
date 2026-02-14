
from jnpr.toby.hldcl.device import execute_cli_command_on_device as cli
from jnpr.toby.hldcl.device import execute_shell_command_on_device as shell
from jnpr.toby.hldcl.device import execute_vty_command_on_device as vty
from jnpr.toby.hldcl.device import add_channel_to_device as create_new_hdl
from jnpr.toby.hldcl.device import get_model_for_device as device_get_model
from jnpr.toby.hldcl.device import get_host_name_for_device as device_get_host_name
from jnpr.toby.hldcl.device import switch_to_superuser as switch_to_su
from jnpr.toby.hldcl.device import reconnect_to_device as reconnect_channel
from jnpr.toby.utils.utils import run_multiple as run_multiple_tasks

from jnpr.toby.utils.junos.system_time import get_system_time as fetch_system_time
import re
import pdb
import jxmlease
from datetime import datetime
from pathlib import Path
import time
import sys

re_cli_pattern= re.compile(r"re\d+_cli")
re_shell_pattern=re.compile(r"re\d+_shell")
fpc_cli_pattern= re.compile(r"(fpc\d+)_cli")
fpc_shell_pattern=re.compile(r"(fpc\d+)_shell")
fpc_vty_pattern=re.compile(r"(fpc\d+)_vty")
fpc_number_pattern=re.compile(r"fpc(\d+)")
print_dash_line="-----------------------------------------------------------"



class LongevityDataCollection:

    def __init__(self,name):
        self.name = name
        self.handles_dict={}
        self.list_of_dicts=[]
        self.responses={}
        self.file_handles={}
        
        self.longevty_rtrs=None
      
        self.default_timeout=900
        
        self.build_evo_re_shell_cmds_list={}
        self.build_evo_re_cmds_list={}
        
        
        
        self.build_evo_fpc_shell_control_cmds_list={}
        
        self.build_evo_fpc_cli_pfe_cmds_list={}
        self.build_evo_fpc_shell_cmds_list={}
        
        self.build_junos_re_cmds_list={}
        self.build_junos_shell_cmds_list={}
        
        self.build_junos_fpc_aft_vty_cmds_list={}
        self.build_junos_ulc_fpc_ukern_shell_cmds_list={}
        self.build_junos_fpc_ukern_mpc_shell_cmds_list={}
        
        self.junos_aft_cards={}
        
        self.re_cli_responses={}
        self.re_shell_responses={}
        self.fpc_cli_responses={}
        self.fpc_shell_responses={}
        self.fpc_vty_responses={}
        self.junos_ulc_fpc_shell_responses={}
        self.junos_non_ulc_fpc_shell_responses={}
        
        
    
    def is_evo(self, device, testbed):
        osname =  testbed.get_t(resource=device, attribute='flavor') 
        #osname = testbed.get_t(resource=device, controller='re0', attribute='osname')
        return osname.lower() == 'evo'
   
    
    def execute_parallel(self, handles:list):
        
       
        dut_list = self.rtrs
        list_of_dicts = []
        list_of_dicts1 = []
        re_cmds_list=['show chassis hardware','show version']
        for dut in dut_list:
              
            
            
            list_of_dicts.append({'fname': self.execute_cli_commands,
                                'kwargs': {'dev': dut, 'commands':re_cmds_list}})
            
            
         
        return run_multiple_tasks(list_of_dicts)
    
    
    def longevity_data_collection(self, longevity_rtrs:list, node_dict_data:dict, log_dir:str, position:str):
        
        self.responses={}
        
        #print(f"mohan-->{self.junos_aft_cards}")
        #sys.exit()
        self.create_directory_if_not_exists(directory=f"{log_dir}/{position}")
        
    
        self.execute_across_all_devices_in_parallel(longevity_rtrs=longevity_rtrs, node_dict_data=node_dict_data)
        
          # write to .log file
      
        for rtr in longevity_rtrs:       
            dev_hdl = t.get_handle(resource=rtr)
            
            # close the channels
            # get channel list from the dev_handle
            #print(f"mmmm->{self.handles_dict}")
            #channel_list=self.handles_dict[rtr]
            #for channel in channel_list:
            #    print(f"releasing channel {channel}")
            #    dev_hdl.current_node.current_controller.channels[channel].close()
            
            #t.log(f"Released all channels for rtr {rtr}")
            host_name =device_get_host_name(device=dev_hdl)
            now = datetime.now()
            timestamp = now.strftime("%d_%m_%Y_%H_%M_%S")
            fname=f"{host_name}.{position}.{timestamp}.log"   
            with open(f"{log_dir}/{position}/{fname}", 'w') as W:
                
                #responses_list=[self.re_cli_responses[rtr], self.re_shell_responses[rtr], self.fpc_cli_responses[rtr], self.fpc_shell_responses[rtr], self.fpc_vty_responses[rtr], self.junos_ulc_fpc_shell_responses[rtr],self.junos_non_ulc_fpc_shell_responses[rtr]]
                responses_list=[self.re_cli_responses.get(rtr,None),
                                self.re_shell_responses.get(rtr, None),
                                self.fpc_cli_responses.get(rtr, None),
                                self.fpc_shell_responses.get(rtr,None),
                                self.fpc_vty_responses.get(rtr, None),
                                self.junos_ulc_fpc_shell_responses.get(rtr,None),
                                self.junos_non_ulc_fpc_shell_responses.get(rtr,None)           
                ]
                                
                for responses in responses_list:
                    if responses:
                        for resp in responses:
                            W.write(resp)
            W.close()
            
        return True
    def execute_across_all_devices_in_parallel(self, longevity_rtrs:list, node_dict_data:dict):
        
        
        list_of_dicts_devices = []
        for rtr in longevity_rtrs:
            
        
            self.re_cli_responses[rtr]=[]
            self.re_shell_responses[rtr]=[]
            
            self.fpc_cli_responses[rtr]=[]
            self.fpc_shell_responses[rtr]=[]
            self.fpc_vty_responses[rtr]=[]
            self.junos_ulc_fpc_shell_responses[rtr]=[]
            self.junos_non_ulc_fpc_shell_responses[rtr]=[]
            
            
            self.execute_same_in_device_parallel(rtr,node_dict_data[rtr])
             
        run_multiple_tasks(self.list_of_dicts)
        
           
    
    def execute_same_in_device_parallel(self, dev, node_list):
        
        dev_hdl = t.get_handle(resource=dev)
        
        
        #list_of_dicts = []
        #print(node_list)
        channel_list=[]
        #if dev in self.handles_dict:
        #    channel_list=self.handles_dict[dev]
        #    for channel in channel_list:
        #osname =  testbed.get_t(resource=dev, controller='re0', attribute='osname') 
        #if not dev_hdl.is_evo():
        #if osname.lower() == 'junos':
        if not self.is_evo(dev, t):
            reconnect_channel(device=dev_hdl, timeout=360, interval=10, all=True)
        
        rtr_model = device_get_model(dev_hdl).lower()
        
        for node in node_list:
            
            if 're1' in node:
                continue 
            now = datetime.now()
            timestamp = now.strftime("%d_%m_%Y_%H_%M_%S")
            
            try:
                channel_name=f"{node}_cli"
                #if channel_name not in channel_list:
                create_new_hdl(device=dev_hdl, channel_type='text', channel_name=channel_name)
                if self.is_evo(dev, t):
                    switch_to_su(device=dev_hdl, channel_name=channel_name)
                channel_list.append(channel_name)
            except Exception as err:
                t.log('ERROR', "failed to create the handle {}".format(err))
              
                reconnect_channel(device=dev_hdl, timeout=360, interval=10, all=True)
                create_new_hdl(device=dev_hdl, channel_type='text', channel_name=channel_name)
                if self.is_evo(dev, t):
                    switch_to_su(device=dev_hdl, channel_name=channel_name)
                channel_list.append(channel_name)
                #return
         
            #time.sleep(60)
            # for re shell
            try:
                #if channel_name not in channel_list:
                channel_name=f"{node}_shell"
                create_new_hdl(device=dev_hdl, channel_type='text', channel_name=channel_name)
                if self.is_evo(dev, t):
                    switch_to_su(device=dev_hdl, channel_name=channel_name)
                channel_list.append(channel_name)
            except Exception as err:
                t.log('ERROR', "failed to create the handle {}".format(err))
                reconnect_channel(device=dev_hdl, timeout=360, interval=10, all=True)
                create_new_hdl(device=dev_hdl, channel_type='text', channel_name=channel_name)
                if self.is_evo(dev, t):
                    switch_to_su(device=dev_hdl, channel_name=channel_name)
                channel_list.append(channel_name)
                #return
                
            #time.sleep(60)
            if not self.is_evo(dev, t) and 'fpc' in node:
                try:
                    channel_name=f"{node}_vty"
                    #if channel_name not in channel_list:
                    create_new_hdl(device=dev_hdl, channel_type='text', channel_name=channel_name)
                    if self.is_evo(dev, t):
                        switch_to_su(device=dev_hdl, channel_name=channel_name)
                    #self.handles_dict[dev].append(f"{node}_vty")
                    #self.handles_dict[f"{node}_vty"]=channel_hdl
                    channel_list.append(channel_name)
                except Exception as err:
                    t.log('ERROR', "failed to create the handle {}".format(err))
                    reconnect_channel(device=dev_hdl, timeout=360, interval=10, all=True)
                    create_new_hdl(device=dev_hdl, channel_type='text', channel_name=channel_name)
                    if self.is_evo(dev, t):
                        switch_to_su(device=dev_hdl, channel_name=channel_name)
                    channel_list.append(channel_name)
                    #return
                    
            time.sleep(60)
        #if dev not in self.handles_dict:
        self.handles_dict[dev]=channel_list
        
        for channel in channel_list:
            if re_cli_pattern.search(channel):
                if self.is_evo(dev, t):
                    re_cli_cmds=self.build_evo_re_cmds_list
                else:
                    re_cli_cmds=self.build_junos_re_cmds_list
                    
                self.list_of_dicts.append({'fname': self.execute_re_cli_commands, 
                            'kwargs': {'dev': dev, 'text_channel':channel,'re_cli_cmds':re_cli_cmds}})
            if re_shell_pattern.search(channel):
                if self.is_evo(dev, t):
                    re_shell_cmds=self.build_evo_re_shell_cmds_list
                else:
                    re_shell_cmds=self.build_junos_shell_cmds_list
                
                self.list_of_dicts.append({'fname': self.execute_re_shell_commands, 
                            'kwargs': {'dev': dev, 'text_channel':channel,'re_shell_cmds':re_shell_cmds}})
            if fpc_cli_pattern.search(channel):
                print("mmmmmmmm")
                found=fpc_cli_pattern.search(channel)
                fpc=found.group(1)
                if self.is_evo(dev, t):
                    self.list_of_dicts.append({'fname':self.execute_fpc_cli_commands,
                                'kwargs': {'dev': dev, 'fpc':fpc, 'text_channel':channel}})
                print("kkkkkkkk")
            if fpc_shell_pattern.search(channel):
                found=fpc_shell_pattern.search(channel)
                fpc=found.group(1)
                if self.is_evo(dev, t):
                    self.list_of_dicts.append({'fname':self.execute_fpc_shell_commands,
                                'kwargs': {'dev': dev, 'fpc':fpc, 'text_channel':channel}})
                else:
                    
                    fpc_found = fpc_number_pattern.search(fpc)
                    fpc_number = fpc_found.group(1)
                    fpc_key=f"{dev}.{fpc_number}"
                    if self.junos_aft_cards:
                        if fpc_key in self.junos_aft_cards.keys():
                            self.list_of_dicts.append({'fname':self.execute_junos_ulc_fpc_shell_commands,
                                        'kwargs': {'dev': dev, 'fpc':fpc, 'text_channel':channel}})
                    else: 
                        self.list_of_dicts.append({'fname':self.execute_junos_non_ulc_fpc_shell_commands,
                                    'kwargs': {'dev': dev, 'fpc':fpc, 'text_channel':channel}})
            if fpc_vty_pattern.search(channel):
                found=fpc_vty_pattern.search(channel)
                fpc=found.group(1)
                fpc_found = fpc_number_pattern.search(fpc)
                fpc_number = fpc_found.group(1)
                fpc_key=f"{dev}.{fpc_number}"
                if self.junos_aft_cards:
                    if fpc_key in self.junos_aft_cards.keys():
                        
                        self.list_of_dicts.append({'fname':self.execute_fpc_vty_commands,
                                    'kwargs': {'dev': dev, 'fpc':fpc, 'text_channel':channel}})
                
                
        return True
        
        
       
    def execute_re_cli_commands(self, dev, text_channel, re_cli_cmds):
        print("IN execute_re_cli_commands started..... ")
        dev_hdl = t.get_handle(resource=dev)
        host_name =device_get_host_name(device=dev_hdl)
        kwargs ={}
        kwargs['timeout']=self.default_timeout
        for cmd in re_cli_cmds[dev]:
            disp_str=f"\n{print_dash_line}\n"
            cmd_execute=f"{cmd}"
            time_execute_stamp=self.get_current_time_of_device(dev)
            disp_str+=f"\n[{time_execute_stamp}] [{host_name}] [CMD] {cmd_execute}\n"
            disp_str+=f"\n{print_dash_line}\n"
            try:
                response = cli(dev_hdl, channel=text_channel, command=cmd, pattern='Toby-.*>$',**kwargs)
                disp_str+=f"\n{response}\n"
                disp_str+=f"\n{print_dash_line}\n"
                self.re_cli_responses[dev].append(disp_str)
                #self.responses[dev].append(response)
            except Exception as err:
                t.log(level="ERROR", message=f"Failed to execute shell {cmd_execute} command with errror : {str(err)}")
                if reconnect_channel(device=dev_hdl, channel_name=text_channel):
                    response = cli(dev_hdl, channel=text_channel, command=cmd_execute,**kwargs) 
                    disp_str+=f"\n{response}\n"
                    disp_str+=f"\n{print_dash_line}\n"
                    self.re_cli_responses[dev].append(disp_str)
                    #self.responses[dev].append(disp_str)
                pass
        print("IN execute_re_cli_commands completed... ")
    
    def execute_re_shell_commands(self, dev, text_channel, re_shell_cmds):
        print("IN execute_re_shell_commands start....")
        dev_hdl = t.get_handle(resource=dev)
        host_name =device_get_host_name(device=dev_hdl)
        kwargs ={}
        kwargs['timeout']=self.default_timeout

        re_shell_responses=[]
        for cmd in re_shell_cmds[dev]:
            disp_str1=f"\n{print_dash_line}\n"
            cmd_execute=f"{cmd}"
            time_execute_stamp=self.get_current_time_of_device(dev)
            disp_str1+=f"\n[{time_execute_stamp}] [{host_name}] [CMD] {cmd_execute}\n"
            disp_str1+=f"\n{print_dash_line}\n"
            try:
               
                response1 = shell(dev_hdl, channel=text_channel, command=cmd, **kwargs)
                disp_str1+=f"\n{response1}\n"
                disp_str1+=f"\n{print_dash_line}\n"
                
                #self.responses[dev].append(disp_str1) 
                self.re_shell_responses[dev].append(disp_str1)
                
                #self.responses[dev].append(response)
            except Exception as err:
                t.log(level="ERROR", message=f"Failed to execute shell command {cmd_execute} with errror : {str(err)}")
                if reconnect_channel(device=dev_hdl, channel_name=text_channel):
                    response1 = shell(dev_hdl, channel=text_channel, command=cmd_execute, **kwargs) 
                    disp_str1+=f"\n{response1}\n"
                    disp_str1+=f"\n{print_dash_line}\n"
                    self.re_shell_responses[dev].append(disp_str1)
                    #self.responses[dev].append(disp_str1)
                pass
        print("execute_re_shell_commands complete")

    def execute_fpc_cli_commands(self, dev, fpc, text_channel):
        
        print("execute_fpc_cli_commands start")
        #pdb.set_trace()
        dev_hdl = t.get_handle(resource=dev)
        host_name =device_get_host_name(device=dev_hdl)
        kwargs={}
        fpc_cli_responses=[]
        kwargs['timeout']=self.default_timeout
        for cmd in self.build_evo_fpc_cli_pfe_cmds_list[dev][fpc]:
            disp_str2=f"\n{print_dash_line}\n"
            if 'show nh db' in cmd:
                kwargs['timeout']=5400
            else:
                kwargs['timeout']=self.default_timeout
            cmd_execute=f"request pfe execute target {fpc} command \"{cmd}\""
            time_execute_stamp=self.get_current_time_of_device(dev)
            #${time_execute_stamp}] [${host_name}] [FPC${fpc}] [CMD] ${cmd}
            disp_str2+=f"\n[{time_execute_stamp}] [{host_name}] [{fpc.upper()}] [CMD] {cmd}\n"
            disp_str2+=f"\n{print_dash_line}\n"
            #response = cli(dev_hdl, channel=text_channel, command=f"request pfe execute target {fpc} command \"{cmd}\"")
            try:
                response2 = cli(dev_hdl, channel=text_channel, command=cmd_execute, pattern='Toby-.*>$', **kwargs)
                disp_str2+=f"\n{response2}\n"
                disp_str2+=f"\n{print_dash_line}\n"
                #self.responses[dev].append(disp_str2)
                self.fpc_cli_responses[dev].append(disp_str2)
            except Exception as err:
                t.log(level="ERROR", message=f"Failed to execute CLI command {cmd_execute} with errror : {str(err)}")
                
                if reconnect_channel(device=dev_hdl, channel_name=text_channel):
                    response = cli(dev_hdl, channel=text_channel, command=cmd_execute, **kwargs) 
                    disp_str2+=f"\n{response}\n"
                    disp_str2+=f"\n{print_dash_line}\n"
                    #self.responses[dev].append(disp_str2)
                    self.fpc_cli_responses[dev].append(disp_str2)
                pass
            #self.responses[dev].append(response)
         
    def execute_fpc_shell_commands(self,dev, fpc, text_channel):
        print("execute_fpc_shell_commands start")
        dev_hdl = t.get_handle(resource=dev)
        
        host_name =device_get_host_name(device=dev_hdl)
        kwargs={}
        kwargs['timeout']=self.default_timeout
       
        key=f"{dev}_{fpc}_shell"
        
        fpc_shell_responses=[]
        
        # control commands
        for cmd in self.build_evo_fpc_shell_control_cmds_list[dev][fpc]:
           
            cmd_execute=f"chvrf iri scp-internal -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR {cmd} {fpc}:"
            #cmd_execute=f"chvrf iri scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR {cmd} fpc0:"
            try:
                shell(dev_hdl, channel=text_channel, command=cmd_execute, pattern=[r'.*#[\s]?', r'%[\s]?', 'Terminal type.*'])
            except Exception as err:
                t.log(level="ERROR", message=f"Failed to execute shell command with errror : {str(err)}")
                pass
            #shell(dev_hdl, command=password, pattern=[r'#[\s]?', r'%[\s]?', 'Terminal type.*'], channel=text_channel)
            
            
        for cmd in self.build_evo_fpc_shell_cmds_list[dev][fpc]:
            disp_str3=f"\n{print_dash_line}\n"
            cmd_execute=f"chvrf iri ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR root@{fpc} {cmd}"
            time_execute_stamp=self.get_current_time_of_device(dev)
            disp_str3+=f"\n[{time_execute_stamp}] [{host_name}] [{fpc.upper()}] [CMD] {cmd}\n"
            disp_str3+=f"\n{print_dash_line}\n"
            try:
                #response = shell(dev_hdl, channel=text_channel, command=f"chvrf iri ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR root@{fpc} {cmd}")
                response3 = shell(dev_hdl, channel=text_channel, command=cmd_execute, **kwargs)
                disp_str3+=f"\n{response3}\n"
                disp_str3+=f"\n{print_dash_line}\n"
                #self.responses[dev].append(disp_str3)
                self.fpc_shell_responses[dev].append(disp_str3)
            except Exception as err:
                t.log(level="ERROR", message=f"Failed to execute shell command {cmd_execute} with errror : {str(err)}")
                
                if reconnect_channel(device=dev_hdl, channel_name=text_channel):
                    response = shell(dev_hdl, channel=text_channel, command=cmd_execute, **kwargs)
                    disp_str+=f"\n{response}\n"
                    disp_str+=f"\n{print_dash_line}\n"
                    #self.responses[dev].append(disp_str)
                    self.fpc_shell_responses[dev].append(disp_str3)
                pass


        
    def execute_fpc_vty_commands(self,dev, fpc, text_channel):
        
        dev_hdl = t.get_handle(resource=dev)
        host_name =device_get_host_name(device=dev_hdl)
        kwargs={}
        kwargs['timeout']=self.default_timeout
        fpc_found = fpc_number_pattern.search(fpc)
        fpc_number = fpc_found.group(1)
        for cmd in self.build_junos_fpc_aft_vty_cmds_list[dev][fpc_number]:
            disp_str4=f"\n{print_dash_line}\n"
            cmd_execute=f"request pfe execute target {fpc} command \"{cmd}\""
            time_execute_stamp=self.get_current_time_of_device(dev)
            disp_str4+=f"\n[{time_execute_stamp}] [{host_name}] [{fpc.upper()}] [CMD] {cmd}\n"
            disp_str4+=f"\n{print_dash_line}\n"
            #response = cli(dev_hdl, channel=text_channel, command=f"request pfe execute target {fpc} command \"{cmd}\"")
            try:
                response4 = vty(dev_hdl, destination=fpc, channel=text_channel, command=cmd_execute, **kwargs)
                disp_str4+=f"\n{response4}\n"
                disp_str4+=f"\n{print_dash_line}\n"
                #self.responses[dev].append(disp_str4)
                self.fpc_vty_responses[dev].append(disp_str4)
            except Exception as err:
                t.log(level="ERROR", message=f"Failed to execute vty command {cmd_execute} with errror : {str(err)}")
                
                if reconnect_channel(device=dev_hdl, channel_name=text_channel):
                    response4 = vty(dev_hdl, destination=fpc, channel=text_channel, command=cmd_execute, **kwargs) 
                    disp_str4+=f"\n{response4}\n"
                    disp_str4+=f"\n{print_dash_line}\n"
                    #self.responses[dev].append(disp_str4)  
                    self.fpc_vty_responses[dev].append(disp_str4)
                pass    
            
            #self.responses[dev].append(response)
    
    
    def execute_junos_ulc_fpc_shell_commands(self,dev, fpc, text_channel):
        print("execute_junos_ulc_fpc_shell_commands started...")
        dev_hdl = t.get_handle(resource=dev)
        host_name =device_get_host_name(device=dev_hdl)
        kwargs={}
        kwargs['timeout']=self.default_timeout
        fpc_found = fpc_number_pattern.search(fpc)
        fpc_number = fpc_found.group(1)
        print(f"KUMAR {self.build_junos_ulc_fpc_ukern_shell_cmds_list[dev].keys()}")
        for cmd in self.build_junos_ulc_fpc_ukern_shell_cmds_list[dev][fpc_number]:
            disp_str5=f"\n{print_dash_line}\n"
            cmd_execute=f"cprod -A {fpc}.0 -c \"{cmd}\""
            time_execute_stamp=self.get_current_time_of_device(dev)
            disp_str5+=f"\n[{time_execute_stamp}] [{host_name}] [{fpc.upper()}] [CMD] {cmd}\n"
            disp_str5+=f"\n{print_dash_line}\n"
            #response = cli(dev_hdl, channel=text_channel, command=f"request pfe execute target {fpc} command \"{cmd}\"")
            try:
                response5 = shell(dev_hdl, channel=text_channel, command=cmd_execute, **kwargs)
                disp_str5+=f"\n{response5}\n"
                disp_str5+=f"\n{print_dash_line}\n"
                self.junos_ulc_fpc_shell_responses[dev].append(disp_str5)
                #self.responses[dev].append(disp_str5)
            except Exception as err:
                t.log(level="ERROR", message=f"Failed to execute shell command {cmd_execute} with errror : {str(err)}")
                
                if reconnect_channel(device=dev_hdl, channel_name=text_channel):
                    response5 = shell(dev_hdl, channel=text_channel, command=cmd_execute, **kwargs) 
                    disp_str5+=f"\n{response5}\n"
                    disp_str5+=f"\n{print_dash_line}\n"
                    #self.responses[dev].append(disp_str5)
                    self.junos_ulc_fpc_shell_responses[dev].append(disp_str5)
                    
                pass
        print("execute_junos_ulc_fpc_shell_commands completed")
      
    def execute_junos_non_ulc_fpc_shell_commands(self,dev, fpc, text_channel):
        
        print("execute_junos_non_ulc_fpc_shell_commands started...")
        dev_hdl = t.get_handle(resource=dev)
        host_name =device_get_host_name(device=dev_hdl)
        kwargs={}
        kwargs['timeout']=self.default_timeout
        fpc_found = fpc_number_pattern.search(fpc)
        fpc_number = fpc_found.group(1)
        for cmd in self.build_junos_fpc_ukern_mpc_shell_cmds_list[dev][fpc_number]:
            disp_str6=f"\n{print_dash_line}\n"
            cmd_execute=f"cprod -A {fpc} -c \"{cmd}\""
            time_execute_stamp=self.get_current_time_of_device(dev)
            disp_str6+=f"\n[{time_execute_stamp}] [{host_name}] [{fpc.upper()}] [CMD] {cmd}\n"
            disp_str6+=f"\n{print_dash_line}\n"
            #response = cli(dev_hdl, channel=text_channel, command=f"request pfe execute target {fpc} command \"{cmd}\"")
            try:
                response6 = shell(dev_hdl, channel=text_channel, command=cmd_execute,**kwargs)
                disp_str6+=f"\n{response6}\n"
                disp_str6+=f"\n{print_dash_line}\n"
                self.junos_non_ulc_fpc_shell_responses[dev].append(disp_str6)
                
            except Exception as err:
                t.log(level="ERROR", message=f"Failed to execute shell command{cmd_execute} with errror : {str(err)}")
                
                if reconnect_channel(device=dev_hdl, channel_name=text_channel):
                    response6 = shell(dev_hdl, channel=text_channel, command=cmd_execute,**kwargs)
                    disp_str6+=f"\n{response6}\n"
                    disp_str6+=f"\n{print_dash_line}\n"
                    self.junos_non_ulc_fpc_shell_responses[dev].append(disp_str6)
                    #self.responses[dev].append(disp_str6)  
                pass
        print("execute_junos_non_ulc_fpc_shell_commands completed")
    def get_current_time_of_device(self, rtr:str) -> str:
        
        dev_hdl = t.get_handle(resource=rtr)
        
        hostname= device_get_host_name(device=dev_hdl)

        
        rtr_model = device_get_model(dev_hdl).lower()
        
    
        
        is_rtr_mx=False
        is_rtr_ptx=False
        is_rtr_acx=False
        is_rtr_srx=False
        is_rtr_ex=False
        is_rtr_qfx=False
        is_rtr_qfx5100=False
        
        
        if 'mx' in rtr_model:
            is_rtr_mx=True
        if 'ptx' in rtr_model:
            is_rtr_ptx=True
        if 'acx' in rtr_model:
            is_rtr_acx=True
        if 'srx' in rtr_model:
            is_rtr_srx=True
        if 'ex' in rtr_model:
            is_rtr_ex=True
        if 'qfx5100' in rtr_model or 'qfx5120' in rtr_model or 'qfx5130' in rtr_model or 'qfx52' in rtr_model or 'qfx511' in rtr_model:
            is_rtr_qfx=True 
        if 'qfx5100' in rtr_model:
            is_rtr_qfx5100=True 
        if not (is_rtr_ex or is_rtr_qfx5100 or is_rtr_qfx) or self.is_evo(rtr, t): 
            return fetch_system_time(device=dev_hdl)
            
        
        local_node_type=''
        if is_rtr_ex or is_rtr_qfx5100:
            local_node_type='fpc0'
        elif is_rtr_qfx:
            local_node_type='localre'
        
       
        cmd = "show system uptime"

        rpc_str = dev_hdl.get_rpc_equivalent(command=cmd)
        
        etree_obj = dev_hdl.execute_rpc(command=rpc_str).response()
        status = jxmlease.parse_etree(etree_obj)
        print("jjjjjjjj")
        status = status['multi-routing-engine-results']['multi-routing-engine-item']
        print("kkkkkkkkk")
        if status['re-name'] == 'localre':
            date_time = status['system-uptime-information']['current-time']['date-time']
        
        
        match = re.match(r"([0-9-: ]+)\s([A-Z]+)", date_time, re.DOTALL)
        current_time_dt = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")

        return current_time_dt

    def longevity_data_collection_init(self, longevity_rtrs:list, node_dict:dict, junos_aft_cards:dict=None) -> None:
        
        self.longevty_rtrs=longevity_rtrs
        self.junos_aft_cards=junos_aft_cards
        
        for rtr in self.longevty_rtrs:
             # intilize the data for fpc cmd list:
            dev_hdl = t.get_handle(resource=rtr)
            rtr_model = device_get_model(dev_hdl).lower()
            
            if self.is_evo(rtr, t):
                self.build_evo_fpc_cli_pfe_cmds_list[rtr]={}
                self.build_evo_fpc_shell_control_cmds_list[rtr]={}
                self.build_evo_fpc_shell_cmds_list[rtr]={}
                
                fpc_list=self.get_fpc_info(rtr)
                #node_dict[rtr]
                self.build_evo_re_cmds(rtr, node_dict, fpc_list)
                self.build_evo_re_shell_cmds(rtr, node_dict)
                
                if 'qfx5' not in rtr_model:
                    self.build_evo_fpc_pfe_cmds(rtr=rtr, fpc_list=fpc_list)
                    self.build_evo_fpc_with_pfe_ids_cmds(rtr=rtr, fpc_list=fpc_list)    
                    self.build_evo_fpc_shell_control_cmds(rtr=rtr, fpc_list=fpc_list)
                    self.build_evo_fpc_shell_cmds(rtr=rtr, fpc_list=fpc_list)
            else: 
                self.build_junos_fpc_aft_vty_cmds_list[rtr]={}
                self.build_junos_ulc_fpc_ukern_shell_cmds_list[rtr]={}
                self.build_junos_fpc_ukern_mpc_shell_cmds_list[rtr]={}
                
                fpc_list=self.get_fpc_info(rtr)
                self.build_junos_re_cmds(rtr,node_dict, fpc_list)
                self.build_junos_shell_cmds(rtr, node_dict, fpc_list)
                
                for fpc in fpc_list:
                    fpc_found = fpc_number_pattern.search(fpc)
                    fpc_number = fpc_found.group(1)
                    
                    if junos_aft_cards:
                        key=f'{rtr}.{fpc_number}'
                        if key in junos_aft_cards.keys():
                            self.build_junos_fpc_aft_vty_cmds(rtr,fpc_number)
                            self.build_junos_ulc_fpc_ukern_shell_cmds(rtr, fpc_number)
                    else:
                        self.build_junos_fpc_ukern_mpc_shell_cmds(rtr, fpc_number)
                
       
       
             
           


       
    
    def build_junos_re_cmds(self, rtr, node_dict:dict, fpc_list:list) -> None:
        
        #------------------------------------------------------------------------------
        #List of Commands to Caputre from RE. In Future want to add new one, can be added here.
        #-------------------------------------------------------------------------------  
        _re_cmds_list = [
            'show version',
            'show chassis fpc',
            'show chassis fpc pic-status',
            'show chassis hardware',
            'show system alarms',
            'show system process extensive',
            'show task memory detail', 
            'show route summary', 
            'show krt state',
            'show krt queue',
            'show route forwarding-table family inet summary',
            'show route forwarding-table family inet6 summary'       
        ]
        self.build_junos_re_cmds_list[rtr]=_re_cmds_list
        
    def build_junos_shell_cmds(self, rtr, node_dict:dict, fpc_list:list) -> None:
        
        
        #------------------------------------------------------------------------------
        #List of Commands to run on RE Shell. In Future want to add new one, can be added here
        #-------------------------------------------------------------------------------
        
        _re_shell_cmd_list =  [
            'top -o res -b -n -d 1',
            'df -h /var',
            'du -sh /var',
            'vmstat -s',
            'netstat -np | grep 19010 | grep ESTABLISHED',
            'ifsmon -I -t',
            'ifsmon -c -t', 
            'ifsmon -p -t', 
            'ifsmon -g -t', 
            'ifsmon -C -t',
            'ifsmon -Id -t',   
            'netstat -jk -t',
            'netstat -m -t',
            'vmstat -z',
            'vmstat -m',
            'vmstat -misz',
            'sysctl -a net.pdk_stats',
            'top -o cpu -d 1'
        ]
        
        self.build_junos_shell_cmds_list[rtr]=_re_shell_cmd_list
        
    
    def build_junos_fpc_ukern_mpc_shell_cmds(self, rtr, fpc:str): # done
        
        #------------------------------------------------------------------------------
        # List of Commands to Caputre from FPC(ukern mpc only) or cli-pfe. 
        # In Future want to add new one, can be added here.
        #-------------------------------------------------------------------------------    
        # Works only ukern mpcs  
        
        fpc_ukern_mpc_shell_cmd_list =    [
            'show heap',
            'show heap 0',
            'show heap 0 accounting pc size',
            'show heap 0 accounting pc',
            'show heap 0 accounting rates',
            'show heap 1',
            'show heap 1 accounting size',
            'show heap 1 accounting pc',
            'show heap 1 accounting rates',
            'show packet',
            'show packet statistics',
            'show ukern_trace memory-composition',
            'show route summary',
            'show route all summary',
            'show nhdb summary detail',
            'show vbf summary',
            'show jnh 0 pool summary verbose',
            'show jnh 0 pool usage',
            'show jnh 0 pool detail',
            'show jnh 0 pool layout',
            'show jnh 0 pool composition',
            'show jnh 0 pool stats nh',
            'show jnh 0 pool stats fw',
            'show jnh 0 pool stats cnt',
            'show jnh 1 pool summary verbose',
            'show jnh 1 pool usage',
            'show jnh 1 pool detail',
            'show jnh 1 pool layout',
            'show jnh 1 pool composition',
            'show jnh 1 pool stats nh',
            'show jnh 1 pool stats fw',
            'show jnh 1 pool stats cnt',
            'show piles',
            'show linux cpu usage',
            'show nh management',
        ]
     
        self.build_junos_fpc_ukern_mpc_shell_cmds_list[rtr][fpc] = fpc_ukern_mpc_shell_cmd_list #done
        
    
    
    def build_junos_fpc_aft_vty_cmds(self, rtr:str, fpc:str):  #done
        
        #------------------------------------------------------------------------------
        # List of Commands to Caputre from AFT FPC
        # In Future want to add new one, can be added here.
        #-------------------------------------------------------------------------------  
        aft_fpc_cmd_list =    [
            'show system info',
            'show sandbox tokens zombie yes',
            'show sandbox stats',
            'show aft transport stats',
            'show jnh pool vlayout inst cmn',
            'show jnh pool vstats inst cmn',
            'show jnh pool vsummary inst cmn',
            'show jnh pool layout inst cmn',
            'show jnh pool composition inst cmn',
            'show jnh pool summary inst cmn',
            'show jnh pool detail inst cmn',
            'show jnh alloc table'
        ]
        dev_hdl = t.get_handle(resource=rtr)
        rtr_model = device_get_model(dev_hdl).lower()    
        
        pfe_fpc_cmds_list=[]
        if 'qfx' in rtr_model or 'ex' in rtr_model:
            pfe_instances=self.get_pfe_instances_from_junos_qfx_fpc(rtr)
        else:
            
            pfe_instances=self.get_pfe_instances_from_junos_fpc(rtr, f"fpc{fpc}")
            
        for pfe in pfe_instances:
            pfe_fpc_cmds_list.append(f"show jnh pool layout inst {pfe}")
            pfe_fpc_cmds_list.append(f"show jnh pool composition inst {pfe}")
            pfe_fpc_cmds_list.append(f"show jnh pool summary inst {pfe}")
            pfe_fpc_cmds_list.append(f"show jnh pool detail inst {pfe}")
            pfe_fpc_cmds_list.append(f"show jnh pool stats inst {pfe}") 
            pfe_fpc_cmds_list.append(f"show jnh hash summary inst{pfe}")                                         
     
        self.build_junos_fpc_aft_vty_cmds_list[rtr][fpc]=aft_fpc_cmd_list+pfe_fpc_cmds_list  # Done
        
        
      
      
    def build_junos_ulc_fpc_ukern_shell_cmds(self, rtr:str, fpc:str) -> None:
        
        dev_hdl = t.get_handle(resource=rtr)
        rtr_model = device_get_model(dev_hdl).lower()
        #self.build_junos_ulc_fpc_ukern_shell_cmds_list[rtr]={}
        fpc_ukern_cprod_cmd_list    =  [
            'show heap',
            'show packet',
            'show packet statistics',
            'show ukern_trace memory-composition',
        ]
        _fpc_ukern_cprod_cmd_list=[]
        if 'qfx' in rtr_model or 'ex' in rtr_model:
            pfe_instances=self.get_pfe_instances_from_junos_qfx_fpc(rtr)
        else:
            pfe_instances=self.get_pfe_instances_from_junos_fpc(rtr, f"fpc{fpc}")
        for pfe in pfe_instances:
            _fpc_ukern_cprod_cmd_list.append(f"show heap {pfe}")
            _fpc_ukern_cprod_cmd_list.append(f"show heap {pfe} accounting pc size")
            _fpc_ukern_cprod_cmd_list.append(f"show heap {pfe} accounting pc")
            _fpc_ukern_cprod_cmd_list.append(f"show heap {pfe} accounting rates")
            
        self.build_junos_ulc_fpc_ukern_shell_cmds_list[rtr][fpc]=fpc_ukern_cprod_cmd_list+_fpc_ukern_cprod_cmd_list
            
        
        
    def build_evo_re_cmds(self, rtr: str, node_dict:dict,fpc_list:list) -> None:
        
        re_cmds_list = ['show platform distributor statistics summary',
                    'show platform distributor statistics all-clients',
                    'show version',
                    'show chassis fpc',
                    'show chassis fpc pic-status',
                    'show chassis hardware',
                    'show system alarms',
                    'show system process extensive', 
                    'show task memory detail',
                    'show route summary', 
                    'show krt state', 
                    'show krt queue',
                    'show platform object-info anomalies summary',
                    'show platform application-info allocations',
                    'show route forwarding-table family inet summary',
                    'show route forwarding-table family inet6 summary',
                    'show route forwarding-table family mpls summary',
                    'show platform application-info allocations',
                    'show platform binding-queue summary',
                    'show platform binding-queue incomplete',
                    'show platform binding-queue complete-deleted',
                    'show platform app-controller summary',
                    'show platform dependency-state',
                    'show platform dmf',
                    'show system memory statistics jemalloc-stats',
                    'show system storage',
                    'show platform object-info anomalies',
                #    'show platform object-info anomalies app pfetokend',
                #    'show platform application-info allocations app pfetokend',
                    'show platform app-controller incomplete',
                #    'show platform app-controller incomplete app pfetokend',
        ]
        
        node_list= node_dict.get(rtr, None)
        
        for _node in node_list:
            re_cmds_list.append(f"show system memory statistics smap-stats node {_node}")
            re_cmds_list.append(f"show system applications node {_node}")
        
        dev_hdl = t.get_handle(resource=rtr) 
        rtr_model = device_get_model(dev_hdl).lower()
        if 'qfx5' not in rtr_model:
            for fpc in fpc_list:
                fpc_found = fpc_number_pattern.search(fpc)
                fpc_number = fpc_found.group(1)
                re_cmds_list.append(f"show services accounting flow inline-jflow fpc-slot {fpc_number}")
            
        self.build_evo_re_cmds_list[rtr]=re_cmds_list
        
    def build_evo_re_shell_cmds(self, rtr: str, node_dict:dict) -> None:
        
        re_shell_cmd_list = [
            'top -o RES -b -n1',
            'df -h /var',
            'du -sh /var',
            'vmstat -s',
            'cat /proc/meminfo',
            'netstat -np | grep 19010 | grep ESTABLISHED',
            'cli -c "set task accounting on"',
            'sleep 30',
            'cli -c "show task accounting detail | no-more"',
            'cli -c "set task accounting off"',
            'cli -c "show task jobs | no-more"',
            'cli -c "show task io | no-more"',
            'cli -c "set task accounting on"',
            'sleep 30',
            'cli -c "show task accounting detail | no-more"',
            'cli -c "set task accounting off"',
            'cli -c "show task jobs | no-more"',
            'cli -c "show task io | no-more"',
            'cli -c "set task accounting on"',
            'sleep 30',
            'cli -c "show task accounting detail | no-more"',
            'cli -c "set task accounting off"',
            'cli -c "show task jobs | no-more"',
            'cli -c "show task io | no-more"',
            'top -b -n 1 | awk \'$8 == "Z" || $8 == "T"\'',
            'python3 /var/home/regress/ps_mem.py',
        ]
        
        self.build_evo_re_shell_cmds_list[rtr]=re_shell_cmd_list
        
    
    def build_evo_fpc_pfe_cmds(self, rtr:str, fpc_list:list) -> None:
        
        
       
        #------------------------------------------------------------------------------
        #List of Commands to Caputre from FPC or cli-pfe. In Future want to add new one, can be added here.
        #-------------------------------------------------------------------------------    
        fpc_cmd_list =    [
            'show sandbox stats',
            'show cda npu utilization packet-rates',
            'show cda statistics server api',
            'show cda trapstats',
            'show cda notifstats',
            'show npu utilization info',
            'show npu memory info',
            'show nh summary',
            'show nh management',
            'show route summary',
            'show route all summary',
            'show route ack',
            'show aft transport stats',
            'show jexpr unilist stats',
            'show jexpr route mpls stats',
            'show irp memory app usage',
            'show irp memory lb usage',
            'show interfaces summary',
            'show host-path app wedge-detect state | grep State',
            'show nh db',
            'show system cpu'
        ]
        
        for fpc in fpc_list:
        #    fpc_cmd_list.append(f'show services accounting flow inline-jflow fpc-slot {fpc} | no-more')
            if fpc not in self.build_evo_fpc_cli_pfe_cmds_list[rtr]:
                self.build_evo_fpc_cli_pfe_cmds_list[rtr][fpc]=fpc_cmd_list
            else:
                self.build_evo_fpc_cli_pfe_cmds_list[rtr][fpc].extend(fpc_cmd_list)
            
   
        
        
    def build_evo_fpc_with_pfe_ids_cmds(self, rtr:str, fpc_list:list) -> None:
        
      
        #------------------------------------------------------------------------------
        #List of Commands to Caputre on FPC with pfe id. In Future want to add new one, can be added here.
        #-------------------------------------------------------------------------------
        _fpc_pfe_ids_cmd_list =   [
            'show jexpr chash pfe',
            'show jexpr jtm egress-memory summary chip',
            'show jexpr jtm egress-const-memory chip',
            'show jexpr jtm egress-private-desc chip',
            'show jexpr jtm egress-public-desc chip',
            'show jexpr jtm egress-mactbl-memory chip',
            'show jexpr jtm egress-tunnel-memory chip',
            'show jexpr jtm ingress-main-memory chip',
            'show jexpr jtm ingress-special-memory chip',
            'show jexpr jtm mce-block-memory chip',
            'show jexpr plct usage counter dev',
            'show jexpr plct usage policer dev',
            
        ]
        fpc_pfe_ids_cmd_list=[]
        for fpc in fpc_list:
            pfe_ids = self.get_active_pfe_ids_from_fpc(rtr, fpc)
            # get_pfe_Chash_ids_from_pfe
            for pfe in pfe_ids:
                fpc_pfe_ids_cmd_list.extend([f"{c} {pfe}" for c in _fpc_pfe_ids_cmd_list])
                chash_ids=self.evo_get_pfe_chash_id_list(rtr, fpc, pfe)
                for chas_id in chash_ids:
                    fpc_pfe_ids_cmd_list.append(f'show jexpr chash pfe {pfe} id {chas_id}')

            if fpc not in self.build_evo_fpc_cli_pfe_cmds_list[rtr]:
                self.build_evo_fpc_cli_pfe_cmds_list[rtr][fpc]=fpc_pfe_ids_cmd_list
            else:
                self.build_evo_fpc_cli_pfe_cmds_list[rtr][fpc].extend(fpc_pfe_ids_cmd_list)
        
        
        
        
    
    def build_evo_fpc_shell_cmds(self, rtr:str, fpc_list:list)-> None:
        
        
        #------------------------------------------------------------------------------
        #List of Commands to Caputre from FPC Shell. In Future want to add new one, can be added here.
        #-------------------------------------------------------------------------------
        
        fpc_shell_cmd_list = [
            'top -o RES -b -n1',
            'df -h /var',
            'du -sh /var',
            'ls -lSR /var/log',
            'vmstat -s',
            'cat /proc/meminfo',
            'netstat -np | grep 19010 | grep ESTABLISHED/',
            'top -b -n 1 | awk \'$8 == "Z" || $8 == "T"\'',
        ]
        
        if not self.evo_is_chassis_form_factor_fixed(rtr):
            fpc_shell_cmd_list.append('python3 ps_mem.py')
        
        for fpc in fpc_list:
            self.build_evo_fpc_shell_cmds_list[rtr][fpc]=fpc_shell_cmd_list
        
    def build_evo_fpc_shell_control_cmds(self, rtr:str, fpc_list:list) -> None:
        
        if self.evo_is_chassis_form_factor_fixed(rtr):
            return None
        
        fpc_shell_control_cmd_list = [
            '/var/home/regress/ps_mem.py'  
        ]
        for fpc in fpc_list:
            self.build_evo_fpc_shell_control_cmds_list[rtr][fpc]=fpc_shell_control_cmd_list
        
        
    def get_fpc_info(self, rtr)-> list:
        
        dev_hdl = t.get_handle(resource=rtr)
        cmd = "show chassis fpc"
        res = dev_hdl.cli(command=cmd, format='xml').response()
        response = jxmlease.parse(res)['rpc-reply']['fpc-information']
        response = response.jdict()
        ans = []
        ans = response['fpc-information']['fpc']
        #ans = response['fpc-information']
        active_slots = []
        print(type(ans))
        if isinstance(ans, jxmlease.listnode.XMLListNode):
            for fpc in ans:
                state = str(fpc['state'])
                slot = int(fpc['slot'])
                if state == 'Online':
                    active_slots.append(f"fpc{slot}")
        elif isinstance(ans, jxmlease.dictnode.XMLDictNode):
            _fpc_data=ans
            print(f"mmmm {_fpc_data}")
            state = str(_fpc_data['state'])
            slot = int(_fpc_data['slot'])
            if state == 'Online':
                active_slots.append(f"fpc{slot}")
        print("completed")    
        return active_slots
    
    
    
    
    def get_pfe_instances_from_junos_qfx_fpc(self, rtr:str)-> list:
        
        pfe_instances=[]
        for pfe in range(0,6):
            pfe_instances.append(pfe)
        return pfe_instances
    
    def get_pfe_instances_from_junos_fpc(self, rtr:str, fpc:str) -> dict:
        
        dev_hdl = t.get_handle(resource=rtr)
        cmd = f"show chassis fabric fpcs | display xml"
        res = dev_hdl.cli(command=cmd).response()
        #fm-fpc-state-information/fm-fpc-ln[slot="${fpc}"]/fm-pfe-ln/pfe-slot
        response = jxmlease.parse(res)['rpc-reply']['fm-fpc-state-information']
        response = response.jdict()
        #print(response)
        ans = []
        #insts/instances/pfeInst
        ans = response['fm-fpc-state-information']['fm-fpc-ln']
        start =str(ans)[0]
        if start != '[':
            ans=[ans]
        fpc_pfe_instances={}
        for i, _fpc in enumerate(ans):
            #slot = fpc['fpc-slot1-q']
            slot=int(_fpc['slot'])
            key=f'fpc{slot}'   
            if key not in fpc_pfe_instances:
                fpc_pfe_instances[key]=[]
            pfe_in = _fpc['fm-pfe-ln']       
            if isinstance(pfe_in, jxmlease.listnode.XMLListNode):
                for pfeL in pfe_in:      
                    fpc_pfe_instances[key].append(int(pfeL['pfe-slot']))            
            elif isinstance(pfe_in, jxmlease.dictnode.XMLDictNode):
                fpc_pfe_instances[key].append(int(pfeL['pfe-slot']))
                
        return fpc_pfe_instances.get(fpc, None)
        
        
    def get_active_pfe_ids_from_fpc(self, rtr:str, fpc):
        
        
        dev_hdl = t.get_handle(resource=rtr)
        cmd = f"request pfe execute command \"show pfe id info | display xml\" target {fpc} | except SENT"
        res = dev_hdl.cli(command=cmd).response()
        response = jxmlease.parse(res)['rpc-reply']['am-pfe-id-info']
        response = response.jdict()
        #print(response)
        ans = []
        #insts/instances/pfeInst
        ans = response['am-pfe-id-info']['insts']
        
        
        pfe_instaces=[]
        for inst in ans['instances']:
            pfe_inst=int(inst['pfeInst'])
            if pfe_inst not in pfe_instaces:
                pfe_instaces.append(pfe_inst)
    
        
        return pfe_instaces        
                
    def evo_get_pfe_chash_id_list(self, rtr:str, fpc:str, pfe:str) -> list:
        
        dev_hdl = t.get_handle(resource=rtr)
        
        cmd=f"request pfe execute target {fpc} command \"show jexpr chash pfe {pfe}\""
        res = dev_hdl.cli(command=cmd).response()
        
        data=res.split('\n')
        chash_ids=[]
        for _s in data:
            if re.search(r'^\s+(\d+)',_s):
                found=re.search(r'^\s+(\d+)',_s)
                chash_ids.append(found.group(1))
        
        chash_ids=list(set(chash_ids))
       
    
        return chash_ids
        
        
        
        #${cmd_out} =     Execute Cli Command on Device   device=${rh}    timeout=${cmd_timeout}
        #...    command=request pfe execute target fpc${fpc} command "show jexpr chash pfe ${pfe}"      pattern=Toby.*>$
        #${chash_id_list} =    Get Regexp Matches    ${cmd_out}    (\?m)^\\s+(\\d+)    1
        #${chash_id_list} =   Validate List Arg     ${chash_id_list}
        #${chash_id_list} =    Remove Duplicates    ${chash_id_list}
        
        
    def evo_is_chassis_form_factor_fixed(self, rtr)-> bool:
        
        dev_hdl = t.get_handle(resource=rtr)
        kwargs ={}
        kwargs['timeout']=self.default_timeout
        cmd="/usr/sbin/nodeinfo --getSystemType"
        cmd_resp =  shell(device=dev_hdl, command=cmd, **kwargs)
        if 'SingleNode' == cmd_resp:
            return True
        
        return False
    

    def create_directory_if_not_exists(self, directory) -> bool:
        path = Path(directory)
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            t.log(f"Directory '{directory}' created successfully.")
        else:
            t.log(f"Directory '{directory}' already exists.")
            
        return True

    
if __name__ == "__main__":
    
    
    pass
