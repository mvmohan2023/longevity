def interfaces_lldp_counter(gnmi_value, cli_value):
    # Variations accomodation
    if int(cli_value)-int(gnmi_value) <= 10:
        print(f"Comparision passed for {gnmi_value} vs {cli_value}")
        return True
    else:
        print(f"Comparision failed for {gnmi_value} vs {cli_value}")
        return False
