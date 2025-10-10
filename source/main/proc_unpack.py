#!/usr/bin/env python3
# $Id: $
#
#  Aleksey Romanov
#
#  Copyright (c) 2021, Juniper Networks, Inc.
#  All rights reserved.
#
"""Common part for unpack utilities."""

##@file  prrof_unpack.py
##@brief unpacks profiling info and builds helper scripts.sh

from typing import List, Tuple
import os
import shutil
import subprocess

SPARSE_ROOT = "sparse-root"

# Our target is python-3.5. So,we simply cannot use
# constructs, like f-strings that are not available
# in this version
# pylint: disable=consider-using-f-string
# pylint: disable=use-dict-literal
# pylint: disable=use-list-literal

# For now we prefer explicit exception handling
# pylint: disable=consider-using-with

# pylint: disable=too-few-public-methods
# pylint: disable=too-many-branches
# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-locals
# pylint: disable=too-many-return-statements
# pylint: disable=too-many-statements


# Note on handling python site-package libs
# The site-package libs do not have
# junos-version information.
#
# Also they are not-stripped.
#
# Fortunately we only 4 blocks of such libs
# used in 3 reposd we can figure out what
# is what by trial and error

class SitePackageHelper():
    """Map python site libs"""

    def __init__(self) -> None:
        self.evoapp_publish_key: str = "/volume/evo/files/publish/evoapp/v/"
        self.evoapp_sb_key: str = "/cevo/evoapp/"
        self.ifmand_publish_key: str = "/volume/evo/files/publish/ifmand/v/"
        self.ifmand_sb_key: str = "/cevo/ifmand/"
        self.firewall_publish_key: str = "/volume/evo/files/publish/dfwd/v/"
        self.firewall_sb_key: str = "/cevo/firewall/"
        self.python_common: str = "python/obj-re-64b/install"
        self.evoapp_prefix: str = ""
        self.ifmand_prefix: str = " "
        self.firewall_prefix_a: str = ""
        self.firewall_prefix_b: str = ""

    def find_second_slash(self, path: str, start_off: int) -> int:
        """Find next two slash characters

        Return offset of the second slash
        """
        if len(path) <=  start_off:
            raise ValueError("Path is too short")

        pos = path.find("/", start_off)
        if pos < 0:
            raise ValueError("Slash not found")

        pos = path.find("/", pos + 1)
        if pos < 0:
            raise ValueError("Slash not found")

        return pos

    def learn(self, path: str) -> None:
        """Figure out mount points of python related repos

        Libraries that constitute python site-packages do not
        have standard evo information allowing to locate them
        when running on the host side.

        So we figure out location information for such library
        in two steps.

        1. Any library may be located either in the sandbox or
           in the archive of published components. We use evo information
           from other libraries to figure repo location (sandbox vs archive)
           for the 3 repos of interest.

           For example, all libraries in evoapp repo either have prefix
           /volume/evo/files/publish/evoapp/v/ or the re path contains
           /cevo/evoapp/

        2. We do not know which python library belongs to which repo,
           but we know that python library names are unique. So on  we
           try every site-package library against every repo learned on
           thee step path and take one that exists.

           For example we have a library X that belongs to ifmand repo,
           combinations of this library name with any other repo
           do not exist.

           Say,  first we try evoapp-host-path + X this file does not
           exist, so we try ifmand-path + X this file exists and
           we know the actual pat of lib X on the host side.
        """
        if not self.evoapp_prefix:
            # Check published
            if path.startswith(self.evoapp_publish_key):
                second_slash = self.find_second_slash(
                    path, len(self.evoapp_publish_key))
                self.evoapp_prefix = (
                    path[:second_slash + 1] + self.python_common)
                return

            # Check the sandbox
            pos = path.find(self.evoapp_sb_key)
            if pos < 0:
                return

            self.evoapp_prefix = (
                path[:pos + len(self.evoapp_sb_key)] + self.python_common)
            return

        if not self.ifmand_prefix:
            # Check published
            if path.startswith(self.ifmand_publish_key):
                second_slash = self.find_second_slash(
                    path, len(self.ifmand_publish_key))
                self.ifmand_prefix = (
                    path[:second_slash + 1] + self.python_common)
                return

            # Check the sandbox
            pos = path.find(self.ifmand_sb_key)
            if pos < 0:
                return

            self.ifmand_prefix = (
                path[:pos + len(self.ifmand_sb_key)] + self.python_common)
            return

        if not self.firewall_prefix_a:
            # Check published
            if path.startswith(self.firewall_publish_key):
                second_slash = self.find_second_slash(
                    path, len(self.firewall_publish_key))
                self.firewall_prefix_a = (
                    path[:second_slash + 1] + "lib/libevo-firewall/" +
                    self.python_common)
                self.firewall_prefix_b = (
                    path[:second_slash + 1] + "lib/libfw-bitparser/" +
                    self.python_common)
                return

            # Check the sandbox
            pos = path.find(self.firewall_sb_key)
            if pos < 0:
                return

            self.firewall_prefix_a = (
                path[:pos + len(self.firewall_sb_key)] + "lib/libevo-firwall/" +
                self.python_common)
            self.firewall_prefix_b = (
                path[:pos + len(self.firewall_sb_key)] + "lib/libfw-bitparser/" +
                self.python_common)
            return

helper = SitePackageHelper()

class Ctx():
    """Processing context

    We accumulate common information about from
    several data files. And use it to check for conflicts
    """

    def __init__(self)->None:
        self.all_libs = list() # type: List[str]
        self.all_procs = list() # type: List[str]

class Data():
    """Simple data holder.

    We have too much data for tuple
    """
    def __init__(self) -> None:
        self.proc = ""
        self.yocto = ""
        self.gdb = ""
        self.eprog = ""
        self.jprog = ""
        self.version_strs = list() # type: List[str]
        # Dictionary: basename to full library path to detect
        # duplicaties and conflicts
        self.elibs = list() # type: List[str]
        self.jlibs = list() # type: List[str]
        self.olibs = list() # type: List[str]

class Result():
    """Result of the unpacking step"""
    def __init__(self) -> None:
        self.unpack_dir = ""
        self.is_64bit = False
        self.info_files = list() # type: List[str]
        self.raw_data = list() # type: List[str]
        self.sparse_root = ""
        self.prog_symlinks = list() # type: List[str]
        self.debug_symlinks = list() # type: List[str]
        self.prog_manuals = list() # type: List[str]
        self.jtools = ""
        self.yocto = ""
        self.gdb = ""
        self.version_strs = list() # type: List[str]

def get_unpack_dir(archive: str, dest_dir: str) -> Tuple[bool, str, str]:
    """Create unpack directory..

    Return: result, msg, unpack directory.
    """
    if not os.path.exists(dest_dir):
        return (False, "destination directory {} does not exist", "")

    try:
        arch_base = os.path.basename(archive)
    except OSError as ex_desc:
        return (False, "bad archive path {}: {}".format(archive, ex_desc), "")

    pos = arch_base.rfind(".")
    if pos <= 0:
        return (False, "bad archive name {}".format(archive), "")

    unpack_dir = dest_dir + "/" + arch_base[:pos]+ ".unpack"

    if os.path.exists(unpack_dir):
        shutil.rmtree(unpack_dir)

    try:
        os.makedirs(unpack_dir)
        unpack_dir = os.path.realpath(unpack_dir)
        os.makedirs(unpack_dir + "/" + SPARSE_ROOT + "/lib")
        os.makedirs(unpack_dir + "/" + SPARSE_ROOT + "/lib64")
        os.makedirs(unpack_dir + "/" + SPARSE_ROOT + "/usr/lib")
        os.makedirs(unpack_dir + "/" + SPARSE_ROOT + "/usr/lib64")

        # Add ".debug" sub-dirs
        os.makedirs(unpack_dir + "/" + SPARSE_ROOT + "/lib/.debug")
        os.makedirs(unpack_dir + "/" + SPARSE_ROOT + "/lib64/.debug")
        os.makedirs(unpack_dir + "/" + SPARSE_ROOT + "/usr/lib/.debug")
        os.makedirs(unpack_dir + "/" + SPARSE_ROOT + "/usr/lib64/.debug")
    except OSError as ex_desc:
        return (
            False,
            "unable to create unpack directory {}: {}".format(unpack_dir, ex_desc),
            "")

    return (True, "", unpack_dir)

def get_info_files(raw_dir: str) -> List[str]:
    """Get info files from a directory"""

    info_files = list() # type: List[str]

    for dirpath, _, filenames in os.walk(raw_dir):
        for fname in filenames:
            if not fname.endswith(".build_info"):
                continue
            info_files.append(os.path.join(dirpath, fname))

    # It is ok if specific archive does not have build-info files
    return info_files


def unpack_tar(archive: str,  unpack_dir: str) -> Tuple[bool, str, str, List[str]]:
    """Create unpack directory and unpack data..

    Return: result, msg, raw-data dir, and build_info files
    """

    try:
        arch_base = os.path.basename(archive)
    except OSError as ex_desc:
        return (False, "bad archive path {}: {}".format(archive, ex_desc), "", list())

    pos = arch_base.rfind(".")
    if pos <= 0:
        return (False, "bad archive name {}".format(archive), "", list())

    # Unpack archive
    raw_base = arch_base[:pos]
    raw_data = raw_base + ".raw"

    try:
        os.makedirs(unpack_dir + "/" + raw_data)
    except OSError as ex_desc:
        return (
            False,
            "unable to create {} directory in {}: {}".format(raw_data, unpack_dir, ex_desc),
            "",
            list())

    tar_cmd = "tar -x -f {} -a -C {}/{}".format(archive, unpack_dir, raw_data)

    try:
        subprocess.check_call([tar_cmd], shell=True)
    except subprocess.CalledProcessError as ex_desc:
        return (False, "unable to extract unpack tar archive {}".format(ex_desc), "", list())


    # Get list of info files
    raw_dir = unpack_dir + "/" + raw_data
    info_files = get_info_files(raw_dir)

    return (True, "", raw_data, info_files)


def get_proc_info(info_file: str
) -> Tuple[bool, str, Data]:
    """Process info file.

    Returns: result, message, yocto, gdb, prog list of libs
    """

    info_f = open(info_file, "r", encoding="utf-8")
    if not info_f:
        return (False, "unable to open {}".format(info_file), Data())

    data = Data()
    line_count = 0
    for line in info_f:
        line = line.strip()
        line_count += 1

        if line.startswith("PROC: "):
            if data.proc:
                info_f.close()
                return (False,
                        "duplicate proc string {}:{}".format(info_file, line_count),
                        Data())
            data.proc = line[6:]
            continue

        if line.startswith("YCTO: "):
            if data.yocto:
                info_f.close()
                return (False,
                        "duplicate yocto string {}:{}".format(info_file, line_count),
                        Data())
            data.yocto = line[6:]
            continue

        if line.startswith("EGDB: "):
            if data.gdb:
                info_f.close()
                return (False,
                        "duplicate gdb string {}:{}".format(info_file, line_count),
                        Data())
            data.gdb = line[6:]
            continue

        if line.startswith("EPRG: "):
            if data.eprog or data.jprog:
                info_f.close()
                return (False,
                        "duplicate prog string {}:{}".format(info_file, line_count),
                        Data())
            data.eprog = line[6:]
            continue

        if line.startswith("JPRG: "):
            if data.eprog or data.jprog:
                info_f.close()
                return (False,
                        "duplicate prog string {}:{}".format(info_file, line_count),
                        Data())
            data.jprog = line[6:]
            continue

        if line.startswith("SV") and line[4] == ":" and line[5] == " ":
            data.version_strs.append(line[6:])
            continue

        if line.startswith("ELIB: "):
            data.elibs.append(line[6:])
            continue

        if line.startswith("JLIB: "):
            data.jlibs.append(line[6:])
            continue

        if line.startswith("OPRG: "):
            continue

        if line.startswith("ILIB: "):
            continue

        if line.startswith("OLIB: "):
            data.olibs.append(line[6:])
            continue

        if line:
            info_f.close()
            return (False, "unrecognized line  {}:{}".format(info_file, line_count), Data())

    info_f.close()

    if data.proc:
        pos = data.proc.rfind("/")
        if pos <= 0:
            # Data.proc should be a full path
            # and it should not be directly under root
            return (False, "bad proc {}".format(data.proc), Data())

    return (True, "", data)


def get_debug_path(path: str) -> Tuple[bool, str, str]:
    """Get debug version of library/program"""

    try:
        dirname = os.path.dirname(path)
        basename = os.path.basename(path)
    except OSError as ex_desc:
        return (False, "bad path {}: {}".format(path, ex_desc), "")

    if not dirname or not basename:
        return (False, "bad path {}".format(path), "")

    try:
        debug_path = os.path.realpath(dirname + "/.debug/" + basename)
        if not os.path.exists(debug_path):
            return (False, "bad path {}".format(debug_path), "")
    except OSError as ex_desc:
        return (False, "bad path {}: {}".format(path, ex_desc), "")

    return (True, "", debug_path)


def proc_elib(ctx: Ctx, lib: str, unpack_dir: str, simple: bool) -> Tuple[bool, str, bool]:
    """Get debug version of lib and symlink it"""

    res, msg, debug_lib = get_debug_path(lib)
    if not res:
        return (res, msg, False)

    try:
        basename = os.path.basename(lib)
    except OSError as ex_desc:
        return (False, "bad path {}: {}".format(lib, ex_desc), False)

    is_64bit = False

    if lib.find("/usr/lib/") >= 0:
        lib_pref = "/usr/lib/"
    elif lib.find("/usr/lib64/") >= 0:
        lib_pref = "/usr/lib64/"
        is_64bit = True
    elif lib.find("/lib/") >= 0:
        lib_pref = "/lib/"
    elif lib.find("/lib64/") >= 0:
        lib_pref = "/lib64/"
        is_64bit = True
    else:
        return (False, "unexpected lib path {}".format(lib), False)

    lib_key = lib_pref + basename
    if lib_key in ctx.all_libs:
        return (True, "", is_64bit)

    helper.learn(lib)

    try:
        if not simple:
            os.symlink(lib, unpack_dir + "/" + SPARSE_ROOT + lib_pref + basename)
        os.symlink(debug_lib, unpack_dir + "/" + SPARSE_ROOT + lib_pref + ".debug/" + basename)
    except OSError as ex_desc:
        return (False, "bad lib {}: {}".format(lib, ex_desc), False)

    ctx.all_libs.append(lib_key)

    return (True, "", is_64bit)


def proc_jlib(ctx: Ctx, lib: str, unpack_dir: str) -> Tuple[bool, str, bool]:
    """Get just symlink the jlib"""

    try:
        basename = os.path.basename(lib)
    except OSError as ex_desc:
        return (False, "bad path {}: {}".format(lib, ex_desc), False)

    is_64bit = False

    if lib.find("/amd64") >= 0:
        prefix = "/usr/lib64/"
        is_64bit = True
    else:
        prefix = "/usr/lib/"

    lib_key = prefix + basename
    if lib_key in ctx.all_libs:
        return (True, "", is_64bit)

    try:
        os.symlink(lib, unpack_dir + "/" + SPARSE_ROOT + prefix + basename)
    except OSError as ex_desc:
        return (False, "bad lib {}: {}".format(lib, ex_desc), False)

    ctx.all_libs.append(lib_key)

    return (True, "", is_64bit)

def proc_olib(ctx: Ctx, lib: str, unpack_dir: str, yocto: str) -> Tuple[bool, str, bool]:
    """Best effort other-lib processing"""

    is_64bit = False
    if lib.find("/lib64") >= 0:
        is_64bit = True

    pos = lib.find("site-packages")
    if pos < 0:
        # We have to map only site packages because
        # we built them ourselves the rest of the libs
        # will be picked up from yocto
        return (True, "", is_64bit)

    if lib in ctx.all_libs:
        return (True, "", is_64bit)

    found_lib: str = ""

    try_lib: str  = helper.evoapp_prefix + lib
    if os.path.exists(try_lib):
        found_lib = try_lib

    if not found_lib:
        try_lib = helper.ifmand_prefix + lib
        if os.path.exists(try_lib):
            found_lib = try_lib

    if not found_lib:
        try_lib = helper.firewall_prefix_a + lib
        if os.path.exists(try_lib):
            found_lib = try_lib

    if not found_lib:
        try_lib = helper.firewall_prefix_b + lib
        if os.path.exists(try_lib):
            found_lib = try_lib

    if not found_lib:
        try_lib = yocto + lib
        if os.path.exists(try_lib):
            # Will be picked up from yocto
            return (True, "", is_64bit)

    if not found_lib:
        return (False, "bad path {}: no repo match".format(lib), False)

    try:
        basename = os.path.basename(lib)
        dirname = os.path.dirname(lib)
    except OSError as ex_desc:
        return (False, "bad path {}: {}".format(lib, ex_desc), "")

    dir_path = unpack_dir + "/" + SPARSE_ROOT + dirname

    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

    try:
        os.symlink(found_lib, dir_path + "/" + basename)
    except OSError as ex_desc:
        return (False, "bad lib {}: {}".format(found_lib, ex_desc), False)

    ctx.all_libs.append(lib)

    return (True, "", is_64bit)

def proc_eprog(ctx: Ctx, proc: str, prog: str, unpack_dir: str) -> Tuple[bool, str, str, str]:
    """Get debug version of proc and symlink it

    Returns success/failure, message, relative program symlink, relative debug symlink
    """

    if proc in ctx.all_procs:
        return (False, "duplicate proc {}".format(proc), "", "")

    if proc[0] != "/":
        return (False, "bad proc {}".format(proc), "", "")

    res, msg, debug_prog = get_debug_path(prog)
    if not res:
        return (res, msg, "", "")

    try:
        dirname = os.path.dirname(proc)
        basename = os.path.basename(proc)
    except OSError as ex_desc:
        return (False, "bad proc {}: {}".format(proc, ex_desc), "", "")

    try:
        os.makedirs(unpack_dir + "/" + SPARSE_ROOT + dirname, exist_ok=True)
        os.symlink(prog, unpack_dir + "/" + SPARSE_ROOT + dirname + "/" + basename)

        os.makedirs(unpack_dir + "/" + SPARSE_ROOT + dirname + "/.debug", exist_ok=True)
        os.symlink(debug_prog, unpack_dir + "/" + SPARSE_ROOT + dirname + "/.debug/" + basename)
    except OSError as ex_desc:
        return (False, "bad proc {}: {}".format(proc, ex_desc), "", "")

    return (True, "", dirname + "/" + basename, dirname + "/.debug/" + basename)


def proc_jprog(ctx: Ctx, proc: str, prog: str, unpack_dir: str) -> Tuple[bool, str, str, str]:
    """Symlink the program, note for junos same program the debug one

    Returns success/failure, message, relative program symlink, relative debug symlink
    """

    if proc in ctx.all_procs:
        return (False, "duplicate proc {}".format(proc), "", "")

    if proc[0] != "/":
        return (False, "bad proc {}".format(proc), "", "")

    try:
        dirname = os.path.dirname(proc)
        basename = os.path.basename(proc)
    except OSError as ex_desc:
        return (False, "bad proc: {} {}".format(proc, ex_desc), "", "")

    try:
        os.makedirs(unpack_dir + "/" + SPARSE_ROOT + dirname[1:0], exist_ok=True)
        os.symlink(prog, unpack_dir + "/" + SPARSE_ROOT + dirname[1:0] + "/" + basename)
    except OSError as ex_desc:
        return (False, "bad proc {}: {}".format(proc, ex_desc), "", "")

    return (True, "", dirname + "/" + basename, dirname[1:0] + "/" + basename)

def proc_oprog(ctx: Ctx, proc: str, yocto: str, unpack_dir: str) -> Tuple[bool, str, str, str]:
    """Get debug version of proc and symlink it

    Lookup for a program under yocto directory and link it under sparse  root
    """

    if proc in ctx.all_procs:
        return (False, "duplicate proc {}".format(proc), "", "")

    if proc[0] != "/":
        return (False, "bad proc {}".format(proc), "", "")

    try:
        dirname = os.path.dirname(proc)
        basename = os.path.basename(proc)
    except OSError as ex_desc:
        return (False, "bad proc {}: {}".format(proc, ex_desc), "", "")

    prog = yocto + dirname + "/" + basename
    if not os.path.exists(prog):
        return (False, "bad proc target {}".format(prog), "", "")

    debug_prog = yocto + dirname + "/.debug/" + basename

    if not os.path.exists(debug_prog):
        return (False, "bad proc target {}".format(debug_prog), "", "")

    try:
        os.makedirs(unpack_dir + "/" + SPARSE_ROOT + dirname, exist_ok=True)
        os.symlink(prog, unpack_dir + "/" + SPARSE_ROOT + dirname + "/" + basename)

        os.makedirs(unpack_dir + "/" + SPARSE_ROOT + dirname + "/.debug", exist_ok=True)
        os.symlink(debug_prog, unpack_dir + "/" + SPARSE_ROOT + dirname + "/.debug/" + basename)
    except OSError as ex_desc:
        return (False, "bad proc {}: {}".format(proc, ex_desc), "", "")

    return (True, "", dirname + "/" + basename, dirname + "/.debug/" + basename)


def get_jtools(gdb_str: str) -> Tuple[bool, str, str]:
    """Get poky-base fom gdb_str"""

    pos = gdb_str.find("-gdb")
    if pos < 0:
        return (False, "bad gdb-str {}".format(gdb_str), "")

    return (True, "",  gdb_str[:pos + 1])


def proc_unpack(archives: List[str], dest_dir: str, simple: bool) -> Tuple[bool, str, Result]:
    """Main entry point"""

    if not archives:
        return (False, "no archives", Result())

    res, msg, unpack_dir = get_unpack_dir(archives[0], dest_dir)
    if not res:
        return (False, msg, Result())

    raw_data = list() # type: List[str]
    info_files = list() # type: List[str]

    for archive in archives:
        res, msg, raw_data_dir, cur_info_files  = unpack_tar(archive, unpack_dir)
        if not res:
            return (res, msg, Result())

        raw_data.append(raw_data_dir)
        info_files = info_files + cur_info_files

    jtools = ""
    real_yocto = ""
    real_gdb = ""
    prog_symlinks = list() # type: List[str]
    debug_symlinks = list() # type: List[str]
    prog_manuals = list() # type: List[str]
    version_strs = list() # type: List[str]
    is_64bit = False

    ctx = Ctx()

    for info_file in info_files:
        res, msg, data = get_proc_info(info_file)
        if not res:
            return (res, msg, Result())

        try:
            cur_yocto = os.path.realpath(data.yocto)
            if not os.path.exists(cur_yocto):
                return (False, "bad path {}".format(cur_yocto), Result())
            if cur_yocto[-1] == "/":
                cur_yocto = cur_yocto[:-1]
            if real_yocto and  real_yocto != cur_yocto:
                return (False, "yocto conflict: {}".format(info_file), Result())
            real_yocto = cur_yocto

            cur_gdb = os.path.realpath(data.gdb)
            if not os.path.exists(cur_gdb):
                return (False, "bad path {}".format(cur_gdb), Result())
            if "/usr/bin/" not in cur_gdb:
                return (False, "bad gdb path: {}".format(cur_gdb), Result())
            if real_gdb and  real_gdb != cur_gdb:
                return (False, "gdb conflict: {}".format(info_file), Result())
            real_gdb = cur_gdb
        except OSError as ex_desc:
            return (False, "unexpected real path failure: {}".format(ex_desc), Result())

        for lib in data.elibs:
            res, msg, cur_64bit = proc_elib(ctx, lib, unpack_dir, simple)
            if not res:
                print("WARNING: {}".format(msg))
                continue

            if not is_64bit and cur_64bit:
                is_64bit = True

        for lib in data.jlibs:
            res, msg, cur_64bit  = proc_jlib(ctx, lib, unpack_dir)
            if not res:
                print("WARNING: {}".format(msg))
                continue

        for lib in data.olibs:
            res, msg, cur_64bit  = proc_olib(ctx, lib, unpack_dir, real_yocto)
            if not res:
                print("WARNING: {}".format(msg))
                continue

            if not is_64bit and cur_64bit:
                is_64bit = True

        res, msg, cur_jtools = get_jtools(data.gdb)
        if not res:
            return (res, msg, Result())

        if jtools and jtools != cur_jtools:
            return (False, "jtools conflict: {}".format(info_file), Result())

        if not jtools:
            jtools = cur_jtools

        if data.eprog:
            res, msg, prog_link, debug_link = proc_eprog(ctx, data.proc, data.eprog, unpack_dir)
            if not res:
                return (res, msg, Result())

            prog_symlinks.append(prog_link)
            debug_symlinks.append(debug_link)
        elif data.jprog:
            res, msg, prog_link, debug_link = proc_jprog(ctx, data.proc, data.jprog, unpack_dir)
            if not res:
                return (res, msg, Result())

            prog_symlinks.append(prog_link)
            debug_symlinks.append(debug_link)
        elif data.proc:
            res, msg, prog_link, debug_link = proc_oprog(ctx, data.proc, real_yocto, unpack_dir)
            if not res:
                return (res, msg, Result())
            prog_symlinks.append(prog_link)
            debug_symlinks.append(debug_link)

        if not version_strs:
            # It seems like an overkill to check version strings
            # for conflicts so we are using the first one
            version_strs = data.version_strs

    result = Result()
    result.unpack_dir = unpack_dir
    result.is_64bit = is_64bit
    result.info_files = info_files
    result.raw_data = raw_data
    result.sparse_root = SPARSE_ROOT
    result.prog_symlinks = prog_symlinks
    result.debug_symlinks = debug_symlinks
    result.prog_manuals = prog_manuals
    result.jtools = jtools
    result.yocto = real_yocto
    result.gdb = real_gdb
    result.version_strs = version_strs

    return (True, "", result)
