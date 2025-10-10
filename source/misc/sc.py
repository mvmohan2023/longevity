import subprocess

switches = [
    'san-q5130-01', 'san-q5220-01', 'san-q5230-01', 'san-q5240-01', 'san-q5240-02',
    'san-q5240-03', 'san-q5240-15', 'san-q5240-q02'
]

scenarios = ['ActiveTest_Scenario1', 'ActiveTest_Scenario2', 'ActiveTest_Scenario3']
reports = [
    #{'src': 'jemalloc_resident_usage_on_re0-', 'dst': 'jemalloc_resident_usage_on_re0-'},
    #{'src': 'jemalloc_total_allocated_on_re0-', 'dst': 'jemalloc_total_allocated_on_re0-'}
    {'src': 'SDB_live_objects_re0-','dst': 'SDB_live_objects_re0-'}
]

password = "Embe1mpls"

for switch in switches:
    for scenario in scenarios:
        for report in reports:
            src_path = f"{scenario}/dashboard/{switch}/lrm_config_post_test/{report['src']}{switch}*report.html"
            if scenario == 'ActiveTest_Scenario1':
                dst_path = f"root@san-jvision-02:/root/longevity/{switch}/{report['dst']}{switch}_report_{scenarios.index(scenario)+1}.html"
            elif scenario == 'ActiveTest_Scenario2':
                dst_path = f"root@san-jvision-02:/root/longevity/{switch}/{report['dst']}{switch}_report_{scenarios.index(scenario)+1}.html"
            else:
                dst_path = f"root@san-jvision-02:/root/longevity/{switch}/{report['dst']}{switch}_report_{scenarios.index(scenario)+1}.html"

            scp_cmd = f"sshpass -p '{password}' scp {src_path} {dst_path}"
            print(f"Executing: {scp_cmd}")
            subprocess.run(scp_cmd, shell=True)
