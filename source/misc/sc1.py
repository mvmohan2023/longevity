import subprocess

switches = [
    'san-q5130-01', 'san-q5220-01', 'san-q5230-01', 'san-q5240-01', 'san-q5240-02',
    'san-q5240-03', 'san-q5240-15', 'san-q5240-q02']
#switches= ['san-q5240-03','san-q5240-15','san-q5240-q02','san-q5230-01','san-q5220-01','san-q5130-01']
#switches = [
#    'san-q5240-15', 'san-q5240-q02'
#]
files_info= {'san-q5130-01':'debug_collector_2025-06-27_15_57_29.tar.gz','san-q5240-02':'debug_collector_2025-06-27_15_50_16.tar.gz','san-q5230-01':"debug_collector_2025-06-27_15_56_38.tar.gz",'san-q5240-q02':'debug_collector_2025-06-27_15_53_04.tar.gz',
'san-q5240-15':'debug_collector_2025-06-27_15_55_21.tar.gz','san-q5240-03':'ddebug_collector_2025-06-27_15_33_04.tar.gz'}
password = "Embe1mpls"

for switch in switches:

    #src_path = "/volume/baas-scratch/ajaykh/images/junos-evo-install-qfx-ms-x86-64-23.4I20250626193926-EVO_ajaykh.iso"
    src_path = "/volume/cd/evo/images/evo-rel-25.3/rel_253-202508151100.0/junos-evo-install-qfx-ms-x86-64-25.3-202508151100.0-EVO.iso"
    #src_path = f"root@{switch}://var/tmp/{files_info[switch]}"
    dst_path = f"root@{switch}://var/tmp/"   
    #dst_path = f"/volume/labcores/PR/PR-1889672/jun27/{switch}_debug_collector.tar.gz"
    
    

    scp_cmd = f"sshpass -p '{password}' scp {src_path} {dst_path}"
    print(f"Executing: {scp_cmd}")
    subprocess.run(scp_cmd, shell=True)
