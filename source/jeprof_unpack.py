#!/usr/bin/env python3
#
# $Id: $
#
#  Aleksey Romanov
#
#  Copyright (c) 2021, Juniper Networks, Inc.
#  All rights reserved.
#
"""Memory-profile unpack utility"""

##@file  jeprof_unpack.py
##@brief unpacks profiling info and builds helper scripts

from typing import Dict, List, Tuple
import argparse
import os
import shutil
import sys
import textwrap
import proc_unpack

# Our target is python-3.5. So we simply cannot use
# constructs, like f-strings, that are not available
# in this version
# pylint: disable=consider-using-f-string
# pylint: disable=use-dict-literal
# pylint: disable=use-list-literal

# For now we prefer explicit exception handling
# pylint: disable=consider-using-with

# pylint: disable=too-many-locals
# pylint: disable=too-many-branches
# pylint: disable=too-many-statements

def proc_heap_files(hfiles: List[str], unpack_dir: str) -> List[str]:
    """Extract heap files.

    Return list of basenames
    """

    ret = list()  # type: List[str]

    if not hfiles:
        print("WARNING: no heap-files")
        return ret

    # We need prefix length to print paths relative to unapack_dir
    pref_len = len(unpack_dir) + 1

    # Dictionary of base-name to file-name
    hfile_dict = dict() # type: Dict[str, str]

    for hfile in hfiles:
        basename = os.path.basename(hfile)

        prev_file_name = hfile_dict.get(basename, "")

        if prev_file_name:
            print("WARNING: heap file conflict")
            print("   previous: unpack_dir/{}".format(prev_file_name[pref_len:]))
            print("   current:  unpack_dir/{}".format(hfile[pref_len:]))
            continue

        shutil.copy(hfile, unpack_dir)
        hfile_dict[basename] = hfile
        ret.append(basename)

    return ret


def main(archives: List[str], dest_dir: str) -> Tuple[bool, str]:
    """Main entry point"""

    # Do full unpack
    res, msg, result = proc_unpack.proc_unpack(archives, dest_dir, False)
    if not res:
        return (res, msg)

    sparse_root = result.unpack_dir + "/" + result.sparse_root

    if result.is_64bit:
        lib_prefix= \
            "$SR/" + \
            ",$Y/" + \
            ",$SR/lib64/.debug/" + \
            ",$SR/lib64/" + \
            ",$SR/usr/lib64/.debug/" + \
            ",$SR/usr/lib64/" + \
            ",$Y/lib64/.debug/" + \
            ",$Y/lib64/" + \
            ",$Y/usr/lib64/.debug/" + \
            ",$Y/usr/lib64/"
    else:
        lib_prefix = \
            "$SR/" + \
            ",$Y/" + \
            ",$SR/lib/.debug/" + \
            ",$SR/lib/" + \
            ",$SR/usr/lib/.debug/" + \
            ",$SR/usr/lib/" + \
            ",$Y/lib/.debug/" + \
            ",$Y/lib//" + \
            ",$Y/usr/lib/.debug/" + \
            ",$Y/usr/lib/"


    # Make jeprof.sh
    jeprof_script = result.unpack_dir + "/jeprof.sh"
    try:
        jeprof_f = open(jeprof_script, "w", encoding="utf-8")
        print("#!/bin/sh", file=jeprof_f)
        print("export JEPROF=" + result.yocto + "/usr/bin/jeprof", file=jeprof_f)
        print("export SR=" + sparse_root, file=jeprof_f)
        print("export Y=" + result.yocto, file=jeprof_f)
        print("export LIB_PREFIX={}".format(lib_prefix), file=jeprof_f)
        print("export JEPROF_TOOLS={}".format(result.jtools), file=jeprof_f)
        print("$JEPROF --lib_prefix=$LIB_PREFIX \"$@\"", file=jeprof_f)
        jeprof_f.close()
        os.chmod(jeprof_script, 0o755)
    except OSError as ex_desc:
        return (False, "unable to create {}: {}".format(jeprof_script, ex_desc))

    print("Success: unpacked the data and created a jeprof script")

    print("")
    print("Version information:")
    print("")
    for line in result.version_strs:
        print(line)

    print("")
    print("Extracted data location:")
    print("")
    print("unpack_dir:        {}".format(result.unpack_dir))

    for raw in result.raw_data:
        print("unpacked raw data: <unpack_dir>/{}".format(raw))

    first_prog_symlink = ""
    if not result.debug_symlinks and not result.prog_manuals:
        print("WARNING: no program information in archive")

    if result.debug_symlinks:
        first_prog_symlink = result.sparse_root + result.debug_symlinks[0]
        for symlink in result.debug_symlinks:
            print("program symlink:   <unpack_dir>/{}".format(result.sparse_root + symlink))

    if result.prog_manuals:
        print("Manually create following symlinks")
        first_prog_symlink = result.sparse_root + result.prog_manuals[0]
        for prog in result.prog_manuals:
            print("program symlink:   <unpack_dir>/{}".format(result.sparse_root + prog))

    print("jeprof script:     <unpack_dir>/jeprof.sh")

    heap_files = list() # type: List[str]

    for raw in result.raw_data:
        raw_dir = result.unpack_dir + "/" + raw
        for dirpath, _, filenames in os.walk(raw_dir):
            for fname in filenames:
                if not fname.endswith(".heap"):
                    continue
                hfile = os.path.join(dirpath, fname)
                heap_files.append(hfile)

    out_heap_files = proc_heap_files(heap_files, result.unpack_dir)

    for hfile in out_heap_files:
        print("heap file:         <unpack_dir>/{}".format(hfile))

    if out_heap_files:
        example_heap_file = out_heap_files[0]
    else:
        example_heap_file = "xxx.heap"

    pos = example_heap_file.rfind(".")
    if pos > 0:
        pdf_file = os.path.basename(example_heap_file)[:pos] + ".pdf"
    else:
        pdf_file = "xxx.pdf"


    print("Run jeprof as: ")
    print("<jeprof-script> <jeprof-options> <program-symlink> <heap-files>")
    print("")

    print("For example:")
    print("cd <unpack_dir>")

    if first_prog_symlink:
        run_str = "./jeprof.sh --pdf {} {} > {}".format(
            "./" + first_prog_symlink, example_heap_file, pdf_file)
    else:
        run_str = "./jeprof.sh --pdf {} {} > {}".format(
            "<provide-program>", example_heap_file, pdf_file)

    print(run_str)

    return (True, "")

if __name__ == '__main__' :

    descr = textwrap.dedent("""\
    Unpack prof data and create links to debug libraries.

    1. Create directory to unpack the data under <dest_dir>,
       directory name is derive from the first archive base name and
       ".unpack" suffix. If the first archive base name was yyyy.tgz
       create directory <dest_dir>/yyyy.unpack.
    3. Unpack the .tgz archives into <dest_dir>/yyyy.unpack/xxxx.raw directories
       where xxxx is the base name of an archive.
    2. Copy var/log/*.heap (or var/tmp/*.heap) files from raw-data
       to <dest_dir>yyyy.unpack.
    3. Create a sparse-root directory containing symlinks to all libraries
       and programs.
    5. Create jeprof.sh sccript to run the analysis

    For example if archive-1.tgz, archive-2.tgz and archive-3.tgz are provided on
    the command line then the following directory hierarchy will be created under
    the  destination directory.

    <dest_dir>
    <dest_dir>/archive-1.unpack
    <dest_dir>/archive-1.unpack/archive-1.raw
    <dest_dir>/archive-1.unpack/archive-2.raw
    <dest_dir>/archive-1.unpack/archive-3.raw
    <dest_dir>/archive-1.unpack/sparse_root
    <dest_dir>/archive-1.unpack/*.heap
    <dest_dir>/archive-1.unpack/jeprof.sh

    After that jeprof could be run as:

    <jeprof-script> <jeprof-options> <program-symlink> <heap-files>
    """)


    usage = textwrap.dedent("""\
    jeprof_unpack.py [-d dest_dir] <archive> <archive>...
    """)

    epilog = textwrap.dedent("""\

    Session example:

    ./jeprof_unpack.py ifmand.9848.2022_01_30.16_37_21.tgz snmpd.2022_01_31.19_01_19.tgz
    Success: unpacked the data and created a jeprof script

    Version information:

    Hostname: vbrackla-RE0
    Model: ptx10003-160c
    Junos: 22.2I20220129113908-EVO_aromanov
    Yocto: 3.0.2
    Linux Kernel: 5.2.60-yocto-standard-g5ca1dce
    JUNOS-EVO OS 64-bit [junos-evo-install-ptx-fixed-x86-64-22.2I20220129113908-EVO_aromanov]

    Extracted data location:

    unpack_dir:        /homes/aromanov/test_collectors/ifmand.9848.2022_01_30.16_37_21.unpack
    unpacked raw data: <unpack_dir>/ifmand.9848.2022_01_30.16_37_21.raw
    unpacked raw data: <unpack_dir>/snmpd.2022_01_31.19_01_19.raw
    program symlink:   <unpack_dir>/sparse-root/usr/sbin/.debug/ifmand
    program symlink:   <unpack_dir>/sparse-root/usr/sbin/.debug/snmpd
    program symlink:   <unpack_dir>/sparse-root/usr/sbin/.debug/snmpd-subagent
    jeprof script:     <unpack_dir>/jeprof.sh
    heap file:         <unpack_dir>/ifmand.9848.1.heap
    heap file:         <unpack_dir>/ifmand.9848.2.heap
    Run jeprof as:
    <jeprof-script> <jeprof-options> <program-symlink> <heap-files>

    For example:
    cd <unpack_dir>
    ./jeprof.sh --pdf ./sparse-root/usr/sbin/.debug/ifmand ifmand.9848.1.heap > ifmand.9848.1.pdf

    The .build_info example:

    PROC: /usr/sbin/ifmand
    EGDB: /volume/evo/files/opt/poky/3.0.2-9/sysroots/x86_64-pokysdk-linux/usr/bin/x86_64-poky-linux/x86_64-poky-linux-gdb
    YCTO: /volume/evo/files/yocto/yocto-images-3.0/20220113.175333/ptx-developer-deploy-image-re-64b
    EPRG: /volume/evo/files/publish/ifmand/v/master/29.0.427.3/app/obj-re-64b/install/usr/sbin/ifmand
    SV00: Hostname: vbrackla-RE0
    SV01: Model: ptx10003-160c
    SV02: Junos: 22.2I20220129113908-EVO_aromanov
    SV03: Yocto: 3.0.2
    SV04: Linux Kernel: 5.2.60-yocto-standard-g5ca1dce
    SV05: JUNOS-EVO OS 64-bit [junos-evo-install-ptx-fixed-x86-64-22.2I20220129113908-EVO_aromanov]
    ELIB: /volume/evo/files/publish/alarmd_module/v/master/0.0.325.10/evl-lib/obj-re-64b/install/usr/lib64/libalarmd_module.so.0
    ELIB: /volume/evo/files/publish/app-controller/v/master/6.0.18.2/app_controller_module/evl-lib/obj-re-64b/install/usr/lib64/libapp_controller_module.so.0
    ELIB: /volume/evo/files/publish/app-controller/v/master/6.0.18.2/cmd/obj-re-64b/install/usr/lib64/libapp-controller-cmd.so.0
    ELIB: /volume/evo/files/publish/app-controller/v/master/6.0.18.2/obj-re-64b/install/usr/lib64/libapp-controller-evoapp.so.0
    """)

    parser = argparse.ArgumentParser(
        prog="jeprof_unpack.py",  epilog=epilog,
        description=descr, usage=usage, formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument("-d", "--dest_dir", default=".",
                        help="destination directory, default is cwd")

    parser.add_argument("archives", nargs='+', help="tgz archives")

    try:
        args = parser.parse_args()
    except IOError as xex_desc:
        print("{}".format(xex_desc), file=sys.stderr)
        sys.exit(1)

    # import pdb; pdb.set_trace()

    xres, xmsg = main(args.archives, args.dest_dir)
    if not xres:
        print("{}".format(xmsg), file=sys.stderr)
        sys.exit(1)

    sys.exit()
