def interfaces_lldp_counter(gnmi_value, cli_value):
    '''
    This is a callback function to compare LLDP counter gnmi value with cli value
    Technology Area : protocols/LLDP
    Authors         : tpradhan@juniper.net
    '''
    # Variations accomodation
    if int(cli_value)-int(gnmi_value) <= 11:
        print(f"Comparision passed for {gnmi_value} vs {cli_value}")
        return True
    else:
        print(f"Comparision failed for {gnmi_value} vs {cli_value}")
        return False
