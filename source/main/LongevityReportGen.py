from datetime import datetime
import os
import pdb
import re
import logging
import logging
import numpy as np

resource_graph_links = {}
global_failed_memory_apps_dict = {}
_scenario=""
_hostname=""

def get_keys_for_hostname(global_data_dict, hostname):
    return [key for key in global_data_dict if hostname in key]

def filter_by_pattern(data_list, pattern):
    return [item for item in data_list if pattern in item]


def build_node_resource_data(status_resp_data):
    node_resource_data = {}

    for hostname, nodes in status_resp_data.items():
        node_resource_data[hostname] = {}  # Init hostname
        for node, resources in nodes.items():
            node_resource_data[hostname][node] = {}  # Init node
            for resource_key, value in resources.items():
                #pdb.set_trace()
                title, status, details = value
                node_resource_data[hostname][node][title] = {
                    "status": status,
                    "details": details
                }

    return node_resource_data


def extract_template_key_from_filename(filename, hostname, node):
    
    templates = {
        "CPU Usage": ["CPU_Usage_on_{node}-{hostname}.html","%"],
        "NPU Memory Utilization": ["NPU_Memory_Utilization_on_{node_upper}-{hostname}.html","%"],
        "RAM Usage": ["RAM_Usage_RE_ps_mem_{node}-{hostname}.html","GB"],
        "RPD Malloc Allocation": ["RPD_Malloc_Allocation_{node}-{hostname}.html","GB"],
        "SDB Live Objects": ["SDB_live_objects_{node}-{hostname}.html","k"],
        "SDB Object Current Holds": ["SDB_object_current_holds_on_node:{node}-{hostname}.html","k"],
        "SDB Object Holds Total": ["SDB_object_holds_total_on_node:{node}-{hostname}.html","M"],
        "System Storage": ["System_Storage_tmpfs__Usage_on_{node}-{hostname}.html","%"],
        "Jemalloc Resident Usage": ["jemalloc_resident_usage_on_{node}-{hostname}.html","MB"],
        "Jemalloc Allocated[total]": ["jemalloc_total_allocated_on_{node}-{hostname}.html","MB"],
        "Proc Mem Info": ["proc_mem_info_on_{node}-{hostname}.html","MB"],
        "Brcm Inspection": ["brcm_inspect_on_{node}-{hostname}.html",""],
    }
    node_upper = node.upper()

    for key, template in templates.items():
        # Fill in the known parts
        expected_pattern = template[0].format(node=node, node_upper=node_upper, hostname=hostname)

        # Use "in" or "infix match" to avoid exact match requirement
        if expected_pattern in filename:
            return (key,template[1])
    return (None,None)  # No match found

class LongevityReportGenerator:
    def __init__(self, hostname, node, graph_loc, resource_graph_links):
        self.hostname = hostname
        self.node = node
        self.graph_loc = graph_loc
        self.report_file_names = {}
        self.shared_resource_graph_links = resource_graph_links
        if hostname not in self.shared_resource_graph_links:
            self.shared_resource_graph_links[hostname] = {}
        self.shared_resource_graph_links[hostname][node] = self.build_resource_graph_links()
        #self.resource_graph_links = self.build_resource_graph_links()
        
    def build_resource_keys_from_node_list(self, node_list, hostname, global_dict_keys):
        # Template mappings for resources (with {node} or {node_upper})
        templates = {
            "CPU Usage": "CPU_Usage_on_{node}-{hostname}.html",
            "NPU Memory Utilization": "NPU_Memory_Utilization_on_{node_upper}-{hostname}.html",
            "RAM Usage": "RAM_Usage_RE_ps_mem_{node}-{hostname}.html",
            "RPD Malloc Allocation": "RPD_Malloc_Allocation_{node}-{hostname}.html",  # Only once per host
            "SDB Live Objects": "SDB_live_objects_{node}-{hostname}.html",
            "SDB Object Current Holds": "SDB_object_current_holds_on_node:{node}-{hostname}.html",
            "SDB Object Holds Total": "SDB_object_holds_total_on_node:{node}-{hostname}.html",
            "System Storage": "System_Storage_tmpfs__Usage_on_{node}-{hostname}.html",
            "Jemalloc Resident": "jemalloc_resident_usage_on_{node}-{hostname}.html",
            "Jemalloc Allocated": "jemalloc_total_allocated_on_{node}-{hostname}.html",
            "Proc Mem Info": "proc_mem_info_on_{node_upper}-{hostname}.html",
            "Brcm Inspection": "brcm_inspect_on_{node}-{hostname}.html",
        }

        result_keys = []

        for node in node_list:
            for label, template in templates.items():
                file_name = template.format(node=node, node_upper=node.upper(), hostname=hostname)
                if file_name in global_dict_keys:
                    result_keys.append(file_name)

        return result_keys


    def build_resource_graph_links(self):
        base_mapping = {
            "CPU Usage_{node}": "CPU_Usage_on_{node}-{hostname}.html",
            "RAM Usage_{node}": "RAM_Usage_RE_ps_mem_{node}-{hostname}.html",
            "RPD Malloc Allocation_{node}": "RPD_Malloc_Allocation_{node}-{hostname}.html",
            "SDB Object Current Holds_{node}": "SDB_object_current_holds_on_node:{node}-{hostname}.html",
            "SDB Object Holds Total_{node}": "SDB_object_holds_total_on_node:{node}-{hostname}.html",
            "System Storage_{node}": "System_Storage_tmpfs__Usage_on_{node}-{hostname}.html",
            "Jemalloc Resident Usage_{node}": "jemalloc_resident_usage_on_{node}-{hostname}.html",
            "Jemalloc Allocated[total]_{node}": "jemalloc_total_allocated_on_{node}-{hostname}.html",
            "Proc Mem Info_{node}": "proc_mem_info_on_{node}-{hostname}.html",
            "Brcm Inspection_{node}": "brcm_inspect_on_{node}-{hostname}.html",
        }

        graph_links = {}
        for key_template, file_template in base_mapping.items():
            key = key_template.format(node=self.node)
            file_name = file_template.format(node=self.node, hostname=self.hostname)
            report_file_name = file_name.replace(".html", "_report.html")
            self.report_file_names[key]=report_file_name
            #self.report_file_names[key]=report_file_name
            graph_links[key] = {
                "graph": f"{self.graph_loc}{file_name}",
                "report": f"{self.graph_loc}{report_file_name}"
            }
        #pdb.set_trace()
        return graph_links

    def render_status(self, status):
        color = "#8BC34A" if status == "Pass" else "#F44336"
        return f'<span style="color:{color};font-weight:bold">{status}</span>'

    def generate_nodewise_resource_report(self, report_path, test_name, host_info, node_resource_data,
                                          longevity_devices, longevity_duration, dashboard_url, result_html_path):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Longevity Test Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        table {{ border-collapse: collapse; width: 100%; margin-bottom: 30px; }}
        th, td {{ border: 1px solid #aaa; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        h2 {{ color: #3f51b5; }}
    </style>
</head>
<body>

<h1>Longevity Test Report - {test_name}</h1>
<p><strong>Generated:</strong> {timestamp}</p>
<p><strong>Longevity Duration:</strong> {longevity_duration}</p>
<p><strong>Dashboard:</strong> <a href="{dashboard_url}" target="_blank">{dashboard_url}</a></p>
<p><strong>Detailed Analysis:</strong> <a href="{result_html_path}" target="_blank">{result_html_path}</a></p>
<br>
"""

        html += "<h2>Host Information</h2><table><tr><th>Host</th><th>Platform</th><th>Version</th></tr>"
        for host, data in host_info.items():
            html += f"<tr><td>{host}</td><td>{data['platform']}</td><td>{data['version']}</td></tr>"
        html += "</table>"

        html += "<h2>Resource Validation per Node</h2>"
        for _dut, _dut_resouces in node_resource_data.items():
            for node, resources in _dut_resouces.items():
                html += f"<h3>Node:{_dut}:{node}</h3><table><tr><th>Resource</th><th>Status</th><th>Details</th><th>Graph</th></tr>"
                for res_name, res_data in resources.items():
                    status = res_data.get("status", "Unknown")
                    key = f"{res_name}_{node}"
                    #pdb.set_trace()
                    graph_info = self.shared_resource_graph_links.get(_dut, {}).get(node, {}).get(key, {})
                    #pdb.set_trace()
                    #graph_info = self.shared_resource_graph_links[host][node].get(key, {})
                    graph_file = graph_info.get("graph", "")
                    if 'brcm' in res_name.lower():
                        graph_file = ""
                    #pdb.set_trace()
                    report_file = graph_info.get("report", "")

                    thumbnail = f'''
                    <a href="{graph_file}" target="_blank" title="View Graph">
                        &#128200;
                    </a>
                    ''' if graph_file else "N/A"

                    report_img = f'''
                    <a href="{report_file}" target="_blank">
                        <img src="https://cdn-icons-png.flaticon.com/512/337/337946.png" alt="report" height="30">
                    </a>
                    ''' if report_file else "N/A"

                    html += f"<tr><td>{res_name}</td><td>{self.render_status(status)}</td><td>{report_img}</td><td>{thumbnail}</td></tr>"
                html += "</table>"

        html += "<h2>Longevity DUT Events</h2><table><tr><th>DUT</th><th>Events</th><th>Times Executed</th></tr>"
        for dut, data in longevity_devices.items():
            html += f"<tr><td>{dut}</td><td>{', '.join(data['events'])}</td><td>{data['count']}</td></tr>"
        html += "</table></body></html>"

        with open(report_path, "w") as f:
            f.write(html)

        return report_path




class JemallocReportGenerator:
    def __init__(self, jemalloc_data, title, unit, show_full_trend=False):
        self.jemalloc_data = jemalloc_data
        self.show_full_trend = show_full_trend
        self.unit = unit
        self.title = title
        self.overall_status = "Pass"
        self.analysis_results = {}  # {app_name: trend_status}

    def basic_linear_regression(self, y_values):
        x = np.arange(len(y_values))
        y = np.array(y_values)

        x_mean = x.mean()
        y_mean = y.mean()

        numerator = np.sum((x - x_mean) * (y - y_mean))
        denominator = np.sum((x - x_mean) ** 2)

        slope = numerator / denominator if denominator != 0 else 0
        intercept = y_mean - slope * x_mean

        ss_total = np.sum((y - y_mean) ** 2)
        ss_res = np.sum((y - (slope * x + intercept)) ** 2)
        r_squared = 1 - (ss_res / ss_total) if ss_total != 0 else 0

        return slope, intercept, r_squared

    def check_memory_trend(self, data):
        if not data or len(data) < 3:
            return False

        values = list(data.values())
        test_pre = data.get("test_pre", values[0])
        lrm_post = data.get("lrm_post", values[-1])
        baseline_ok = lrm_post <= test_pre

        slope, _, r_squared = self.basic_linear_regression(values)
        max_val = max(values)
        slope_threshold = 0.1 if max_val <= 100 else 0.5

        leak_suspected = not baseline_ok and slope > slope_threshold and r_squared > 0.6
        return not leak_suspected

    def precompute_analysis(self):
        for app, data in self.jemalloc_data.items():
            self.analysis_results[app] = self.check_memory_trend(data)

    def generate_high_level_summary(self):
        total_apps = len(self.jemalloc_data)
        fail_count = sum(1 for status in self.analysis_results.values() if not status)
        pass_count = total_apps - fail_count
        if fail_count >= 1:
            self.overall_status = "Fail"

        return f"""
        <h3>High-Level Summary</h3>
        <table border="1" cellspacing="0" cellpadding="5" style="width: 60%;">
            <tr style="background-color: #f2f2f2; font-weight: bold;">
                <th>Total Processes</th>
                <th>Memory Leak Detected (Fail)</th>
                <th>No Leak Detected (Pass)</th>
            </tr>
            <tr>
                <td align="center">{total_apps}</td>
                <td align="center" style="color: red;"><b>{fail_count}</b></td>
                <td align="center" style="color: green;"><b>{pass_count}</b></td>
            </tr>
        </table>
        """

    def generate_failed_app_summary(self):
        red_rows = ""
        green_rows = ""

        for app, data in self.jemalloc_data.items():
            status = self.analysis_results.get(app, False)
            color = "green" if status else "red"

            row = f"""
            <tr>
                <td>{app}</td>
                <td>{", ".join([f"{k}: {v}{self.unit}" for k, v in data.items()])}</td>
                <td style="color: {color}; font-weight: bold;">{"Pass" if status else "Fail"}</td>
            </tr>
            """
            if status:
                green_rows += row
            else:
                red_rows += row

        rows = red_rows + green_rows

        return f"""
        <h3>Memory Leak Detection Table</h3>
        <table border="1" cellspacing="0" cellpadding="5" style="border-collapse: collapse; width: 100%; margin-top: 20px;">
            <tr style="background-color: #f2f2f2; font-weight: bold;">
                <th>Application</th>
                <th>Memory Checkpoints ({self.unit})</th>
                <th>Status</th>
            </tr>
            {rows}
        </table>
        """

    def generate_full_trend_table(self):
        headers = ['Application'] + list(next(iter(self.jemalloc_data.values())).keys())
        rows = ""
        for app, data in self.jemalloc_data.items():
            cells = "".join(f"<td>{data.get(k)}{self.unit}</td>" for k in headers[1:])
            rows += f"<tr><td>{app}</td>{cells}</tr>"

        header_html = "".join(f"<th>{h}</th>" for h in headers)
        return f"""
        <h3>📈 Complete Memory Trend</h3>
        <table border="1" cellspacing="0" cellpadding="5" style="width: 100%;">
            <tr style="background-color: #f2f2f2; font-weight: bold;">{header_html}</tr>
            {rows}
        </table>
        """

    def generate_html_report(self, output_file):
        self.precompute_analysis()

        report_html = f"""
        <html>
        <head><title>{self.title} Observation</title></head>
        <body style="font-family: Arial, sans-serif; margin: 20px;">
            <h2 style="color:#3f51b5;">{self.title} Observation Report</h2>
            {self.generate_high_level_summary()}
            {self.generate_failed_app_summary()}
        """

        if self.show_full_trend:
            report_html += self.generate_full_trend_table()

        report_html += "</body></html>"

        with open(output_file, "w") as f:
            f.write(report_html)

        print(f"✅ Jemalloc report saved to: {output_file}")
        return output_file





class EvoInfraCheckReportGenerator:
    def __init__(self, j_data, title, unit, show_full_trend=False):
        self.j_data = j_data
        self.unit = unit
        self.title = title
        self.show_full_trend = show_full_trend
        self.analysis_results = {}
        self.overall_status = "Pass"

    def basic_linear_regression(self, y_values):
        x = np.arange(len(y_values))
        y = np.array(y_values)
        x_mean = x.mean()
        y_mean = y.mean()
        numerator = np.sum((x - x_mean) * (y - y_mean))
        denominator = np.sum((x - x_mean) ** 2)
        slope = numerator / denominator if denominator != 0 else 0
        intercept = y_mean - slope * x_mean
        ss_total = np.sum((y - y_mean) ** 2)
        ss_res = np.sum((y - (slope * x + intercept)) ** 2)
        r_squared = 1 - (ss_res / ss_total) if ss_total != 0 else 0
        return slope, intercept, r_squared

    def analyze(self, data):
        checkpoints = [v for k, v in data.items() if k.startswith("test_") and isinstance(v, (int, float))]
        if len(checkpoints) < 3:
            return "Pass"
        slope, _, r_squared = self.basic_linear_regression(checkpoints)
        max_val = max(checkpoints)
        slope_threshold = 0.1 if max_val <= 100 else 0.5
        if slope > slope_threshold and r_squared > 0.6:
            return "Fail"
        return "Pass"

    def generate_failed_app_summary(self):
        red_rows = ""
        green_rows = ""
        for app, data in self.j_data.items():
            status = self.analyze(data)
            color = "green" if status == "Pass" else "red"
            row = f"""
            <tr>
                <td>{app}</td>
                <td style='white-space: pre-line;'>""" + "\n".join(f"{k}: {v}{self.unit}" for k, v in data.items()) + f"""</td>
                <td style='color: {color}; font-weight: bold;'>{status}</td>
            </tr>
            """
            if color == 'green':
                green_rows += row
            else:
                red_rows += row
        return f"""
        <h3>🔍 Evo Infra Deviation Report</h3>
        <table border='1' cellspacing='0' cellpadding='5' style='width: 100%;'>
            <tr style='background-color: #f2f2f2; font-weight: bold;'>
                <th>Application</th>
                <th>Checkpoints</th>
                <th>Status</th>
            </tr>
            {red_rows + green_rows}
        </table>
        """

    def generate_html_report(self, output_file):
        report = f"""
        <html>
        <head><title>{self.title} Observation</title></head>
        <body style='font-family: Arial;'>
            <h2 style='color:#3f51b5'>{self.title} Observation Report</h2>
            {self.generate_failed_app_summary()}
        </body>
        </html>
        """
        with open(output_file, 'w') as f:
            f.write(report)
        print(f"✅ Evo Infra report saved to: {output_file}")
        return output_file




class SystemStorageCheckReportGenerator:
    def __init__(self, j_data, title, unit, show_full_trend=False):
        self.j_data = j_data
        self.show_full_trend = show_full_trend
        self.unit = unit
        self.title = title
        self.overall_status = "Pass"
        self.analysis_results = {}  # {mount_point: (trend_status, deviation_status, lrm_status)}

    def basic_linear_regression(self, y_values):
        x = np.arange(len(y_values))
        y = np.array(y_values)

        x_mean = x.mean()
        y_mean = y.mean()

        numerator = np.sum((x - x_mean) * (y - y_mean))
        denominator = np.sum((x - x_mean) ** 2)

        slope = numerator / denominator if denominator != 0 else 0
        intercept = y_mean - slope * x_mean

        ss_total = np.sum((y - y_mean) ** 2)
        ss_res = np.sum((y - (slope * x + intercept)) ** 2)
        r_squared = 1 - (ss_res / ss_total) if ss_total != 0 else 0

        return slope, intercept, r_squared

    def analyze_storage_trend(self, data, allowed_deviation_percent=5):
        test_keys = sorted(k for k in data if k.startswith("test_"))
        test_values = [data[k] for k in test_keys if isinstance(data.get(k), (int, float))]

        if len(test_values) < 3:
            logging.warning("Not enough test_* checkpoints for trend validation.")
            trend_status = True  # Assume no leak
        else:
            slope, _, r_squared = self.basic_linear_regression(test_values)
            max_val = max(test_values)
            slope_threshold = 0.1 if max_val <= 100 else 0.5
            trend_status = not (slope > slope_threshold and r_squared > 0.6)

        test_pre = data.get("test_pre")
        test_post = data.get("test_post")
        if test_pre is None or test_post is None:
            logging.warning("Missing test_pre or test_post for deviation validation.")
            deviation_status = False
        else:
            deviation = test_post - test_pre
            threshold = (test_pre * allowed_deviation_percent) / 100
            deviation_status = deviation <= threshold

        lrm_pre = data.get("lrm_pre")
        lrm_post = data.get("lrm_post")
        if lrm_pre is None or lrm_post is None:
            logging.warning("Missing lrm_pre or lrm_post for baseline validation.")
            lrm_status = False
        else:
            lrm_status = abs(lrm_post - lrm_pre) <= 1  # exact match expected or 1 MB tolerance

        return trend_status, deviation_status, lrm_status

    def check_trend(self, app_data):
        return self.analyze_storage_trend(app_data)

    def precompute_analysis(self):
        for app, data in self.j_data.items():
            self.analysis_results[app] = self.analyze_storage_trend(data)

    def generate_high_level_summary(self):
        total_apps = len(self.j_data)
        fail_count = sum(1 for t, d, l in self.analysis_results.values() if not (t and d and l))
        pass_count = total_apps - fail_count
        if fail_count >= 1:
            self.overall_status = "Fail"

        return f"""
        <h3>Storage Utilization Summary</h3>
        <table border=\"1\" cellspacing=\"0\" cellpadding=\"5\" style=\"width: 60%;\">
            <tr style=\"background-color: #f2f2f2; font-weight: bold;\">
                <th>Total Mount Points</th>
                <th>Exceeded Usage Threshold (Fail)</th>
                <th>Usage Within Limit (Pass)</th>
            </tr>
            <tr>
                <td align=\"center\">{total_apps}</td>
                <td align=\"center\" style=\"color: red;\"><b>{fail_count}</b></td>
                <td align=\"center\" style=\"color: green;\"><b>{pass_count}</b></td>
            </tr>
        </table>
        """

    def generate_failed_app_summary(self):
        red_rows = ""
        green_rows = ""

        for app, data in self.j_data.items():
            trend_status, deviation_status, lrm_status = self.analysis_results.get(app, (False, False, False))
            trend_color = "green" if trend_status else "red"
            dev_color = "green" if deviation_status else "red"
            lrm_color = "green" if lrm_status else "red"
            row = f"""
            <tr>
                <td>{app}</td>
                <td style=\"white-space: pre-line;\">{"<br>".join([f"{k}: {v}{self.unit}" for k, v in data.items()])}</td>
                <td style=\"color: {trend_color}; font-weight: bold;\">{trend_status}</td>
                <td style=\"color: {dev_color}; font-weight: bold;\">{deviation_status}</td>
                <td style=\"color: {lrm_color}; font-weight: bold;\">{lrm_status}</td>
            </tr>
            """
            if trend_status and deviation_status and lrm_status:
                green_rows += row
            else:
                red_rows += row

        rows = red_rows + green_rows

        return f"""
        <h3>🚨 Storage Deviation Report</h3>
        <table border=\"1\" cellspacing=\"0\" cellpadding=\"5\" style=\"border-collapse: collapse; width: 100%; margin-top: 20px;\">
            <tr style=\"background-color: #f2f2f2; font-weight: bold;\">
                <th title=\"Mount point or resource being monitored\">Mount Point</th>
                <th title=\"Usage trend across checkpoints\">Checkpoint Values ({self.unit})</th>
                <th title=\"Checks for linear increase across test_* checkpoints\">Trend Check</th>
                <th title=\"Checks deviation between test_pre and test_post\">Deviation Check</th>
                <th title=\"Checks reset between lrm_pre and lrm_post\">Baseline Reset Check</th>
            </tr>
            {rows}
        </table>
        """

    def generate_full_trend_table(self):
        headers = ['Mount Point'] + list(next(iter(self.j_data.values())).keys())
        rows = ""
        for app, data in self.j_data.items():
            cells = "".join(f"<td>{data.get(k)}{self.unit}</td>" for k in headers[1:])
            rows += f"<tr><td>{app}</td>{cells}</tr>"

        header_html = "".join(f"<th>{h}</th>" for h in headers)
        return f"""
        <h3>📈 Complete Mount Point Usage Trend</h3>
        <table border=\"1\" cellspacing=\"0\" cellpadding=\"5\" style=\"width: 100%;\">
            <tr style=\"background-color: #f2f2f2; font-weight: bold;\">{header_html}</tr>
            {rows}
        </table>
        """

    def generate_html_report(self, output_file):
        self.precompute_analysis()

        report_html = f"""
        <html>
        <head><title>{self.title} Observation</title></head>
        <body style=\"font-family: Arial, sans-serif; margin: 20px;\">
            <h2 style=\"color:#3f51b5;\">{self.title} Observation Report</h2>
            {self.generate_high_level_summary()}
            {self.generate_failed_app_summary()}
        """

        if self.show_full_trend:
            report_html += self.generate_full_trend_table()

        report_html += "</body></html>"

        with open(output_file, "w") as f:
            f.write(report_html)

        print(f"✅ Storage report saved to: {output_file}")
        return output_file



class CPUUtilizationReportGenerator:
    def __init__(self, cpu_data, default_threshold=70):
        self.cpu_data = cpu_data
        self.default_threshold = default_threshold
        self.overall_status = "Pass"

    def basic_linear_regression(self, y_values):
        x = np.arange(len(y_values))
        y = np.array(y_values)
        x_mean = x.mean()
        y_mean = y.mean()
        numerator = np.sum((x - x_mean) * (y - y_mean))
        denominator = np.sum((x - x_mean) ** 2)
        slope = numerator / denominator if denominator != 0 else 0
        intercept = y_mean - slope * x_mean
        ss_total = np.sum((y - y_mean) ** 2)
        ss_res = np.sum((y - (slope * x + intercept)) ** 2)
        r_squared = 1 - (ss_res / ss_total) if ss_total != 0 else 0
        return slope, intercept, r_squared

    def check_cpu_trend(self, usage_data):
        values = list(usage_data.values())
        if len(values) < 3:
            return "Pass"
        slope, _, r_squared = self.basic_linear_regression(values)
        if slope > 0.2 and r_squared > 0.6:
            return "Fail"
        return "Pass"

    def generate_summary_table(self):
        rows = ""
        for process, data in self.cpu_data.items():
            if 'idle' in process.lower():
                continue
            status = self.check_cpu_trend(data)
            color = "green" if status == "Pass" else "red"
            if color == 'red':
                self.overall_status = "Fail"
            usage_str = ", ".join([f"{k}: {v}%" for k, v in data.items()])
            rows += f"""
            <tr>
                <td>{process}</td>
                <td>{usage_str}</td>
                <td>{self.default_threshold}%</td>
                <td style='color: {color}; font-weight: bold;'>{status}</td>
            </tr>
            """
        return f"""
        <h3>CPU Utilization Summary</h3>
        <table border='1' cellspacing='0' cellpadding='5' style='width: 90%;'>
            <tr style='background-color: #f2f2f2; font-weight: bold;'>
                <th>Process</th>
                <th>CPU Usage (Snapshots)</th>
                <th>Threshold</th>
                <th>Status</th>
            </tr>
            {rows}
        </table>
        """

    def generate_html_report(self, output_file):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        html_content = f"""
        <html>
        <head><title>CPU Utilization Report</title></head>
        <body style='font-family: Arial;'>
            <h2>CPU Utilization Analysis Report</h2>
            <p><strong>Generated:</strong> {timestamp}</p>
            {self.generate_summary_table()}
        </body>
        </html>
        """
        with open(output_file, "w") as f:
            f.write(html_content)
        print(f"✅ CPU Utilization report saved to: {output_file}")
        return output_file


class BroadcomInspectionReport:
    def __init__(self, base_dir, output_html="brcm_inspection_report.html"):
        self.base_dir = base_dir
        self.output_html = output_html
        self.logical_path = os.path.join(base_dir, "logical")
        self.diffs_path = os.path.join(base_dir, "diffs/logical")
        self.ignore_patterns = ("CTR", "STATS", "STATUS", "INFO", "TOD")
        self.overall_status = "Fail"
       
    def count_total_tables(self):
        try:
            return len(os.listdir(self.logical_path))
        except FileNotFoundError:
            print(f"Directory '{self.logical_path}' not found.")
            return 0
        except NotADirectoryError:
            print(f"'{self.logical_path}' is not a directory.")
            return 0
        except PermissionError:
            print(f"Permission denied to access '{self.logical_path}'.")
            return 0
        except Exception as e:
            print(f"An error occurred: {e}")
            return 0

    def get_failed_tables_bk(self):
        all_diffs = os.listdir(self.diffs_path)
        return sorted([f for f in all_diffs if not any(ig in f for ig in self.ignore_patterns)])

    def get_failed_tables(self):
        try:
            all_diffs = os.listdir(self.diffs_path)
        except FileNotFoundError:
            print(f"Directory '{self.diffs_path}' not found.")
            return []
        
        failed_tables = sorted(
            [f for f in all_diffs if not any(ig in f for ig in self.ignore_patterns)]
        )
        return failed_tables
    
    def generate_html(self, total_tables, failed_tables):
        passed_count = total_tables - len(failed_tables)
        summary_color = "green" if not failed_tables else "red"
        summary_status = "Pass" if not failed_tables else "Fail"
        result_folder_path = "../../../brcmsnapshot/lrm_config_post_test_brcm_snapshot/"

        html = f"""
        <html>
        <head>
            <title>Broadcom Inspection Report</title>
            <style>
                body {{ font-family: Arial; margin: 20px; }}
                h2 {{ color: #2c3e50; }}
                table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
                th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .pass {{ color: green; font-weight: bold; }}
                .fail {{ color: red; font-weight: bold; }}
                .badge {{ font-weight: bold; padding: 5px 10px; border-radius: 5px; color: white; }}
                .badge-pass {{ background-color: green; }}
                .badge-fail {{ background-color: red; }}
            </style>
        </head>
        <body>
            <h2>Broadcom Inspection Report</h2>
            <p><strong>Overall Status:</strong> <span class="badge badge-{summary_status.lower()}">{summary_status}</span>&nbsp;&nbsp;
                <strong> Report </strong> <a href="{result_folder_path}" target="_blank">Brcm Inspection Report</a></p>
            <p><strong>Total Tables Inspected:</strong> {total_tables}</p>
            <p><strong>Passed:</strong> <span class="pass">{passed_count}</span> &nbsp;&nbsp; 
               <strong>Failed:</strong> <span class="fail">{len(failed_tables)}</span></p>

            <h3>Failure Summary</h3>
            <table>
                <tr><th>Table Name</th><th>Status</th></tr>
        """

        if failed_tables:
            for table in failed_tables:
                html += f"<tr><td>{table}</td><td class='fail'>Fail</td></tr>"
        else:
            html += "<tr><td colspan='2' class='pass'>No unexpected diff tables found. All checks passed.</td></tr>"

        html += """
            </table>
        </body>
        </html>
        """
        return html

    def generate_html_report(self, output_file):
        if os.path.isdir(self.logical_path):
            total_tables = self.count_total_tables()
            failed_tables = self.get_failed_tables()
            if not failed_tables:
               self.overall_status= "Pass"
            html_content = self.generate_html(total_tables, failed_tables)
            with open(output_file, "w") as f:
                f.write(html_content)
            return output_file

# Example usage
#report = BroadcomInspectionReport("/mnt/data/brcmsnapshot/lrm_config_post_test_brcm_snapshot/")
#report.generate_report()
from datetime import timedelta

def seconds_to_hours_minutes(seconds):
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h:{minutes}m"
def generate_report(nodes_data, global_data_dict, scenario, scenario_execution_secs, host_info, log_dir):
             
    status_resp_data = {}
    for hostname, nodes_data in nodes_data.items():
        status_resp_data[hostname]={}
        #get the keys based on hostname.
        host_data_keys = get_keys_for_hostname(global_data_dict, hostname)
        log_dir = f"/volume/regressions/results/JUNOS/HEAD/mmahadevaswa/longevity/IPCLOS/conversion/converted/jpytest_logs/longevity_ipclos_20250331-200749/test_suite_iter_0/ActiveTest_Scenario1"
        brcm_dir = f"{log_dir}/brcmsnapshot/lrm_config_post_test_brcm_snapshot"
        #/volume/regressions/results/JUNOS/HEAD/mmahadevaswa/longevity/IPCLOS/conversion/converted/jpytest_logs/longevity_ipclos_20250331-200749/test_s
        #uite_iter_0/ActiveTest_Scenario1/brcmsnapshot/test_config_post_test_brcm_snapshot
        graph_loc = f"dashboard/{hostname}/lrm_config_post_test/"
        
        for node in nodes_data:
            status_resp_data[hostname][node]={}
            node_resouces_keys = filter_by_pattern(host_data_keys, node)
            #if 're0' in node:
            #    node_resource_keys.append('')
            report_generator = LongevityReportGenerator(hostname, node, graph_loc, resource_graph_links)
            #pdb.set_trace()
            for resource_usage_key in node_resouces_keys:
                
                overall_jemalloc_allocated_total_status = None
                overall_jemalloc_resident_status = None
                report_file_name = resource_usage_key.replace(".html", "_report.html")
                _data = global_data_dict[resource_usage_key]
                status_resp_data[hostname][node][resource_usage_key] =[]
                (title,unit) = extract_template_key_from_filename(resource_usage_key, hostname, node)
                #pdb.set_trace()
                error_msg = ""
                #memory_reporter_total_status = memory_reporter.overall_status
                if 'malloc' in resource_usage_key.lower() or 'mem_info' in resource_usage_key.lower() or 'ram_usage' in resource_usage_key.lower():
                    _reporter = JemallocReportGenerator(_data, title=title, unit=unit)
                    _reporter.generate_html_report(
                        f"{log_dir}/{graph_loc}{report_file_name}"
                    )
                    _reporter_total_status = _reporter.overall_status
                    
                    if _reporter.overall_status == "Fail":
                        error_msg = "Memory spike after test_post"
                elif 'sdb' in resource_usage_key.lower():
                    _reporter = EvoInfraCheckReportGenerator(_data, title=title, unit=unit)
                    _reporter.generate_html_report(
                        f"{log_dir}/{graph_loc}{report_file_name}"
                    )
                    if _reporter.overall_status == "Fail":
                        error_msg = "sdb objects counts increased after test_post"
                elif 'storage' in resource_usage_key.lower():
                    _reporter = SystemStorageCheckReportGenerator(_data, title=title, unit=unit)
                    _reporter.generate_html_report(
                        f"{log_dir}/{graph_loc}{report_file_name}"
                    )
                    if _reporter.overall_status == "Fail":
                        error_msg = "Storage has increased"
                elif 'cpu' in resource_usage_key.lower():
                    _reporter = CPUUtilizationReportGenerator(_data, default_threshold=70)
                    _reporter.generate_html_report(
                        f"{log_dir}/{graph_loc}{report_file_name}"
                    )
                    if _reporter.overall_status == "Fail":
                        error_msg = "Cpu utilization Spiked for few process.."
                elif 'brcm' in resource_usage_key.lower():           
                    _reporter = BroadcomInspectionReport(brcm_dir)
                    if os.path.isdir(_reporter.logical_path):
                        _reporter.generate_html_report(
                            f"{log_dir}/{graph_loc}{report_file_name}"
                        )
                        if _reporter.overall_status == "Fail":
                            error_msg = "Brcm tables are not cleaned up"
              
                
                status_resp_data[hostname][node][resource_usage_key]=[title, _reporter.overall_status,error_msg]       
                                 
    node_resource_data = build_node_resource_data(status_resp_data)
    #pdb.set_trace()
    # Final Report Generation
    final_html_path = f"{log_dir}/longevity_report.html"
    #dashboard_url = f"{log_dir}/"
    report_generator.generate_nodewise_resource_report(
            report_path=final_html_path,
            test_name=scenario,
            host_info={"svla-q5240-01": {"platform": "qfx5240-64od", "version": "23.4X100-D30.5-EVO"},"svla-q5240-02":{"platform": "qfx5240-64od", "version": "23.4X100-D30.5-EVO"}},
            node_resource_data=node_resource_data,
            longevity_devices={
                "svla-q5240-01": {"events": ["clear_bgp", "reload_config"], "count": 6},
                "svla-q5240-02": {"events": ["clear_bgp", "reload_config"], "count": 6}
            },
            longevity_duration=seconds_to_hours_minutes(scenario_execution_secs),
            dashboard_url="http://your-dashboard.local",
            result_html_path="analyze_results.html"
        )
    


def test_te():
    
    nodes_data = {'svla-q5240-01':['re0'],'svla-q5240-02':['re0']}
    
    global_data_dict= {'jemalloc_total_allocated_on_re0-svla-q5240-01.html':{
            'evopfemand': {'lrm_pre': 256, 'test_pre': 256, 'test_itr_0': 256, 'test_post': 256, 'lrm_post': 256},
            'cmdd': {'lrm_pre': 46, 'test_pre': 48, 'test_itr_0': 146, 'test_post': 146, 'lrm_post': 48},
            'app3': {'lrm_pre': 70, 'test_pre': 72, 'test_itr_0': 150, 'test_post': 149, 'lrm_post': 72},
        },'jemalloc_resident_usage_on_re0-svla-q5240-01.html':{
            'evopfemand': {'lrm_pre': 256, 'test_pre': 256, 'test_itr_0': 256, 'test_post': 256, 'lrm_post': 256},
            'cmdd': {'lrm_pre': 46, 'test_pre': 48, 'test_itr_0': 146, 'test_post': 46, 'lrm_post': 48},
            'app3': {'lrm_pre': 70, 'test_pre': 72, 'test_itr_0': 150, 'test_post': 70, 'lrm_post': 72},
        },'RPD_Malloc_Allocation_re0-svla-q5240-01.html':{
            'rpd': {'lrm_pre': 0.17, 'test_pre': 0.17, 'test_itr_0': 0.17, 'test_post': 0.17, 'lrm_post': 0.17},
        },'jemalloc_total_allocated_on_re0-svla-q5240-02.html':{
            'evopfemand': {'lrm_pre': 256, 'test_pre': 256, 'test_itr_0': 256, 'test_post': 256, 'lrm_post': 256},
            'cmdd': {'lrm_pre': 46, 'test_pre': 48, 'test_itr_0': 146, 'test_post': 146, 'lrm_post': 48},
            'app3': {'lrm_pre': 70, 'test_pre': 72, 'test_itr_0': 150, 'test_post': 149, 'lrm_post': 72},
        },'jemalloc_resident_usage_on_re0-svla-q5240-02.html':{
            'evopfemand': {'lrm_pre': 256, 'test_pre': 256, 'test_itr_0': 256, 'test_post': 256, 'lrm_post': 256},
            'cmdd': {'lrm_pre': 46, 'test_pre': 48, 'test_itr_0': 146, 'test_post': 46, 'lrm_post': 48},
            'app3': {'lrm_pre': 70, 'test_pre': 72, 'test_itr_0': 150, 'test_post': 70, 'lrm_post': 72},
        },'RPD_Malloc_Allocation_re0-svla-q5240-02.html':{
            'rpd': {'lrm_pre': 0.17, 'test_pre': 0.17, 'test_itr_0': 0.17, 'test_post': 0.17, 'lrm_post': 0.17},
        },'RAM_Usage_RE_ps_mem_re0-svla-q5240-01.html':{
            'EvoPfemand-main': {'lrm_pre': 0.6,'test_pre': 0.6, 'test_itr_0': 0.6, 'test_post':0.6, 'lrm_post': 0.6},
            'java':{'lrm_pre': 0.4,'test_pre': 0.4, 'test_itr_0': 0.4, 'test_post':0.4, 'lrm_post': 0.4},
            'packetio':{'lrm_pre': 0.3,'test_pre': 0.3, 'test_itr_0': 0.3, 'test_post':0.3, 'lrm_post': 0.3},
        },'RAM_Usage_RE_ps_mem_re0-svla-q5240-02.html':{
            'EvoPfemand-main': {'lrm_pre': 0.6,'test_pre': 0.6, 'test_itr_0': 0.6, 'test_post':0.6, 'lrm_post': 0.6},
            'java':{'lrm_pre': 0.4,'test_pre': 0.4, 'test_itr_0': 0.4, 'test_post':0.4, 'lrm_post': 0.4},
            'packetio':{'lrm_pre': 0.3,'test_pre': 0.3, 'test_itr_0': 0.3, 'test_post':0.3, 'lrm_post': 0.3},
        },'proc_mem_info_on_re0-svla-q5240-01.html':{
            'proc_mem_info': {'lrm_pre': 30.671,'test_pre': 30.671, 'test_itr_0': 30.671, 'test_post':30.671, 'lrm_post': 30.671}
        },'proc_mem_info_on_re0-svla-q5240-02.html':{
            'proc_mem_info': {'lrm_pre': 30.671,'test_pre': 30.671, 'test_itr_0': 30.671, 'test_post':30.671, 'lrm_post': 30.671}
        },'SDB_object_current_holds_on_node:re0-svla-q5240-02.html': {
            'rpdagent':{'lrm_pre': 6072,'test_pre': 6072, 'test_itr_0': 6072, 'test_post':6072, 'lrm_post': 6072},
            'ppmdagent':{'lrm_pre': 6032,'test_pre': 6032, 'test_itr_0': 6032, 'test_post':6092, 'lrm_post': 6072}
        },'SDB_object_current_holds_on_node:re0-svla-q5240-01.html': {
            'rpdagent':{'lrm_pre': 6072,'test_pre': 6072, 'test_itr_0': 6072, 'test_post':6072, 'lrm_post': 6072},
            'ppmdagent':{'lrm_pre': 6032,'test_pre': 6032, 'test_itr_0': 6032, 'test_post':6092, 'lrm_post': 6072}
        },'SDB_object_holds_total_on_node:re0-svla-q5240-01.html': {
            '_objmon':{'lrm_pre': 56,'test_pre': 56, 'test_itr_0': 56, 'test_post':56, 'lrm_post': 56},
            'hwdre_':{'lrm_pre': 9.65,'test_pre': 9.65, 'test_itr_0': 9.65, 'test_post':9.65, 'lrm_post': 9.65}
        },'SDB_object_holds_total_on_node:re0-svla-q5240-02.html': {
            '_objmon':{'lrm_pre': 56,'test_pre': 56, 'test_itr_0': 56, 'test_post':56, 'lrm_post': 56},
            'hwdre_':{'lrm_pre': 9.65,'test_pre': 9.65, 'test_itr_0': 9.65, 'test_post':9.65, 'lrm_post': 9.65}
        },'System_Storage_tmpfs__Usage_on_re0-svla-q5240-01.html': {
            'run':{'lrm_pre': 56,'test_pre': 56, 'test_itr_0': 56, 'test_post':56, 'lrm_post': 56},
            'dev/shm':{'lrm_pre': 9.65,'test_pre': 9.65, 'test_itr_0': 9.65, 'test_post':9.65, 'lrm_post': 9.65}
        },'System_Storage_tmpfs__Usage_on_re0-svla-q5240-02.html':{
            'run':{'lrm_pre': 1,'test_pre': 1, 'test_itr_0': 1, 'test_post':1, 'lrm_post': 1},
            'dev/shm':{'lrm_pre': 6,'test_pre': 6, 'test_itr_0': 6, 'test_post':6, 'lrm_post': 6}
        },'CPU_Usage_on_re0-svla-q5240-01.html': {
            'Idle':{'lrm_pre': 94,'test_pre': 84, 'test_itr_0': 72, 'test_post':84, 'lrm_post': 54},
            'User':{'lrm_pre': 5,'test_pre': 5, 'test_itr_0': 11, 'test_post':14, 'lrm_post': 6},
            'System':{'lrm_pre': 1,'test_pre': 3, 'test_itr_0': 4, 'test_post':2, 'lrm_post': 1},
            'tacsysb':{'lrm_pre': 1,'test_pre': 3, 'test_itr_0': 5, 'test_post':2, 'lrm_post': 1}
        },'CPU_Usage_on_re0-svla-q5240-02.html': {
            'Idle':{'lrm_pre': 94,'test_pre': 84, 'test_itr_0': 72, 'test_post':69, 'lrm_post': 54},
            'User':{'lrm_pre': 5,'test_pre': 5, 'test_itr_0': 11, 'test_post':14, 'lrm_post': 6},
            'System':{'lrm_pre': 1,'test_pre': 3, 'test_itr_0': 4, 'test_post':2, 'lrm_post': 1},
            'tacsysb':{'lrm_pre': 1,'test_pre': 3, 'test_itr_0': 5, 'test_post':2, 'lrm_post': 1}
        },'brcm_inspect_on_re0-svla-q5240-01.html': {
            'lrm_config_post_test':True,
            'test_config_post_test':True,
        }
           
    }
    scenario_execution_secs=172800
    host_info={"svla-q5240-01": {"platform": "qfx5240-64od", "version": "23.4X100-D30.5-EVO"},"svla-q5240-02":{"platform": "qfx5240-64od", "version": "23.4X100-D30.5-EVO"}}
    scenario="ActiveTestScenario1"
    log_dir = f"/volume/regressions/results/JUNOS/HEAD/mmahadevaswa/longevity/IPCLOS/conversion/converted/jpytest_logs/longevity_ipclos_20250331-200749/test_suite_iter_0/ActiveTest_Scenario1"
    generate_report(nodes_data, global_data_dict, scenario, scenario_execution_secs, host_info, log_dir)
        
    
from datetime import timedelta

class LongevityReportOrchestrator:
    def __init__(self, nodes_data, global_data_dict, scenario, scenario_execution_secs, host_info, log_dir):
        self.nodes_data = nodes_data
        self.global_data_dict = global_data_dict
        self.scenario = scenario
        self.scenario_execution_secs = scenario_execution_secs
        self.host_info = host_info
        self.log_dir = log_dir
        self.status_resp_data = {}
        self.failed_memory_apps_dict={}
       
    def seconds_to_hours_minutes(self, seconds):
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours}h:{minutes}m"

    def run(self):
        
        global _scenario
        _scenario=self.scenario
        
        #pdb.set_trace()
        for hostname, nodes_data in self.nodes_data.items():
            
            #pdb.set_trace()
            
            global global_failed_memory_apps_dict
            if hostname not in global_failed_memory_apps_dict:
                global _hostname
                _hostname = hostname
                global_failed_memory_apps_dict[hostname]={}
                
            global_failed_memory_apps_dict[hostname][self.scenario]=[]
            self.status_resp_data[hostname] = {}
            host_data_keys = get_keys_for_hostname(self.global_data_dict, hostname)
            brcm_dir = f"{self.log_dir}/brcmsnapshot/lrm_config_post_test_brcm_snapshot"
            graph_loc = f"dashboard/{hostname}/lrm_config_post_test/"

            for node in nodes_data:
                self.status_resp_data[hostname][node] = {}
                node_resouces_keys = filter_by_pattern(host_data_keys, node)
                #pdb.set_trace()
                report_generator = LongevityReportGenerator(hostname, node, graph_loc, resource_graph_links)

                for resource_usage_key in node_resouces_keys:
                    report_file_name = resource_usage_key.replace(".html", "_report.html")
                    _data = self.global_data_dict[resource_usage_key]
                    self.status_resp_data[hostname][node][resource_usage_key] = []
                    title, unit = extract_template_key_from_filename(resource_usage_key, hostname, node)
                    error_msg = ""

                    if 'malloc' in resource_usage_key.lower() or 'mem_info' in resource_usage_key.lower() or 'ram_usage' in resource_usage_key.lower():
                        _reporter = JemallocReportGenerator(_data, title=title, unit=unit)
                    elif 'sdb' in resource_usage_key.lower():
                        _reporter = EvoInfraCheckReportGenerator(_data, title=title, unit=unit)
                    elif 'storage' in resource_usage_key.lower():
                        _reporter = SystemStorageCheckReportGenerator(_data, title=title, unit=unit)
                    elif 'cpu' in resource_usage_key.lower():
                        _reporter = CPUUtilizationReportGenerator(_data, default_threshold=70)
                    elif 'brcm' in resource_usage_key.lower():
                        _reporter = BroadcomInspectionReport(brcm_dir)
                    else:
                        continue

                    _reporter.generate_html_report(f"{self.log_dir}/{graph_loc}{report_file_name}")
                    if _reporter.overall_status == "Fail":
                        if 'malloc' in resource_usage_key.lower() or 'mem_info' in resource_usage_key.lower():
                            error_msg = "Memory spike after test_post"
                        elif 'sdb' in resource_usage_key.lower():
                            error_msg = "sdb objects counts increased after test_post"
                        elif 'storage' in resource_usage_key.lower():
                            error_msg = "Storage has increased"
                        elif 'cpu' in resource_usage_key.lower():
                            error_msg = "Cpu utilization Spiked for few process.."
                        elif 'brcm' in resource_usage_key.lower():
                            error_msg = "Brcm tables are not cleaned up"

                    self.status_resp_data[hostname][node][resource_usage_key] = [title, _reporter.overall_status, error_msg]
       
        self.finalize_report(report_generator)
        #pdb.set_trace()
        self.failed_memory_apps_dict=global_failed_memory_apps_dict
        #pdb.set_trace()

    def finalize_report(self, report_generator):
        node_resource_data = build_node_resource_data(self.status_resp_data)
        final_html_path = f"{self.log_dir}/longevity_report.html"
        report_generator.generate_nodewise_resource_report(
            report_path=final_html_path,
            test_name=self.scenario,
            host_info=self.host_info,
            node_resource_data=node_resource_data,
            longevity_devices={
                "svla-q5240-01": {"events": ["clear_bgp", "reload_config"], "count": 6},
                "svla-q5240-02": {"events": ["clear_bgp", "reload_config"], "count": 6}
            },
            longevity_duration=self.seconds_to_hours_minutes(self.scenario_execution_secs),
            dashboard_url="http://your-dashboard.local",
            result_html_path="analyze_results.html"
        )

'''
if __name__ == "__main__":
    nodes_data = {'svla-q5240-01': ['re0'], 'svla-q5240-02': ['re0']}
    
    global_data_dict= {'jemalloc_total_allocated_on_re0-svla-q5240-01.html':{
            'evopfemand': {'lrm_pre': 256, 'test_pre': 256, 'test_itr_0': 256, 'test_post': 256, 'lrm_post': 256},
            'cmdd': {'lrm_pre': 46, 'test_pre': 48, 'test_itr_0': 146, 'test_post': 146, 'lrm_post': 48},
            'app3': {'lrm_pre': 70, 'test_pre': 72, 'test_itr_0': 150, 'test_post': 149, 'lrm_post': 72},
        },'jemalloc_resident_usage_on_re0-svla-q5240-01.html':{
            'evopfemand': {'lrm_pre': 256, 'test_pre': 256, 'test_itr_0': 256, 'test_post': 256, 'lrm_post': 256},
            'cmdd': {'lrm_pre': 46, 'test_pre': 48, 'test_itr_0': 146, 'test_post': 46, 'lrm_post': 48},
            'app3': {'lrm_pre': 70, 'test_pre': 72, 'test_itr_0': 150, 'test_post': 70, 'lrm_post': 72},
        },'RPD_Malloc_Allocation_re0-svla-q5240-01.html':{
            'rpd': {'lrm_pre': 0.17, 'test_pre': 0.17, 'test_itr_0': 0.17, 'test_post': 0.17, 'lrm_post': 0.17},
        },'jemalloc_total_allocated_on_re0-svla-q5240-02.html':{
            'evopfemand': {'lrm_pre': 256, 'test_pre': 256, 'test_itr_0': 256, 'test_post': 256, 'lrm_post': 256},
            'cmdd': {'lrm_pre': 46, 'test_pre': 48, 'test_itr_0': 146, 'test_post': 146, 'lrm_post': 48},
            'app3': {'lrm_pre': 70, 'test_pre': 72, 'test_itr_0': 150, 'test_post': 149, 'lrm_post': 72},
        },'jemalloc_resident_usage_on_re0-svla-q5240-02.html':{
            'evopfemand': {'lrm_pre': 256, 'test_pre': 256, 'test_itr_0': 256, 'test_post': 256, 'lrm_post': 256},
            'cmdd': {'lrm_pre': 46, 'test_pre': 48, 'test_itr_0': 146, 'test_post': 46, 'lrm_post': 48},
            'app3': {'lrm_pre': 70, 'test_pre': 72, 'test_itr_0': 150, 'test_post': 70, 'lrm_post': 72},
        },'RPD_Malloc_Allocation_re0-svla-q5240-02.html':{
            'rpd': {'lrm_pre': 0.17, 'test_pre': 0.17, 'test_itr_0': 0.17, 'test_post': 0.17, 'lrm_post': 0.17},
        },'RAM_Usage_RE_ps_mem_re0-svla-q5240-01.html':{
            'EvoPfemand-main': {'lrm_pre': 0.6,'test_pre': 0.6, 'test_itr_0': 0.6, 'test_post':0.6, 'lrm_post': 0.6},
            'java':{'lrm_pre': 0.4,'test_pre': 0.4, 'test_itr_0': 0.4, 'test_post':0.4, 'lrm_post': 0.4},
            'packetio':{'lrm_pre': 0.3,'test_pre': 0.3, 'test_itr_0': 0.3, 'test_post':0.3, 'lrm_post': 0.3},
        },'RAM_Usage_RE_ps_mem_re0-svla-q5240-02.html':{
            'EvoPfemand-main': {'lrm_pre': 0.6,'test_pre': 0.6, 'test_itr_0': 0.6, 'test_post':0.6, 'lrm_post': 0.6},
            'java':{'lrm_pre': 0.4,'test_pre': 0.4, 'test_itr_0': 0.4, 'test_post':0.4, 'lrm_post': 0.4},
            'packetio':{'lrm_pre': 0.3,'test_pre': 0.3, 'test_itr_0': 0.3, 'test_post':0.3, 'lrm_post': 0.3},
        },'proc_mem_info_on_re0-svla-q5240-01.html':{
            'proc_mem_info': {'lrm_pre': 30.671,'test_pre': 30.671, 'test_itr_0': 30.671, 'test_post':30.671, 'lrm_post': 30.671}
        },'proc_mem_info_on_re0-svla-q5240-02.html':{
            'proc_mem_info': {'lrm_pre': 30.671,'test_pre': 30.671, 'test_itr_0': 30.671, 'test_post':30.671, 'lrm_post': 30.671}
        },'SDB_object_current_holds_on_node:re0-svla-q5240-02.html': {
            'rpdagent':{'lrm_pre': 6072,'test_pre': 6072, 'test_itr_0': 6072, 'test_post':6072, 'lrm_post': 6072},
            'ppmdagent':{'lrm_pre': 6032,'test_pre': 6032, 'test_itr_0': 6032, 'test_post':6092, 'lrm_post': 6072}
        },'SDB_object_current_holds_on_node:re0-svla-q5240-01.html': {
            'rpdagent':{'lrm_pre': 6072,'test_pre': 6072, 'test_itr_0': 6072, 'test_post':6072, 'lrm_post': 6072},
            'ppmdagent':{'lrm_pre': 6032,'test_pre': 6032, 'test_itr_0': 6032, 'test_post':6092, 'lrm_post': 6072}
        },'SDB_object_holds_total_on_node:re0-svla-q5240-01.html': {
            '_objmon':{'lrm_pre': 56,'test_pre': 56, 'test_itr_0': 56, 'test_post':56, 'lrm_post': 56},
            'hwdre_':{'lrm_pre': 9.65,'test_pre': 9.65, 'test_itr_0': 9.65, 'test_post':9.65, 'lrm_post': 9.65}
        },'SDB_object_holds_total_on_node:re0-svla-q5240-02.html': {
            '_objmon':{'lrm_pre': 56,'test_pre': 56, 'test_itr_0': 56, 'test_post':56, 'lrm_post': 56},
            'hwdre_':{'lrm_pre': 9.65,'test_pre': 9.65, 'test_itr_0': 9.65, 'test_post':9.65, 'lrm_post': 9.65}
        },'System_Storage_tmpfs__Usage_on_re0-svla-q5240-01.html': {
            'run':{'lrm_pre': 56,'test_pre': 56, 'test_itr_0': 56, 'test_post':56, 'lrm_post': 56},
            'dev/shm':{'lrm_pre': 9.65,'test_pre': 9.65, 'test_itr_0': 9.65, 'test_post':9.65, 'lrm_post': 9.65}
        },'System_Storage_tmpfs__Usage_on_re0-svla-q5240-02.html':{
            'run':{'lrm_pre': 1,'test_pre': 1, 'test_itr_0': 1, 'test_post':1, 'lrm_post': 1},
            'dev/shm':{'lrm_pre': 6,'test_pre': 6, 'test_itr_0': 6, 'test_post':6, 'lrm_post': 6}
        },'CPU_Usage_on_re0-svla-q5240-01.html': {
            'Idle':{'lrm_pre': 94,'test_pre': 84, 'test_itr_0': 72, 'test_post':84, 'lrm_post': 54},
            'User':{'lrm_pre': 5,'test_pre': 5, 'test_itr_0': 11, 'test_post':14, 'lrm_post': 6},
            'System':{'lrm_pre': 1,'test_pre': 3, 'test_itr_0': 4, 'test_post':2, 'lrm_post': 1},
            'tacsysb':{'lrm_pre': 1,'test_pre': 3, 'test_itr_0': 5, 'test_post':2, 'lrm_post': 1}
        },'CPU_Usage_on_re0-svla-q5240-02.html': {
            'Idle':{'lrm_pre': 94,'test_pre': 84, 'test_itr_0': 72, 'test_post':69, 'lrm_post': 54},
            'User':{'lrm_pre': 5,'test_pre': 5, 'test_itr_0': 11, 'test_post':14, 'lrm_post': 6},
            'System':{'lrm_pre': 1,'test_pre': 3, 'test_itr_0': 4, 'test_post':2, 'lrm_post': 1},
            'tacsysb':{'lrm_pre': 1,'test_pre': 3, 'test_itr_0': 5, 'test_post':2, 'lrm_post': 1}
        },'brcm_inspect_on_re0-svla-q5240-01.html': {
            'lrm_config_post_test':True,
            'test_config_post_test':True,
        }
           
    }
    #global_data_dict = {}  # placeholder, fill with actual test data structure
    scenario_execution_secs = 172800
    host_info = {
        "svla-q5240-01": {"platform": "qfx5240-64od", "version": "23.4X100-D30.5-EVO"},
        "svla-q5240-02": {"platform": "qfx5240-64od", "version": "23.4X100-D30.5-EVO"}
    }
    scenario = "ActiveTestScenario1"
    log_dir = "/volume/regressions/results/JUNOS/HEAD/mmahadevaswa/longevity/IPCLOS/conversion/converted/jpytest_logs/longevity_ipclos_20250331-200749/test_suite_iter_0/ActiveTest_Scenario1"
    brcm_host_names=['svla-q5240-01']
    orchestrator = LongevityReportOrchestrator(
        nodes_data=nodes_data,
        global_data_dict=global_data_dict,
        scenario=scenario,
        scenario_execution_secs=scenario_execution_secs,
        host_info=host_info,
        log_dir=log_dir
    )
    orchestrator.run()
'''