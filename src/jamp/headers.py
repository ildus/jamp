import re
import os
import subprocess as sp
import pickle

from functools import cache
from typing import Optional

headers_cache = None
headers_cache_loaded = None
FN_CACHE = "jamp_saved_headers.cache"
HEADERS_CACHE_VERSION = 1


def load_headers_cache():
    global headers_cache
    global headers_cache_loaded

    if headers_cache is not None or headers_cache_loaded:
        return

    if os.path.exists(FN_CACHE):
        with open(FN_CACHE, "rb") as f:
            headers_cache = pickle.load(f)
            version = headers_cache.get("jamp_version")
            if version != HEADERS_CACHE_VERSION:
                headers_cache = {}
                headers_cache["jamp_version"] = HEADERS_CACHE_VERSION
                print(
                    f"jamp: headers cache was invalidated, new version is {HEADERS_CACHE_VERSION}"
                )
    else:
        headers_cache = {}

    headers_cache_loaded = True


def save_headers_cache():
    if headers_cache:
        try:
            with open(FN_CACHE, "wb") as f:
                pickle.dump(headers_cache, f)
        except Exception as e:
            print(f"jamp: could not save to headers cache to {FN_CACHE}: {e}")
            os.unlink(FN_CACHE)


def get_cached_headers(state, fn: str, timestamp: float):
    if headers_cache:
        data = headers_cache.get(fn)
        if data:
            saved_timestamp = data[0]
            if saved_timestamp < timestamp:
                if state.verbose:
                    print(
                        f"{fn} saved headers ignored, {saved_timestamp} < {timestamp}"
                    )

                # file was modified
                del headers_cache[fn]
                return None

            return data[1]


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

    ts = None
    if headers is None:
        try:
            ts = os.path.getmtime(target.boundname)
        except FileNotFoundError:
            ts = None
        else:
            headers = get_cached_headers(state, target.boundname, ts)

    target.headers = headers or scan_headers(state, target.boundname, tuple(hdrscan))

    if state.debug_headers:
        if state.limit_target is not None:
            if state.limit_target in target.name:
                print(target.name, target.headers)
        else:
            print(target.name, target.headers)

    if target.headers:
        if ts is not None and headers is None:
            headers_cache[target.boundname] = (ts, target.headers)

        lol.append(target.headers)

        with target.overlay(state):
            for rule_name in hdrrule:
                exec_one_rule(state, rule_name, lol)

    if before_incs != len(target.includes):
        change_pairs = []

        for inc in target.includes:
            found_inc = inc.bind_location(state, strict=True)

            # Sometimes new found includes already have a some location but
            # just with different grist for example.
            # Then just use an old target.
            if found_inc is not None and inc != found_inc:
                change_pairs.append((inc, found_inc))

        if change_pairs:
            for old, new in change_pairs:
                target.includes.remove(old)
                target.includes.add(new)

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
                "jamp: errors while headers searching, "
                "use verbose option to turn on all messages"
            )
            state.headers_complained = True

        if state.verbose:
            print(f"jamp: {fn} not found while searching headers, skipped")

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
