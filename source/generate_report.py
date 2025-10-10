from datetime import datetime

from datetime import datetime
import pdb
def generate_nodewise_resource_report(
    report_path,
    test_name,
    host_info,
    node_resource_data,
    longevity_devices,
    longevity_duration,
    dashboard_url,
    result_html_path,
    resource_graph_links
):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def render_status(status):
        color = "#8BC34A" if status == "Pass" else "#F44336"
        return f'<span style="color:{color};font-weight:bold">{status}</span>'

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

    # Host Info Section
    html += "<h2>Host Information</h2><table><tr><th>Host</th><th>Platform</th><th>Version</th></tr>"
    for host, data in host_info.items():
        html += f"<tr><td>{host}</td><td>{data['platform']}</td><td>{data['version']}</td></tr>"
    html += "</table>"

    # Node Resource Validation Table
    html += "<h2>Resource Validation per Node</h2>"
    for node, resources in node_resource_data.items():
        html += f"<h3>Node: {node}</h3><table><tr><th>Resource</th><th>Status</th><th>Details</th><th>Graph</th></tr>"
        for res_name, res_data in resources.items():
            status = res_data.get("status", "Unknown")
            details = res_data.get("details", "")
            key = f"{res_name}_{node}"
            graph_info = resource_graph_links.get(key, {})
            graph_file = graph_info.get("graph", "")
            report_file = graph_info.get("report", "")
            graph_file = resource_graph_links.get(key, "")
            #graph_link = f'<a href="{graph_file}" target="_blank">{graph_file}</a>' if graph_file else "N/A"
            #graph_file = resource_graph_links.get(res_name, "")
            if graph_file:
                #thumbnail = f'<a href="{graph_file}" target="_blank"><img src="{graph_file}" alt="graph" height="80"></a>'
                thumbnail = f'''
                <a href="{graph_file}" target="_blank" title="View Graph">
                    &#128200;
                </a>
                '''
            else:
                thumbnail = "N/A"
            report_img = ""
            #pdb.set_trace()
            if report_file:
                report_img = (
                    f'<a href="{report_file}" target="_blank">'
                    f'<img src="https://cdn-icons-png.flaticon.com/512/337/337946.png" alt="report" height="30">'
                    f'</a>'
                )
            
            html += f"<tr><td>{res_name}</td><td>{render_status(status)}</td><td>{report_img}</td><td>{thumbnail}</td></tr>"
        html += "</table>"

    # Longevity Device Event Summary
    html += "<h2>Longevity DUT Events</h2><table><tr><th>DUT</th><th>Events</th><th>Times Executed</th></tr>"
    for dut, data in longevity_devices.items():
        html += f"<tr><td>{dut}</td><td>{', '.join(data['events'])}</td><td>{data['count']}</td></tr>"
    html += "</table>"

    html += "</body></html>"

    with open(report_path, "w") as f:
        f.write(html)

    return report_path



def build_resource_graph_links_old(node, hostname, graph_loc="graphs/"):
    resource_graph_links = {
        f"Cpu Usage_{node}": f"{graph_loc}CPU_Usage_on_{node}-{hostname}.html",
        f"Total RAM Usage per Program (Private + Shared)_{node}": f"{graph_loc}RAM_Usage_RE_ps_mem--{hostname}.html",
        f"RPD Malloc Allocation_{node}": f"{graph_loc}RPD_Malloc_Allocation-{hostname}.html",
        f"SDB Object current Holds - Total_{node}": f"{graph_loc}SDB_object_current_holds_on_node:{node}-{hostname}.html",
        f"SDB Object Holds- Total_{node}": f"{graph_loc}SDB_object_holds_total_on_node:{node}-{hostname}.html",
        f"System Storage_{node}": f"{graph_loc}System_Storage_tmpfs__Usage_on_{node}-{hostname}.html",
        f"Jemalloc Resident Usage_{node}": f"{graph_loc}jemalloc_resident_usage_on_{node}-{hostname}.html",
        f"Jemalloc Allocated[total]_{node}": f"{graph_loc}jemalloc_total_allocated_on_{node}-{hostname}.html",
        f"Proc_mem_info_{node}": f"{graph_loc}proc_mem_info_on_{node.upper()}-{hostname}.html"
    }
    
    return resource_graph_links

def build_resource_graph_links(node, hostname, graph_loc="graphs/"):
    base_mapping = {
        "Cpu Usage_{node}": "CPU_Usage_on_{node}-{hostname}.html",
        "Total RAM Usage per Program (Private + Shared)_{node}": "RAM_Usage_RE_ps_mem-{node}-{hostname}.html",
        "RPD Malloc Allocation_{node}": "RPD_Malloc_Allocation-{node}-{hostname}.html",
        "SDB Object current Holds - Total_{node}": "SDB_object_current_holds_on_node:{node}-{hostname}.html",
        "SDB Object Holds- Total_{node}": "SDB_object_holds_total_on_node:{node}-{hostname}.html",
        "System Storage_{node}": "System_Storage_tmpfs__Usage_on_{node}-{hostname}.html",
        "Jemalloc Resident Usage_{node}": "jemalloc_resident_usage_on_{node}-{hostname}.html",
        "Jemalloc Allocated[total]_{node}": "jemalloc_total_allocated_on_{node}-{hostname}.html",
        "Proc_mem_info_{node}": "proc_mem_info_on_{node}-{hostname}.html"
    }

    graph_links = {}
    for key_template, file_template in base_mapping.items():
        key = key_template.format(node=node)
        file_name = file_template.format(node=node, hostname=hostname)
        report_file_name = file_name.replace(".html", "_report.html")
        graph_links[key] = {
            "graph": f"{graph_loc}{file_name}",
            "report": f"{graph_loc}{report_file_name}"
        }

    return graph_links




import os

# Sample Jemalloc Data
jemalloc_data = {
    'evopfemand': {'lrm_pre': 256, 'test_pre': 256, 'test_itr_0': 256, 'test_post': 256, 'lrm_post': 256},
    'cmdd': {'lrm_pre': 46, 'test_pre': 48, 'test_itr_0': 146, 'test_post': 146, 'lrm_post': 48},
    'app3': {'lrm_pre': 70, 'test_pre': 72, 'test_itr_0': 150, 'test_post': 149, 'lrm_post': 72},
    'app4': {'lrm_pre': 34, 'test_pre': 36, 'test_itr_0': 36, 'test_post': 36, 'lrm_post': 36}
}

# Define output file
hostname = "svla-q5240-01"
html_file_path = f"/volume/regressions/results/JUNOS/HEAD/mmahadevaswa/longevity/IPCLOS/conversion/converted/jpytest_logs/longevity_ipclos_20250331-200749/test_suite_iter_0/ActiveTest_Scenario1/dashboard/{hostname}/lrm_config_post_test/jemalloc_total_allocated_on_re0-{hostname}_report.html"

def check_memory_trend(app_data):
    """
    Checks memory trend between test_itr_0 and test_post to determine Pass/Fail.
    Pass: Memory remains the same or shows a linear trend.
    Fail: Memory deviates or reduces abnormally (potential memory leak).
    """
    test_itr_0_value = app_data.get('test_itr_0')
    test_post_value = app_data.get('test_post')

    # Check if memory remains the same or shows linear progression
    if test_itr_0_value == test_post_value or test_itr_0_value < test_post_value:
        return "Pass"  # No memory leak or abnormal behavior
    return "Fail"  # Potential memory leak or abnormality

def generate_high_level_summary(jemalloc_data):
    """Generates a high-level summary table."""
    total_apps = len(jemalloc_data)
    pass_count = sum(1 for app, data in jemalloc_data.items() if check_memory_trend(data) == "Pass")
    fail_count = total_apps - pass_count

    summary_html = f"""
    <h3>High-Level Summary</h3>
    <table border="1" cellspacing="0" cellpadding="5" style="border-collapse: collapse; width: 60%; margin-top: 20px;">
        <tr style="background-color: #f2f2f2; font-weight: bold;">
            <th>Total Processes</th>
            <th>Applications with Memory Leak Indicated</th>
            <th>Applications with No Memory Leak</th>
        </tr>
        <tr>
            <td style="text-align: center;">{total_apps}</td>
            <td style="text-align: center; color: red; font-weight: bold;">{fail_count}</td>
            <td style="text-align: center; color: green; font-weight: bold;">{pass_count}</td>
        </tr>
    </table>
    """
    return summary_html

def generate_failed_app_summary(jemalloc_data):
    """Generates a table summarizing only failed applications."""
    rows = ""
    for app, data in jemalloc_data.items():
        status = check_memory_trend(data)
        if status == "Fail":
            row = f"""
            <tr>
                <td>{app}</td>
                <td>{", ".join([f"{k}: {v}MB" for k, v in data.items()])}</td>
                <td style="color: red; font-weight: bold;">{status}</td>
            </tr>
            """
            rows += row

    if not rows:
        rows = """
        <tr>
            <td colspan="3" style="text-align: center; font-weight: bold;">✅ No Failed Applications Detected</td>
        </tr>
        """

    failed_summary_html = f"""
    <h3>Failed Application Summary</h3>
    <table border="1" cellspacing="0" cellpadding="5" style="border-collapse: collapse; width: 100%; margin-top: 20px;">
        <tr style="background-color: #f2f2f2; font-weight: bold;">
            <th>Application</th>
            <th>Memory Checkpoints (MB)</th>
            <th>Status</th>
        </tr>
        {rows}
    </table>
    """
    return failed_summary_html

def generate_html_report(jemalloc_data, output_file):
 
    """Generates the HTML report with high-level summary and failed app summary."""
    high_level_summary = generate_high_level_summary(jemalloc_data)
    failed_app_summary = generate_failed_app_summary(jemalloc_data)

    html_content = f"""
    <html>
    <head>
        <title>Jemalloc Observation Report</title>
    </head>
    <body style="font-family: Arial, sans-serif; margin: 20px;">
        <h2 style="color: #333;">Jemalloc Memory Observation Report</h2>
        {high_level_summary}
        {failed_app_summary}
    </body>
    </html>
    """

    with open(output_file, "w") as file:
        file.write(html_content)

# Generate the HTML Report
generate_html_report(jemalloc_data, html_file_path)
print(f"✅ HTML report generated: {html_file_path}")



















node = "re0"
hostname = "svla-q5240-01"
graph_loc=f"dashboard/{hostname}/lrm_config_post_test/"

resource_graph_links = build_resource_graph_links(node, hostname, graph_loc=graph_loc)










path = generate_nodewise_resource_report(
    report_path="/volume/regressions/results/JUNOS/HEAD/mmahadevaswa/longevity/IPCLOS/conversion/converted/jpytest_logs/longevity_ipclos_20250331-200749/test_suite_iter_0/ActiveTest_Scenario1/longevity_report.html",
    test_name="TestSample1",
    host_info={
        "svla-q5240-01": {"platform": "qfx5240-64od", "version": "23.4X100-D30.5-EVO"},
    },
    node_resource_data={
        "re0": {
            "RPD Malloc Allocation": {"status": "Pass"},
            "Total RAM Usage per Program (Private + Shared)": {"status": "Pass"},
            "Jemalloc Allocated[total]": {"status": "Fail", "details": "Memory spike after test_post"},
            "Jemalloc Resident Usage":{"status": "Pass"},
            "Cpu Usage":{"status": "Pass"},
            "System Storage":{"status": "Pass"},
            "Proc_mem_info":{"status": "Pass"},
            "SDB Object Holds- Total":{"status": "Pass"},
            "SDB Object current  Holds - Total": {"status": "Pass"},
            
        },
        "fpc0": {
            "Cpu Usage": {"status": "Pass"},
            "System Storage": {"status": "Fail", "details": "Usage > 85%"},
        }
    },
    longevity_devices={
        "longevity_device1": {"events": ["clear_bgp", "reload_config"], "count": 6}
    },
    longevity_duration="7h 15m",
    dashboard_url="http://your-dashboard.local",
    result_html_path="analyze_results.html",
    resource_graph_links=resource_graph_links
)
print(path)