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
        cli_value = "65535"
        
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

def interfaces_lldp_counter(gnmi_value, cli_value):
    # Variations accomodation
    if int(cli_value)-int(gnmi_value) <= 10:
        print(f"Comparision passed for {gnmi_value} vs {cli_value}")
        return True
    else:
        print(f"Comparision failed for {gnmi_value} vs {cli_value}")
        return False


def platform_hardware_version(gnmi_value, cli_value):
    # Variations accomodation
    if cli_value == "n/a":
        cli_value = "none"
    elif cli_value == "None":
        cli_value = "N/A"
        
    if str(gnmi_value) == str(cli_value):
        print(f"Comparision passed for {gnmi_value} vs {cli_value}")
        return True
    else:
        print(f"Comparision failed for {gnmi_value} vs {cli_value}")
        return False

def platform_hardware_versionx(gnmi_value, cli_value):
    # Variations accommodation
#    if cli_value == "":
#        cli_value = " none"
#    elif gnmi_value == "none":
#        gnmi_value = " "
    if "none" in gnmi_value : 
        cli_value = " "
    elif "None" in cli_value :
        gnmi_value = "None"    

    if str(gnmi_value) == str(cli_value):
        print(f"Comparison passed for {gnmi_value} vs {cli_value}")
        return True
    else:
        print(f"Comparison failed for {gnmi_value} vs {cli_value}")
        return False


def compare_integer_with_unit(val1, val2):
    """
    Compare two values and return True if their numeric parts match.
    Example: "12150 rpm" and "12150" should match.
    """

    try:
        num1 = int(''.join(filter(str.isdigit, str(val1))))
        num2 = int(''.join(filter(str.isdigit, str(val2))))
        if num1 == num2:
            print(f"Numeric comparison passed for {val1} vs {val2}")
            return True
        else:
            print(f"Numeric comparison failed for {val1} vs {val2}")
            return False
    except ValueError:
        print(f"ValueError: Could not extract integer from {val1} or {val2}")
        return False


