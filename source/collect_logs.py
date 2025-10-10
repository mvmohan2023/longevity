import os
import pdb
def find_log_files(path, switches, test_scenarios):
    configs = ["lrm_config_pre_test", "test_config_pre_test", "test_config_itr_0", "test_config_post_test", "lrm_config_post_test"]
    configs = ["lrm_config_pre_test", "lrm_config_post_test"]
    for switch in switches:
        print("\n\n")
        for scenario in test_scenarios:
            print(f"\n==={scenario} logs of {switch}=======\n")
            for config in configs:
                dir_path = os.path.join(path, scenario, config)
                #pdb.set_trace()
                if os.path.exists(dir_path):
                    for file in os.listdir(dir_path):
                        if file.startswith(switch + ".") and file.endswith(".log"):
                            print(f"file_path:{os.path.join(dir_path, file)}")
                            l_file = os.path.join(dir_path, file).split('jpytest_logs')
                            #print("l_file[1])
                            
                            print(f"Url: https://ttqc-web01.juniper.net/~mmahadevaswa/jpytest_logs{l_file[1]}")

path = "/volume/regressions/results/JUNOS/HEAD/mmahadevaswa/longevity/IPCLOS/conversion/converted/jpytest_logs/longevity_ipclos_20250614-112624/test_suite_iter_0/"
switches = ['san-q5240-15','san-q5240-q02','']
switches= ['san-q5240-02','san-q5240-03','san-q5240-15','san-q5240-q02','san-q5230-01','san-q5220-01','san-q5130-01']
test_scenarios = ["ActiveTest_Scenario1", "ActiveTest_Scenario2", "ActiveTest_Scenario3"]


find_log_files(path, switches, test_scenarios)