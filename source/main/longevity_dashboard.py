import sys
import string
import os
import re
import math
import plotly
import plotly.offline as py
import plotly.graph_objs as go
import humanfriendly
from typing import List, Dict
from argparse import ArgumentParser
import os
import socket
from robot.libraries.BuiltIn import BuiltIn
import yaml
import platform
from jnpr import toby
from robot import run_cli
import psutil
from shutil import copyfile
from jnpr.toby.docs.doc_reader import reader as doc_reader
from jnpr.toby.frameworkDefaults import credentials
from jnpr.toby.utils import junoscheck
from jnpr.toby.utils.generate_text_logs import generate_text_logs
from jnpr.toby.utils.ParamsParameterFileData import ParamsFileData
from robot.running import TestSuiteBuilder
from robot.model import SuiteVisitor
from pprint import pprint
import logging
import pdb

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

if platform.system().lower().startswith('win') is False:
    import pwd
else:
    pass

logging.basicConfig(level=logging.INFO)


global_resource_data = {}
global_resource_labels_x_axis = {}
y_axis_label = {}
paper_color = {}
graph_type = {}

def conv_KB_to_MB(input_kilobyte):
    megabyte = 1./1000
    convert_mb = megabyte * input_kilobyte
    return convert_mb
def conv_MB_to_GB(input_megabyte):
    gigabyte = 1.0/1024
    convert_gb = gigabyte * input_megabyte
    return convert_gb
def conv_bytes_to_kb(input_bytes):
    KBytes = input_bytes//1024
    return KBytes

def return_bytes(input_val:int, unit_type:str) -> int:
    num_bytes = humanfriendly.parse_size(f"{input_val}{unit_type}")
    return num_bytes


def conv_bytes_to_MB(num_bytes:int) -> int:

    return num_bytes//1048576

def get_web_prefix() -> str:

    user = pwd.getpwuid(os.getuid()).pw_name

    # get the fqdn and use it as web_prefix assuming HTTP server is configured for public_html directory.
    web_prefix = None
    environment = yaml.safe_load(open(os.path.join(os.path.dirname(credentials.__file__), "environment.yaml")))
    webserver_regex_data = environment['log_web_server']
    hostname = socket.getfqdn().lower()
    for webserver_regex in webserver_regex_data:
        if re.search(r'{}'.format(webserver_regex), hostname):
            hostname = webserver_regex_data[webserver_regex]
    web_prefix = 'https://' + hostname + '/~' + user + '/'
    #print(web_prefix)
    return web_prefix


class LongevityDashboard:
    
    def __init__(self) -> None:

        self._test = {}
        self._longevity = {}
        self.global_resource_data = {}
        self.global_resource_labels_x_axis = {}
        self.y_axis_label = {}
        self.paper_color = {}
        self.graph_type = {}   
        self.scenario_data = {}
        self.global_view = False
        
    def get_global_iterations(self,log_dir_location: str) -> List:
    
        
        return [ name for name in os.listdir(log_dir_location) if os.path.isdir(os.path.join(log_dir_location, name)) and name.startswith('test_suite_iter_') ]
        
        
    def get_test_sceanrio_log_directory(self,log_dir_location: str, pattern: str ) -> List:
        
        return [ name for name in os.listdir(log_dir_location) if os.path.isdir(os.path.join(log_dir_location, name)) and name.endswith(pattern) ]
        
    def plot_graph(self, x_axis:dict, graph_data:dict, out_dir:str, host_name:str, platform:str, version:str, url:str='', chart_type:str = 'line') -> None:

        fichier_html_graphs=open(f"{out_dir}/Longevity_dashboard.html",'w')
        os.system(f"chmod -R 755 {out_dir}/Longevity_dashboard.html")
        #fichier_html_graphs.write("<html><head></head><body><h1><center><b>Longevity Dashboard</b></center></h1>"+"\n")
        
        fichier_html_graphs.write(f'''<html><head></head><body><center><table border="0" cellpadding="1" cellspacing="1" style="height:97px; width:748px">
        <thead>
            <tr>
                <th colspan="3" scope="col"><span style="color:#3300ff"><span style="font-size:36px">Longevity Dashboard</span></span></th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td style="text-align:center"><span style="font-size:20px"><strong>Host:</strong></span><span style="color:#27ae60"><span style="font-size:20px"><strong>{host_name}</strong></span></span><span style="font-size:24px"><span style="color:#2980b9"><strong> </strong></span></span></td>
                <td style="text-align:center"><strong><span style="font-size:20px">Platform:</span><span style="color:#27ae60"><span style="font-size:20px">{platform}</span></span></strong></td>
                <td style="text-align:center"><strong><span style="font-size:20px">Version:</span><span style="color:#27ae60"><span style="font-size:20px">{version}</span></span></strong></td>
            </tr>
        </tbody>
        </table>

        <p>&nbsp;&nbsp;</p>

        <p>&nbsp;</p></center>''')
        if url:
            fichier_html_graphs.write(f'<p><span style="font-size:24px"><span style="color:#2980b9"><strong>Memory Profiling(</strong></span><a href="{url}"><span style="color:#e74c3c"><strong>click here</strong></span></a><span style="color:#2980b9"><strong>)</strong></span></span></p>')

        i=0
        total_items = list(graph_data.keys())
        max_items = len(total_items)
        color1 = '#00bfff'
        color2 = '#ff4000'
        while 1:
            if i<max_items:
                trace = []
                if host_name not in total_items[i]:
                    i+=1
                    continue
                graph_data_to_plot=graph_data[total_items[i]]
                for k,v in graph_data_to_plot.items():
                    if self.graph_type:
                        chart_type=self.graph_type.get(total_items[i], None)
                    else:
                        chart_type='line'

                    if chart_type == 'bar':
                        trace.append(go.Bar(
                            x=x_axis[total_items[i]],
                            y=graph_data_to_plot[k],
                            name=f"{k}",
                            yaxis='y1',
                            width=0.2,
                        ))
                    else:
                        trace.append(go.Scatter(
                            x=x_axis[total_items[i]],
                            y=graph_data_to_plot[k],
                            name=f"{k}",
                            yaxis='y1',
                            mode="lines+markers",
                                marker=dict(
                                size=6,
                            ),
                        ))
                data = trace
                layout = go.Layout(
                    title= (total_items[i]),
                    titlefont=dict(
                    #family='Courier New, monospace',
                    family='Droid Sans Mono',
                    size=15,
                    #color='#7f7f7f'
                    color='#f2105c',
                    ),
                    paper_bgcolor=self.paper_color[total_items[i]],
                    #plot_bgcolor='#f3f4f4',
                    plot_bgcolor='rgba(0,0,0,0)',
                    yaxis=dict(
                        title=f"{self.y_axis_label[total_items[i]]}",
                        titlefont=dict(
                            color=color1
                        ),
                        tickfont=dict(
                            color=color1
                        )
                    )
                )
                fig = go.Figure(data=data, layout=layout)
                fig.update_xaxes(tickangle=45)
                html_fname = f"{total_items[i]}"
                html_fname = re.sub(r"\s","_", html_fname)
                html_fname = re.sub(r"\(","_", html_fname)
                html_fname = re.sub(r"\)","_", html_fname)
                html_fname = re.sub(r"_-","--", html_fname)
                
                plotly.offline.plot(fig, filename=f"{out_dir}/{html_fname}.html",auto_open=False)
                fichier_html_graphs.write("  <object data=\""+f'{html_fname}.html'+"\" width=\"750\" height=\"600\"></object>"+"\n")
                os.system(f"chmod -R 755 {out_dir}/{html_fname}.html")

                i+=1
            else:
                break
        fichier_html_graphs.write("</body></html>")

    def parse_ps_mem_output(self,log_dir_location:str, host_name:str, node: str,scenario=None) -> None:
        
        dir_list=os.listdir(f"{log_dir_location}")
        mem_track={}
        tags = {}
        tags_list = []
        if 'RE' in node:
            re_match = re.compile(f"\[CMD\]\s+python\d?\s+\/var\/home\/regress\/ps_mem.py")
        elif 'fpc' in node:
            re_match = re.compile(f"root@{node}\s+python\d?\s+ps_mem.py")

        logging.info(f"Collecting of 'ps_mem.py' o/p data of host:{host_name} for the node:{node} is started...")
        for sub_dir in dir_list:
            if sub_dir.startswith('iteration_') or sub_dir.startswith('lrm_') or sub_dir.startswith('test_') or sub_dir.startswith('manual_mem'):
                    main_loop=1
                    list_files = os.listdir(f"{log_dir_location}/{sub_dir}")
                    for f in list_files:
                        if f.startswith(f"{host_name}"):
                            se = re.compile(f"{host_name}.{sub_dir}.(.*).log")
                            m = se.search(f)
                            stamp = m.group(1)
                            tags[sub_dir]= stamp
                            tags_list.append(f"{sub_dir}")  
                            with open(f"{log_dir_location}/{sub_dir}/{f}") as R:
                                lines = R.readlines()
                                i = 0
                                while i < len(lines):
                                    if re_match.search(lines[i]):
                                        while True:
                                            if "=================================" in lines[i]:
                                                for j in range(3,14):
                                                    match=re.search(r'=\s+(.*)\s+(.*iB)\s+(.*)',lines[i-j])
                                                    if 'KiB' in match.group(2):
                                                        MiB = conv_KB_to_MB(float(match.group(1)))
                                                        GiB = round(conv_MB_to_GB(float(MiB)), 2)
                                                    elif 'MiB' in  match.group(2):
                                                        GiB = round(conv_MB_to_GB(float(match.group(1))),2)
                                                    else:
                                                        GiB = match.group(1)
                                                    if match.group(3) not in mem_track:
                                                        mem_track[match.group(3)]=[GiB]
                                                    else:
                                                        mem_track[match.group(3)].append(GiB)
                                                main_loop=0
                                                break

                                            i+=1
                                    if main_loop==0:
                                        break
                                    i+=1

        plot_mem_graph={}
        for k,v in mem_track.items():
            val = [ float(x) for x in v]
            if len(val) == len(tags_list):
                plot_mem_graph[k]=val
        key = f'RAM Usage {node}(ps_mem)-{host_name}'
        self.global_resource_data[key] = plot_mem_graph
        self.global_resource_labels_x_axis[key] = tags_list
        self.y_axis_label[key] = 'RAM usage(GB)'
        self.paper_color[key] = '#F0F0FF'
        
        logging.info(f"Collecting of 'ps_mem.py' o/p data of host:{host_name} for the node:{node} is completed")
        if self.global_view:
            self.scenario_data[scenario][key]={}
            self.scenario_data[scenario][key]['_resource_data']=self.global_resource_data[key]
            self.scenario_data[scenario][key]['_resource_labels_x_axis']=self.global_resource_labels_x_axis[key]
            self.scenario_data[scenario][key]['_y_axis_label']=self.y_axis_label[key]
            self.scenario_data[scenario][key]['_paper_color']= self.paper_color[key]
        
        
        

        
    def collect_data_from_jemalloc(self,log_dir_location:str, host_name:str, nodes_list:List[str], collection_type:str,scenario=None) -> None:
        dir_list=os.listdir(f"{log_dir_location}")
        mem_track={}
        tags = {}
        tags_list = []
        re_main_match = re.compile(f"(.*) jemalloc summary statistics")
        if collection_type == 'Allocated':
            re_sub_match = re.compile(f"Allocated\s+: (\d+)")
            d_string = 'total allocated'
        elif collection_type == 'Resident':
            re_sub_match = re.compile(f"Resident\s+:\s+(\d+)")
            d_string = 'resident usage'
        
        logging.info(f"Collecting of 'jemalloc summary statistics' o/p data of host:{host_name} and collection type({collection_type})is started...")
        for sub_dir in dir_list:
            if sub_dir.startswith('iteration_') or sub_dir.startswith('lrm_') or sub_dir.startswith('test_') or sub_dir.startswith('manual_mem'):
                    main_loop=True
                    list_files = os.listdir(f"{log_dir_location}/{sub_dir}")
                    for f in list_files:
                        if f.startswith(f"{host_name}"):
                            se = re.compile(f"{host_name}.{sub_dir}.(.*).log")
                            m = se.search(f)
                            stamp = m.group(1)
                            tags[sub_dir]= stamp
                            tags_list.append(f"{sub_dir}")  
                            with open(f"{log_dir_location}/{sub_dir}/{f}") as R:
                                lines = R.readlines()
                                i = 0
                                while i<len(lines):
                                    re_main_match_str = re_main_match.search(lines[i])
                                    if re_main_match_str:
                                        while True:
                                            re_sub_match_str = re_sub_match.search(lines[i])
                                            i+=1
                                            if re_sub_match_str:
                                                kb = conv_bytes_to_kb(int(re_sub_match_str.group(1)))
                                                MiB = float(round(conv_KB_to_MB(kb), 2))
                                                if re_main_match_str.group(1) not in mem_track:
                                                    mem_track[re_main_match_str.group(1)]=[MiB]
                                                else:
                                                    mem_track[re_main_match_str.group(1)].append(MiB)
                                                break
                                            if "-----------------------------------------------------------" in lines[i]:
                                                main_loop=False
                                                break
                                    i+=1
                                    if not main_loop:
                                        break

        plot_mem_graph={}
        for k,v in mem_track.items():
            val = [ int(x) for x in v]
            if len(val) == len(tags_list):
                plot_mem_graph[k]=val
        
        keys_list = list(plot_mem_graph.keys())
        plot_new_graph = {}
        node_dict_list = {}
        for node in nodes_list:
            node_dict_list[node] = {}
            r = re.compile(f"{node}.*")
            temp_keys_list = list(filter(r.match,keys_list))
            for temp_key in temp_keys_list:
                node_dict_list[node][temp_key]=plot_mem_graph[temp_key]
            key = f'jemalloc {d_string} on {node}-{host_name}'
            self.global_resource_data[key]= node_dict_list[node] 
            self.global_resource_labels_x_axis[key]=tags_list
            self.y_axis_label[key]=f'jemalloc {collection_type}(Megabyte(MB))'
            self.paper_color[key] = '#b6cdee'
           
       
            if self.global_view:
                self.scenario_data[scenario][key]={}
                self.scenario_data[scenario][key]['_resource_data']=self.global_resource_data[key]
                self.scenario_data[scenario][key]['_resource_labels_x_axis']=self.global_resource_labels_x_axis[key]
                self.scenario_data[scenario][key]['_y_axis_label']=self.y_axis_label[key]
                self.scenario_data[scenario][key]['_paper_color']= self.paper_color[key]
        
        logging.info(f"Collecting of 'jemalloc summary statistics' o/p data of host:{host_name} and collection type({collection_type}) is completed\n")

        #print(self.global_resource_data)

    def collect_data_from_npu_mem(self,log_dir_location:str, host_name:str, node:str, collection_type:str,scenario=None) -> None:

        dir_list=os.listdir(f"{log_dir_location}")
        mem_track={}
        tags = {}
        tags_list = []
        re_main_match = re.compile(f"\[{node}\].*show npu memory info")
        if collection_type == 'mem-util-kht-dlu-idb-utilization':
            re_sub_match = re.compile(f"(\w+:\w+).*mem-util-kht-dlu-idb-utilization\s+(\d+)")
            d_string = 'kht dlu idb utilization'
        elif collection_type == 'mem-util-flt-tcam-utilization':
            re_sub_match = re.compile(f"(\w+:\w+).*mem-util-flt-tcam-utilization\s+(\d+)")
            d_string = 'flt tcam utilization'
        elif collection_type == 'mem-util-flt-alpha-0-kht-utilization':
            re_sub_match = re.compile(f"(\w+:\w+).*mem-util-flt-alpha-0-kht-utilization\s+(\d+)")
            d_string = 'flt alpha 0 kht utilization'
        elif collection_type == 'mem-util-flt-alpha-1-kht-utilization':
            re_sub_match = re.compile(f"(\w+:\w+).*mem-util-flt-alpha-1-kht-utilization\s+(\d+)")
            d_string = 'flt alpha 1 kht utilization'
        
        logging.info(f"Collecting of 'show npu memory info' o/p data of host:{host_name} for the node:{node} of collection type({collection_type} is started...")
        for sub_dir in dir_list:
            #if sub_dir.startswith('iteration_') or sub_dir.startswith('lrm_') or sub_dir.startswith('test_') or sub_dir.startswith('manual_mem'):
            if sub_dir.startswith('iteration_') or sub_dir.startswith('test_') or sub_dir.startswith('manual_mem'):
                    main_loop=True
                    print(f"Processing.....{log_dir_location}/{sub_dir}")
                    list_files = os.listdir(f"{log_dir_location}/{sub_dir}")
                    for f in list_files:
                        if f.startswith(f"{host_name}"):
                            se = re.compile(f"{host_name}.{sub_dir}.(.*).log")
                            m = se.search(f)
                            stamp = m.group(1)
                            tags[sub_dir]= stamp
                            tags_list.append(f"{sub_dir}")  
                            with open(f"{log_dir_location}/{sub_dir}/{f}") as R:
                                lines = R.readlines()
                                i = 0
                                while i<len(lines):
                                    re_main_match_str = re_main_match.search(lines[i])
                                    if re_main_match_str:
                                        i+=1
                                        while True:
                                            re_sub_match_str = re_sub_match.search(lines[i])
                                            i+=1
                                            if re_sub_match_str:
                                                if f"{re_sub_match_str.group(1)}_{collection_type}" not in mem_track:
                                                    mem_track[f"{re_sub_match_str.group(1)}_{collection_type}"]=[int(re_sub_match_str.group(2))]
                                                else:
                                                    mem_track[f"{re_sub_match_str.group(1)}_{collection_type}"].append(int(re_sub_match_str.group(2)))
                                            if "-----------------------------------------------------------" in lines[i]:
                                                main_loop=False
                                                break
                                    i+=1
                                    if not main_loop:
                                        break

        plot_mem_graph={}
        for k,v in mem_track.items():
            val = [ int(x) for x in v]
            if len(val) == len(tags_list):
                plot_mem_graph[k]=val
        key=f'npu memory {d_string} on {node}-{host_name}'
        self.global_resource_data[key]= plot_mem_graph 
        self.global_resource_labels_x_axis[key]=tags_list
        self.y_axis_label[key]=f'npu memory {collection_type}(%))'
        self.paper_color[key] = '#b2b2b1'
        
        logging.info(f"Collecting of 'show npu memory info' o/p data of host:{host_name} for the node:{node} of collection type({collection_type} is completed\n")
        if self.global_view:
            self.scenario_data[scenario][key]={}
            self.scenario_data[scenario][key]['_resource_data']=self.global_resource_data[key]
            self.scenario_data[scenario][key]['_resource_labels_x_axis']=self.global_resource_labels_x_axis[key]
            self.scenario_data[scenario][key]['_y_axis_label']=self.y_axis_label[key]
            self.scenario_data[scenario][key]['_paper_color']= self.paper_color[key]

    def collect_data_from_show_system_process_extensive(self,log_dir_location:str, host_name:str, node:str,scenario=None) -> None:

        dir_list=os.listdir(f"{log_dir_location}")
        cpu_track={}
        tags = {}
        tags_list = []
        re_main_match = re.compile(f"show system process extensive")
        re_loop_match = re.compile(f"node:\s+{node}") 
        re_sub_match1 = re.compile(f"%Cpu\(.*\):\s+(.*)\sus,\s+(.*)\ssy,\s+(.*)\s+ni,\s+(.*)\s+id,.*") 
        re_sub_match2 = re.compile(r"^\d+.*\s+\d{2}:\d{2}:\d{2}\s+.*\s+(\d*[.,]?\d)\s+(.*)$")

        logging.info(f"Collecting of 'show system process extensive' o/p data of host:{host_name} for the node:{node} is started...")
        for sub_dir in dir_list:
            if sub_dir.startswith('lrm_') or sub_dir.startswith('test_config') or sub_dir.startswith('manual_mem'):
                    main_loop=True
                    list_files = os.listdir(f"{log_dir_location}/{sub_dir}")
                    for f in list_files:
                        if f.startswith(f"{host_name}"):
                            se = re.compile(f"{host_name}.{sub_dir}.(.*).log")
                            m = se.search(f)
                            stamp = m.group(1)
                            tags[sub_dir]= stamp
                            tags_list.append(f"{sub_dir}")  
                            with open(f"{log_dir_location}/{sub_dir}/{f}") as R:
                                lines = R.readlines()
                                i = 0
                                while i<len(lines):
                                    re_main_match_str = re_main_match.search(lines[i])
                                    if re_main_match_str:
                                        i+=1
                                        while True:
                                            re_loop_match_str = re_loop_match.search(lines[i])
                                            if re_loop_match_str:
                                                while True:
                                                    re_sub_match1_str=re_sub_match1.search(lines[i])
                                                    re_sub_match2_str=re_sub_match2.search(lines[i])
                                                    if re_sub_match1_str:
                                                        if 'User' not in cpu_track:
                                                            cpu_track['User']=[float(re_sub_match1_str.group(1))]
                                                        else:
                                                            cpu_track['User'].append(float(re_sub_match1_str.group(1)))
                                                        if 'System' not in cpu_track:
                                                            cpu_track['System'] = [float(re_sub_match1_str.group(2))]
                                                        else:
                                                            cpu_track['System'].append(float(re_sub_match1_str.group(2)))
                                                        if 'Idle' not in cpu_track:
                                                            cpu_track['Idle'] =  [float(re_sub_match1_str.group(4))] 
                                                        else:
                                                            cpu_track['Idle'].append(float(re_sub_match1_str.group(4)))
                                                    if re_sub_match2_str:
                                                        if re_sub_match2_str.group(2) not in cpu_track:
                                                            cpu_track[re_sub_match2_str.group(2)]=[float(re_sub_match2_str.group(1))]
                                                        else:
                                                            cpu_track[re_sub_match2_str.group(2)].append(float(re_sub_match2_str.group(1)))
                                                    if len(lines[i].strip()) == 0 and "-------------------------------" in lines[i+1]:
                                                        main_loop=False
                                                        break
                                                    i+=1
                                            if not main_loop:
                                                break
                                            i+=1
                                    i+=1
                                    if not main_loop:
                                        break

        plot_cpu_graph={}
        for k,v in cpu_track.items():
            val = [ int(x) for x in v]
            if len(val) == len(tags_list):
                if not all(v == 0 for v in val):
                    plot_cpu_graph[k]=val
        key = f'CPU Usage on {node}-{host_name}'
        self.global_resource_data[key]= plot_cpu_graph 
        self.global_resource_labels_x_axis[key]=tags_list
        self.y_axis_label[key]=f'Cpu Usage(%)'
        self.paper_color[key] = '#c6b6c1'
        
        logging.info(f"Collecting of 'show system process extensive' o/p data of host:{host_name} for the node:{node} is completed\n")
        if self.global_view:
            self.scenario_data[scenario][key]={}
            self.scenario_data[scenario][key]['_resource_data']=self.global_resource_data[key]
            self.scenario_data[scenario][key]['_resource_labels_x_axis']=self.global_resource_labels_x_axis[key]
            self.scenario_data[scenario][key]['_y_axis_label']=self.y_axis_label[key]
            self.scenario_data[scenario][key]['_paper_color']= self.paper_color[key]

    def collect_data_from_show_system_proc_mem_info(self,log_dir_location:str, host_name:str,node:str='RE0',scenario=None) -> None:

        dir_list=os.listdir(f"{log_dir_location}")
        mem_track={}
        tags = {}
        tags_list = []
        node=node.upper()
        if 'RE0' in node:
            re_main_match = re.compile(f"\[{host_name}\]\s+\[CMD\]\s+cat\s+\/proc\/meminfo")
        else:
            re_main_match = re.compile(f"\[{host_name}\]\s+\[{node}\]\s+\[CMD\]\s+cat\s+\/proc\/meminfo")
        re_sub_match1 =  re.compile(r'MemTotal:\s+(\d+)\s+(.*)')  
        re_sub_match2 =  re.compile(r'MemFree:\s+(\d+)\s+(.*)')  
        re_sub_match3 =  re.compile(r'MemAvailable:\s+(\d+)\s+(.*)')  

        logging.info(f"Collecting of 'cat /proc/meminfo' o/p data of host:{host_name} for the node:{node} is started...")
        for sub_dir in dir_list:
            if sub_dir.startswith('lrm_') or sub_dir.startswith('test_config') or sub_dir.startswith('manual_mem'):
                    main_loop=True
                    list_files = os.listdir(f"{log_dir_location}/{sub_dir}")
                    for f in list_files:
                        if f.startswith(f"{host_name}"):
                            se = re.compile(f"{host_name}.{sub_dir}.(.*).log")
                            m = se.search(f)
                            stamp = m.group(1)
                            tags[sub_dir]= stamp
                            tags_list.append(f"{sub_dir}")  
                            with open(f"{log_dir_location}/{sub_dir}/{f}") as R:
                                lines = R.readlines()
                                i = 0
                                re_sub=None
                                while i<len(lines):
                                    re_main_match_str = re_main_match.search(lines[i])
                                    if re_main_match_str:
                                        i+=1
                                        while True:
                                            for j in range(i,i+4):
                                                re_sub_match1_str = re_sub_match1.search(lines[j])
                                                re_sub_match2_str = re_sub_match2.search(lines[j])
                                                re_sub_match3_str = re_sub_match3.search(lines[j])
                                                if re_sub_match1_str:
                                                    re_sub=re_sub_match1_str
                                                elif re_sub_match2_str:
                                                    re_sub=re_sub_match2_str
                                                elif re_sub_match3_str:
                                                    re_sub =re_sub_match3_str
                                                if re_sub:
                                                    bytes_n = return_bytes(re_sub.group(1),re_sub.group(2))
                                                    mb = conv_bytes_to_MB(bytes_n)
                                                if re_sub_match1_str:
                                                    if 'MemTotal' not in mem_track:
                                                        mem_track['MemTotal']=[mb]
                                                    else:
                                                        mem_track['MemTotal'].append(mb)
                                                elif re_sub_match2_str:
                                                    if 'MemFree' not in mem_track:
                                                        mem_track['MemFree']=[mb]
                                                    else:
                                                        mem_track['MemFree'].append(mb)
                                                elif re_sub_match3_str:
                                                    if 'MemAvailable' not in mem_track:
                                                        mem_track['MemAvailable']=[mb]
                                                    else:
                                                        mem_track['MemAvailable'].append(mb)
                                            main_loop = False
                                            if not main_loop:
                                                break
                                            i+=1
                                    i+=1
                                    if not main_loop:
                                        break

        plot_mem_graph={}
        for k,v in mem_track.items():
            val = [ int(x) for x in v]
            if len(val) == len(tags_list):
                if not all(v == 0 for v in val):
                    plot_mem_graph[k]=val
        key = f'proc_mem_info on {node}-{host_name}'
        self.global_resource_data[key]= plot_mem_graph 
        self.global_resource_labels_x_axis[key]=tags_list
        self.y_axis_label[key]=f'Memory Allocation(MB)'
        self.graph_type[key]='bar'
        self.paper_color[key] = '#e4fadc'
        
        logging.info(f"Collecting of 'cat /proc/meminfo' o/p data of host:{host_name} for the node:{node} is completed\n")
        if self.global_view:
            self.scenario_data[scenario][key]={}
            self.scenario_data[scenario][key]['_resource_data']=self.global_resource_data[key]
            self.scenario_data[scenario][key]['_resource_labels_x_axis']=self.global_resource_labels_x_axis[key]
            self.scenario_data[scenario][key]['_y_axis_label']=self.y_axis_label[key]
            self.scenario_data[scenario][key]['_paper_color']= self.paper_color[key]


    def collect_data_from_show_system_storage(self,log_dir_location:str, host_name:str,node:str='re0',scenario=None) -> None:

        dir_list=os.listdir(f"{log_dir_location}")
        storage_track={}
        tags = {}
        tags_list = []
        re_main_match = re.compile(f"\[{host_name}\]\s+\[CMD\]\s+show\s+system\s+storage")
        re_loop_match =  re.compile(f"^{node}\:")
        re_sub_match1 =  re.compile(r'^tmpfs\s+\d+.*\s+.*\s+\d+[a-zA-Z]\s+(\d+)\%\s+\/(run)$')
        re_sub_match2 =  re.compile(r'^tmpfs\s+\d+.*\s+.*\s+\d+[a-zA-Z]\s+(\d+)\%\s+\/(dev\/shm)$')

        logging.info(f"Collecting of 'show system storage' o/p data of host:{host_name} for the node:{node} is started...")
        for sub_dir in dir_list:
            if sub_dir.startswith('lrm_') or sub_dir.startswith('test_config'):
                    main_loop=True
                    list_files = os.listdir(f"{log_dir_location}/{sub_dir}")
                    for f in list_files:
                        if f.startswith(f"{host_name}"):
                            se = re.compile(f"{host_name}.{sub_dir}.(.*).log")
                            m = se.search(f)
                            stamp = m.group(1)
                            tags[sub_dir]= stamp
                            tags_list.append(f"{sub_dir}")  
                            with open(f"{log_dir_location}/{sub_dir}/{f}") as R:
                                lines = R.readlines()
                                i = 0
                                re_sub=None
                                try:
                                    while i<len(lines):
                                        re_main_match_str = re_main_match.search(lines[i])
                                        if re_main_match_str:
                                            i+=1
                                            while True:
                                                re_loop_match_str=re_loop_match.search(lines[i])
                                                if re_loop_match_str:
                                                    while True:
                                                        re_sub_match_str1 = re_sub_match1.search(lines[i])
                                                        re_sub_match_str2 = re_sub_match2.search(lines[i])
                                                        re_sub_match_str = None
                                                        if re_sub_match_str1:
                                                            re_sub_match_str=re_sub_match_str1
                                                        if re_sub_match_str2:
                                                            re_sub_match_str=re_sub_match_str2
                                                        
                                                        if re_sub_match_str:
 
                                                            if re_sub_match_str.group(2) not in storage_track:
                                                                storage_track[re_sub_match_str.group(2)]=[re_sub_match_str.group(1)]
                                                            else:
                                                                storage_track[re_sub_match_str.group(2)].append(re_sub_match_str.group(1))
                                                        if len(lines[i]) == 1:
                                                            main_loop=False
                                                            break
                                                        i+=1
                                                i+=1
                                                if i>len(lines) or not main_loop:
                                                    main_loop=False
                                                    break
                                        if not main_loop:
                                            break
                                        i+=1
                                except IndexError:
                                    pass

        plot_storage_graph={}
        for k,v in storage_track.items():
            val = [ float(x) for x in v]
            if len(val) <= len(tags_list):
                plot_storage_graph[k]=val
        key = f'System Storage(tmpfs) Usage on {node}-{host_name}'
        self.global_resource_data[key]= plot_storage_graph 
        self.global_resource_labels_x_axis[key]=tags_list
        self.y_axis_label[key]=f'Capacity(%)'
        #self.graph_type[f'System Storage(tmpfs) Usage on {node}-{host_name}']='bar'
        self.paper_color[key] = '#a5a4ae'
        if self.global_view:
            self.scenario_data[scenario][key]={}
            self.scenario_data[scenario][key]['_resource_data']=self.global_resource_data[key]
            self.scenario_data[scenario][key]['_resource_labels_x_axis']=self.global_resource_labels_x_axis[key]
            self.scenario_data[scenario][key]['_y_axis_label']=self.y_axis_label[key]
            self.scenario_data[scenario][key]['_paper_color']= self.paper_color[key]

        logging.info(f"Collecting of 'show system storage' o/p data of host:{host_name} for the node:{node} is completed...\n")
    
    def parse_junos_show_heap_output(self, log_dir_location:str, host_name:str, node: str, scenario=None) -> None:
    
        dir_list=os.listdir(f"{log_dir_location}")
        junos_heap_track={}
        tags = {}
        tags_list = []
        if 'FPC' in node:
            re_match = re.compile(f"\[\s+{node}\s+\]\s+\[\s+CMD\s+\]\s+show\s+heap$")
        
        logging.info(f'Collecting of show heap output data for host:{host_name} and node {node} is started...')
        for sub_dir in dir_list:
            if sub_dir.startswith('iteration_') or sub_dir.startswith('lrm_') or sub_dir.startswith('test_') or sub_dir.startswith('manual_mem'):
                    main_loop=1
                    list_files = os.listdir(f"{log_dir_location}/{sub_dir}")
                    for f in list_files:
                        if f.startswith(f"{host_name}"):
                            se = re.compile(f"{host_name}.{sub_dir}.(.*).log")
                            m = se.search(f)
                            stamp = m.group(1)
                            tags[sub_dir]= stamp
                            #tags_list.append(f"{sub_dir}_{stamp}")  
                            tags_list.append(f"{sub_dir}")  
                            with open(f"{log_dir_location}/{sub_dir}/{f}") as R:
                                lines = R.readlines()
                                i = 0
                                while i < len(lines):   
                                    if re_match.search(lines[i]):
                                        i+=2
                                        while True:   
                                            found = re.search(r"\d+\s+\w+\s+\w+\s+\w+\s+\w+\s+(\d+)\s+(\w+)",lines[i])
                                            if found:
                                                percent = found.group(1)
                                                name = found.group(2)
                                                if name not in junos_heap_track:
                                                    junos_heap_track[name] = [percent]
                                                else:
                                                    junos_heap_track[name].append(percent)
                                            if "-----------------------------------------------------------" in lines[i] or i > len(lines):
                                                break
                                            i+=1
                                    i+=1
                                    
                                    
        plot_junos_heap_graph={}
    
        for k,v in junos_heap_track.items():
            
            val = [ float(x) for x in v]
            if len(val) == len(tags_list):
                plot_junos_heap_graph[k]=val
       
         
        
        key = f'Heap usage {node}-{host_name}'
        self.global_resource_data[key]=  plot_junos_heap_graph 
        self.global_resource_labels_x_axis[key]=tags_list
        self.y_axis_label[key]=f'Heap usage(%)'
        #self.graph_type[f'System Storage(tmpfs) Usage on {node}-{host_name}']='bar'
        self.paper_color[key] = '#F0F0FF'
        #pdb.set_trace()
        
        if self.global_view:
            self.scenario_data[scenario][key]={}
            self.scenario_data[scenario][key]['_resource_data']=self.global_resource_data[key]
            self.scenario_data[scenario][key]['_resource_labels_x_axis']=self.global_resource_labels_x_axis[key]
            self.scenario_data[scenario][key]['_y_axis_label']=self.y_axis_label[key]
            self.scenario_data[scenario][key]['_paper_color']= self.paper_color[key]
        logging.info(f'Collecting of show heap output for host:{host_name} and node {node} is completed\n')
    
    
    
    
    def plot_graph_for_all_global_iterations_dashboard(self,out_dir: str):

        iterations = self.get_global_iterations(log_dir_location=f"{out_dir}")
        #pdb.set_trace()
        
        for top_dir in iterations:
            self.global_iter_data[top_dir] = {}
            self.global_iter_data[top_dir]['scenario1'] = []
            self.global_iter_data[top_dir]['scenario2'] = []   
            
    def plot_graph_for_single_global_iteation_dashboard(self, out_dir:str, host_name:str, platform:str, version:str,url:str=''):
        
        # log_dir_location=longevity/longi_test_20230424-050849/test_suite_iter_0
        #dir_list = self.get_test_sceanrio_log_directory(log_dir_location, '_Test_Scenario')
        #if tag=='all':
        #    #merge
            
        #    scenario1=self.collect_data_for_dashboard()
        #    scnearo2
        #elif tag == 'Sceanrio1':
        #    
        #elif tag == 'Sceanrio2':
        #    #single 
        
        plot_mem_graph = {}
        tags_list = []
        
        _resource_data_list = []
        sub_dict_list = []
        new_tags = []
        for k in self.scenario_data.keys(): 
            sub_dict = self.tree_traverse(self.scenario_data,k)
            #pdb.set_trace()
            sub_dict_list.append(sub_dict)
            new_tags = [ f"{x}_{k}" for x in self.tree_traverse(sub_dict,'_resource_labels_x_axis') ]
           
            tags_list.extend(new_tags)
   
            #print(len(tags_list))
            #pdb.set_trace()
          
        
        t_keys = sub_dict_list[0].keys()
        t_key_dict = {}
        #pdb.set_trace()
        for j, t_key in enumerate(t_keys):
            #print(f"staart....{t_key}")
            t_key_dict = {}
            t_key_list = []
            for i in range(0, len(sub_dict_list)):
                #pdb.set_trace()
                t_key_list.append(sub_dict_list[i][t_key].get('_resource_data', None))
                y_axis_label = sub_dict_list[i][t_key].get('_y_axis_label', None)
                paper_color = sub_dict_list[i][t_key].get('_paper_color',None)          
                t_key_dict=self.merge_dict(t_key_dict, t_key_list[i])
                      
            #t_key_dict = self.merge_dict(t_key_list[0],t_key_list[1])
            #pdb.set_trace()
            
            self.global_resource_data[t_key] = t_key_dict
            self.global_resource_labels_x_axis[t_key]=tags_list
            self.y_axis_label[t_key]= y_axis_label
            self.paper_color[t_key] = paper_color

            
        self.plot_graph(x_axis=self.global_resource_labels_x_axis, graph_data=self.global_resource_data, out_dir=out_dir, host_name=host_name, platform=platform, version=version, url=url)
        
       
    def merge_dict(self, dict1:dict, dict2:dict)-> dict:
        
        dict3 = {}
        for key in set().union(dict1, dict2):
            if key in dict1: dict3.setdefault(key, []).extend(dict1[key])
            if key in dict2: dict3.setdefault(key, []).extend(dict2[key])
        return dict3
    def tree_traverse(self, tree, key):
        for k, v in tree.items():
            if k == key:
                return v	
            elif isinstance(v, dict):
                p = self.tree_traverse(v, key)
                if p is not None:
                    return p
    def plot_graph_in_dashboard(self, out_dir:str,host_name:str,url:str,platform:str,version:str) -> None:
   
        self.plot_graph(x_axis=self.global_resource_labels_x_axis, graph_data=self.global_resource_data, out_dir=out_dir,host_name=host_name,url=url,platform=platform, version=version)
 
       
    def collect_data_for_dashboard_junos(self, log_dir_location:str, host_name:str, node_dict:Dict,scenario:str):
        
        self.global_view = True
        fpc_list = []
        re_list = []
        if 'fpc_list' in node_dict:
            for fpc in node_dict['fpc_list']:
                fpc_list.append(f"FPC{fpc}")
        elif 're_list' in node_dict:
            for re in node_dict['re_list']:
                re_list.append(f"RE{re}")
                  
        self.scenario_data[scenario]={}
        if fpc_list:
            for fpc in fpc_list: 
                self.parse_junos_show_heap_output(log_dir_location=log_dir_location,host_name=host_name,node=fpc,scenario=scenario)
                
                
            
            
        
          
        
    def collect_data_for_dashboard_evo(self, log_dir_location:str, host_name:str, node_list:List,scenario:str):
        
        
        self.global_view = True
        
        ps_mem_node_list = ['RE']
        fpc_list  = [x for x in node_list if x.startswith('fpc')]
        ps_mem_node_list.extend(fpc_list)
        
        proc_mem_node_list = ['RE0']
        proc_mem_node_list.extend(fpc_list)
        
        
        self.scenario_data[scenario]={}
        for node in ps_mem_node_list:
            #logging.INFO("Testing...")
            self.parse_ps_mem_output(log_dir_location=log_dir_location,host_name=host_name, node=node,scenario=scenario)
            
        
        self.collect_data_from_jemalloc(log_dir_location=log_dir_location,host_name=host_name, nodes_list=node_list,collection_type='Allocated',scenario=scenario)
        self.collect_data_from_jemalloc(log_dir_location=log_dir_location,host_name=host_name, nodes_list=node_list,collection_type='Resident',scenario=scenario)
      
        for fpc in fpc_list:
            self.collect_data_from_npu_mem(log_dir_location=log_dir_location,host_name=host_name, node=node.upper(), collection_type='mem-util-kht-dlu-idb-utilization',scenario=scenario)
            self.collect_data_from_npu_mem(log_dir_location=log_dir_location,host_name=host_name, node=node.upper(), collection_type='mem-util-flt-tcam-utilization',scenario=scenario)
            self.collect_data_from_npu_mem(log_dir_location=log_dir_location,host_name=host_name, node=node.upper(), collection_type='mem-util-flt-alpha-0-kht-utilization',scenario=scenario)
            self.collect_data_from_npu_mem(log_dir_location=log_dir_location,host_name=host_name, node=node.upper(), collection_type='mem-util-flt-alpha-1-kht-utilization',scenario=scenario)

        for node in node_list:
            self.collect_data_from_show_system_process_extensive(log_dir_location=log_dir_location,host_name=host_name, node=node,scenario=scenario)
            self.collect_data_from_show_system_storage(log_dir_location=log_dir_location,host_name=host_name, node=node,scenario=scenario)
        for node in proc_mem_node_list:
            self.collect_data_from_show_system_proc_mem_info(log_dir_location=log_dir_location,host_name=host_name, node=node,scenario=scenario)
                
"""           
if __name__ == "__main__":
    
    
    evo = LongevityDashboard()
    junos = LongevityDashboard()
    



    log_dir_location='/volume/regressions/results/JUNOS/HEAD/mmahadevaswa/longevity/junos/longi_test_20230721-060107/'
    #out_dir = '/volume/regressions/results/JUNOS/HEAD/mmahadevaswa/longevity/longi_test_20230717-210347/test_suite_iter_0/dashboard/ptx10k-kernel-18'
    out_dir1 = '/volume/regressions/results/JUNOS/HEAD/mmahadevaswa/longevity/junos/longi_test_20230721-060107/test_suite_iter_0/dashboard/ameztoi'
    
    scenario_list =['ActiveTest_Scenario1','ActiveTest_Scenario2','ActiveTest_Scenario3','ActiveTest_Scenario4']
    scenario_list =['PassiveTest_Scenario1','PassiveTest_Scenario2','PassiveTest_Scenario3','PassiveTest_Scenario4']
    for scenario in scenario_list:
        sub_log_dir_location=f"{log_dir_location}test_suite_iter_0/{scenario}"
        
        node_list={'fpc_list':['0','2']}
        #evo.collect_data_for_dashboard_evo(log_dir_location=sub_log_dir_location,host_name='ptx10k-kernel-18',node_list=['re0','re1','fpc0','fpc7'],scenario=scenario)
        junos.collect_data_for_dashboard_junos(log_dir_location=sub_log_dir_location,host_name='ameztoi', node_dict=node_list, scenario=scenario)
        #pdb.set_trace()
        
        
    #l.collect_data_for_dashbaord(log_dir_location=log_dir_location,host_name='ptx10k-kernel-18',node_list=['re0','re1','fpc0','fpc7'],scenario='PassiveTest_Scenario2')

        #pdb.set_trace()
    
    
    #evo.plot_graph_for_single_global_iteation_dashboard(out_dir=out_dir,host_name="ptx10k-kernel-18",platform='ptx10008', version="23.4")
    junos.plot_graph_for_single_global_iteation_dashboard(out_dir=out_dir1,host_name='ameztoi', platform='mx240',version='22.4I-20230627.0.0458')

 #   print(evo.scenario_data.keys())  
 #   print(junos.scenario_data.keys())  
        
        
        
    
    #parse_ps_mem_output(log_dir_location=f"{log_dir_location}",host_name='ptx10k-kernel-18', node='RE')
    #parse_ps_mem_output(log_dir_location=f"{log_dir_location}",host_name='ptx10k-kernel-18', node='fpc0')
    #parse_ps_mem_output(log_dir_location=f"{log_dir_location}",host_name='ptx10k-kernel-18', node='fpc7')
#    collect_data_from_jemalloc(log_dir_location=f"{log_dir_location}",host_name='ptx10k-kernel-18', nodes_list=['re0','re1','fpc0','fpc7'],collection_type='Allocated')
#    collect_data_from_jemalloc(log_dir_location=f"{log_dir_location}",host_name='ptx10k-kernel-18', nodes_list=['re0','re1','fpc0','fpc7'],collection_type='Resident')
#    collect_data_from_npu_mem(log_dir_location=f"{log_dir_location}",host_name='ptx10k-kernel-18', node='FPC0', collection_type='mem-util-kht-dlu-idb-utilization')
#    collect_data_from_npu_mem(log_dir_location=f"{log_dir_location}",host_name='ptx10k-kernel-18', node='FPC0', collection_type='mem-util-flt-tcam-utilization')
#    collect_data_from_npu_mem(log_dir_location=f"{log_dir_location}",host_name='ptx10k-kernel-18', node='FPC0', collection_type='mem-util-flt-alpha-0-kht-utilization')
#    collect_data_from_npu_mem(log_dir_location=f"{log_dir_location}",host_name='ptx10k-kernel-18', node='FPC0', collection_type='mem-util-flt-alpha-1-kht-utilization')
#    collect_data_from_npu_mem(log_dir_location=f"{log_dir_location}",host_name='ptx10k-kernel-18', node='FPC7', collection_type='mem-util-kht-dlu-idb-utilization')
#    collect_data_from_npu_mem(log_dir_location=f"{log_dir_location}",host_name='ptx10k-kernel-18', node='FPC7', collection_type='mem-util-flt-tcam-utilization')
#    collect_data_from_npu_mem(log_dir_location=f"{log_dir_location}",host_name='ptx10k-kernel-18', node='FPC7', collection_type='mem-util-flt-alpha-0-kht-utilization')
#    collect_data_from_npu_mem(log_dir_location=f"{log_dir_location}",host_name='ptx10k-kernel-18', node='FPC7', collection_type='mem-util-flt-alpha-1-kht-utilization')
#    collect_data_from_show_system_process_extensive(log_dir_location=f"{log_dir_location}",host_name='ptx10k-kernel-18', node='re0')
#    collect_data_from_show_system_process_extensive(log_dir_location=f"{log_dir_location}",host_name='ptx10k-kernel-18', node='re1')
#    collect_data_from_show_system_process_extensive(log_dir_location=f"{log_dir_location}",host_name='ptx10k-kernel-18', node='fpc0')
#    collect_data_from_show_system_process_extensive(log_dir_location=f"{log_dir_location}",host_name='ptx10k-kernel-18', node='fpc7')
#    collect_data_from_show_system_proc_mem_info(log_dir_location=f"{log_dir_location}",host_name='ptx10k-kernel-18')
#    collect_data_from_show_system_proc_mem_info(log_dir_location=f"{log_dir_location}",host_name='ptx10k-kernel-18', node='fpc0')
#    collect_data_from_show_system_proc_mem_info(log_dir_location=f"{log_dir_location}",host_name='ptx10k-kernel-18', node='fpc7')
#    collect_data_from_show_system_storage(log_dir_location=f"{log_dir_location}",host_name='ptx10k-kernel-18', node='re0')
#    collect_data_from_show_system_storage(log_dir_location=f"{log_dir_location}",host_name='ptx10k-kernel-18', node='re1')
#    collect_data_from_show_system_storage(log_dir_location=f"{log_dir_location}",host_name='ptx10k-kernel-18', node='fpc0')
#    collect_data_from_show_system_storage(log_dir_location=f"{log_dir_location}",host_name='ptx10k-kernel-18', node='fpc7')
    #print(self.global_resource_data)
    #print(self.global_resource_labels_x_axis)
    #plot_graph(x_axis=self.global_resource_labels_x_axis, graph_data=self.global_resource_data)
"""