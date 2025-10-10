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
import itertools

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


if platform.system().lower().startswith('win') is False:
    import pwd
else:
    pass

logging.basicConfig(level=logging.INFO)


RE_TIME_STAMP_SEARCH = re.compile(r"\[(\d{4}-\d{2}-\d{2}\s+\d+:\d+:\d+)\]")
global_resource_data = {}
global_resource_labels_x_axis = {}
y_axis_label = {}
paper_color = {}
graph_type = {}



def conv_KB_to_MB(input_kilobyte):
    megabyte = 1.0/1000
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

class Dashboard:
    
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
        self.events_for_report = {}
        self.events_data = {}
        
        
        
        self.lrm_global_resource_data ={}
        self.lrm_global_resource_labels_x_axis={}
        self.lrm_y_axis_label={}
        self.lrm_paper_color={}
        
        # for report generation:
        self.longevity_report_data = {}
        
        
    def get_global_iterations(self,log_dir_location: str) -> List:
    
        
        return [ name for name in os.listdir(log_dir_location) if os.path.isdir(os.path.join(log_dir_location, name)) and name.startswith('test_suite_iter_') ]
        
        
    def get_test_sceanrio_log_directory(self,log_dir_location: str, pattern: str ) -> List:
        
        return [ name for name in os.listdir(log_dir_location) if os.path.isdir(os.path.join(log_dir_location, name)) and name.endswith(pattern) ]
    
    def check_key_pattern(self, dictionary, pattern):
        return all(re.search(pattern, key) for key in dictionary)    
    def plot_graph(self, x_axis:dict, graph_data:dict, out_dir:str, host_name:str, platform:str, version:str, url:str='', chart_type:str = 'line', rtr:str='') -> None:

        # fix for yaml dump
        if out_dir and graph_data:
            _t_out_dir = out_dir.split('/')
            _t_out_dir_name = _t_out_dir[-1]
            yaml_name = ""
            if _t_out_dir_name == host_name:
                yaml_name = f"{_t_out_dir_name}_cumulative_view"
            elif 'lrm_view' in  _t_out_dir_name:
                yaml_name = f"{host_name}_lrm_view"
            else:
                yaml_name = f"{host_name}_{_t_out_dir_name}"
                
            #with open(f"{out_dir}/{yaml_name}_graph_data.yaml", 'w') as wfile1:
            #    yaml.dump(graph_data, wfile1)
            #    os.system(f"chmod -R 755 {out_dir}/{yaml_name}_graph_data.yaml")
                
            #with open(f"{out_dir}/{yaml_name}_graph_xaxis_label.yaml", 'w') as wfile2:
            #    yaml.dump(x_axis, wfile2)
            #    os.system(f"chmod -R 755 {out_dir}/{yaml_name}_graph_xaxis_label.yaml")
                
                
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

        #print(self.events_for_report.keys())
        if rtr:
            if rtr in self.events_for_report.keys():
                fichier_html_graphs.write('''
        <style>
		table,th,td {border: 1px solid black;border-collapse: collapse;padding: 6px;}
	</style>                                                              
        <body style="text-align:center"><table align="center"><tr><th>List of events executed</th><th>Total times events executed</th></tr>
        ''')
                
                total_events=len(self.events_for_report[rtr]['events'])
                events = self.events_for_report[rtr]['events']
                total_times = self.events_for_report[rtr]['iters']
                for ind,event in enumerate(events):
                    if ind == 0:
                        fichier_html_graphs.write(f'''<tr>
			            <td>{event}</td>
			                <td rowspan="{total_events}">{total_times}</td>
		                </tr>''')
                    else:
                        fichier_html_graphs.write(f'''<tr>
			            <td>{event}</td>
		                </tr>''')
                fichier_html_graphs.write('''</table><br>''')
		
        
        i=0
        total_items = list(graph_data.keys())
        
        max_items = len(total_items)
        color1 = '#00bfff'
        color2 = '#ff4000'

        while 1:
            if i<max_items:
                trace = []
                if 'lrm_view' not in  _t_out_dir_name:
                    _temp_dict = {}
                if host_name not in total_items[i]:
                    i+=1
                    continue
                graph_data_to_plot=graph_data[total_items[i]]
       
                if not graph_data_to_plot:
                    i+=1
                    continue
               
                if graph_data_to_plot:
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
                                    size=0,
                                ),
                            ))
                 
                            if 'lrm_view' not in  _t_out_dir_name and not self.global_view:
                                _temp_dict[k]={}
                   
                                for _i, _check_point in enumerate(x_axis[total_items[i]]):
                                    match = re.search(r'\((.*?)\)', _check_point)
                                    extracted_chk_point = match.group(1) if match else _check_point
                                    _temp_dict[k][extracted_chk_point]=v[_i]
                                
                    data = trace
                    
                    layout = go.Layout(
                        title= (total_items[i]),
                        titlefont=dict(
                        #family='Courier New, monospace',
                        family='Droid Sans Mono',
                        size=18,
                        #color='#7f7f7f'
                        color='#f2105c',
                        ),
                        paper_bgcolor=self.paper_color[total_items[i]],
                        #plot_bgcolor='#f3f4f4',
                        plot_bgcolor='rgba(0,0,0,0)',
                        yaxis=dict(
                            title=f"{self.y_axis_label[total_items[i]]}",
                            titlefont=dict(
                                #color=color1,
                                size=10,
                                color='black'
                            ),
                            tickfont=dict(
                                #color=color1,
                                size=10,
                                color='black'
                            )
                        )
                        
                    )
                    fig = go.Figure(data=data, layout=layout)
                    fig.update_xaxes(tickangle=45)
                    fig.update_xaxes(tickfont_size=10, tickfont_color='black')
                    fig.update_traces(line={'width': 1})
                    
                    html_fname = f"{total_items[i]}"
                    html_fname = re.sub(r"\s","_", html_fname)
                    html_fname = re.sub(r"\(","_", html_fname)
                    html_fname = re.sub(r"\)","_", html_fname)
                    html_fname = re.sub(r"_-","-", html_fname)
                    if 'proc_mem_info' in html_fname:
                        html_fname = html_fname.lower()
                    if 'RPD_Malloc_Allocation' in html_fname:
                        html_fname = html_fname.replace('RPD_Malloc_Allocation', 'RPD_Malloc_Allocation_re0')
                    if 'RAM_Usage_RE_ps_mem' in html_fname:
                        html_fname = html_fname.replace('RAM_Usage_RE_ps_mem', 'RAM_Usage_RE_ps_mem_re0')
                    # store the data
                    
                    #self.longevity_report_data[f"{html_fname}.html"] = graph_data_to_plot
                    if not self.global_view:
                        self.longevity_report_data[f"{html_fname}.html"] = _temp_dict
                    plotly.offline.plot(fig, filename=f"{out_dir}/{html_fname}.html",auto_open=False)
                    fichier_html_graphs.write("  <object data=\""+f'{html_fname}.html'+"\" width=\"800\" height=\"900\"></object>"+"\n")
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
                        if f.startswith(f"{host_name}") and f.endswith(".log"):
                            #pdb.set_trace()
                            se = re.compile(f"{host_name}.{sub_dir}.(.*).log")
                            
                            m = se.search(f)
                            print(sub_dir, m)
                            #pdb.set_trace()
                            stamp = m.group(1)
                            tags[sub_dir]= stamp
                            #tags_list.append(f"{sub_dir}")  
                            with open(f"{log_dir_location}/{sub_dir}/{f}",encoding='utf-8', errors='ignore') as R:
                                
                                lines = R.readlines()
                                i = 0
                                try:
                                    while i < len(lines):
                                        
                                        if re_match.search(lines[i]):
                                            
                        
                                            if RE_TIME_STAMP_SEARCH.search(lines[i]):
                                               
                                                r_found = RE_TIME_STAMP_SEARCH.search(lines[i])
                                                time_stamp = r_found.group(1)
                                                t_title = ''
                                                t_title = re.sub('_config','',sub_dir)
                                                t_title = re.sub('_test','',t_title)
                                                tags_list.append(f"{time_stamp}({t_title})")
                            
                                            while True:
                                                if "=================================" in lines[i]:
                                                    for j in range(3,14):
                                                        match=re.search(r'=\s+(.*)\s+(.*iB)\s+(.*)',lines[i-j])
                                            
                                                        if match:
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
                                except IndexError:
                                    pass

        #pdb.set_trace()
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
        self.paper_color[key] = '#ecf0f1'

        logging.info(f"Collecting of 'ps_mem.py' o/p data of host:{host_name} for the node:{node} is completed")
        if self.global_view:
            self.scenario_data[host_name][scenario][key]={}
            self.scenario_data[host_name][scenario][key]['_resource_data']=self.global_resource_data[key]
            self.scenario_data[host_name][scenario][key]['_resource_labels_x_axis']=self.global_resource_labels_x_axis[key]
            self.scenario_data[host_name][scenario][key]['_y_axis_label']=self.y_axis_label[key]
            self.scenario_data[host_name][scenario][key]['_paper_color']= self.paper_color[key]
        
        
        

        
    def collect_data_from_jemalloc(self,log_dir_location:str, host_name:str, nodes_list:List[str], collection_type:str,scenario=None) -> None:
        dir_list=os.listdir(f"{log_dir_location}")
        mem_track={}
        tags = {}
        tags_list = []
        re_super_match = re.compile(f"\[{host_name}\]\s+\[CMD\]\s+show\s+system\s+memory\s+statistics\s+jemalloc-stats")
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
                        if f.startswith(f"{host_name}") and f.endswith(".log"):
                            se = re.compile(f"{host_name}.{sub_dir}.(.*).log")
                            m = se.search(f)
                            stamp = m.group(1)
                            tags[sub_dir]= stamp
                            with open(f"{log_dir_location}/{sub_dir}/{f}") as R:
                                lines = R.readlines()
                                i = 0
                                try:
                                    while i<len(lines):
                                        re_super_match_str = re_super_match.search(lines[i])
                                        if re_super_match_str:
                                            if RE_TIME_STAMP_SEARCH.search(lines[i]):
                                                r_found = RE_TIME_STAMP_SEARCH.search(lines[i])
                                                time_stamp = r_found.group(1)
                                                t_title = ''
                                                t_title = re.sub('_config','',sub_dir)
                                                t_title = re.sub('_test','',t_title)
                                                tags_list.append(f"{time_stamp}({t_title})")
                                                i+=3
                                            while i<len(lines):
                                                re_main_match_str = re_main_match.search(lines[i])
                                                if re_main_match_str:
                                                    while i<len(lines):
                                                        re_sub_match_str = re_sub_match.search(lines[i])
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
                                                i+=1
                                        i+=1
                                except IndexError:
                                    pass
                                    
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
            self.paper_color[key] = '#ecf0f1'
           
       
            if self.global_view:
                self.scenario_data[host_name][scenario][key]={}
                self.scenario_data[host_name][scenario][key]['_resource_data']=self.global_resource_data[key]
                self.scenario_data[host_name][scenario][key]['_resource_labels_x_axis']=self.global_resource_labels_x_axis[key]
                self.scenario_data[host_name][scenario][key]['_y_axis_label']=self.y_axis_label[key]
                self.scenario_data[host_name][scenario][key]['_paper_color']= self.paper_color[key]
        
        logging.info(f"Collecting of 'jemalloc summary statistics' o/p data of host:{host_name} and collection type({collection_type}) is completed\n")

        #print(self.global_resource_data)

    def collect_data_from_npu_mem(self,log_dir_location:str, host_name:str, node:str, collection_types:list, scenario=None) -> None:

        dir_list=os.listdir(f"{log_dir_location}")
        mem_track={}
        tags = {}
        tags_list = []
        re_main_match = re.compile(f"\[{node}\].*show npu memory info")
        re_sub_match_dict = {}
        for c_type in collection_types:
            re_sub_match_dict[c_type] = re.compile(f"(\w+:\w+:\w+).*{c_type}\s+(\d+)")
        
        d_string = "NPU Memory Utilization"
        re_generic_match = re.compile(f"(\w+:\w+:\w+).*(mem-util-.*-utilization)\s+(\d+)")
        
        logging.info(f"Collecting of 'show npu memory info' o/p data of host:{host_name} for the node:{node} of collection type({collection_types} is started...")
        for sub_dir in dir_list:
            #if sub_dir.startswith('iteration_') or sub_dir.startswith('lrm_') or sub_dir.startswith('test_') or sub_dir.startswith('manual_mem'):
            if sub_dir.startswith('iteration_') or sub_dir.startswith('test_') or sub_dir.startswith('manual_mem'):
                    main_loop=True
                    print(f"Processing.....{log_dir_location}/{sub_dir}")
                    list_files = os.listdir(f"{log_dir_location}/{sub_dir}")
                    for f in list_files:
                        if f.startswith(f"{host_name}") and f.endswith(".log"):
                            se = re.compile(f"{host_name}.{sub_dir}.(.*).log")
                            m = se.search(f)
                            stamp = m.group(1)
                            tags[sub_dir]= stamp
                            #tags_list.append(f"{sub_dir}")  
                            with open(f"{log_dir_location}/{sub_dir}/{f}") as R:
                                lines = R.readlines()
                                i = 0
                                try:
                                    while i<len(lines):
                                        re_main_match_str = re_main_match.search(lines[i])
                                        if re_main_match_str:
                                            if RE_TIME_STAMP_SEARCH.search(lines[i]):
                                               
                                                r_found = RE_TIME_STAMP_SEARCH.search(lines[i])
                                                time_stamp = r_found.group(1)
                                                t_title = ''
                                                t_title = re.sub('_config','',sub_dir)
                                                t_title = re.sub('_test','',t_title)
                                                tags_list.append(f"{time_stamp}({t_title})")
                                            i+=3
                                            while True:
                                                
                                                re_sub_match_str = re_generic_match.search(lines[i])
                                                
                                                
                                                if re_sub_match_str:
                                                   
                                                    
                                                    m_mem_string = re_sub_match_str.group(2)
                                                   
                                                    
                                                    if m_mem_string in re_sub_match_dict.keys():
                                                        
                                                        re_m_mem_match_str = re_sub_match_dict[m_mem_string].search(lines[i])
                                                        
                                                        if re_m_mem_match_str:
                                                            
                                                            key = f"{re_m_mem_match_str.group(1)}_{m_mem_string}"
                                                            if key not in mem_track:
                                                                mem_track[key]=[int(re_m_mem_match_str.group(2))]
                                                            else:
                                            
                                                                mem_track[key].append(int(re_m_mem_match_str.group(2)))
                                                if "-----------------------------------------------------------" in lines[i]:
                                                    
                                                    main_loop=False
                                                    break
                                                i+=1
                                        i+=1
                                        if not main_loop:
                                            break
                                except IndexError:
                                    pass
                                
        
        logging.info(f"Collecting of 'show npu memory info' o/p data of host:{host_name} for the node:{node} of collection type({collection_types} is completed\n")
        plot_mem_graph={}
        if mem_track:
            for k,v in mem_track.items():
                val = [ int(x) for x in v]
                if len(val) == len(tags_list):
                    plot_mem_graph[k]=val
            key=f'{d_string} on {node}-{host_name}'
            self.global_resource_data[key]= plot_mem_graph 
            self.global_resource_labels_x_axis[key]=tags_list
            self.y_axis_label[key]=f'npu memory util (%))'
            self.paper_color[key] = '#b2b2b1'
            self.paper_color[key] = '#ecf0f1'
        if self.global_view and mem_track:
            self.scenario_data[host_name][scenario][key]={}
            self.scenario_data[host_name][scenario][key]['_resource_data']=self.global_resource_data[key]
            self.scenario_data[host_name][scenario][key]['_resource_labels_x_axis']=self.global_resource_labels_x_axis[key]
            self.scenario_data[host_name][scenario][key]['_y_axis_label']=self.y_axis_label[key]
            self.scenario_data[host_name][scenario][key]['_paper_color']= self.paper_color[key]
            

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
                        if f.startswith(f"{host_name}") and f.endswith(".log"):
                            se = re.compile(f"{host_name}.{sub_dir}.(.*).log")
                            m = se.search(f)
                            stamp = m.group(1)
                            tags[sub_dir]= stamp
                            #tags_list.append(f"{sub_dir}")  
                            with open(f"{log_dir_location}/{sub_dir}/{f}") as R:
                                lines = R.readlines()
                                i = 0
                                while i<len(lines):
                                    re_main_match_str = re_main_match.search(lines[i])
                                    if re_main_match_str:
                                        if RE_TIME_STAMP_SEARCH.search(lines[i]):
                                           
                                            r_found = RE_TIME_STAMP_SEARCH.search(lines[i])
                                            time_stamp = r_found.group(1)
                                            #tags_list.append(f"{time_stamp}")
                                            t_title = ''
                                            t_title = re.sub('_config','',sub_dir)
                                            t_title = re.sub('_test','',t_title)
                                            tags_list.append(f"{time_stamp}({t_title})")
                                        i+=1
                                        while True:
                                            if i >= len(lines):
                                                break
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
                                                    if i >= len(lines):
                                                        break
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
        self.paper_color[key] = '#ecf0f1'
        
        logging.info(f"Collecting of 'show system process extensive' o/p data of host:{host_name} for the node:{node} is completed\n")
        if self.global_view:
            self.scenario_data[host_name][scenario][key]={}
            self.scenario_data[host_name][scenario][key]['_resource_data']=self.global_resource_data[key]
            self.scenario_data[host_name][scenario][key]['_resource_labels_x_axis']=self.global_resource_labels_x_axis[key]
            self.scenario_data[host_name][scenario][key]['_y_axis_label']=self.y_axis_label[key]
            self.scenario_data[host_name][scenario][key]['_paper_color']= self.paper_color[key]

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
                        if f.startswith(f"{host_name}") and f.endswith(".log"):
                            se = re.compile(f"{host_name}.{sub_dir}.(.*).log")
                            m = se.search(f)
                            stamp = m.group(1)
                            tags[sub_dir]= stamp
                            #tags_list.append(f"{sub_dir}")  
                            with open(f"{log_dir_location}/{sub_dir}/{f}") as R:
                                lines = R.readlines()
                                i = 0
                                re_sub=None
                                while i<len(lines):
                                    re_main_match_str = re_main_match.search(lines[i])
                                    if re_main_match_str:
                                        if RE_TIME_STAMP_SEARCH.search(lines[i]):
                                           
                                            r_found = RE_TIME_STAMP_SEARCH.search(lines[i])
                                            time_stamp = r_found.group(1)
                                            t_title = ''
                                            t_title = re.sub('_config','',sub_dir)
                                            t_title = re.sub('_test','',t_title)
                                            tags_list.append(f"{time_stamp}({t_title})")
                                        i+=1
                                        while True:
                                            for j in range(i,i+4):
                                                re_sub_match1_str = re_sub_match1.search(lines[j])
                                                #re_sub_match2_str = re_sub_match2.search(lines[j])
                                                re_sub_match3_str = re_sub_match3.search(lines[j])
                                                if re_sub_match1_str:
                                                    re_sub=re_sub_match1_str
                                                #if re_sub_match2_str:
                                                #    re_sub=re_sub_match2_str
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
                                                #elif re_sub_match2_str:
                                                #    if 'MemFree' not in mem_track:
                                                #        mem_track['MemFree']=[mb]
                                                #    else:
                                                #        mem_track['MemFree'].append(mb)
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
        #self.graph_type[key]='bar'
        self.paper_color[key] = '#e4fadc'
        self.paper_color[key] = '#ecf0f1'
        
        logging.info(f"Collecting of 'cat /proc/meminfo' o/p data of host:{host_name} for the node:{node} is completed\n")
        if self.global_view:
            self.scenario_data[host_name][scenario][key]={}
            self.scenario_data[host_name][scenario][key]['_resource_data']=self.global_resource_data[key]
            self.scenario_data[host_name][scenario][key]['_resource_labels_x_axis']=self.global_resource_labels_x_axis[key]
            self.scenario_data[host_name][scenario][key]['_y_axis_label']=self.y_axis_label[key]
            self.scenario_data[host_name][scenario][key]['_paper_color']= self.paper_color[key]


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
                        if f.startswith(f"{host_name}") and f.endswith(".log"):
                            se = re.compile(f"{host_name}.{sub_dir}.(.*).log")
                            m = se.search(f)
                            stamp = m.group(1)
                            tags[sub_dir]= stamp
                            #tags_list.append(f"{sub_dir}")  
                            with open(f"{log_dir_location}/{sub_dir}/{f}") as R:
                                lines = R.readlines()
                                i = 0
                                re_sub=None
                                try:
                                    while i<len(lines):
                                        re_main_match_str = re_main_match.search(lines[i])
                                        if re_main_match_str:
                                            if RE_TIME_STAMP_SEARCH.search(lines[i]):
                                               
                                                r_found = RE_TIME_STAMP_SEARCH.search(lines[i])
                                                time_stamp = r_found.group(1)
                                                t_title = ''
                                                t_title = re.sub('_config','',sub_dir)
                                                t_title = re.sub('_test','',t_title)
                                                tags_list.append(f"{time_stamp}({t_title})")
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
        self.paper_color[key] = '#ecf0f1'
        if self.global_view:
            self.scenario_data[host_name][scenario][key]={}
            self.scenario_data[host_name][scenario][key]['_resource_data']=self.global_resource_data[key]
            self.scenario_data[host_name][scenario][key]['_resource_labels_x_axis']=self.global_resource_labels_x_axis[key]
            self.scenario_data[host_name][scenario][key]['_y_axis_label']=self.y_axis_label[key]
            self.scenario_data[host_name][scenario][key]['_paper_color']= self.paper_color[key]

        logging.info(f"Collecting of 'show system storage' o/p data of host:{host_name} for the node:{node} is completed...\n")
    
    def parse_junos_show_heap_output(self, log_dir_location:str, host_name:str, node: str, scenario=None) -> None:
    
        dir_list=os.listdir(f"{log_dir_location}")
        junos_heap_track={}
        tags = {}
        tags_list = []
        
        if 'FPC' in node:
    
            re_match = re.compile(f"\[{node}\]\s+\[CMD\]\s+show\s+heap$")

        logging.info(f'Collecting of show heap output data for host:{host_name} and node {node} is started...')
        for sub_dir in dir_list:
            if sub_dir.startswith('iteration_') or sub_dir.startswith('lrm_') or sub_dir.startswith('test_') or sub_dir.startswith('manual_mem'):
                    main_loop=1
                    list_files = os.listdir(f"{log_dir_location}/{sub_dir}")
                    for f in list_files:
                        if f.startswith(f"{host_name}") and f.endswith(".log"):
                            se = re.compile(f"{host_name}.{sub_dir}.(.*).log")
                            m = se.search(f)
                            stamp = m.group(1)
                            tags[sub_dir]= stamp
                            #tags_list.append(f"{sub_dir}_{stamp}")  
                            #tags_list.append(f"{sub_dir}")  
                            with open(f"{log_dir_location}/{sub_dir}/{f}") as R:
                                lines = R.readlines()
                                i = 0
                                while i < len(lines):
                                    
                                    if re_match.search(lines[i]):
                          
                                        if RE_TIME_STAMP_SEARCH.search(lines[i]):
                           
                                               
                                                r_found = RE_TIME_STAMP_SEARCH.search(lines[i])
                                                time_stamp = r_found.group(1)
                                                #tags_list.append(f"{time_stamp}")
                                                t_title = ''
                                                t_title = re.sub('_config','',sub_dir)
                                                t_title = re.sub('_test','',t_title)
                                                tags_list.append(f"{time_stamp}({t_title})")
                               
                                        i+=3
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
        self.paper_color[key] = '#ecf0f1'
       
        
        if self.global_view:
            
            self.scenario_data[host_name][scenario][key]={}
            self.scenario_data[host_name][scenario][key]['_resource_data']=self.global_resource_data[key]
            self.scenario_data[host_name][scenario][key]['_resource_labels_x_axis']=self.global_resource_labels_x_axis[key]
            self.scenario_data[host_name][scenario][key]['_y_axis_label']=self.y_axis_label[key]
            self.scenario_data[host_name][scenario][key]['_paper_color']= self.paper_color[key]
        logging.info(f'Collecting of show heap output for host:{host_name} and node {node} is completed\n')
    
    
    def parse_junos_show_process_extensive(self, log_dir_location:str, host_name:str, node:str='RE', scenario=None) -> None:
    
        dir_list=os.listdir(f"{log_dir_location}")
        junos_show_process_track={}
        tags = {}
        tags_list = []
        if 'RE' in node:
            re_match = re.compile(f"\[{host_name}\]\s+\[CMD]\s+show\s+system\s+process\s+extensive")
            
       
        
        logging.info(f'Collecting of show system process extensive output data for host:{host_name} and node {node} is started...')
        for sub_dir in dir_list:
            if sub_dir.startswith('iteration_') or sub_dir.startswith('lrm_') or sub_dir.startswith('test_') or sub_dir.startswith('manual_mem'):
                    main_loop=1
                    list_files = os.listdir(f"{log_dir_location}/{sub_dir}")
                    for f in list_files:
                        if f.startswith(f"{host_name}") and f.endswith(".log"):
                            se = re.compile(f"{host_name}.{sub_dir}.(.*).log")
                            m = se.search(f)
                            stamp = m.group(1)
                            tags[sub_dir]= stamp
                            #tags_list.append(f"{sub_dir}_{stamp}")  
                            #tags_list.append(f"{sub_dir}")  
                            with open(f"{log_dir_location}/{sub_dir}/{f}") as R:
                                lines = R.readlines()
                                i = 0
                            
                                while i < len(lines):   
                                    if re_match.search(lines[i]):
                                        
                                        if RE_TIME_STAMP_SEARCH.search(lines[i]):
                                               
                                                r_found = RE_TIME_STAMP_SEARCH.search(lines[i])
                                                time_stamp = r_found.group(1)
                                                #tags_list.append(f"{time_stamp}")
                                                t_title = ''
                                                t_title = re.sub('_config','',sub_dir)
                                                t_title = re.sub('_test','',t_title)
                                                tags_list.append(f"{time_stamp}({t_title})")
                                        else:
                                            #tags_list.append(f"{sub_dir}")
                                            t_title = ''
                                            t_title = re.sub('_config','',sub_dir)
                                            t_title = re.sub('_test','',t_title)
                                            tags_list.append(f"({t_title})")
                                            
                                       
                                        i+=3
                                        while True:   
                                            found = re.search(r"\d+\s+\S+\s+\d+\s+\S+\s+\w+\s+\w+\s+\w+\s+\w+\s+\S+\s+([+-]?[0-9]*[.]?[0-9]+)%(\s+.*)",lines[i])
                                            #print(found)
                                            if found:
                                                percent = float(found.group(1))
                                                name = found.group(2)
                                                if (isinstance(percent, float) and percent == 0.0 or 'idle' in name):
                                                    i+=1
                                                    continue
                                                if name not in junos_show_process_track:
                                                    junos_show_process_track[name] = [percent]
                                                   
                                                else:
                                                    junos_show_process_track[name].append(percent)
                                            if "-----------------------------------------------------------" in lines[i] or i > len(lines):
                                                break
                                            i+=1
                                    i+=1
                                    
                                    
        plot_junos_show_process_graph={}
        print (junos_show_process_track)
        
        for k,v in junos_show_process_track.items():
            
            val = [ float(x) for x in v]
            if len(val) == len(tags_list):
                plot_junos_show_process_graph[k]=val
       
         

        key = f'CPU usage {node}-{host_name}'
        self.global_resource_data[key]=  plot_junos_show_process_graph 
        self.global_resource_labels_x_axis[key]=tags_list
        self.y_axis_label[key]=f'CPU usage(%)'
        #self.graph_type[f'System Storage(tmpfs) Usage on {node}-{host_name}']='bar'
        self.paper_color[key] = '#9A9AA3'
        self.paper_color[key] = '#ecf0f1'
       
        
        if self.global_view:
            
            self.scenario_data[host_name][scenario][key]={}
            self.scenario_data[host_name][scenario][key]['_resource_data']=self.global_resource_data[key]
            self.scenario_data[host_name][scenario][key]['_resource_labels_x_axis']=self.global_resource_labels_x_axis[key]
            self.scenario_data[host_name][scenario][key]['_y_axis_label']=self.y_axis_label[key]
            self.scenario_data[host_name][scenario][key]['_paper_color']= self.paper_color[key]
        logging.info(f'Collecting of show system process extensive output data for host host:{host_name} and node {node} is completed\n')
    
    def collect_data_from_show_task_memory_detail(self, log_dir_location:str, host_name:str, scenario=None):
        
        dir_list=os.listdir(f"{log_dir_location}")
        show_task_memory={}
        tags = {}
        tags_list = []
        
        re_match = re.compile(f"\[{host_name}\]\s+\[CMD]\s+show\s+task\s+memory\s+detail")
        re_sub_match = re.compile(r"Total\sbytes\sin\suse:\s+(\d+)\s+\(")
            
       
        
        logging.info(f'Collecting of show system task memory detail for host:{host_name} is started...')
        for sub_dir in dir_list:
            if sub_dir.startswith('iteration_') or sub_dir.startswith('lrm_') or sub_dir.startswith('test_') or sub_dir.startswith('manual_mem'):
                    main_loop=1
                    list_files = os.listdir(f"{log_dir_location}/{sub_dir}")
                    for f in list_files:
                        if f.startswith(f"{host_name}") and f.endswith(".log"):
                            se = re.compile(f"{host_name}.{sub_dir}.(.*).log")
                            m = se.search(f)
                            stamp = m.group(1)
                            tags[sub_dir]= stamp
                            #tags_list.append(f"{sub_dir}_{stamp}")  
                            #tags_list.append(f"{sub_dir}")  
                            with open(f"{log_dir_location}/{sub_dir}/{f}") as R:
                                lines = R.readlines()
                                i = 0
                                try:
                                    while i < len(lines):   
                                        if re_match.search(lines[i]):
                                            if RE_TIME_STAMP_SEARCH.search(lines[i]):
                                               
                                                r_found = RE_TIME_STAMP_SEARCH.search(lines[i])
                                                time_stamp = r_found.group(1)
                                                t_title = ''
                                                t_title = re.sub('_config','',sub_dir)
                                                t_title = re.sub('_test','',t_title)
                                                tags_list.append(f"{time_stamp}({t_title})")
                                                #tags_list.append(f"{time_stamp}")
                                            else:
                                                #tags_list.append(f"{sub_dir}")
                                                t_title = ''
                                                t_title = re.sub('_config','',sub_dir)
                                                t_title = re.sub('_test','',t_title)
                                                tags_list.append(f"({t_title})")
                                            while True:
                                                i+=1
                                                if i >=len(lines):
                                                    break
                                                if re_sub_match.search(lines[i]):
                                                    found=re_sub_match.search(lines[i])
                                                    bytes=int(found.group(1))
                                                    _mb = conv_bytes_to_MB(bytes)
                                                    _gb = conv_MB_to_GB(_mb)
                                                    
                                                    if 'rpd_malloc' not in show_task_memory:
                                                        show_task_memory['rpd_malloc'] = [_gb]
                                                    else:
                                                        show_task_memory['rpd_malloc'].append(_gb)
                                        i+=1
                                except IndexError:
                                    pass
        
        
        plot_show_task_memory_graph={}
    
        for k,v in show_task_memory.items():
            
            val = [ float(x) for x in v]
            if len(val) == len(tags_list):
                plot_show_task_memory_graph[k]=val
       
         
        
        key = f'RPD Malloc Allocation-{host_name}'
        self.global_resource_data[key]=  plot_show_task_memory_graph 
        self.global_resource_labels_x_axis[key]=tags_list
        self.y_axis_label[key]=f'RPD Malloc Allocation(GB)'
        self.paper_color[key] = '#F0F0FF'
        self.paper_color[key] = '#ecf0f1'

        
        if self.global_view:
            
            self.scenario_data[host_name][scenario][key]={}
            self.scenario_data[host_name][scenario][key]['_resource_data']=self.global_resource_data[key]
            self.scenario_data[host_name][scenario][key]['_resource_labels_x_axis']=self.global_resource_labels_x_axis[key]
            self.scenario_data[host_name][scenario][key]['_y_axis_label']=self.y_axis_label[key]
            self.scenario_data[host_name][scenario][key]['_paper_color']= self.paper_color[key]
        logging.info(f'Collecting of show task memory detail for host:{host_name} is completed\n')                              
                                        
    
    def collect_show_platform_distributor_statistics(self, log_dir_location:str, host_name:str,scenario=None) -> None:
    
        dir_list=os.listdir(f"{log_dir_location}")
        evo_show_platform_distributor_track={}
        tags = {}
        tags_list = []
     
        re_match = re.compile(f"\[{host_name}\]\s+\[CMD]\s+show\s+platform\s+distributor\s+statistics\s+summary")
            
       
        
        logging.info(f'Collecting of show platform distributor statistics summary output data for host:{host_name} is started...')
        for sub_dir in dir_list:
            
            if sub_dir.startswith('iteration_') or sub_dir.startswith('lrm_') or sub_dir.startswith('test_') or sub_dir.startswith('manual_mem'):
                   
                    main_loop=True
                    list_files = os.listdir(f"{log_dir_location}/{sub_dir}")
                    for f in list_files:
                        if f.startswith(f"{host_name}") and f.endswith(".log"):
                            se = re.compile(f"{host_name}.{sub_dir}.(.*).log")
                            m = se.search(f)
                            stamp = m.group(1)
                            tags[sub_dir]= stamp
                            #tags_list.append(f"{sub_dir}_{stamp}")  
                            #tags_list.append(f"{sub_dir}")  
                            with open(f"{log_dir_location}/{sub_dir}/{f}") as R:
                                lines = R.readlines()
                                i = 0
                            
                                while i < len(lines):   
                                    if re_match.search(lines[i]):
                                        if RE_TIME_STAMP_SEARCH.search(lines[i]):                                               
                                                r_found = RE_TIME_STAMP_SEARCH.search(lines[i])
                                                time_stamp = r_found.group(1)
                                                #tags_list.append(f"{time_stamp}")
                                                t_title = ''
                                                t_title = re.sub('_config','',sub_dir)
                                                t_title = re.sub('_test','',t_title)
                                                tags_list.append(f"{time_stamp}({t_title})")
                                        else:
                                            #tags_list.append(f"{sub_dir}")
                                            t_title = ''
                                            t_title = re.sub('_config','',sub_dir)
                                            t_title = re.sub('_test','',t_title)
                                            tags_list.append(f"({t_title})")
                                        i+=3
                                        while True:                                       
                                            found = re.search(r"Node:\s+(\S+)",lines[i])                                           
                                            if found:
                                                node=found.group(1)
                                            found1 = re.search(r"SDB\s+live\s+objects\s+:\s+(\d+)",lines[i])                              
                                            if found1:                                          
                                                objects = found1.group(1)
                                                if node:                                                                             
                                                    if node not in evo_show_platform_distributor_track:
                                                        evo_show_platform_distributor_track[node] = [objects]                                                       
                                                    else:
                                                        evo_show_platform_distributor_track[node].append(objects)
                                            if "-----------------------------------------------------------" in lines[i] or i > len(lines):
                                                main_loop=False
                                                break
                                            i+=1
                                       
                                    if not main_loop:
                                       
                                        break
                                    i+=1
                                    
                                    
        plot_show_platform_distributor_graph={}


        for k,v in evo_show_platform_distributor_track.items():
            plot_show_platform_distributor_graph={}
            val = [ float(x) for x in v]
            if len(val) == len(tags_list):
                plot_show_platform_distributor_graph[k]=val
            key = f'SDB live objects {k}-{host_name}'
            self.global_resource_data[key]=  plot_show_platform_distributor_graph 
            self.global_resource_labels_x_axis[key]=tags_list
            self.y_axis_label[key]=f'Number of SDB Live Objects'
            #self.graph_type[f'System Storage(tmpfs) Usage on {node}-{host_name}']='bar'
            self.paper_color[key] = '#9A9AA3'
            self.paper_color[key] = '#ecf0f1'
           
            
            if self.global_view:
                
                self.scenario_data[host_name][scenario][key]={}
                self.scenario_data[host_name][scenario][key]['_resource_data']=self.global_resource_data[key]
                self.scenario_data[host_name][scenario][key]['_resource_labels_x_axis']=self.global_resource_labels_x_axis[key]
                self.scenario_data[host_name][scenario][key]['_y_axis_label']=self.y_axis_label[key]
                self.scenario_data[host_name][scenario][key]['_paper_color']= self.paper_color[key]
        logging.info(f'Collecting of show platform distributor statistics summary output data for host:{host_name} is completed\n')    
    
    
    def collect_show_platform_distributor_statistics_all_clients(self, log_dir_location:str, host_name:str,scenario=None) -> None:
    
        dir_list=os.listdir(f"{log_dir_location}")
        evo_show_platform_distributor_cleints_track={}
        tags = {}
        tags_list = []
     
        re_match = re.compile(f"\[{host_name}\]\s+\[CMD]\s+show\s+platform\s+distributor\s+statistics\s+all-clients")                     
        logging.info(f'Collecting of show platform distributor statistics all-clients output data for host:{host_name} is started...')
        for sub_dir in dir_list:
            
            if sub_dir.startswith('iteration_') or sub_dir.startswith('lrm_') or sub_dir.startswith('test_') or sub_dir.startswith('manual_mem'):
                   
                    main_loop=True
                    list_files = os.listdir(f"{log_dir_location}/{sub_dir}")
                    for f in list_files:
                        if f.startswith(f"{host_name}") and f.endswith(".log"):
                            se = re.compile(f"{host_name}.{sub_dir}.(.*).log")
                            m = se.search(f)
                            stamp = m.group(1)
                            tags[sub_dir]= stamp
                            #tags_list.append(f"{sub_dir}_{stamp}")  
                            #tags_list.append(f"{sub_dir}")  
                            with open(f"{log_dir_location}/{sub_dir}/{f}") as R:
                                lines = R.readlines()
                                i = 0
                            
                                while i < len(lines):   
                                    if re_match.search(lines[i]):
                                        
                                        if RE_TIME_STAMP_SEARCH.search(lines[i]):
                                               
                                                r_found = RE_TIME_STAMP_SEARCH.search(lines[i])
                                                time_stamp = r_found.group(1)
                                                #tags_list.append(f"{time_stamp}")
                                                t_title = ''
                                                t_title = re.sub('_config','',sub_dir)
                                                t_title = re.sub('_test','',t_title)
                                                tags_list.append(f"{time_stamp}({t_title})")
                                        else:
                                            #tags_list.append(f"{sub_dir}")
                                            t_title = ''
                                            t_title = re.sub('_config','',sub_dir)
                                            t_title = re.sub('_test','',t_title)
                                            tags_list.append(f"({t_title})")
                                            
                                       
                                        i+=3
                                        node = None
                                        client = None
                                        while True: 
                                            found1 = re.search(r"Node:\s+(\S+)",lines[i])
                                            found2 = re.search(r"Client\s+\d+\s+\((\S+)\)", lines[i])
                                            found3 = re.search(r"SDB\s+object\s+holds\s+total\s+:\s+(\d+)",lines[i])
                                            
                                            if found1:
                                                node=found1.group(1)
                                            elif found2:
                                                 client=found2.group(1)
                                            elif found3:
                                                objects = found3.group(1)
                                                if int(objects) > 0:
                                                    if node and client:          
                                                        if node not in evo_show_platform_distributor_cleints_track:
                                                            evo_show_platform_distributor_cleints_track[node] = {}
                                                        if client not in evo_show_platform_distributor_cleints_track[node]:
                                                            evo_show_platform_distributor_cleints_track[node][client] = [objects]
                                                           
                                                        else:
                                                            evo_show_platform_distributor_cleints_track[node][client].append(objects)
                                                        node=None
                                                        client=None
                                                       
                                            if "-----------------------------------------------------------" in lines[i] or i > len(lines):
                                                main_loop=False
                                                break
                                            i+=1
                                       
                                    if not main_loop:
                                       
                                        break
                                    i+=1
                                    
                                    


        
        for k in evo_show_platform_distributor_cleints_track.keys():
            plot_show_platform_distributor_cleints_graph={}
            for k1,v in evo_show_platform_distributor_cleints_track[k].items():
                val = [ float(x) for x in v]
                if len(val) == len(tags_list):
                    plot_show_platform_distributor_cleints_graph[k1]=val
            
            key = f'SDB object holds total on node:{k}-{host_name}'
            self.global_resource_data[key]=  plot_show_platform_distributor_cleints_graph 
            self.global_resource_labels_x_axis[key]=tags_list
            self.y_axis_label[key]=f'Number of SDB object holds total' 
            #self.graph_type[f'System Storage(tmpfs) Usage on {node}-{host_name}']='bar'
            self.paper_color[key] = '#9A9AA3'
            self.paper_color[key] = '#ecf0f1'
           
            
            if self.global_view:
                
                self.scenario_data[host_name][scenario][key]={}
                self.scenario_data[host_name][scenario][key]['_resource_data']=self.global_resource_data[key]
                self.scenario_data[host_name][scenario][key]['_resource_labels_x_axis']=self.global_resource_labels_x_axis[key]
                self.scenario_data[host_name][scenario][key]['_y_axis_label']=self.y_axis_label[key]
                self.scenario_data[host_name][scenario][key]['_paper_color']= self.paper_color[key]
        logging.info(f'Collecting of show platform distributor statistics all-clients output data for host:{host_name} is completed\n')
        
    def collect_show_platform_distributor_statistics_sdb_current_holds(self, log_dir_location:str, host_name:str,scenario=None) -> None:
    
        dir_list=os.listdir(f"{log_dir_location}")
        evo_show_platform_distributor_track={}
        tags = {}
        tags_list = []
     
        re_match = re.compile(f"\[{host_name}\]\s+\[CMD]\s+show\s+platform\s+distributor\s+statistics\s+summary")
            
       
        
        logging.info(f'Collecting of show platform distributor statistics summary output data for host:{host_name} is started...')
        for sub_dir in dir_list:
            
            if sub_dir.startswith('iteration_') or sub_dir.startswith('lrm_') or sub_dir.startswith('test_') or sub_dir.startswith('manual_mem'):
                   
                    main_loop=True
                    list_files = os.listdir(f"{log_dir_location}/{sub_dir}")
                    for f in list_files:
                        if f.startswith(f"{host_name}") and f.endswith(".log"):
                            se = re.compile(f"{host_name}.{sub_dir}.(.*).log")
                            m = se.search(f)
                            stamp = m.group(1)
                            tags[sub_dir]= stamp
                            #tags_list.append(f"{sub_dir}_{stamp}")  
                            #tags_list.append(f"{sub_dir}")  
                            with open(f"{log_dir_location}/{sub_dir}/{f}") as R:
                                lines = R.readlines()
                                i = 0
                            
                                while i < len(lines):   
                                    if re_match.search(lines[i]):
                                        
                                        if RE_TIME_STAMP_SEARCH.search(lines[i]):
                                               
                                                r_found = RE_TIME_STAMP_SEARCH.search(lines[i])
                                                time_stamp = r_found.group(1)
                                                #tags_list.append(f"{time_stamp}")
                                                t_title = ''
                                                t_title = re.sub('_config','',sub_dir)
                                                t_title = re.sub('_test','',t_title)
                                                tags_list.append(f"{time_stamp}({t_title})")
                                        else:
                                            #tags_list.append(f"{sub_dir}")
                                            t_title = ''
                                            t_title = re.sub('_config','',sub_dir)
                                            t_title = re.sub('_test','',t_title)
                                            tags_list.append(f"({t_title})")
                                            
                                       
                                        i+=3
                                        while True: 
                                      
                                            found = re.search(r"Node:\s+(\S+)",lines[i])
                                            
                                            if found:
                                                node=found.group(1)
                                            #found1 = re.search(r"SDB\s+live\s+objects\s+:\s+(\d+)",lines[i])
                                            found1 = re.search(r"SDB\s+object\s+current\s+holds\s+:\s+(\d+)",lines[i])
                              
                                            if found1:
                                          
                                                objects = found1.group(1)
                                                if node:
                                                                             
                                                    if node not in evo_show_platform_distributor_track:
                                                        evo_show_platform_distributor_track[node] = [objects]
                                                       
                                                    else:
                                                        evo_show_platform_distributor_track[node].append(objects)
                                            if "-----------------------------------------------------------" in lines[i] or i > len(lines):
                                                main_loop=False
                                                break
                                            i+=1
                                       
                                    if not main_loop:
                                       
                                        break
                                    i+=1
                                    
                                    
        plot_show_platform_distributor_graph={}

       
        for k,v in evo_show_platform_distributor_track.items():
            plot_show_platform_distributor_graph={}
            val = [ float(x) for x in v]
            if len(val) == len(tags_list):
                plot_show_platform_distributor_graph[k]=val
            key = f'SDB object current holds {k}-{host_name}'
            self.global_resource_data[key]=  plot_show_platform_distributor_graph 
            self.global_resource_labels_x_axis[key]=tags_list
            self.y_axis_label[key]=f'Number of SDB object current holds'
            #self.graph_type[f'System Storage(tmpfs) Usage on {node}-{host_name}']='bar'
            self.paper_color[key] = '#9A9AA3'
            self.paper_color[key] = '#ecf0f1'
           
            
            if self.global_view:
                
                self.scenario_data[host_name][scenario][key]={}
                self.scenario_data[host_name][scenario][key]['_resource_data']=self.global_resource_data[key]
                self.scenario_data[host_name][scenario][key]['_resource_labels_x_axis']=self.global_resource_labels_x_axis[key]
                self.scenario_data[host_name][scenario][key]['_y_axis_label']=self.y_axis_label[key]
                self.scenario_data[host_name][scenario][key]['_paper_color']= self.paper_color[key]
        logging.info(f'Collecting of show platform distributor statistics summary output data for host:{host_name} is completed\n')    
    
    
    def collect_show_platform_distributor_statistics_all_clients_sdb_current_holds(self, log_dir_location:str, host_name:str,scenario=None) -> None:
    
        dir_list=os.listdir(f"{log_dir_location}")
        evo_show_platform_distributor_cleints_track={}
        tags = {}
        tags_list = []
     
        re_match = re.compile(f"\[{host_name}\]\s+\[CMD]\s+show\s+platform\s+distributor\s+statistics\s+all-clients")
            
       
        
        logging.info(f'Collecting of show platform distributor statistics all-clients output data for host:{host_name} is started...')
        for sub_dir in dir_list:
            
            if sub_dir.startswith('iteration_') or sub_dir.startswith('lrm_') or sub_dir.startswith('test_') or sub_dir.startswith('manual_mem'):
                   
                    main_loop=True
                    list_files = os.listdir(f"{log_dir_location}/{sub_dir}")
                    for f in list_files:
                        if f.startswith(f"{host_name}") and f.endswith(".log"):
                            se = re.compile(f"{host_name}.{sub_dir}.(.*).log")
                            m = se.search(f)
                            stamp = m.group(1)
                            tags[sub_dir]= stamp
                            #tags_list.append(f"{sub_dir}_{stamp}")  
                            #tags_list.append(f"{sub_dir}")  
                            with open(f"{log_dir_location}/{sub_dir}/{f}") as R:
                                lines = R.readlines()
                                i = 0
                            
                                while i < len(lines):   
                                    if re_match.search(lines[i]):
                                        
                                        if RE_TIME_STAMP_SEARCH.search(lines[i]):
                                               
                                                r_found = RE_TIME_STAMP_SEARCH.search(lines[i])
                                                time_stamp = r_found.group(1)
                                                #tags_list.append(f"{time_stamp}")
                                                t_title = ''
                                                t_title = re.sub('_config','',sub_dir)
                                                t_title = re.sub('_test','',t_title)
                                                tags_list.append(f"{time_stamp}({t_title})")
                                        else:
                                            #tags_list.append(f"{sub_dir}")
                                            t_title = ''
                                            t_title = re.sub('_config','',sub_dir)
                                            t_title = re.sub('_test','',t_title)
                                            tags_list.append(f"({t_title})")
                                            
                                       
                                        i+=3
                                        node = None
                                        client = None
                                        while True: 
                                            found1 = re.search(r"Node:\s+(\S+)",lines[i])
                                            found2 = re.search(r"Client\s+\d+\s+\((\S+)\)", lines[i])
                                            #found3 = re.search(r"SDB\s+object\s+holds\s+total\s+:\s+(\d+)",lines[i])
                                            #SDB object current holds 
                                            found3 = re.search(r"SDB\s+object\s+current\s+holds\s+:\s+(\d+)",lines[i])
                                            
                                            if found1:
                                                node=found1.group(1)
                                            elif found2:
                                                 client=found2.group(1)
                                            elif found3:
                                                objects = found3.group(1)
                                                if int(objects) > 0:
                                                    if node and client:          
                                                        if node not in evo_show_platform_distributor_cleints_track:
                                                            evo_show_platform_distributor_cleints_track[node] = {}
                                                        if client not in evo_show_platform_distributor_cleints_track[node]:
                                                            evo_show_platform_distributor_cleints_track[node][client] = [objects]
                                                           
                                                        else:
                                                            evo_show_platform_distributor_cleints_track[node][client].append(objects)
                                                        node=None
                                                        client=None
                                                       
                                            if "-----------------------------------------------------------" in lines[i] or i > len(lines):
                                                main_loop=False
                                                break
                                            i+=1
                                       
                                    if not main_loop:
                                       
                                        break
                                    i+=1
                                    
                                    


        
        for k in evo_show_platform_distributor_cleints_track.keys():
            plot_show_platform_distributor_cleints_graph={}
            for k1,v in evo_show_platform_distributor_cleints_track[k].items():
                val = [ float(x) for x in v]
                if len(val) == len(tags_list):
                    plot_show_platform_distributor_cleints_graph[k1]=val
            
            key = f'SDB object current holds on node:{k}-{host_name}'
            self.global_resource_data[key]=  plot_show_platform_distributor_cleints_graph 
            self.global_resource_labels_x_axis[key]=tags_list
            self.y_axis_label[key]=f'Number of SDB object current holds' 
            #self.graph_type[f'System Storage(tmpfs) Usage on {node}-{host_name}']='bar'
            self.paper_color[key] = '#9A9AA3'
            self.paper_color[key] = '#ecf0f1'
           
            
            if self.global_view:
                
                self.scenario_data[host_name][scenario][key]={}
                self.scenario_data[host_name][scenario][key]['_resource_data']=self.global_resource_data[key]
                self.scenario_data[host_name][scenario][key]['_resource_labels_x_axis']=self.global_resource_labels_x_axis[key]
                self.scenario_data[host_name][scenario][key]['_y_axis_label']=self.y_axis_label[key]
                self.scenario_data[host_name][scenario][key]['_paper_color']= self.paper_color[key]
        logging.info(f'Collecting of show platform distributor statistics all-clients output data for host:{host_name} is completed\n')    
            
            
    def plot_graph_for_all_global_iterations_dashboard(self,out_dir: str):

        iterations = self.get_global_iterations(log_dir_location=f"{out_dir}")
       
        
        for top_dir in iterations:
            self.global_iter_data[top_dir] = {}
            self.global_iter_data[top_dir]['scenario1'] = []
            self.global_iter_data[top_dir]['scenario2'] = []   
            
    def plot_graph_for_single_global_iteation_dashboard(self, out_dir:str, host_name:str, platform:str, version:str, lrm_view:bool, rtr:str='', url:str=''):
        
        
        # fix for multiple host
        _scenario_data=self.scenario_data[host_name]
        plot_mem_graph = {}
        tags_list = []
        
        _resource_data_list = []
        sub_dict_list = []
        new_tags = []
        for k in _scenario_data.keys(): 
            sub_dict = self.tree_traverse(_scenario_data,k)
            sub_dict_list.append(sub_dict)
            new_tags = [ f"{x}_{k}" for x in self.tree_traverse(sub_dict,'_resource_labels_x_axis') ]
           
            tags_list.extend(new_tags)
   
    
        t_keys = sub_dict_list[0].keys()
        t_key_dict = {}
       
        for j, t_key in enumerate(t_keys):
            t_key_dict = {}
            t_key_list = []
            new_tags_list = []
            for i in range(0, len(sub_dict_list)):
                t_key_list.append(sub_dict_list[i][t_key].get('_resource_data', None))
                y_axis_label = sub_dict_list[i][t_key].get('_y_axis_label', None)
                paper_color = sub_dict_list[i][t_key].get('_paper_color',None)
                test_id=i+1
                new_tags = [ f"{x}_{test_id}" for x in self.tree_traverse(sub_dict_list[i][t_key],'_resource_labels_x_axis') ]  
                new_tags_list.extend(new_tags)      
                t_key_dict=self.merge_dict(t_key_dict, t_key_list[i])
            
            
            lrm_indices = [i for i, x in enumerate(new_tags_list) if 'lrm_' in x]
            
            lrm_tags_list = [x for x in new_tags_list if 'lrm_' in x]
           
            lrm_t_key_dict = {}
            lrm_data_set = None
            if lrm_indices:
                
                for lrm_d_key, lng_data_list in t_key_dict.items():
                    
                    try:
                        lrm_data_set = [lng_data_list[_index] for _index in lrm_indices]
                    except IndexError:
                        pass
                    if lrm_data_set:
                        lrm_t_key_dict[lrm_d_key] = lrm_data_set
                
                self.lrm_global_resource_data[t_key] = lrm_t_key_dict
                self.lrm_global_resource_labels_x_axis[t_key] = lrm_tags_list
                self.lrm_y_axis_label[t_key]= y_axis_label
                self.lrm_paper_color[t_key] = paper_color
                
            self.global_resource_data[t_key] = t_key_dict
            self.global_resource_labels_x_axis[t_key]=new_tags_list
            self.y_axis_label[t_key]= y_axis_label
            self.paper_color[t_key] = paper_color

        if not lrm_view: 
               
            self.plot_graph(x_axis=self.global_resource_labels_x_axis, graph_data=self.global_resource_data, out_dir=out_dir, host_name=host_name, platform=platform, version=version, url=url, rtr=rtr)
        else:
            self.plot_graph(x_axis=self.lrm_global_resource_labels_x_axis, graph_data=self.lrm_global_resource_data, out_dir=out_dir, host_name=host_name, platform=platform, version=version, url=url, rtr=rtr)
        
       
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
 
       
    def collect_data_for_dashboard_junos(self, log_dir_location:str, host_name:str, node_dict:Dict, scenario:str):
        
        self.global_view = True
        import re
        scenario = re.sub(r"\S+Test_Scenario",'',scenario)
        fpc_list = []
        re_list = []
        if 'fpc_list' in node_dict:
            for fpc in node_dict['fpc_list']:
                fpc_list.append(f"FPC{fpc}")
        elif 're_list' in node_dict:
            for re in node_dict['re_list']:
                re_list.append(f"RE{re}")
            
        if host_name not in self.scenario_data:
            self.scenario_data[host_name]={}
            
        self.scenario_data[host_name][scenario]={}
        
        
        
        if fpc_list:
            for fpc in fpc_list: 
                self.parse_junos_show_heap_output(log_dir_location=log_dir_location,host_name=host_name,node=fpc,scenario=scenario)
         
        self.parse_junos_show_process_extensive(log_dir_location=log_dir_location,host_name=host_name,node='RE',scenario=scenario)
        
        self.collect_data_from_show_task_memory_detail(log_dir_location=log_dir_location, host_name=host_name,scenario=scenario)
     
        #self.events_report(events_log_dir_location=log_dir_location, scenario=scenario, max_test_id=1)
        
    def collect_data_for_dashboard_evo(self, log_dir_location:str, host_name:str, node_list:List,scenario:str, collection_types=None):
        
        
        self.global_view = True
        
        ps_mem_node_list = ['RE']
        fpc_list  = [x for x in node_list if x.startswith('fpc')]
        ps_mem_node_list.extend(fpc_list)
        
        proc_mem_node_list = ['RE0']
        proc_mem_node_list.extend(fpc_list)
        
        if host_name not in self.scenario_data:
            self.scenario_data[host_name]={}
            
        self.scenario_data[host_name][scenario]={}

        for node in ps_mem_node_list:
            #logging.INFO("Testing...")
            self.parse_ps_mem_output(log_dir_location=log_dir_location,host_name=host_name, node=node,scenario=scenario)
            
        
        self.collect_data_from_jemalloc(log_dir_location=log_dir_location,host_name=host_name, nodes_list=node_list,collection_type='Allocated',scenario=scenario)
        self.collect_data_from_jemalloc(log_dir_location=log_dir_location,host_name=host_name, nodes_list=node_list,collection_type='Resident',scenario=scenario)
      
        if collection_types:
            for node in fpc_list:       
                self.collect_data_from_npu_mem(log_dir_location=log_dir_location,host_name=host_name, node=node.upper(), scenario=scenario, collection_types=collection_types)
        
        for node in node_list:
            self.collect_data_from_show_system_process_extensive(log_dir_location=log_dir_location,host_name=host_name, node=node,scenario=scenario)
            self.collect_data_from_show_system_storage(log_dir_location=log_dir_location,host_name=host_name, node=node,scenario=scenario)
        for node in proc_mem_node_list:
            self.collect_data_from_show_system_proc_mem_info(log_dir_location=log_dir_location,host_name=host_name, node=node,scenario=scenario)
        
        self.collect_data_from_show_task_memory_detail(log_dir_location=log_dir_location, host_name=host_name,scenario=scenario)
        
        self.collect_show_platform_distributor_statistics(log_dir_location=log_dir_location, host_name=host_name,scenario=scenario)
        
        self.collect_show_platform_distributor_statistics_all_clients(log_dir_location=log_dir_location, host_name=host_name,scenario=scenario)
        
        self.collect_show_platform_distributor_statistics_sdb_current_holds(log_dir_location=log_dir_location, host_name=host_name,scenario=scenario)
        
        self.collect_show_platform_distributor_statistics_all_clients_sdb_current_holds(log_dir_location=log_dir_location, host_name=host_name,scenario=scenario)
        
        

                
    def events_report(self, events_log_dir_location:str, test_type:str, max_test_id:int) -> None:
        
        for test_id in range(int(max_test_id)):
            t_id= test_id+1
            sub_log_location=f"{events_log_dir_location}/{test_type}Test_Scenario{t_id}"
            print (sub_log_location)
            f1_name=f"{sub_log_location}/halt-cmds-replay.txt"
            if os.path.isfile(f1_name):
                with open(f1_name) as R:
                    for i,line in enumerate(R):
                        if line:
                            t_data = line.split('|')
                            if t_data[0] not in self.events_data:
                                self.events_data[t_data[0]]=[t_data[-2]]
                            else:
                                self.events_data[t_data[0]].append(t_data[-2])
            for k,v in self.events_data.items():
                t_data = self.events_data[k]
                total_events = len(t_data)
                t_data.sort()
                n = list(k for k,_ in itertools.groupby(t_data))
                unq_len = len(n)
                iterations =total_events//unq_len
                data = []
                for x in n:
                    n_data = ' | '.join(x)
                    if k not in self.events_for_report:
                        self.events_for_report[k]={}
                        self.events_for_report[k]['events'] = [n_data]
                    else:
                        self.events_for_report[k]['events'].append(n_data)
                self.events_for_report[k]['iters'] = iterations
            


if __name__ == "__main__":
    

    evo = Dashboard()
    #junos = Dashboard()

    #BASE_DIR = '/volume/regressions/results/JUNOS/HEAD/mmahadevaswa/longevity'
    #scenario_list =['ActiveTest_Scenario1','ActiveTest_Scenario2','ActiveTest_Scenario3']
    
    
    """"
    ###### junos start for single
    #log_dir_location=f'{BASE_DIR}/test5/ActiveTest_Scenario3'
    log_dir_location="/volume/regressions/results/JUNOS/HEAD/ksanka/longevity/24.2R2/SP_MPLS_VPNSERVICES_2_20240801-185456/test_suite_iter_0/ActiveTest_Scenario2"
    out_dir='/volume/regressions/results/JUNOS/HEAD/mmahadevaswa/longevity/test2'
    #log_dir_location=f'{BASE_DIR}/generic/23.3R1/longi_test_20230820-231637/test_suite_iter_0/ActiveTest_Scenario2'
    host_name = 'long-mx2k-01'
    plat = 'MX2020'
    version='24.2X1.2'
    fpc_list = [10,12,15]
    for fpc in fpc_list:
        junos.parse_junos_show_heap_output(log_dir_location=log_dir_location,host_name=host_name,node=f"FPC{fpc}")
    junos.parse_junos_show_process_extensive(log_dir_location=log_dir_location,host_name=host_name)
    junos.collect_data_from_show_task_memory_detail(log_dir_location=log_dir_location, host_name=host_name)
    junos.plot_graph_in_dashboard(out_dir=out_dir,host_name=host_name,platform=plat, version=version,url='')
    
    #### junos end for single
    """
    
    
    """
    ## JUNOS for consolidated view:
    
    #### Consolited view ######
    
    #log_dir_location=f'{BASE_DIR}/generic/23.3R1/longi_test_20230820-231637/'
    #log_dir_location=f'{BASE_DIR}/dedicated/23.3R3/SP_MPLS_VPNSERVICES_2_20230929-045748/'
    #log_dir_location='/volume/regressions/results/JUNOS/HEAD/ksanka/longevity/24.2R2/SP_MPLS_VPNSERVICES_2_20240801-185456/'
    #log_dir_location='/volume/regressions/results/JUNOS/HEAD/ksanka/longevity/24.2R2/SP_MPLS_VPNSERVICES_2_20240801-185456/'
    #out_dir="/volume/regressions/results/JUNOS/HEAD/ksanka/longevity/24.2R2/SP_MPLS_VPNSERVICES_2_20240801-185456/test_suite_iter_0/dashboard/long-mx2k-01"
    
    
    junos_host_list=['long-mx2k-01']
    junos_plat_data = {'long-mx2k-01':'mx2020-premium2-dc'}
    junos_router_id = {'long-mx2k-01':'r9'}
    #junos_plat_data = {'shifu01':'qfx5210-64c-afo'}
    junos_node_data = {}
    
    junos_node_data['long-mx2k-01']={'fpc_list':['10','12','15']}
   
    
    #node_list={'fpc_list':['1','3']}
    junos.events_report(events_log_dir_location=f"{log_dir_location}test_suite_iter_0/", test_type='Active', max_test_id=3)
    for host_name in junos_host_list:
        node_list=junos_node_data[host_name]
        for scenario in scenario_list:
            sub_log_dir_location=f"{log_dir_location}test_suite_iter_0/{scenario}"      
            junos.collect_data_for_dashboard_junos(log_dir_location=sub_log_dir_location,host_name=host_name, node_dict=node_list, scenario=scenario)
        
    for host_name in junos_host_list:
        plat= junos_plat_data[host_name]
        version='24.2X1.2'
        rtr=junos_router_id[host_name]
        #rtr = ''
        #out_dir = f"{log_dir_location}test_suite_iter_0/dashboard/{host_name}"
        out_dir = f"/volume/regressions/results/JUNOS/HEAD/ksanka/longevity/24.2R2/SP_MPLS_VPNSERVICES_2_20240801-185456/test1/dashboard/{host_name}"     
        junos.plot_graph_for_single_global_iteation_dashboard(out_dir=out_dir,host_name=host_name, platform=plat,version=version,lrm_view=False, rtr=rtr)
        lrm_out_dir = f"{out_dir}/lrm_view"
        junos.plot_graph_for_single_global_iteation_dashboard(out_dir=lrm_out_dir,host_name=host_name, platform=plat,version=version,lrm_view=True, rtr=rtr)
    
    """
 
    ### consolited view for EVO:
    
    #log_dir_location=f'{BASE_DIR}/dedicated/23.3R3/SP_MPLS_VPNSERVICES_2_20230929-045748/'
    log_dir_location='/volume/regressions/results/JUNOS/HEAD/mmahadevaswa/longevity/IPCLOS/conversion/converted/jpytest_logs/longevity_ipclos_20250430-151254/'
    #evo_host_list=['long-ptx108-02','long-ptx10k-01','long-ptx104-01']
    evo_host_list=['svla-q5240-01']
    scenario_list =['ActiveTest_Scenario1','ActiveTest_Scenario2','ActiveTest_Scenario3']
    #scenario_list =['PassiveTest_Scenario1','PassiveTest_Scenario2','PassiveTest_Scenario3']
    #evo_host_list = ['long-ptx108-02']
    #evo_host_list = ['long-ptx10k-01']
    evo_plat_data = {'svla-q5240-01':'qfx5240-64c','long-ptx10k-01':'ptx10001-36mr-ac','long-ptx104-01':'ptx10004 ','qnc-hillside-02':'qfx5700','boxer':'qfx5130-32cd','rpd-vpn-spec-b':'qfx5130-32cd','rpd-vpn-spec-a':'qfx5130-32cd'}
    evo_router_id = {'svla-q5240-01':'r0','long-ptx10k-01':'r4','long-ptx104-01':'r5','qnc-hillside-02':'r0','boxer':'r1','rpd-vpn-spec-b':'r2','rpd-vpn-spec-a':'r3'}
    evo_node_data = {}
    version='24.3R1.1-EVO'
    #plat="ptx10004"
    rtr=''
    
    #evo_node_data['stqc-p10k4-01']={'fpc_list':['fpc0','fpc1']}
    #evo_node_data['long-ptx108-02']=['re0','re1','fpc0']
    #evo_node_data['long-ptx10k-01']=['re0']
    evo_node_data['svla-q5240-01']=['re0']
    #evo_node_data['qnc-hillside-02']=['re0', 'fpc0', 'fpc1', 'fpc2', 'fpc3']
    #evo_node_data['boxer']=['re0', 'fpc0']
    #evo_node_data['rpd-vpn-spec-b']=['re0', 'fpc0']
    #evo_node_data['rpd-vpn-spec-a']=['re0', 'fpc0']
    
    collection_types=['mem-util-kht-epp-mapid-utilization', 'mem-util-kht-l2domain-utilization', 'mem-util-kht-slu-my-mac-utilization', 'mem-util-kht-dlu-idb-utilization', 'mem-util-jnh-mm-global-utilization', 'mem-util-jnh-mm-private-utilization', 'mem-util-jnh-loadbal-utilization', 'mem-util-epp-total-mem-utilization', 'mem-util-flt-vfilter-utilization', 'mem-util-flt-phyfilter-utilization', 'mem-util-flt-alpha-0-kht-utilization', 'mem-util-policer-id-utilization', 'mem-util-plct-utilization']
    collection_types = None
    for host_name in evo_host_list:
        #node_list = evo_node_data[host_name]['fpc_list']
        #node_list = ['re0','re1','fpc0','fpc1']
        node_list = evo_node_data[host_name]
        for scenario in scenario_list:
            sub_log_dir_location=f"{log_dir_location}test_suite_iter_0/{scenario}"    
            #evo.scenario_data[scenario] = {}
            evo.collect_data_for_dashboard_evo(log_dir_location=sub_log_dir_location,host_name=host_name,node_list=node_list,scenario=scenario,collection_types=collection_types)
            
            #evo.collect_data_from_show_task_memory_detail(log_dir_location=sub_log_dir_location, host_name=host_name,scenario=scenario) 
    
    for host_name in evo_host_list:
        version='24.3R1.1-EVO'
        rtr = evo_router_id[host_name]
        plat = evo_plat_data[host_name]
        #out_dir = f"{log_dir_location}test_suite_iter_0/dashboard/{host_name}" 
        out_dir = f"/volume/regressions/results/JUNOS/HEAD/mmahadevaswa/longevity/24.3R1.1/longevity_dcf_20240831-015843/test_suite_iter_0/dashboard/{host_name}"    
        out_dir = f"/volume/regressions/results/JUNOS/HEAD/mmahadevaswa/longevity/IPCLOS/conversion/converted/jpytest_logs/longevity_ipclos_20250430-151254/test_suite_iter_0/dashboard/{host_name}"
        evo.plot_graph_for_single_global_iteation_dashboard(out_dir=out_dir,host_name=host_name, platform=plat,version=version,lrm_view=False, rtr=rtr) 
        out_dir1 = f"{out_dir}/lrm_view"   
        evo.plot_graph_for_single_global_iteation_dashboard(out_dir=out_dir1,host_name=host_name, platform=plat,version=version,lrm_view=True, rtr=rtr)  
       
   
    
    """
    ####### Evo start for single
 
    #log_dir_location=f'{BASE_DIR}/dedicated/23.2R2/SP_MPLS_VPNSERVICES_2_20240702-231745/test_suite_iter_0/ActiveTest_Scenario1'
    log_dir_location="/volume/regressions/results/JUNOS/HEAD/mmahadevaswa/longevity/dedicated/23.2R2/SP_MPLS_VPNSERVICES_2_20240702-231745/test_suite_iter_0/sirius/"
    #out_dir='/volume/regressions/results/JUNOS/HEAD/mmahadevaswa/longevity/test5/dashboard/shifu01'
    out_dir='/volume/regressions/results/JUNOS/HEAD/mmahadevaswa/longevity/generic/22.4R3/longevity_generic_20230827-045344/test_suite_iter_0/ActiveTest_Scenario1/dashboard/stqc-p10k4-01/lrm_config_post_test'
    out_dir=f'/volume/regressions/results/JUNOS/HEAD/mmahadevaswa/longevity/dedicated/23.2R2/SP_MPLS_VPNSERVICES_2_20240702-231745/test_suite_iter_0/ActiveTest_Scenario1/tt-tapas-15556501-vm'
    host_name="10.54.169.50"
    plat="ptx10008"
    rtr='r0'
    node_list = ['re0','fpc0']    
    fpc_list =['fpc0']
    
    proc_mem_node_list = ['RE0']
    proc_mem_node_list.extend(fpc_list)
   
    
    if True:
        evo.parse_ps_mem_output(log_dir_location=log_dir_location, host_name=host_name, node='RE')
        for fpc in fpc_list:
            evo.parse_ps_mem_output(log_dir_location=log_dir_location, host_name=host_name, node=fpc)
        evo.collect_data_from_jemalloc(log_dir_location=log_dir_location, host_name=host_name, nodes_list=node_list, collection_type='Allocated')
        evo.collect_data_from_jemalloc(log_dir_location=log_dir_location, host_name=host_name, nodes_list=node_list, collection_type='Resident')
        collection_types=['mem-util-kht-epp-mapid-utilization', 'mem-util-kht-l2domain-utilization', 'mem-util-kht-slu-my-mac-utilization', 'mem-util-kht-dlu-idb-utilization', 'mem-util-jnh-mm-global-utilization', 'mem-util-jnh-mm-private-utilization', 'mem-util-jnh-loadbal-utilization', 'mem-util-epp-total-mem-utilization', 'mem-util-flt-vfilter-utilization', 'mem-util-flt-phyfilter-utilization', 'mem-util-flt-alpha-0-kht-utilization', 'mem-util-policer-id-utilization', 'mem-util-plct-utilization']
        for node in fpc_list:
            #evo.collect_data_from_npu_mem(log_dir_location=log_dir_location,host_name=host_name, node=node.upper(), collection_type='mem-util-kht-dlu-idb-utilization')
            #evo.collect_data_from_npu_mem(log_dir_location=log_dir_location,host_name=host_name, node=node.upper(), collection_type='mem-util-flt-tcam-utilization')
            #evo.collect_data_from_npu_mem(log_dir_location=log_dir_location,host_name=host_name, node=node.upper(), collection_type='mem-util-flt-alpha-0-kht-utilization')
            evo.collect_data_from_npu_mem(log_dir_location=log_dir_location,host_name=host_name, node=node.upper(), collection_types=collection_types)


        for node in node_list:
            evo.collect_data_from_show_system_process_extensive(log_dir_location=log_dir_location,host_name=host_name, node=node)
            evo.collect_data_from_show_system_storage(log_dir_location=log_dir_location,host_name=host_name, node=node)
        for node in proc_mem_node_list:
            evo.collect_data_from_show_system_proc_mem_info(log_dir_location=log_dir_location,host_name=host_name, node=node)
            
        evo.collect_data_from_show_task_memory_detail(log_dir_location=log_dir_location, host_name=host_name)
        
    evo.collect_show_platform_distributor_statistics(log_dir_location=log_dir_location, host_name=host_name)
    evo.collect_show_platform_distributor_statistics_all_clients(log_dir_location=log_dir_location, host_name=host_name)
    evo.plot_graph_in_dashboard(out_dir=out_dir,host_name=host_name,platform=plat, version="22.4R3.2-EVO",url='')
    
    """
 
        
    #lng_common.Collect Data From Jemalloc   ${Log Dir}   ${host_name}   ${node_list}   Allocated
    #lng_common.Collect Data From Jemalloc   ${Log Dir}   ${host_name}   ${node_list}   Resident

    

    #evo.plot_graph_in_dashboard(out_dir=out_dir,host_name=host_name,platform=plat, version="23.3R1",url='')
    
    """
    scenario_list =['ActiveTest_Scenario1','ActiveTest_Scenario2','ActiveTest_Scenario3']
    
    host_name = 'sup-tb3-geodc-2-scapa' 
    plat = 'PTX10008'
    version='22.3X80-D36.12-EVO'
    rtr='r0'
    log_dir_location='/volume/regressions/results/JUNOS/HEAD/phiremath/anCX_ACTIVE_LONGEVITY/LOG/RUN1/ancx_activity_longevity_20230816-133842/'
    #log_dir_location='/volume/regressions/results/JUNOS/HEAD/mmahadevaswa/longevity/generic/23.3R1/longi_test_20230819-154436/test_suite_iter_0/ActiveTest_Scenario1'
    out_dir = "/volume/regressions/results/JUNOS/HEAD/phiremath/anCX_ACTIVE_LONGEVITY/LOG/RUN1/ancx_activity_longevity_20230816-133842/test_suite_iter_0/dashboard"
    
    evo.events_report(events_log_dir_location=f"{log_dir_location}/test_suite_iter_0/",test_type='Active',max_test_id=3)

    node_list=['re0','re1','fpc0','fpc1','fpc2','fpc3','fpc4','fpc5','fpc6','fpc7']  # evo
    #node_list={'fpc_list':['1','3']}  # junos
                                                                                                 
    for scenario in scenario_list:
        sub_log_dir_location=f"{log_dir_location}test_suite_iter_0/{scenario}"      
        evo.collect_data_for_dashboard_evo(log_dir_location=sub_log_dir_location,host_name=host_name,node_list=node_list,scenario=scenario)
        #junos.collect_data_for_dashboard_junos(log_dir_location=sub_log_dir_location,host_name=host_name, node_dict=node_list, scenario=scenario)
        
    
    #evo.plot_graph_for_single_global_iteation_dashboard(out_dir=out_dir,host_name="ptx10k-kernel-18",platform='ptx10008', version="23.3R1.1-EVO")
    evo.plot_graph_for_single_global_iteation_dashboard(out_dir=out_dir,host_name=host_name, platform=plat,version=version,rtr=rtr)


    #evo.parse_ps_mem_output(log_dir_location=f"{log_dir_location}",host_name=host_name, node='RE')
   
    #for id in range(0,8):
    #    evo.parse_ps_mem_output(log_dir_location=f"{log_dir_location}",host_name=host_name, node=f"fpc{id}")

    #evo.parse_ps_mem_output(log_dir_location=f"{log_dir_location}",host_name='ptx10k-kernel-18', node='fpc7')

    #evo.plot_graph_in_dashboard(out_dir=out_dir,host_name=host_name,platform=plat, version="22.3X80-D36.12-EVO",url='')
    #plot_graph(x_axis=self.global_resource_labels_x_axis, graph_data=self.global_resource_data) 
    '''
    """


