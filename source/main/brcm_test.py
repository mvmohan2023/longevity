import sys
import os

# If `brcm_inspect.py` is in a different directory, add its path


# Import the class
from brcm_snapshot import BRCMDataCollector

if __name__ == "__main__":
    
    
    collector = BRCMDataCollector(
        host="10.83.6.47",
        user="root",
        remote_dir="/var/log/batch_cli",
        local_dir="/path/to/local/log/dir",
        qfx_switch="svla-q5240-01.englab.juniper.net",
        root_passwd="Embe1mpls",
        longevity_dir="/volume/regressions/results/JUNOS/HEAD/mmahadevaswa/longevity/IPCLOS/conversion/converted/logs/",
        scenario="Active_test_scenario1",
        check_point="lrm_config_pre_test"
    )
    
    # Execute the collection process
    snap_dir = collector.execute()
    
    
    print(snap_dir)
    
    collector = BRCMDataCollector(
        host="10.83.6.47",
        user="root",
        remote_dir="/var/log/batch_cli",
        local_dir="/path/to/local/log/dir",
        qfx_switch="svla-q5240-01.englab.juniper.net",
        root_passwd="Embe1mpls",
        longevity_dir="/volume/regressions/results/JUNOS/HEAD/mmahadevaswa/longevity/IPCLOS/conversion/converted/logs/",
        scenario="Active_test_scenario1",
        check_point="lrm_config_post_test",
        base_dir=snap_dir
    )
    snap_dir = collector.execute()
    
    print(snap_dir)
