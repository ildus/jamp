import argparse
import os
import subprocess as sp

from jamp import executors
from jamp.classes import State, Target
from jamp.paths import check_vms, escape_path


def parse_args():
    parser = argparse.ArgumentParser(
        prog="jamp",
        description="Jam Build System (Python version)",
    )
    parser.add_argument("-b", "--build", action="store_true", help="call ninja")
    parser.add_argument("-v", "--verbose", action="store_true", help="verbose output")
    parser.add_argument(
        "-d",
        "--debug",
        default=[],
        choices=["headers", "depends", "include", "env"],
        help="show headers",
        nargs="+",
    )
    parser.add_argument(
        "-t", "--target", default=None, help="limit target for debug info"
    )
    parser.add_argument(
        "-f", "--jamfile", default="Jamfile", help="--specify jam file name"
    )
    parser.add_argument(
        "-s", "--env", action="append", help="--specify extra env variables"
    )
    args = parser.parse_args()
    return args


def main_cli():
    """Command line entrypoint"""

    curdir = os.path.abspath(os.getcwd())
    basedir = os.path.dirname(__file__)
    jambase = os.path.join(basedir, "Jambase")
    args = parse_args()

    state = State(
        verbose=args.verbose,
        debug_headers="headers" in args.debug,
        debug_deps="depends" in args.debug,
        debug_include="include" in args.debug,
        debug_env="env" in args.debug,
        target=args.target,
    )
    jamfile = args.jamfile
    state.vars.set("JAMFILE", [jamfile])
    state.vars.set("NINJA_ROOTDIR", [curdir])

    for var in args.env or ():
        parts = var.split("=")
        state.vars.set(parts[0], [parts[1]])

    if not os.path.exists(jamfile):
        print("Jamfile not found")
        exit(1)

    with open(jambase) as f:
        jambase_contents = f.read()

    if args.verbose:
        print("...parsing jam files...")

    cmds = state.parse_and_compile(jambase_contents)

    if args.verbose:
        print("...execution...")

    executors.run(state, cmds)
    if args.verbose:
        print("...binding targets and searching headers...")

    executors.bind_targets(state)

    print(f"...found {len(state.targets)} target(s)...")
    if args.verbose:
        print("...writing build.ninja...")

    with open("build.ninja", "w") as f:
        ninja_build(state, f)

    if args.build:
        sp.run(["ninja"])


def ninja_build(state: State, output):
    """Write ninja.build"""

    from jamp.ninja_syntax import Writer

    writer = Writer(output, width=120)

    target: Target = None

    counter = 0
    for step in state.build_steps:
        upd_action = step[1]
        upd_action.name = f"{upd_action.action.name}{counter}".replace("+", "_")
        counter += 1

        full_cmd = upd_action.get_command(state)
        if check_vms():
            fn = f"{upd_action.name}.com"

            writer.rule(
                upd_action.name,
                command=f"@{fn}",
                description=upd_action.description(),
                rspfile=fn,
                rspfile_content=full_cmd,
                restat=upd_action.restat,
                generator=upd_action.generator,
            )
        else:
            writer.rule(
                upd_action.name,
                full_cmd,
                restat=upd_action.restat,
                generator=upd_action.generator,
            )

    phonies = {}
    for target in state.targets.values():
        deps = (escape_path(i) for i in target.get_dependency_list(state))
        if target.notfile:
            writer.build(target.name, "phony", implicit=deps)
            phonies[target.name] = True

    for target in state.targets.values():
        if target.collection is not None:
            if target.collection_name() in phonies:
                continue

            deps = (escape_path(i) for i in target.collection)
            writer.build(target.collection_name(), "phony", implicit=deps)
            phonies[target.collection_name()] = True

    for step in state.build_steps:
        all_deps = set()
        outputs = set()
        targets, upd_action = step

        for target in targets:
            if target.boundname:
                outputs.add(target.boundname)

        for target in targets:
            deps = target.get_dependency_list(state, outputs=outputs)
            all_deps.update(deps)

        if outputs:
            inputs = set(
                [
                    escape_path(source.boundname or source.name)
                    for source in upd_action.sources
                ]
            )
            res_deps = (
                dep for dep in all_deps if dep not in inputs and dep not in outputs
            )

            writer.build(
                (escape_path(i) for i in outputs),
                upd_action.name,
                inputs,
                implicit=res_deps,
            )
