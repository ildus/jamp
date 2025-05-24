import sys
import os
import re
import subprocess as sp

from typing import Union
from pathlib import Path

from jamp.classes import State, Target, Exec
from jamp.jam_syntax import Arg, Node
from jamp.expand import var_expand, lol_get
from jamp.pattern import match


def output(text, end="\n"):
    if not hasattr(sys, "_called_from_test"):
        print(text, end=end)
    else:
        Builtins.output += text + end


class Builtins:
    """Singleton with builtin rules"""

    output = ""

    def __init__(self):
        self.dir_counter = 0

    @classmethod
    def clear_output(cls):
        cls.output = ""

    def glob(self, state: State, lol: list):
        from jamp.executors import Result

        dirs = lol_get(lol, 0)
        patterns = lol_get(lol, 1)

        if len(patterns) == 0 or len(dirs) == 0:
            return []

        res = []
        for d in dirs:
            p = Path(d)
            if not p.is_dir():
                continue

            for f in p.iterdir():
                for m in patterns:
                    if match(m, f.name) == 0:
                        res.append(os.path.join(d, f.name))
                        break

        return Result(res)

    def mkdir(self, state: State, paths_arg: list):
        from jamp.paths import Pathname

        paths = expand(state, paths_arg)

        dirs_target = state.targets.get("dirs")
        if dirs_target is None:
            print("fatal error, dirs target not found")
            return

        dirs_target.is_dirs_target = True

        for path in paths:
            p = Pathname()
            p.parse(paths[0])
            p.grist = ""

            dry = p.build()
            if dry == "." or dry == "..":
                continue

            if dirs_target.collected_dirs is None:
                dirs_target.collected_dirs = set()

            dirs_target.collected_dirs.add(dry)

    def pathexists(self, state, paths_arg):
        from jamp.executors import Result
        from jamp.paths import Pathname

        paths = expand(state, paths_arg)
        res = []
        if len(paths):
            p = Pathname()
            p.parse(paths[0])
            p.grist = ""
            if os.path.exists(p.build()):
                res = ["1"]

        return Result(res)

    def match(self, state: State, lol: list):
        from jamp.executors import Result

        strings = lol_get(lol, 1)
        patterns = lol_get(lol, 0)

        if len(patterns) == 0 or len(strings) == 0:
            return []

        if not hasattr(self, "match_complained"):
            print("jamp: Match rule works by Python regular expression rules")
            self.match_complained = True

        res = []
        for s in strings:
            for p in patterns:
                matches = re.findall(p, s)
                if not matches:
                    continue

                if isinstance(matches[0], str):
                    res += [m for m in matches if m]
                elif isinstance(matches[0], tuple):
                    for m in matches:
                        for innertup in m:
                            val = "".join(innertup)
                            if val:
                                res.append(val)

        return Result(res)

    def depends(self, state: State, lol: list, includes=False):
        """
        Depends() - DEPENDS/INCLUDES rule

        The DEPENDS builtin rule appends each of the listed sources on the
        dependency list of each of the listed targets.  It binds both the
        targets and sources as TARGETs.

        TODO: use includes
        """

        targets = lol_get(lol, 0)
        sources = lol_get(lol, 1)

        if sources == ["."]:
            return

        if targets == sources:
            return

        for target_name in targets:
            target = Target.bind(state, target_name)

            if includes:
                target.add_includes(state, sources)
            else:
                target.add_depends(state, sources)

    def includes(self, state: State, args: list):
        return self.depends(state, args, includes=True)

    def always(self, state: State, targets: list):
        targets = expand(state, targets)
        for target_name in targets:
            target = Target.bind(state, target_name)
            state.always_build.add(target)

    def notfile(self, state: State, targets: list):
        """Set the targets as phony"""

        targets = expand(state, targets)
        for target_name in targets:
            target = Target.bind(state, target_name)
            target.notfile = True

    def generated(self, state: State, targets: list):
        """Force targets use generator in their rules"""

        targets = expand(state, targets)
        for target_name in targets:
            target = Target.bind(state, target_name)
            target.generated = True

    def restat(self, state: State, targets: list):
        """Force targets use restat in their rules"""

        targets = expand(state, targets)
        for target_name in targets:
            target = Target.bind(state, target_name)
            target.restat = True

    def temporary(self, state: State, targets: list):
        targets = expand(state, targets)
        for target_name in targets:
            target = Target.bind(state, target_name)
            target.temporary = True

    def leaves(self, state: State, targets: list):
        if hasattr(self, "leaves_complained"):
            return

        print('jamp: "leaves" rule is ignored')
        self.leaves_complained = True

    def nocare(self, state: State, targets: list):
        targets = expand(state, targets)
        for target_name in targets:
            target = Target.bind(state, target_name)
            target.nocare = True

    def noupdate(self, state: State, targets: list):
        targets = expand(state, targets)
        for target_name in targets:
            target = Target.bind(state, target_name)
            target.noupdate = True

    def _print(self, val: Union[str, list], first: bool = True):
        """unflatten before printing"""
        if isinstance(val, str):
            if not first:
                output(" ", end="")

            output(val, end="")
            first = False
        else:
            for item in val:
                first = self._print(item, first)

        return first

    def echo(self, state: State, params: list):
        self._print(params)
        output("")

    def exit(self, state, args):
        self.echo(state, args)
        exit(1)

    def pdb(self, state, args):
        from jamp.executors import FLOW_DEBUG

        return FLOW_DEBUG

    def command(self, state: State, args):
        from jamp.executors import Result

        cmd = " ".join(expand(state, args))
        output = ""
        try:
            output = sp.check_output(cmd, shell=True)
            output = output.decode("utf8").strip()
        except sp.CalledProcessError:
            if state.verbose:
                print(f"jamp: command returned non-zero status:\n{cmd}\n{output}")
            elif not hasattr(self, "nonzero_complained"):
                print(
                    "jamp: some of Command rules returned "
                    "non-zero status (use --verbose for more info)"
                )
                self.nonzero_complained = True

        return Result([output])


def flatten(res: list):
    # try to remove one level
    if isinstance(res, list) and len(res) == 1:
        res = res[0]

    return res


def iter_var(var, skip_empty=True):
    if isinstance(var, str):
        yield var
    elif isinstance(var, list):
        for item in var:
            yield item
    else:
        raise Exception(f"unexpected var for iteration: {var}")


def validate(var):
    if not isinstance(var, list):
        raise Exception(f"validation: expected list, got: {var}")
    if len(var) > 0:
        if not isinstance(var[0], str):
            raise Exception(f"validation: expected str on second level, got: {var[0]}")


def validate_lol(var):
    if not isinstance(var, list):
        raise Exception(f"LOL validation: expected list, got: {var}")
    if len(var) > 0:
        if not isinstance(var[0], list):
            raise Exception(
                f"LOL validation: expected list on second level, got: {var[0]}"
            )


def expand(state: State, arg: Union[Arg, tuple, str], skip_empty=True):
    """Make list of strings from some type of an argument"""

    if arg is None or (skip_empty and arg == ""):
        return []
    elif arg == "":
        return [""]
    elif isinstance(arg, str):
        res = var_expand(arg, state.params, state.vars)
    elif isinstance(arg, Exec):
        from jamp.executors import Result

        execval = arg.execute(state)
        if execval is None:
            res = []
        elif isinstance(execval, Result):
            res = execval.val
        else:
            raise Exception(f"expected result, got {execval}")
    elif isinstance(arg, Arg):
        res = expand(state, arg.value, skip_empty=skip_empty)
    elif isinstance(arg, list):
        res = []
        for item in arg:
            val = expand(state, item, skip_empty=skip_empty)
            for v in iter_var(val, skip_empty=skip_empty):
                res.append(v)
    else:
        raise Exception(f"could not expand arg: {arg}")

    validate(res)
    return res


def expand_lol(state: State, arg: tuple):
    """Make string from some type of an argument"""

    if isinstance(arg, tuple) and len(arg) and arg[0] == Node.LOL:
        res = []
        for lol_list in arg[1:]:
            if lol_list:
                res.append(expand(state, lol_list))
    elif isinstance(arg, list):
        res = [[expand(state, item) for item in arg]]
    else:
        raise Exception(f"could not expand LOL: {arg}")

    validate_lol(res)
    return res


def re_expand(state: State, string: str, params: list):
    def exp(m: re.Match[str]) -> str:
        expanded = var_expand(m.string[m.start() : m.end()], params, state.vars)
        return " ".join(expanded)

    return re.sub(r"\$\([^\(]+\)", exp, string)
