#!/usr/bin/env python3
"""Process data collector utility"""
#
# $Id: $
#
#  Aleksey Romanov
#
#  Copyright (c) 2021, Juniper Networks, Inc.
#  All rights reserved.
#

##@file  proc_collector.py
##@brief collects process build information

from typing import Dict, List, TextIO, Tuple, Union
import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import textwrap

# Our target is python-3.5. So we simply cannot use
# constructs, like f-strings that are not available
# in this version
# pylint: disable=consider-using-f-string
# pylint: disable=use-dict-literal
# pylint: disable=use-list-literal

# For now we prefer explicit exception handling
# pylint: disable=consider-using-with

# pylint: disable=too-few-public-methods
# pylint: disable=too-many-arguments
# pylint: disable=too-many-branches
# pylint: disable=too-many-locals
# pylint: disable=too-many-return-statements

VAR_LOG = "/var/log"
VAR_TMP = "/var/tmp"
YOCTO_VER = "/usr/share/cevo/yocto_version"
USWITCHD_KEY = "@switchd"
USWITCHD_PROG = "/usr/bin/uswitchd"

class ProgData:
    """Class to keep results of program p processing.

    We have too many components to fit them into tuple.
    """

    def __init__(self) -> None:
        self.proc = ""
        self.evo_gdb = ""
        self.yocto_version = ""
        self.evo_prog = ""
        self.jnx_prog = ""
        self.other_prog = ""

        # EVO program may contain statically linked
        # evo libraries - it is currently unused
        # but it may happen, we will add these
        # libraries to the list of evo-libs
        self.evo_libs = list() # type: List[str]

class LibData:
    """Class to keep results of library processing.

    We have too many components to fit them into tuple.
    """

    def __init__(self) -> None:
        self.evo_libs = list() # type: List[str]
        self.jnx_libs = list() # type: List[str]
        self.invalid_libs = list() # type: List[str]
        self.other_libs = list() # type: List[str]


def make_datetime_str() -> str:
    """Format the current date+time"""
    now = datetime.datetime.now()
    return now.strftime(".%Y_%m_%d.%H_%M_%S")


def get_section_by_name(fname:str, sname: str) -> Tuple[bool, str, bytes]:
    """Extract section offset and length"""

    cmd = ["/usr/bin/readelf", "-S", "-W",  fname]
    try:
        res = subprocess.check_output(cmd)
    except subprocess.CalledProcessError as ex_descr:
        return (False, "readelf failed {}".format(ex_descr), b'')

    res_str = res.decode()
    off_str = ""
    size_str = ""

    for line in res_str.split("\n"):
        if not line:
            continue

        # print(line)

        parts = line.split()
        if len(parts) < 7:
            continue

        # Note: sections if numbers < 10 have leading
        # '[' as a separate part
        if parts[1] == sname:
            off_str = parts[4]
            size_str = parts[5]
            break

        if parts[2] == sname:
            off_str = parts[5]
            size_str = parts[6]
            break

    if not off_str or not size_str:
        # Not found is a success
        return (True, "", b'')

    try:
        off = int(off_str, 16)
        size = int(size_str, 16)
    except ValueError:
        # Should not happen
        return (False, "{} bad information".format(sname), b'')

    if size == 0:
        return (True, "", b'')

    try:
        file_f = open(fname, "rb")
    except OSError:
        return (False, "unable to open {} for reading".format(fname), b'')

    try:
        file_f.seek(off)
        data = file_f.read(size)
    except OSError as ex_desc:
        return (False, "read failure: {}".format(ex_desc) , b'')
    finally:
        file_f.close()

    return (True, "", data)


def get_jnx_object(fname:str, data: bytes) -> Tuple[bool, bool, str, str]:
    """Extract jnx object information

    Return whether jnx info found, whether it is good,
    error message, object itself.
    """

    if len(data) < 4:
        # Not a jnx info
        return (False, True, "", "")

    # We may have bugs where proper version generation
    # is skipped. In this case we have prefix
    # @(#)
    if data[:4] == b'@(#)' and "mustd" in fname:
        # The first 128 bytes are used for prefix and directory
        sw_size = 128
        sw_dir_off = 5
        sw_dir_size = sw_size - sw_dir_off
    elif data[:4] == b'@JNX':
        # Junos sw-version starts from
        # the magic string "@JNX"
        # it has fixed lenght and data
        # of interest are at fixed offset
        sw_size = 1860
        sw_dir_off = 1538
        sw_dir_size = 256
    else:
        # Not a jnx info
        return (False, True, "", "")

    if len(data) < sw_size:
        return(True, False, "bad junos sw-version", "")

    tmp_data= data[sw_dir_off : sw_dir_off + sw_dir_size]
    off = 0
    for off, val in enumerate(tmp_data):
        if val == 0:
            break

    # Replace double slashes with single slash
    tmp_build_dir = tmp_data[:off].decode()
    build_dir = tmp_build_dir.replace("//", "/")

    pos = fname.rfind("/")
    pos += 1

    if build_dir[-1] == "/":
        obj_path = build_dir + fname[pos:]
    else:
        obj_path = build_dir + "/" + fname[pos:]
    return (True, True, "", obj_path)


def get_junos_params(fname: str) -> Tuple[bool, str, str, List[str]]:
    """Extracts build information

    If EVO_INFO is present extract all EVO_OBJECT values from file.
    Otherwise extract build directory information from sw-version,
    if available.
    """

    res, msg, data  = get_section_by_name(fname, ".junos.version")
    if not res:
        return(res, msg, "", list())

    # Try JNX version info first
    is_jnx, res, msg, jnx_obj_str = get_jnx_object(fname, data)
    if is_jnx:
        return (res, msg, jnx_obj_str, list())

    off = 0
    for off, val in enumerate(data):
        if val == 0:
            break

    str_data = data[:off].decode()
    list_data = str_data.split("\n")
    obj_str_list= list()

    for entry in list_data:
        if not entry.startswith("EVO_OBJECT="):
            continue
        obj_str_list.append(entry[11:])

    return (True, "", "", obj_str_list)

def get_proc_pid(proc: str) -> Tuple[bool, str, str, int]:
    """Extract process information.

    Return: success/failure, message, full-path, pid
    """

    # We want some flexibility in specifying file name
    # but we do not want to be too smart
    full_name = ""

    if os.path.exists("/usr/bin/" + proc) :
        full_name = "/usr/bin/" + proc
    elif os.path.exists("/usr/sbin/" + proc):
        full_name = "/usr/sbin/" + proc
    elif os.path.exists(proc):
        full_name = proc
    else:
        return (False, "bad proc-specification: {}".format(proc), "", 0)

    cmd = ["/bin/ps", "ax", "-o", "pid,command"]
    try:
        res = subprocess.check_output(cmd)
    except subprocess.CalledProcessError as ex_descr:
        return (False, "{}".format(ex_descr), "", 0)

    res_str = res.decode()

    for line in res_str.split("\n"):
        if not line:
            continue

        parts = line.split()
        if len(parts) < 2:
            continue

        if full_name == USWITCHD_PROG and parts[1] == USWITCHD_KEY:
            # We expect that parts[0] to be a proper integer
            pid = int(parts[0])
            return (True, "", full_name, pid)

        if full_name == parts[1]:
            # We expect that parts[0] to be a proper integer
            pid = int(parts[0])
            return (True, "", full_name, pid)

    return (False, "process {} is not running".format(proc), "", 0)

def get_pid_proc(pid: int) -> Tuple[bool, str, str]:
    """Extract process information.

    Return: success/failure, message, full-path
    """

    cmd = ["/bin/ps", "ax", "-o", "pid,command"]
    try:
        res = subprocess.check_output(cmd)
    except subprocess.CalledProcessError as ex_descr:
        return (False, "{}".format(ex_descr), "")

    res_str = res.decode()

    for line in res_str.split("\n"):
        if not line:
            continue

        parts = line.split()
        if len(parts) < 2:
            continue

        if parts[0] == "PID":
            continue

        cur_pid = int(parts[0])
        if cur_pid == pid:
            # @switch is special
            if parts[1] == USWITCHD_KEY:
                return (True, "", USWITCHD_PROG)
            return (True, "", parts[1])
        continue

    return (False, "process {} is not running".format(pid), "")


def get_lib_info(proc: str, pid: int) -> Tuple[bool, str, LibData]:
    """Get list of loaded libraries."""

    maps_file_name = "/proc/" + str(pid) + "/maps"
    try:
        maps_f = open(maps_file_name, "r", encoding="utf-8")
    except OSError as ex_desc:
        return (False,
                "failed to open maps file {} for {}: {}".format(
                    maps_file_name, proc, ex_desc),
                LibData())

    # Same library is used many times we use set to avoid duplicated
    tmp_set = set()

    lib_data = LibData()

    while True:
        line = maps_f.readline()
        if not line:
            break

        line = line.rstrip()

        if len(line) <= 73:
            # The file path starts from position 73
            continue

        if line[72] != ' ':
            # Should have space before the data
            continue

        # Discard everything before position 73
        line = line[73:]

        if not line.startswith("/"):
            # Not starting from slash
            continue

        if line.find(".so") < 0:
            # Not a shared lib
            continue

        if line in tmp_set:
            # Duplicate
            continue

        tmp_set.add(line)

        res, _, jnx_obj, obj_list = get_junos_params(line)

        if not res:
            lib_data.invalid_libs.append(line)
            continue

        if jnx_obj:
            lib_data.jnx_libs.append(jnx_obj)
            continue

        if obj_list:
            lib_data.evo_libs = lib_data.evo_libs + obj_list
            continue

        lib_data.other_libs.append(line)

    return (True, "", lib_data)


def get_yocto_info() -> Tuple[bool, str, str, str]:
    """Get EVO_YOCTO= and EVO_GDB= values"""

    if not os.path.exists(YOCTO_VER):
        # Not running on the router
        # these values are inapplicable
        return (True, "", "", "")

    try:
        ver_f = open(YOCTO_VER, "r", encoding="utf-8")
    except OSError:
        return (False, "unable to open {}".format(YOCTO_VER), "", "")

    yocto_str = ""
    gdb_str = ""
    for line in ver_f:
        line = line.strip()
        if line.startswith("EVO_YOCTO="):
            yocto_str = line[10:]
            continue
        if line.startswith("EVO_GDB="):
            gdb_str = line[8:]
            continue


    ver_f.close()

    if not yocto_str:
        return (False, "EVO_YOCTO= is not found", "", "")

    if not gdb_str:
        return (False, "EVO_GDB= is not found", "", "")


    return (True, "", yocto_str, gdb_str)


def get_prog_info(prog: str) -> Tuple[bool, str, ProgData]:
    """Get program file info.

    The result fields are:
    0. Success/failure
    1. Error message
    2. Collected data
    """

    res, msg, jnx_obj, obj_list = get_junos_params(prog)

    if not res:
        return (False, msg, ProgData())

    res, msg, yocto_str, gdb_str = get_yocto_info()
    if not res:
        return (False, msg, ProgData())

    pres = ProgData()
    pres.evo_gdb = gdb_str
    pres.yocto_version = yocto_str

    if jnx_obj:
        pres.jnx_prog = jnx_obj
        return (True, "", pres)

    if not obj_list:
        pres.other_prog = prog
        return (True, "", pres)

    pres.evo_prog = obj_list[0]
    pres.evo_libs = obj_list[1:]
    return(True, "", pres)

def get_cli_version() -> List[str]:
    """Extract cli version"""

    cmd = ["/usr/sbin/cli", "show", "version"]
    try:
        res = subprocess.check_output(cmd)
    except subprocess.CalledProcessError:
        return list()

    res_str = res.decode()

    out = list() # type: List[str]
    for line in res_str.split("\n"):
        if not line:
            continue
        out.append(line)

    return out


def get_proc_json(proc: str, pid: int, out: TextIO) -> Tuple[bool, str]:
    """Extract program evo information in json format"""

    res, msg, lib_data = get_lib_info(proc, pid)
    if not res:
        return (False, msg)

    res, msg, prog_data = get_prog_info(proc)
    if not res:
        return (False, msg)

    json_dict = dict() # type: Dict[str, Union[str, List[str]]]

    json_dict["PROC"] = proc
    json_dict["EGDB"] = prog_data.evo_gdb
    json_dict["YCTO"] = prog_data.yocto_version

    if prog_data.evo_prog:
        json_dict["EPRG"] = prog_data.evo_prog
    elif prog_data.jnx_prog:
        json_dict["JPRG"] = prog_data.jnx_prog
    else:
        json_dict["OPRG"] = prog_data.other_prog

    version_data = get_cli_version()
    for off, line_str in enumerate(version_data):
        json_dict["SV{:02d}".format(off)] = line_str

    # We want a sorted distinct list of all libraries
    all_set = set(lib_data.evo_libs)
    all_set.update(prog_data.evo_libs)
    all_list = sorted(all_set)
    json_dict["ELIB"] = all_list

    all_set = set(lib_data.jnx_libs)
    all_list = sorted(all_set)
    json_dict["JLIB"] = all_list

    all_set = set(lib_data.invalid_libs)
    all_list = sorted(all_set)
    json_dict["ILIB"] = all_list

    all_set = set(lib_data.other_libs)
    all_list = sorted(all_set)
    json_dict["OLIB"] = all_list

    json.dump(json_dict, out)

    return (True, "")

def get_proc_info(proc: str, pid: int, out: TextIO) -> Tuple[bool, str]:
    """Extract program evo information"""

    res, msg, lib_data = get_lib_info(proc, pid)
    if not res:
        return (False, msg)

    res, msg, prog_data = get_prog_info(proc)
    if not res:
        return (False, msg)

    print("PROC: {}".format(proc), file=out)
    print("EGDB: {}".format(prog_data.evo_gdb), file=out)
    print("YCTO: {}".format(prog_data.yocto_version), file=out)

    if prog_data.evo_prog:
        print("EPRG: {}".format(prog_data.evo_prog), file=out)
    elif prog_data.jnx_prog:
        print("JPRG: {}".format(prog_data.jnx_prog), file=out)
    else:
        print("OPRG: {}".format(prog_data.other_prog), file=out)

    version_data = get_cli_version()
    for off, line_str in enumerate(version_data):
        print("SV{:02d}: {}".format(off, line_str), file=out)

    # We want a sorted distinct list of all libraries
    all_set = set(lib_data.evo_libs)
    all_set.update(prog_data.evo_libs)

    all_list = sorted(all_set)

    for lib in all_list:
        print("ELIB: {}".format(lib), file=out)

    all_set = set(lib_data.jnx_libs)
    all_list = sorted(all_set)

    for lib in all_list:
        print("JLIB: {}".format(lib), file=out)

    all_set = set(lib_data.invalid_libs)
    all_list = sorted(all_set)

    for lib in all_list:
        print("ILIB: {}".format(lib), file=out)

    all_set = set(lib_data.other_libs)
    all_list = sorted(all_set)

    for lib in all_list:
        print("OLIB: {}".format(lib), file=out)

    return (True, "")


def main_proc(real_proc: str, pid: int, base_name: str,
              datetime_str: str, use_json: bool
) -> Tuple[bool, str, str]:
    """Perform data collection operations

    Return success/failure, message, out_file
    """

    if use_json:
        ext = ".json"
    else:
        ext = ".build_info"

    if os.path.exists(YOCTO_VER):
        out_name = VAR_LOG + "/" + base_name + "." + str(pid) + datetime_str + ext
    else:
        out_name = VAR_TMP + "/" + base_name + "." + str(pid) + datetime_str + ext

    try:
        out_file = open(out_name, "w", encoding="utf-8")
    except FileExistsError as ex_desc:
        return(False, "unable to create {}: {}".format(out_name, ex_desc), "")
    except OSError as ex_desc:
        return(False, "unable to create {}: {}".format(out_name, ex_desc), "")

    print("generating: {}".format(out_name))

    if use_json:
        res, msg = get_proc_json(real_proc, pid, out_file)
    else:
        res, msg = get_proc_info(real_proc, pid, out_file)
    out_file.close()
    if not res:
        return (res, msg, "")

    return (True, "", out_name)


def make_archive(tar_file: str, out_files: List[str], data_files: List[str]
) -> Tuple[bool, str, List[str]]:
    """Create tar archive and stored data files

    Returns success/failure, message, not found files"
    """

    tar_cmd = ["/bin/tar",
               "czf",
               tar_file
    ]
    tar_cmd = tar_cmd + out_files

    # Best effort: get kallsyms
    try:
        shutil.copy("/proc/kallsyms", "/var/tmp/")
        tar_cmd.append("/var/tmp/kallsyms")
    except Exception: # pylint: disable=broad-except
        pass

    # Best effort: data files
    not_found_list = list() # type: List[str]
    for fname in data_files:
        if os.path.exists(fname):
            tar_cmd.append(fname)
        else:
            not_found_list.append(fname)

    try:
        subprocess.check_output(tar_cmd)
    except subprocess.CalledProcessError as ex_descr:
        # Note: return code 1 is acceptable
        if ex_descr.returncode != 1:
            return (False, "{}".format(ex_descr), list())

    return (True, "", not_found_list)

def main(archive: str, use_json: bool, name_list:
         List[str], pid_list: List[int], data_files: List[str]
) -> Tuple[bool, str]:
    """Check arguments and call main_proc"""

    datetime_str = make_datetime_str()

    # List of out_file names
    out_file_list = list() # type: List[str]

    # List of programs to check for duplicates
    proc_list = list() # type: List[str]

    # Process pid list first, so if we have both
    # we use more restrictive specification
    #
    # We already checked pid list for duplicates
    for pid in pid_list:
        res, msg, proc = get_pid_proc(pid)
        if not res:
            return (False, msg)

        proc_list.append(proc)

        base_name = os.path.basename(proc)

        res, msg, out_file =  main_proc(proc, pid, base_name, datetime_str, use_json)
        if not res:
            return (False, msg)

        out_file_list.append(out_file)

    # Process name list
    for name in name_list:
        res, msg, proc, pid = get_proc_pid(name)
        if not res:
            return (False, msg)

        if proc in proc_list:
            print("Duplicate program specification {}: ignored".format(proc),
                  file=sys.stderr)
            continue
        proc_list.append(proc)

        base_name = os.path.basename(proc)

        res, msg, out_file =  main_proc(proc, pid, base_name, datetime_str, use_json)
        if not res:
            return (False, msg)

        out_file_list.append(out_file)

    tar_file = VAR_TMP + "/" + archive + datetime_str  + ".tgz"

    res, msg, not_found_list  = make_archive(tar_file, out_file_list, data_files)
    if res:
        print("created tar archive: {}".format(tar_file))
        if not_found_list:
            print("WARNING: files not found:")
        for fname in not_found_list:
            print("  {}".format(fname))

    return (res, msg)


if __name__ == '__main__' :

    descr = textwrap.dedent("""\
    Extract build information from running programs, extracts kallsyms.
    Add optional files and pack into a /var/tmp/archive_name.<date>.<time>.tgz

    The build information is presented as an ordered list of entries
    one entry per string. Each entry has a key followed by ": " and value.

    The key values are:

    PROC  - the full path of the process
    EGDB  - location of platform gdb
    YCTO  - location of yocto component
    EPRG  - location of EVO proram
    JPRG  - location of JNX program
    OPRG  - other program, same as PROC
    SV00  - line zero of show-version command output
    SV01  - line 1 of  line of show-version command output
    SV02  - more show-version command output
    ELIB  - <evo-library-location>
    JLIB  - <jnx-library-location>
    ILIB  - library path with invalid .junos.version
    OLIB  - library path with no .junos.version
    """)

    usage = textwrap.dedent("""\

    proc_collector.py [-j] [-n <name_list>] [-p <pid_list>] archive_name [data_files]
        save program information and  optionally <data_files>, the programs are
        specified by the list name or by the list of pids or both
    """)

    epilog = textwrap.dedent("""\
    examples:

    /var/tmp/proc_collector.py -n ifmand,snmpd collection /var/log/ifmand.9848.*.heap

    This command will extract build information from running /usr/sbin/ifmand and
    /usr/sbin/snmpd processes will add heap files and pack it all into
    /var/tmp/collection.<date>.<time>.tgz archive
    """)

    parser = argparse.ArgumentParser(
        prog="proc_collector.py",  epilog=epilog,
        description=descr, usage=usage, formatter_class=argparse.RawTextHelpFormatter)


    json_help = textwrap.dedent("""\
    use json format for output
    """)

    parser.add_argument("-j", "--json", action="store_true", help=json_help)

    name_list_help = textwrap.dedent("""\
    comma separated list of program names,
    a program should be a full path
    or be located in /usr/bin or /usr/sbin.
    """)

    parser.add_argument("-n", "--name_list", help=name_list_help)

    pid_list_help = textwrap.dedent("""\
    comma separated list of pids.
    """)
    parser.add_argument("-p", "--pid_list", help=pid_list_help)


    archive_help = textwrap.dedent("""\
    archive name
    """)

    parser.add_argument("archive", help=archive_help)

    data_files_help = textwrap.dedent("""\
    if present will be added to an archive
    """)

    parser.add_argument("data_files", nargs='*', help=data_files_help)

    try:
        xargs = parser.parse_args()
    except IOError as xex_desc:
        print("{}".format(xex_desc), file=sys.stderr)
        sys.exit(1)

    xname_list = list() # type: List[str]
    nword_list = list() # type: List[str]

    if xargs.name_list:
        nword_list = xargs.name_list.split(",")

    for nword in nword_list:
        nword = nword.strip()
        if not nword:
            print("Empty program name", file=sys.stderr)
            sys.exit(2)

        if nword in xname_list:
            print("Duplicate program name {}: ignored".format(nword),
                  file=sys.stderr)
            continue

        if "/" in nword and nword[0] != "/":
            print("Bad program name {}".format(nword), file=sys.stderr)
            sys.exit(2)

        if nword == USWITCHD_KEY:
            print("Notice: {}  is a representation of {}".format(USWITCHD_KEY, USWITCHD_PROG))
            xname_list.append(USWITCHD_PROG)
            continue

        xname_list.append(nword)

    xpid_list = list() # type List[int]
    pword_list = list() # type List[str]

    if xargs.pid_list:
        pword_list = xargs.pid_list.split(",")

    for pword in pword_list:
        pword = pword.strip()
        if not pword:
            print("Empty pid", file=sys.stderr)
            sys.exit(2)

        try:
            xpid = int(pword)
        except ValueError as xex_desc:
            print("Bad pid {}: {}".format(pword, xex_desc), file=sys.stderr)
            sys.exit(2)

        if xpid in xpid_list:
            print("Duplicate pid {}: ignored".format(xpid),
                  file=sys.stderr)

        xpid_list.append(xpid)

    if not xname_list and not xpid_list and not xargs.data_files:
        print("No names, no pids and no data files", file=sys.stderr)
        sys.exit(2)

    xres, xmsg = main(xargs.archive, xargs.json, xname_list, xpid_list, xargs.data_files)
    if not xres:
        print(xmsg, file=sys.stderr)
        sys.exit(2)

    sys.exit()
