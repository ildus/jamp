import re
import os
import subprocess as sp

from functools import cache
from typing import Optional


def target_find_headers(state, target, db: Optional[dict] = None) -> bool:
    from jamp.executors import exec_one_rule

    before_incs = len(target.includes)

    if target.boundname is None:
        return False

    if target.headers:
        return False

    hdrscan = state.vars.get("HDRSCAN", on_target=target)
    hdrrule = state.vars.get("HDRRULE", on_target=target)

    if not hdrscan or not hdrrule:
        return False

    lol = [[target.name]]
    headers = db.get(target.boundname) if db else None
    target.headers = headers or scan_headers(state, target.boundname, tuple(hdrscan))

    if state.debug_headers:
        if state.limit_target is not None:
            if state.limit_target in target.name:
                print(target.name, target.headers)
        else:
            print(target.name, target.headers)

    if target.headers:
        lol.append(target.headers)

        with target.overlay(state):
            for rule_name in hdrrule:
                exec_one_rule(state, rule_name, lol)

    if before_incs != len(target.includes):
        for inc in target.includes:
            inc.bind_location(state, strict=True)

        return True

    return False


def skip_include(state, boundname):
    sub_root = state.sub_root()
    if not boundname:
        return True

    if sub_root and not boundname.startswith(sub_root[0]):
        # skip outside headers scanning
        if state.verbose and boundname not in state.scan_skipped:
            if len(state.scan_skipped) == 0:
                print(
                    "info: headers outside the source root "
                    "directory will be skipped from headers scan"
                )
            print(f"skipped from headers scan: {boundname}")
            state.scan_skipped.add(boundname)

        return True

    return False


@cache
def scan_headers(state, fn: str, hdrscan: tuple):
    patterns = []
    for pattern in hdrscan:
        patterns.append(re.compile(pattern))

    if not os.path.exists(fn):
        if not state.verbose and not state.headers_complained:
            print(
                "warning: errors while headers searching, "
                "use verbose option to turn on all messages"
            )
            state.headers_complained = True

        if state.verbose:
            print(f"warning: {fn} not found while searching headers, skipped")

        return

    headers = []
    for pattern in patterns:
        with open(fn, errors="surrogateescape") as f:
            for i, line in enumerate(f):
                for m in re.finditer(pattern, line):
                    headers += list(m.groups())

    return headers


def scan_ripgrep_output(state, pattern):
    expect_fn = True
    headers = None
    fn = None
    skip_file = False

    res = {}

    lines = sp.check_output(["rg", "--heading", "-N", pattern])
    for line in lines.splitlines():
        if line == b"":
            expect_fn = True
            continue

        try:
            line = line.decode("utf8")
        except UnicodeDecodeError:
            continue

        if expect_fn:
            expect_fn = False
            fn = os.path.abspath(line)
            skip_file = fn.endswith(".yi")
            continue

        if skip_file:
            continue

        headers = res.setdefault(fn, [])

        for m in re.finditer(pattern, line):
            headers += list(m.groups())

    return res


def scan_grep_output(state, pattern):
    from jamp.paths import check_vms

    res = {}
    lines = sp.check_output(["grep", "-I", "-s", "-H", "-r", "-E", pattern])

    for line in lines.splitlines():
        try:
            line = line.decode("utf8")
        except UnicodeDecodeError:
            continue

        try:
            fn, match = line.split(":", 1)
        except ValueError:
            print(f"grep returned unexpected output: {line}")
            continue

        fn = os.path.abspath(fn) if not check_vms() else fn
        if fn.endswith(".yi"):
            continue

        headers = res.setdefault(fn, [])

        for m in re.finditer(pattern, match):
            headers += list(m.groups())

    return res
