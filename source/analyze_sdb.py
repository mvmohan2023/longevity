

import os
import re
import glob
import numpy as np
from tabulate import tabulate
import csv

import plotly.graph_objects as go

class MemoryLeakDetector:
    def extract_sdb_live_objects(self, log_file):
        try:
            with open(log_file, 'r') as file:
                content = file.read()
                pattern = r"show platform distributor statistics summary.*?SDB live objects\s*:\s*(\d+)"
                match = re.search(pattern, content, re.DOTALL)
                if match:
                    return match.group(1)
        except Exception as e:
            print(f"Error reading {log_file}: {str(e)}")
        return None



    def plot_sdb_live_objects(self, switch_results):
        fig = go.Figure()
        test_points = ['lrm_pre1', 'lrm_post1', 'lrm_pre2', 'lrm_post2', 'lrm_pre3', 'lrm_post3']
        for switch, results in switch_results.items():
            values = [int(results[key]) for key in test_points if key in results]
            fig.add_trace(go.Scatter(x=test_points[:len(values)], y=values, name=switch))
        fig.update_layout(title='SDB Live Objects Trend', xaxis_title='Test Point', yaxis_title='SDB Live Objects')
        fig.update_xaxes(tickangle=45)
        fig.write_html('sdb_live_objects_trend.html')
        fig.show()
                
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
        combined_values = []
        for key in ["lrm_pre1", "lrm_post1", "lrm_pre2", "lrm_post2", "lrm_pre3", "lrm_post3"]:
            if key in data:
                combined_values.append(int(data[key]))

        if not combined_values or len(combined_values) < 3:
            return False

        test_pre = combined_values[0]
        lrm_post = combined_values[-1]
        baseline_ok = lrm_post <= test_pre

        slope, _, r_squared = self.basic_linear_regression(combined_values)
        max_val = max(combined_values)
        slope_threshold = 0.1 if max_val <= 100 else 0.5

        leak_suspected = not baseline_ok and slope > slope_threshold and r_squared > 0.6
        return not leak_suspected

    def detect_memory_leak(self, switch_results):
        for switch, data in switch_results.items():
            leak_detected = not self.check_memory_trend(data)
            print(f"Switch: {switch}, Memory Leak Detected: {leak_detected}")

    def main(self):
        log_folder ="/volume/regressions/results/JUNOS/HEAD/mmahadevaswa/longevity/IPCLOS/conversion/converted/jpytest_logs/longevity_ipclos_20250626-113011/test_suite_iter_0" 
        switches = ['san-q5240-15','san-q5240-q02','san-q5240-01','san-q5240-02','san-q5240-03','san-q5230-01','san-q5130-01']
        checkpoints = ["lrm_config_pre_test", "lrm_config_post_test"]
        scenarios = ["ActiveTest_Scenario1", "ActiveTest_Scenario2", "ActiveTest_Scenario3"]

        switch_results = {}
        csv_results = []

        with open('sdb_live_objects.csv', 'w', newline='') as csvfile:
            fieldnames = ['Switch', 'Scenario', 'Checkpoint', 'Log File', 'SDB Live Objects']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for switch in switches:
                switch_results[switch] = {}
                for scenario_index, scenario in enumerate(scenarios):
                    for checkpoint in checkpoints:
                        if checkpoint == "lrm_config_pre_test":
                            key = f"lrm_pre{scenario_index+1}"
                        else:
                            key = f"lrm_post{scenario_index+1}"
                        pattern = f"{log_folder}/{scenario}/{checkpoint}/{switch}.{checkpoint}.*.log"
                        log_files = glob.glob(pattern)
                        
                        if log_files:
                            for log_file in log_files:
                                sdb_live_objects = self.extract_sdb_live_objects(log_file)
                                if sdb_live_objects is not None:
                                    switch_results[switch][key] = sdb_live_objects
                                    writer.writerow({
                                        'Switch': switch,
                                        'Scenario': scenario,
                                'Checkpoint': checkpoint,
                                'Log File': log_file,
                                'SDB Live Objects': sdb_live_objects
                            })
                        else:
                            print(f"No log files found for switch {switch}, scenario {scenario}, checkpoint {checkpoint}")

        for switch, results in switch_results.items():
            print(f"\nSwitch: {switch}")
            print(results)

        self.detect_memory_leak(switch_results)
        self.plot_sdb_live_objects(switch_results)


if __name__ == "__main__":
    detector = MemoryLeakDetector()
    detector.main()