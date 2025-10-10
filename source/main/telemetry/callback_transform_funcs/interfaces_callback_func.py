import re
def interface_prefix(gnmi_value, cli_value):    
    # Variations accomodation
    if cli_value == "None":
        cli_value = "32"
    else:
        cli_value = cli_value.split("/")[1]
        
    if str(gnmi_value) == str(cli_value):
        print(f"Comparision passed for {gnmi_value} vs {cli_value}")
        return True
    else:
        print(f"Comparision failed for {gnmi_value} vs {cli_value}")
        return False

def interfaces_mtu(gnmi_value, cli_value):
    # Variations accomodation
    if cli_value == "Unlimited":
        cli_value = "4294967295"
        
    if str(gnmi_value) == str(cli_value):
        print(f"Comparision passed for {gnmi_value} vs {cli_value}")
        return True
    else:
        print(f"Comparision failed for {gnmi_value} vs {cli_value}")
        return False

def interfaces_type(gnmi_value, cli_value):
    # Variations accomodation
    print(gnmi_value, cli_value)
    if cli_value == "Ethernet" and gnmi_value != "other":
        cli_value = "ethernetCsmacd"
    elif cli_value == "Unspecified":
        cli_value = "softwareLoopback"
    else:    
        cli_value = "other"

    if str(gnmi_value) == str(cli_value):
        print(f"Comparision passed for {gnmi_value} vs {cli_value}")
        return True
    else:
        print(f"Comparision failed for {gnmi_value} vs {cli_value}")
        return False
def interfaces_status(gnmi_value, cli_value):
    # Variations accomodation
    if cli_value == "up":
        cli_value = "true"

    if str(gnmi_value) == str(cli_value):
        print(f"Comparision passed for {gnmi_value} vs {cli_value}")
        return True
    else:
        print(f"Comparision failed for {gnmi_value} vs {cli_value}")
        return False
def interfaces_loopback(gnmi_value, cli_value):
    # Variations accomodation
    print(gnmi_value, cli_value)
    if cli_value == "disabled" or cli_value == "None":
        cli_value = "NONE"

    if str(gnmi_value) == str(cli_value):
        print(f"Comparision passed for {gnmi_value} vs {cli_value}")
        return True
    else:
        print(f"Comparision failed for {gnmi_value} vs {cli_value}")
        return False
def interfaces_description(gnmi_value, cli_value):
    # Variations accomodation
    print(f"{gnmi_value}##### {cli_value}####")
    if gnmi_value == "":
        gnmi_value = "None"
    print(f"{gnmi_value}##### {cli_value}####")
    if str(gnmi_value) == str(cli_value):
        print(f"Comparision passed for {gnmi_value} vs {cli_value}")
        return True
    else:
        print(f"Comparision failed for {gnmi_value} vs {cli_value}")
        return False
def interfaces_subinterfaces_name(gnmi_value, cli_value):
    # Variations accomodation
    print(f"{gnmi_value}##### {cli_value}####")
    if gnmi_value == "":
        cli_value = "None"

    if str(gnmi_value) == str(cli_value):
        print(f"Comparision passed for {gnmi_value} vs {cli_value}")
        return True
    else:
        print(f"Comparision failed for {gnmi_value} vs {cli_value}")
        return False
def interfaces_logical(gnmi_value, cli_value):
    # Variations accomodation
    print(f"{gnmi_value}##### {cli_value}####")
    if cli_value == "\n        " or cli_value == "None":
        cli_value = "false"

    if str(gnmi_value) == str(cli_value):
        print(f"Comparision passed for {gnmi_value} vs {cli_value}")
        return True
    else:
        print(f"Comparision failed for {gnmi_value} vs {cli_value}")
        return False
def interfaces_logical_ifl(gnmi_value, cli_value):
    # Variations accomodation
    print(f"{gnmi_value}##### {cli_value}####")
    if "." in cli_value:
        cli_value = "true"

    if str(gnmi_value) == str(cli_value):
        print(f"Comparision passed for {gnmi_value} vs {cli_value}")
        return True
    else:
        print(f"Comparision failed for {gnmi_value} vs {cli_value}")
        return False
def ae_interfaces_speed(gnmi_value, cli_value):
    # Variations accomodation
    cli_value=re.findall("(\d+)",cli_value)
    cli_value=int(cli_value[0])*1000
    #if cli_value == "\n        " or cli_value == "None":
    #    cli_value = "false"
    if str(gnmi_value) == str(cli_value):
        print(f"Comparision passed for {gnmi_value} vs {cli_value}")
        return True
    else:
        print(f"Comparision failed for {gnmi_value} vs {cli_value}")
        return False

def port_speed(gnmi_value, cli_value):
    # Variations accomodation
    cli_value=re.findall("(\d+)",cli_value)
    cli_value=int(cli_value[0])
    gnmi_value=re.findall("(\d+)",gnmi_value)
    gnmi_value=int(gnmi_value[0])
    #if cli_value == "\n        " or cli_value == "None":
    #    cli_value = "false"
    if str(gnmi_value) == str(cli_value):
        print(f"Comparision passed for {gnmi_value} vs {cli_value}")
        return True
    else:
        print(f"Comparision failed for {gnmi_value} vs {cli_value}")
        return False

def system_processes_pid_0(gnmi_value, cli_value):
    # Removing [] from cli ouput. [kernel] to kernel
    if cli_value.startswith("["):
        cli_value = cli_value[1:-1]
        
    if gnmi_value == cli_value:
        print(f"Comparision passed for {gnmi_value} vs {cli_value}")
        return True
    else:
        print(f"Comparision failed for {gnmi_value} vs {cli_value}")
        return False

def system_processes_pid_all(gnmi_value, cli_value):
    # Removing [] from cli ouput. [kernel] to kernel
    if cli_value.startswith("["):
        cli_value = cli_value[1:-1]
    # Removing d from gnmi output. kernel_d to kernel
    if gnmi_value.endswith("d"):
        gnmi_value = gnmi_value[:-1]
        
    if gnmi_value in cli_value:
        print(f"Comparision passed for {gnmi_value} vs {cli_value}")
        return True
    else:
        print(f"Comparision failed for {gnmi_value} vs {cli_value}")
        return False

def interfaces_lldp_counter(gnmi_value, cli_value):
    # Variations accomodation
    if int(cli_value)-int(gnmi_value) <= 10:
        print(f"Comparision passed for {gnmi_value} vs {cli_value}")
        return True
    else:
        print(f"Comparision failed for {gnmi_value} vs {cli_value}")
        return False
