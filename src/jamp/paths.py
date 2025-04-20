#
# Pathname - a name of a file, broken into <grist>dir/base/suffix(member)
#
# <grist> is salt to distinguish between targets that otherwise would
# have the same name:  it never appears in the bound name of a target.
# (member) is an archive member name: the syntax is arbitrary, but must
# agree in parse(), build() and the Jambase.
#
# On VMS, we keep track of whether the original path was a directory
# (without a file), so that $(VAR:D) can climb to the parent.
#

import platform
from pathlib import PurePath
from enum import Enum
from functools import cache


@cache
def check_vms():
    return platform.system() == "OpenVMS"


@cache
def check_windows():
    return platform.system() == "Windows"

@cache
def check_linux():
    return platform.system() == "Linux"


def escape_path(s):
    if check_vms():
        return s.replace("$", "$$").lower()
    return s


def add_paths(s, deps):
    if check_vms():
        for dep in deps:
            s.add(dep.lower())
    else:
        s.update(deps)


class Dir(Enum):
    EMPTY = 0  # empty string */
    DEV = 1  # dev: */
    DEVDIR = 2  # dev:[dir] */
    DOTDIR = 3  # [.dir] */
    DASHDIR = 4  # [-] or [-.dir] */
    ABSDIR = 5  # [dir] */
    ROOT = 6  # [000000] or dev:[000000] */


G_DIR = 0  # take just dir */
G_ROOT = 1  # take just root */
G_VAD = 2  # root's dev: + [abs] */
G_DRD = 3  # root's dev:[dir] + [.rel] */
G_VRD = 4  # root's dev: + [.rel] made [abs] */
G_DDD = 5  # root's dev:[dir] + . + [dir] */

grid = [
    # root/dir	EMPTY	DEV	DEVDIR	DOTDIR	DASH,	ABSDIR	ROOT
    [G_DIR, G_DIR, G_DIR, G_DIR, G_DIR, G_DIR, G_DIR],  # empty
    [G_ROOT, G_DIR, G_DIR, G_VRD, G_VAD, G_VAD, G_VAD],  # dev
    [G_ROOT, G_DIR, G_DIR, G_DRD, G_VAD, G_VAD, G_VAD],  # dev:[dir]
    [G_ROOT, G_DIR, G_DIR, G_DRD, G_DIR, G_DIR, G_DIR],  # dot
    [G_ROOT, G_DIR, G_DIR, G_DRD, G_DDD, G_DIR, G_DIR],  # dash
    [G_ROOT, G_DIR, G_DIR, G_DRD, G_DIR, G_DIR, G_DIR],  # abs
    [G_ROOT, G_DIR, G_DIR, G_VRD, G_DIR, G_DIR, G_DIR],  # root
]


class DirFlags:
    def __init__(self):
        self.flags = Dir.EMPTY
        self.dev = ""
        self.dir = ""

    def __repr__(self):
        return f"{self.flags} {self.dev} {self.dir}"


class Pathname:
    def __init__(self, is_vms=None):
        self.grist = None
        self.root = None
        self.directory = None
        self.base = None
        self.member = None
        self.suffix = None
        self.is_dir = False  # only for VMS, keep track if it's a directory
        self.parent = False

        if is_vms is not None:
            # for testing purposes
            self.is_vms = is_vms
        else:
            self.is_vms = check_vms()

    def zero(self):
        self.grist = ""
        self.root = ""
        self.directory = ""
        self.base = ""
        self.member = ""
        self.suffix = ""
        self.parent = False

    def __repr__(self):
        return (
            f"Path[{self.grist},R={self.root},D={self.directory},B={self.base},"
            f"S={self.suffix},M={self.member}]"
        )

    def parse(self, string):
        idx = string.find(">")

        # check for grist
        if string[0] == "<" and idx > 0:
            self.grist = string[1:idx]
            string = string[idx + 1 :]

        # check for member
        if string.endswith(")"):
            idx = string.rfind("(")
            if idx > 0:
                self.member = string[idx + 1 : -1]
                string = string[0:idx]

        if self.is_vms:
            self.parse_vms(string)
        else:
            path = PurePath(string)
            self.suffix = path.suffix
            self.base = path.stem
            self.root = None
            self.directory = str(path.parent)

    def out_member(self):
        if self.member:
            return "(" + self.member + ")"
        return ""

    def out_grist(self):
        if self.grist:
            if self.grist.startswith("<"):
                return self.grist

            return "<" + self.grist + ">"

        return ""

    def build(self, binding=False):
        if self.is_vms:
            return self.build_vms(binding=binding)

        is_abs = PurePath(self.directory).is_absolute()
        fn = ""
        if self.base:
            fn = self.base + self.suffix
        else:
            fn = self.suffix

        if fn is None:
            fn = ""

        if self.root or self.directory or fn:
            if self.root and self.root != "." and not is_abs:
                path = PurePath(self.root, self.directory, fn)
            else:
                path = PurePath(self.directory, fn)
        else:
            path = ""

        res_path = self.out_grist() + str(path) + self.out_member()
        return res_path

    def keep_only_parent(self):
        if not self.is_vms or (self.is_vms and self.base):
            self.base = None
            self.suffix = None
            self.member = None
        elif self.is_vms:
            self.parent = True

    def parse_vms(self, string):
        # Look for dev:[dir] or dev
        idx = string.find("]")

        if idx > 0:
            self.directory = string[: idx + 1]
        else:
            idx = string.find(":")
            if idx > 0:
                self.directory = string[: idx + 1]

        if idx > 0:
            string = string[idx + 1 :]

        # find suffix
        idx = string.rfind(".")
        if idx > 0:
            self.suffix = string[idx:]
            string = string[0:idx]

        # Leaves base
        self.root = None
        self.base = string

    def dir_flags(self, string: str) -> DirFlags:
        info = DirFlags()

        if string:
            idx = string.find(":")
            if idx > 0:
                info.dev = string[: idx + 1]
                info.dir = string[idx + 1 :]

                if len(info.dir) and info.dir[0] == "[":
                    info.flags = Dir.DEVDIR
                else:
                    info.flags = Dir.DEV
            else:
                info.dev = ""
                info.dir = string

                if string[:2] == "[]":
                    info.flags = Dir.EMPTY
                elif string[:2] == "[.":
                    info.flags = Dir.DOTDIR
                elif string[:2] == "[-":
                    info.flags = Dir.DASHDIR
                else:
                    info.flags = Dir.ABSDIR

        # But if its rooted in any way */
        if info.dir == "[000000]":
            info.flags = Dir.ROOT

        return info

    def build_vms(self, binding=False):
        info_root = self.dir_flags(self.root)
        info_dir = self.dir_flags(self.directory)

        res_path = ""
        g = grid[info_root.flags.value][info_dir.flags.value]

        directory = self.directory or ""
        root = self.root or ""

        if g == G_DIR:
            # take dir
            res_path += directory

        elif g == G_ROOT:
            # take root
            res_path += root

        elif g == G_VAD:
            # root's dev + abs directory
            res_path += info_root.dev + info_dir.dir

        elif g == G_DRD or g == G_DDD:
            # root's dev:[dir] + rel directory
            # sanity checks: root ends with ] */
            if self.root.endswith("]"):
                res_path += root[:-1]
            else:
                res_path += root

            # Add . if separating two -'s
            if g == G_DDD:
                res_path += "."

            # skip [ of dir
            res_path += info_dir.dir[1:]

        elif g == G_VRD:
            # root's dev + rel directory made abs
            res_path += info_root.dev
            res_path += "["

            # skip [. of rel dir */
            res_path += info_dir.dir[2:]

        # Now do the special :P modifier when no file was present.
        # (none)		(none)
        # [dir1.dir2]	[dir1]
        # [dir]		[000000]
        # [.dir]		[]
        # []		[]

        if res_path.endswith("]") and self.parent:
            i = len(res_path) - 1
            prev_c = None
            while i >= 0:
                idx = None
                c = res_path[i]
                if c == ".":
                    idx = i
                elif c == "-":
                    idx = i
                    if i != 0 and res_path[i - 1] == ".":
                        idx = i - 1

                if idx is not None:
                    res_path = res_path[:i] + "]"
                    break

                if c == "[" and prev_c != "]":
                    res_path = res_path[:i] + "[000000]"
                    break

                prev_c = c
                i -= 1

        without_dir = False
        if self.base:
            if not res_path:
                without_dir = True

            res_path += self.base

        # If there is no suffix, we append a "." onto all generated
        # names.  This keeps VMS from appending its own (wrong) idea
        # of what the suffix should be.
        if self.suffix:
            res_path += self.suffix
        elif binding and self.base:
            res_path += "."

        if without_dir and binding:
            res_path = "[]" + res_path

        return self.out_grist() + res_path + self.out_member()
