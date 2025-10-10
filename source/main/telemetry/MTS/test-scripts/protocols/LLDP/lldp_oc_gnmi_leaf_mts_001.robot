*** Settings ***
# $Id$

Documentation
    ...             DESCRIPTION            : MTS Script to validate LLDP leaf level sensor paths of openconfig-lldp.yang using Yang-GNMI Validator
    ...             AUTHOR                 : tpradhan@juniper.net
    ...             TECHNOLOGY AREA        : PROTOCOLS
    ...             SUB AREA               : LLDP
    ...             FEATURE                : LLDP

Resource       MTS/resources/mts_utils/master_resources.robot
Resource       jnpr/toby/Master.robot

# Yang GNMI Validator Imports
Library        MTS/resources/yang_gnmi_validator/openconfig/yang_validator_test_mts.py
Variables      MTS/resources/yang_gnmi_validator/openconfig/yang_validator_test_mts.py


#Runs at the script start.


Suite Setup   Run Keywords   Toby Suite Setup
...    AND    YangGnmiInit
...    AND    Enable GNMI In Dut    ${dut}    50051  # Based on user requirment
...    AND    Yang GNMI Server Setup        ${yang_gnmi_server}    ${yang_gnmi_validator_files} 
   
Suite Teardown    Run Keywords   Toby Suite Teardown    Consolidate And Download Ygnmi Validator Logs    ${yang_gnmi_server}

Test Setup      Run Keywords   Toby Test Setup  
Test Teardown   Run Keywords   Toby Test Teardown

*** Variables ***


*** Keywords ***
YangGnmiInit
    [Documentation]    Creating a dictionary with all the template files and env file required for executing Yang-GNMI Validator

    # DUT & YANG GNMI SERVER HANDLE
    ${dut} =  Get Handle   resource=r0
    Set Suite Variable    ${dut}
    ${dut1} =  Get Handle   resource=r1
    Set Suite Variable    ${dut1}
    ${yang_gnmi_server} =  Get Handle   resource=h0
    Set Suite Variable    ${yang_gnmi_server}

    # Configure Device for GNMI streaming
    Configure Gnmi In Dut     ${dut}

    # Configure LLDP in device
    Config Set       device_list=r0    cmd_list=set protocols lldp interface all    commit=True
    Config Set       device_list=r1    cmd_list=set protocols lldp interface all    commit=True

    # Assign platform annotation file if provided as ENV var
    ${platform_annotation_file} =    Get Environment Variable     PLATFORM_ANNOTATION_FILE    default=None

    #Create a dictionary of all the template, callback/transform func files and env files
    @{callback_and_transform_funcs}  Create List
    ...  /volume/regressions/toby/test-suites/MTS/resources/yang_gnmi_validator/openconfig/callback_transform_funcs

    # ENV file content as list of dicts. Provide a suitable tmp filename to create a dynamic env file with that name
    #${env_dict1}=    Create Dictionary    env_file_tmp_name=lldp_xpath_env.yaml    dut=${tv['r0__name']}
    #${my_env_dict_list}=    Create List    ${env_dict1}


    # Dont change the keys of the dictionary
    &{yang_gnmi_validator_files}   Create Dictionary
    ...    state_only_templates=/volume/regressions/toby/test-suites/MTS/resources/yang_gnmi_validator/openconfig/templates/openconfig-lldp_counters-stateonly_tc_template.yaml
    #...    env_dict_list=${my_env_dict_list}
    ...    callback_and_transform_func_files=${callback_and_transform_funcs}
    ...    platform_annotation_file=${platform_annotation_file}

    # Set the suite variable for files
    Set Suite Variable    ${yang_gnmi_validator_files}

*** Test Cases ***


TC1
    [Documentation]       Validate  /lldp/state/counters/tlv-discard leaf xpaths - state-only group with Yang-GNMI validator
    ...  |     Test Case No: 5.1-1
    [Tags]        sanity  lldp  OpenConfig     tc1     Tc5.1-1
    
    ${test_result} =    Execute Yang Gnmi Validator    ${yang_gnmi_server}    STATE_ONLY_LEAFS.TC_group_1    intf_xpath_env.yaml    state_only_template=${yang_gnmi_validator_files['state_only_templates']}
    
    Should Be True    ${test_result}    Validation of /lldp/state/counters/tlv-discard Leaf Xpaths - State-only Group Failed

TC2
    [Documentation]       Validate /lldp/state/counters/tlv-unknown leaf xpaths - state-only group with Yang-GNMI validator
    ...  |     Test Case No: 5.1-2
    [Tags]        sanity  lldp  OpenConfig     tc2      Tc5.1-2
    
    ${test_result} =    Execute Yang Gnmi Validator    ${yang_gnmi_server}    STATE_ONLY_LEAFS.TC_group_2    intf_xpath_env.yaml    state_only_template=${yang_gnmi_validator_files['state_only_templates']}
    
    Should Be True    ${test_result}    Validation of /lldp/state/counters/tlv-unknown Leaf Xpaths - State-only Group Failed
TC3
    [Documentation]       Validate  /lldp/state/counters/tlv-accepted leaf xpaths - state-only group with Yang-GNMI validator
    ...  |     Test Case No: 5.1-3
    [Tags]        sanity  lldp  OpenConfig     tc3      Tc5.1-3

    ${test_result} =    Execute Yang Gnmi Validator    ${yang_gnmi_server}    STATE_ONLY_LEAFS.TC_group_3    intf_xpath_env.yaml    state_only_template=${yang_gnmi_validator_files['state_only_templates']}

    Should Be True    ${test_result}    Validation of /lldp/state/counters/tlv-accepted Leaf Xpaths - State-only Group Failed

TC4
    [Documentation]       Validate /lldp/state/counters/frame-out leaf xpaths - state-only group with Yang-GNMI validator
    ...  |     Test Case No: 5.1-4
    [Tags]        sanity  lldp  OpenConfig   tc4    Tc5.1-4

    ${test_result} =    Execute Yang Gnmi Validator    ${yang_gnmi_server}    STATE_ONLY_LEAFS.TC_group_4    intf_xpath_env.yaml    state_only_template=${yang_gnmi_validator_files['state_only_templates']}

    Should Be True    ${test_result}    Validation of /lldp/state/counters/frame-out Leaf Xpaths - State-only Group Failed
TC5
    [Documentation]       Validate  /lldp/state/counters/frame-error-in leaf xpaths - state-only group with Yang-GNMI validator
    ...  |     Test Case No: 5.1-3
    [Tags]        sanity  lldp  OpenConfig    tc5    Tc5.1-3

    ${test_result} =    Execute Yang Gnmi Validator    ${yang_gnmi_server}    STATE_ONLY_LEAFS.TC_group_5    intf_xpath_env.yaml    state_only_template=${yang_gnmi_validator_files['state_only_templates']}

    Should Be True    ${test_result}    Validation of /lldp/state/counters/frame-error-in Leaf Xpaths - State-only Group Failed

TC6
    [Documentation]       Validate /lldp/state/counters/frame-in leaf xpaths - state-only group with Yang-GNMI validator
    ...  |     Test Case No: 5.1-3
    [Tags]        sanity  lldp  OpenConfig    tc6     Tc5.1-3

    ${test_result} =    Execute Yang Gnmi Validator    ${yang_gnmi_server}    STATE_ONLY_LEAFS.TC_group_6    intf_xpath_env.yaml    state_only_template=${yang_gnmi_validator_files['state_only_templates']}

    Should Be True    ${test_result}    Validation of /lldp/state/counters/frame-in Leaf Xpaths - State-only Group Failed
TC7
    [Documentation]       Validate  /lldp/interfaces/interface[name=*]/state/counters/frame-in leaf xpaths - state-only group with Yang-GNMI validator
    ...  |     Test Case No: 5.1-4
    [Tags]        sanity  lldp  OpenConfig    tc7      Tc5.1-4

    ${test_result} =    Execute Yang Gnmi Validator    ${yang_gnmi_server}    STATE_ONLY_LEAFS.TC_group_7    intf_xpath_env.yaml    state_only_template=${yang_gnmi_validator_files['state_only_templates']}

    Should Be True    ${test_result}    Validation of /lldp/interfaces/interface[name=*]/state/counters/frame-in Leaf Xpaths - State-only Group Failed

TC8
    [Documentation]       Validate /lldp/interfaces/interface[name=*]/state/counters/frame-error-in leaf xpaths - state-only group with Yang-GNMI validator
    ...  |     Test Case No: 5.1-5
    [Tags]        sanity  lldp  OpenConfig    tc8      Tc5.1-5

    ${test_result} =    Execute Yang Gnmi Validator    ${yang_gnmi_server}    STATE_ONLY_LEAFS.TC_group_8    intf_xpath_env.yaml    state_only_template=${yang_gnmi_validator_files['state_only_templates']}

    Should Be True    ${test_result}    Validation of /lldp/interfaces/interface[name=*]/state/counters/frame-error-in Leaf Xpaths - State-only Group Failed
TC9
    [Documentation]       Validate  /lldp/interfaces/interface[name=*]/state/counters/tlv-discard leaf xpaths - state-only group with Yang-GNMI validator
    ...  |     Test Case No: 5.1-3
    [Tags]        sanity  lldp  OpenConfig    tc9      Tc5.1-3

    ${test_result} =    Execute Yang Gnmi Validator    ${yang_gnmi_server}    STATE_ONLY_LEAFS.TC_group_9    intf_xpath_env.yaml    state_only_template=${yang_gnmi_validator_files['state_only_templates']}

    Should Be True    ${test_result}    Validation of /lldp/interfaces/interface[name=*]/state/counters/tlv-discard Leaf Xpaths - State-only Group Failed

TC10
    [Documentation]       Validate /lldp/interfaces/interface[name=*]/state/counters/frame-out leaf xpaths - state-only group with Yang-GNMI validator
    ...  |     Test Case No: 5.1-4
    [Tags]        sanity  lldp  OpenConfig    tc10      Tc5.1-4

    ${test_result} =    Execute Yang Gnmi Validator    ${yang_gnmi_server}    STATE_ONLY_LEAFS.TC_group_10    intf_xpath_env.yaml    state_only_template=${yang_gnmi_validator_files['state_only_templates']}

    Should Be True    ${test_result}    Validation of /lldp/interfaces/interface[name=*]/state/counters/frame-out Leaf Xpaths - State-only Group Failed
TC11
    [Documentation]       Validate  /lldp/interfaces/interface[name=*]/state/counters/frame-discard leaf xpaths - state-only group with Yang-GNMI validator
    ...  |     Test Case No: 5.1-5
    [Tags]        sanity  lldp  OpenConfig    tc11       Tc5.1-5

    ${test_result} =    Execute Yang Gnmi Validator    ${yang_gnmi_server}    STATE_ONLY_LEAFS.TC_group_11    intf_xpath_env.yaml    state_only_template=${yang_gnmi_validator_files['state_only_templates']}

    Should Be True    ${test_result}    Validation of /lldp/interfaces/interface[name=*]/state/counters/frame-discard Leaf Xpaths - State-only Group Failed

TC12
    [Documentation]       Validate /lldp/interfaces/interface[name=*]/state/counters/frame-error-out leaf xpaths - state-only group with Yang-GNMI validator
    ...  |     Test Case No: 5.1-5
    [Tags]        sanity  lldp  OpenConfig   tc12      Tc5.1-5

    ${test_result} =    Execute Yang Gnmi Validator    ${yang_gnmi_server}    STATE_ONLY_LEAFS.TC_group_12    intf_xpath_env.yaml    state_only_template=${yang_gnmi_validator_files['state_only_templates']}

    Should Be True    ${test_result}    Validation of /lldp/interfaces/interface[name=*]/state/counters/frame-error-out Leaf Xpaths - State-only Group Failed
TC13
    [Documentation]       Validate  /lldp/interfaces/interface[name=*]/state/counters/tlv-unknown leaf xpaths - state-only group with Yang-GNMI validator
    ...  |     Test Case No: 5.1-4
    [Tags]        sanity  lldp  OpenConfig   tc13     Tc5.1-4

    ${test_result} =    Execute Yang Gnmi Validator    ${yang_gnmi_server}    STATE_ONLY_LEAFS.TC_group_13    intf_xpath_env.yaml    state_only_template=${yang_gnmi_validator_files['state_only_templates']}

    Should Be True    ${test_result}    Validation of /lldp/interfaces/interface[name=*]/state/counters/tlv-unknown Leaf Xpaths - State-only Group Failed

