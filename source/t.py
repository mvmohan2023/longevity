import pdb
def extract_template_key_from_filename(filename, hostname, node):
    
    templates = {
        "CPU Usage": ["CPU_Usage_on_{node}-{hostname}.html","%"],
        "NPU Memory Utilization": ["NPU_Memory_Utilization_on_{node_upper}-{hostname}.html","%"],
        "RAM Usage": ["RAM_Usage_{node}_ps_mem-{hostname}.html","GB"],
        "RPD Malloc Allocation": ["RPD_Malloc_Allocation-{node}-{hostname}.html","GB"],
        "SDB Live Objects": ["SDB_live_objects_{node}-{hostname}.html","k"],
        "SDB Object Current Holds": ["SDB_object_current_holds_on_node:{node}-{hostname}.html","k"],
        "SDB Object Total Holds": ["SDB_object_holds_total_on_node:{node}-{hostname}.html","k"],
        "System Storage": ["System_Storage_tmpfs__Usage_on_{node}-{hostname}.html","%"],
        "Jemalloc Resident": ["jemalloc_resident_usage_on_{node}-{hostname}.html","MB"],
        "Jemalloc Allocated": ["jemalloc_total_allocated_on_{node}-{hostname}.html","MB"],
        "Proc Mem Info": ["proc_mem_info_on_{node_upper}-{hostname}.html","MB"],
    }
    node_upper = node.upper()

    for key, template in templates.items():
        #pdb.set_trace()
        # Fill in the known parts
        expected_pattern = template[0].format(node=node, node_upper=node_upper, hostname=hostname)

        # Use "in" or "infix match" to avoid exact match requirement
        #pdb.set_trace()
        if expected_pattern in filename:
            #pdb.set_trace()
            return (key,template[1])
    return (None,None)  # No match found
filename = "CPU_Usage_on_re0-svla-q5240-01.html"
filename = "System_Storage_tmpfs__Usage_on_re0-svla-q5240-01.html"
filename = "RAM_Usage_re0_ps_mem-svla-q5240-01.html"
hostname = "svla-q5240-01"
node = "re0"

(result, unit) = extract_template_key_from_filename(filename, hostname, node)
print("Matched Resource Key:", result, unit)

