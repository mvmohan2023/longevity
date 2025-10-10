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
import pdb

#fichier_html_graphs=open("{out_dir}/Longevity_dashboard.html",'w')
#os.system(f"chmod -R 755 {out_dir}/Longevity_dashboard.html")
#fichier_html_graphs.write("<html><head></head><body><h1><center><b>Longevity Dashboard</b></center></h1>"+"\n")


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
        
        
                
        
        
    
    def get_global_iterations(self,log_dir_location: str) -> List:
    
        
        return [ name for name in os.listdir(log_dir_location) if os.path.isdir(os.path.join(log_dir_location, name)) and name.startswith('test_suite_iter_') ]
        
        
    def get_test_sceanrio_log_directory(self,log_dir_location: str, pattern: str ) -> List:
        
        return [ name for name in os.listdir(log_dir_location) if os.path.isdir(os.path.join(log_dir_location, name)) and name.endswith(pattern) ]
        
    

        
    def plot_graph(self,x_axis:dict, graph_data:dict, out_dir:str, chart_type:str = 'line') -> None:

        fichier_html_graphs=open(f"{out_dir}/Longevity_dashboard.html",'w')
        os.system(f"chmod -R 755 {out_dir}/Longevity_dashboard.html")
        fichier_html_graphs.write("<html><head></head><body><h1><center><b>Longevity Dashboard</b></center></h1>"+"\n")

        i=0
        total_items = list(graph_data.keys())
        max_items = len(total_items)
        color1 = '#00bfff'
        color2 = '#ff4000'
        while 1:
            if i<max_items:
                trace = []
                print (total_items)
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
                            #line=dict(
                            #    color="black",
                            #    width=1,
                            #),
                            #mode='markers',
                            #marker_size=25,

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
                    #paper_bgcolor='rgba(0,0,0,0)',
                                    
                    #paper_bgcolor='#f3f4f4',
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
                #plotly.offline.plot(fig, filename=f'{out_dir}/LChartxxxxxxn_'+str(i)+'.html',auto_open=False)
                #fichier_html_graphs.write("  <object data=\""+'LChartxxxxxxn_'+str(i)+'.html'+"\" width=\"650\" height=\"700\"></object>"+"\n")
                #os.system(f"chmod -R 755 {out_dir}/LChartxxxxxxn_{i}.html")
                html_fname = f"{total_items[i]}"
                html_fname = re.sub(r"\s","_", html_fname)
                html_fname = re.sub(r"\(","_", html_fname)
                html_fname = re.sub(r"\)","_", html_fname)
                
                plotly.offline.plot(fig, filename=f"{out_dir}/{html_fname}.html",auto_open=False)
                fichier_html_graphs.write("  <object data=\""+f'{html_fname}.html'+"\" width=\"650\" height=\"700\"></object>"+"\n")
                os.system(f"chmod -R 755 {out_dir}/{html_fname}.html")

                i+=1
            else:
                break
        fichier_html_graphs.write("</body></html>")

    def parse_ps_mem_output(self,log_dir_location:str, host_name:str, node: str,scenario: str) -> None:
        
        dir_list=os.listdir(f"{log_dir_location}")
        mem_track={}
        tags = {}
        tags_list = []
        if 'RE' in node:
            re_match = re.compile(f"\[CMD\] python /var/home/regress/ps_mem.py")
        elif 'fpc' in node:
            re_match = re.compile(f"root@{node} python ps_mem.py")

        for sub_dir in dir_list:
            if sub_dir.startswith('iteration_') or sub_dir.startswith('lrm_') or sub_dir.startswith('test_') or sub_dir.startswith('manual_mem'):
                    main_loop=1
                    print(f"Processing.....{log_dir_location}/{sub_dir}")
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
        
        
        self.scenario_data[scenario][key]={}
        self.scenario_data[scenario][key]['_resource_data']=self.global_resource_data[key]
        self.scenario_data[scenario][key]['_resource_labels_x_axis']=self.global_resource_labels_x_axis[key]
        self.scenario_data[scenario][key]['_y_axis_label']=self.y_axis_label[key]
        self.scenario_data[scenario][key]['_paper_color']= self.paper_color[key]
        
        
        

        
    def collect_data_from_jemalloc(self,log_dir_location:str, host_name:str, nodes_list:List[str], collection_type:str,scenario: str) -> None:
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
        for sub_dir in dir_list:
            if sub_dir.startswith('iteration_') or sub_dir.startswith('lrm_') or sub_dir.startswith('test_') or sub_dir.startswith('manual_mem'):
                    main_loop=True
                    print(f"Processing.....{log_dir_location}/{sub_dir}")
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
                                while i<len(lines):
                                    re_main_match_str = re_main_match.search(lines[i])
                                    if re_main_match_str:
                                        while True:
                                            re_sub_match_str = re_sub_match.search(lines[i])
                                            i+=1
                                            if re_sub_match_str:
                                                kb = conv_bytes_to_kb(int(re_sub_match_str.group(1)))
                                                MiB = float(round(conv_KB_to_MB(kb), 2))
                                                #MiB = round(conv_MB_to_GB(float(MiB)), 2)
                                                #print(f'{re_sub_match_str.group(1)}==>{kb}--->{MiB}')
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
            key = f'jemalloc {d_string} on {node}'
            self.global_resource_data[key]= node_dict_list[node] 
            self.global_resource_labels_x_axis[key]=tags_list
            self.y_axis_label[key]=f'jemalloc {collection_type}(Megabyte(MB))'
            self.paper_color[key] = '#b6cdee'
            
            self.scenario_data[scenario][key]={}
            self.scenario_data[scenario][key]['_resource_data']=self.global_resource_data[key]
            self.scenario_data[scenario][key]['_resource_labels_x_axis']=self.global_resource_labels_x_axis[key]
            self.scenario_data[scenario][key]['_y_axis_label']=self.y_axis_label[key]
            self.scenario_data[scenario][key]['_paper_color']= self.paper_color[key]

        #print(self.global_resource_data)

    def collect_data_from_npu_mem(self,log_dir_location:str, host_name:str, node:str, collection_type:str,scenario: str) -> None:

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
                            #tags_list.append(f"{sub_dir}_{stamp}")  
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
                                                #print(f"{re_sub_match_str.group(1)}_{collection_type}")
                                                if f"{re_sub_match_str.group(1)}_{collection_type}" not in mem_track:
                                                    #print(re_sub_match_str.group(2))
                                                    mem_track[f"{re_sub_match_str.group(1)}_{collection_type}"]=[int(re_sub_match_str.group(2))]
                                                else:
                                                    print(re_sub_match_str.group(2))
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
        
        self.scenario_data[scenario][key]={}
        self.scenario_data[scenario][key]['_resource_data']=self.global_resource_data[key]
        self.scenario_data[scenario][key]['_resource_labels_x_axis']=self.global_resource_labels_x_axis[key]
        self.scenario_data[scenario][key]['_y_axis_label']=self.y_axis_label[key]
        self.scenario_data[scenario][key]['_paper_color']= self.paper_color[key]

    def collect_data_from_show_system_process_extensive(self,log_dir_location:str, host_name:str, node:str,scenario: str) -> None:

        dir_list=os.listdir(f"{log_dir_location}")
        cpu_track={}
        tags = {}
        tags_list = []
        re_main_match = re.compile(f"show system process extensive")
        re_loop_match = re.compile(f"node:\s+{node}") 
        re_sub_match1 = re.compile(f"%Cpu\(.*\):\s+(.*)\sus,\s+(.*)\ssy,\s+(.*)\s+ni,\s+(.*)\s+id,.*") 
        re_sub_match2 = re.compile(r"^\d+.*\s+\d{2}:\d{2}:\d{2}\s+.*\s+(\d*[.,]?\d)\s+(.*)$")

        for sub_dir in dir_list:
            #if sub_dir.startswith('iteration_') or sub_dir.startswith('lrm_') or sub_dir.startswith('test_') or sub_dir.startswith('manual_mem'):
            if sub_dir.startswith('lrm_') or sub_dir.startswith('test_config') or sub_dir.startswith('manual_mem'):
                    main_loop=True
                    print(f"Processing.....{log_dir_location}/{sub_dir}")
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
                                while i<len(lines):
                                    re_main_match_str = re_main_match.search(lines[i])
                                    if re_main_match_str:
                                        i+=1
                                        while True:
                                            re_loop_match_str = re_loop_match.search(lines[i])
                                            if re_loop_match_str:
                                                #print(re_loop_match_str)
                                                print(f"mmm->{lines[i]}")
                                                while True:
                                                #for j in range(i+2, i+13):
                                                    #print(f"mmmmmmm->{j}")
                                                    #print(lines[j])
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
                                                        #print(re_sub_match2_str)
                                                        #print(re_sub_match2_str.group(2))
                                                        #rint(re_sub_match2_str.group(1))
                                                        if re_sub_match2_str.group(2) not in cpu_track:
                                                            cpu_track[re_sub_match2_str.group(2)]=[float(re_sub_match2_str.group(1))]
                                                        else:
                                                            cpu_track[re_sub_match2_str.group(2)].append(float(re_sub_match2_str.group(1)))
                                                    if len(lines[i].strip()) == 0 and "-------------------------------" in lines[i+1]:
                                                    #if lines[i] == '-------------------------------' or 'node:' in lines[i]:
                                                        main_loop=False
                                                        print(f"ii{cpu_track['Idle']}")
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
        
        self.scenario_data[scenario][key]={}
        self.scenario_data[scenario][key]['_resource_data']=self.global_resource_data[key]
        self.scenario_data[scenario][key]['_resource_labels_x_axis']=self.global_resource_labels_x_axis[key]
        self.scenario_data[scenario][key]['_y_axis_label']=self.y_axis_label[key]
        self.scenario_data[scenario][key]['_paper_color']= self.paper_color[key]

    def collect_data_from_show_system_proc_mem_info(self,log_dir_location:str, host_name:str, scenario: str, node:str='RE0') -> None:

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

        for sub_dir in dir_list:
            #if sub_dir.startswith('iteration_') or sub_dir.startswith('lrm_') or sub_dir.startswith('test_') or sub_dir.startswith('manual_mem'):
            if sub_dir.startswith('lrm_') or sub_dir.startswith('test_config') or sub_dir.startswith('manual_mem'):
                    main_loop=True
                    print(f"Processing.....{log_dir_location}/{sub_dir}")
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
                                                print(re_sub)
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
        
        
        self.scenario_data[scenario][key]={}
        self.scenario_data[scenario][key]['_resource_data']=self.global_resource_data[key]
        self.scenario_data[scenario][key]['_resource_labels_x_axis']=self.global_resource_labels_x_axis[key]
        self.scenario_data[scenario][key]['_y_axis_label']=self.y_axis_label[key]
        self.scenario_data[scenario][key]['_paper_color']= self.paper_color[key]


    def collect_data_from_show_system_storage(self,log_dir_location:str, host_name:str,scenario: str, node:str='re0') -> None:

        dir_list=os.listdir(f"{log_dir_location}")
        storage_track={}
        tags = {}
        tags_list = []
        re_main_match = re.compile(f"\[{host_name}\]\s+\[CMD\]\s+show\s+system\s+storage")
        re_loop_match =  re.compile(f"^{node}\:")
        re_sub_match =  re.compile(r'^tmpfs\s+\d+.*\s+.*\s+\d+[a-zA-Z]\s+(\d+)\%\s+\/(run)$')  

        for sub_dir in dir_list:
            #if sub_dir.startswith('iteration_') or sub_dir.startswith('lrm_') or sub_dir.startswith('test_') or sub_dir.startswith('manual_mem'):
            if sub_dir.startswith('lrm_') or sub_dir.startswith('test_config'):
                    main_loop=True
                    print(f"Processing.....{log_dir_location}/{sub_dir}")
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
                                                        re_sub_match_str = re_sub_match.search(lines[i])
                                                        if re_sub_match_str:
                                                            print(lines[i])
                                                            print(re_sub_match_str)
                                                            print(re_sub_match_str.group(1))
                                                            if re_sub_match_str.group(2) not in storage_track:
                                                                storage_track[re_sub_match_str.group(2)]=[re_sub_match_str.group(1)]
                                                            else:
                                                                storage_track[re_sub_match_str.group(2)].append(re_sub_match_str.group(1))
                                                            main_loop=False
                                                            break
                                                        i+=1
                                                        if i>len(lines):
                                                            main_loop=False
                                                            break
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
        
        self.scenario_data[scenario][key]={}
        self.scenario_data[scenario][key]['_resource_data']=self.global_resource_data[key]
        self.scenario_data[scenario][key]['_resource_labels_x_axis']=self.global_resource_labels_x_axis[key]
        self.scenario_data[scenario][key]['_y_axis_label']=self.y_axis_label[key]
        self.scenario_data[scenario][key]['_paper_color']= self.paper_color[key]

    
    def plot_graph_for_all_global_iterations_dashboard(self,out_dir: str):

        iterations = self.get_global_iterations(log_dir_location=f"{out_dir}")
        pdb.set_trace()
        
        for top_dir in iterations:
            self.global_iter_data[top_dir] = {}
            self.global_iter_data[top_dir]['scenario1'] = []
            self.global_iter_data[top_dir]['scenario2'] = []   
            
    def plot_graph_for_single_global_iteation_dashboard(self, out_dir:str):
        
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
            sub_dict_list.append(sub_dict)
            new_tags = [ f"{x}_{k}" for x in self.tree_traverse(sub_dict,'_resource_labels_x_axis') ]
           
            tags_list.extend(new_tags)
   
            print(len(tags_list))
            #pdb.set_trace()
          
        
        t_keys = sub_dict_list[0].keys()
        for t_key in t_keys:
            print(f"staart....{t_key}")
            t_key_dict = {}
            t_key_list = []
            for i in range(0, len(sub_dict_list)):
                #pdb.set_trace()
                t_key_list.append(sub_dict_list[i][t_key].get('_resource_data', None))
                y_axis_label = sub_dict_list[i][t_key].get('_y_axis_label', None)
                paper_color = sub_dict_list[i][t_key].get('_paper_color',None)          
               
            t_key_dict = self.merge_dict(t_key_list[0],t_key_list[1])
            
            
            self.global_resource_data[t_key] = t_key_dict
            self.global_resource_labels_x_axis[t_key]=tags_list
            self.y_axis_label[t_key]= y_axis_label
            self.paper_color[t_key] = paper_color

            
    
   
            
        self.plot_graph(x_axis=self.global_resource_labels_x_axis, graph_data=self.global_resource_data, out_dir=out_dir)
        
       
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
    def plot_graph_in_dashboard(self,out_dir:str) -> None:
        print(out_dir)
        self.plot_graph(x_axis=self.global_resource_labels_x_axis, graph_data=self.global_resource_data, out_dir=out_dir)
         
        
    def collect_data_for_dashbaord(self, log_dir_location:str, host_name:str, node_list:List,scenario:str):
        
        ps_mem_node_list = ['RE']
        fpc_list  = [x for x in node_list if x.startswith('fpc')]
        ps_mem_node_list.extend(fpc_list)
        
        proc_mem_node_list = ['RE0']
        proc_mem_node_list.extend(fpc_list)
        
        
        self.scenario_data[scenario]={}
        for node in ps_mem_node_list:
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
                
        
        
#    collect_data_from_show_system_proc_mem_info(log_dir_locat
        
if __name__ == "__main__":
    
    
    l = LongevityDashboard()
    
#    log_dir_location='/volume/regressions/results/JUNOS/HEAD/mmahadevaswa/longevity/longi_test_20230317-153831'
#    #log_dir_location='/volume/regressions/results/JUNOS/HEAD/mmahadevaswa/longevity/longi_test_20230314-133926'
    log_dir_location='/volume/regressions/results/JUNOS/HEAD/mmahadevaswa/longevity/longi_test_20230424-050849/'
    out_dir = '/volume/regressions/results/JUNOS/HEAD/mmahadevaswa/longevity/longi_test_20230424-050849/test_suite_iter_0/dashboard/ptx10k-kernel-18'
    
    scenario_list =['PassiveTest_Scenario1','PassiveTest_Scenario2']
    for scenario in scenario_list:
        sub_log_dir_location=f"{log_dir_location}test_suite_iter_0/{scenario}"
        l.collect_data_for_dashbaord(log_dir_location=sub_log_dir_location,host_name='ptx10k-kernel-18',node_list=['re0','re1','fpc0','fpc7'],scenario=scenario)
    #l.collect_data_for_dashbaord(log_dir_location=log_dir_location,host_name='ptx10k-kernel-18',node_list=['re0','re1','fpc0','fpc7'],scenario='PassiveTest_Scenario2')

        #pdb.set_trace()
    l.plot_graph_for_single_global_iteation_dashboard(out_dir=out_dir)

    print(l.scenario_data.keys())    
        
        
        
    
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

    