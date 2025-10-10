import os

# Sample Jemalloc Data
jemalloc_data = {
    'evopfemand': {'lrm_pre': 256, 'test_pre': 256, 'test_itr_0': 256, 'test_post': 256, 'lrm_post': 256},
    'cmdd': {'lrm_pre': 46, 'test_pre': 48, 'test_itr_0': 146, 'test_post': 146, 'lrm_post': 48},
    'app3': {'lrm_pre': 70, 'test_pre': 72, 'test_itr_0': 150, 'test_post': 149, 'lrm_post': 72},
    'app4': {'lrm_pre': 34, 'test_pre': 36, 'test_itr_0': 36, 'test_post': 36, 'lrm_post': 36}
}

# Define output file
html_file_path = "jemalloc_observation.html"

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
    <h3>📊 High-Level Summary</h3>
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
    <h3>❌ Failed Application Summary</h3>
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
