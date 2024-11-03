import re
import os

from functools import cache


def target_find_headers(state, target):
    from jamp.executors import exec_one_rule

    if target.boundname is None:
        return

    hdrscan = state.vars.get("HDRSCAN", on_target=target)
    hdrrule = state.vars.get("HDRRULE", on_target=target)

    if not hdrscan or not hdrrule:
        return

    lol = [[target.name]]
    headers = scan_headers(state, target.boundname, tuple(hdrscan))

    if state.debug_headers:
        if state.limit_target is not None:
            if state.limit_target in target.name:
                print(target.name, headers)
        else:
            print(target.name, headers)

    if headers:
        lol.append(headers)

        with target.overlay(state):
            for rule_name in hdrrule:
                exec_one_rule(state, rule_name, lol)


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
