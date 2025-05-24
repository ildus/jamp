import argparse
import os
import sys
import subprocess as sp

from collections import OrderedDict

from jamp import executors, headers
from jamp.classes import State, Target, UpdatingAction
from jamp.paths import check_vms, escape_path, add_paths, check_windows


def parse_args(skip_args=False):
    parser = argparse.ArgumentParser(
        prog="jamp",
        description="Jam Build System (Python version)",
    )
    parser.add_argument("-b", "--build", action="store_true", help="call ninja")
    parser.add_argument("-v", "--verbose", action="store_true", help="verbose output")
    parser.add_argument("--profile", action="store_true", help="profile the execution")
    parser.add_argument(
        "--depfiles",
        action="store_true",
        help="use depfile feature of ninja (only Unix)",
    )
    parser.add_argument(
        "--no-headers-cache", action="store_true", help="do not cache found headers"
    )
    parser.add_argument(
        "-s",
        "--search-type",
        default="base",
        choices=["base", "ripgrep", "grep", "none"],
        help="headers search type (default is basic jam algorithm)",
    )
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
        "--unwrap-phony",
        default=[],
        help=(
            "unwrap specified phony targets in deps (useful for debug, "
            "to find exact triggering input)"
        ),
        nargs="+",
    )
    parser.add_argument(
        "-f", "--jamfile", default="Jamfile", help="--specify jam file name"
    )
    parser.add_argument(
        "-e", "--env", action="append", help="--specify extra env variables"
    )
    args = parser.parse_args(args=[] if skip_args else None)
    return args


def main_app(args):
    """Main entrypoint"""

    curdir = os.path.abspath(os.getcwd())
    basedir = os.path.dirname(__file__)
    jambase = os.path.join(basedir, "Jambase")

    state = State(
        verbose=args.verbose,
        debug_headers="headers" in args.debug,
        debug_deps="depends" in args.debug,
        debug_include="include" in args.debug,
        debug_env="env" in args.debug,
        target=args.target,
        unwrap_phony=args.unwrap_phony,
    )
    jamfile = args.jamfile

    state.vars.set("JAMFILE", [jamfile])
    state.vars.set("JAMP_PYTHON", [sys.executable])
    state.vars.set("JAMP_OPTIONS", sys.argv[1:])
    state.vars.set("NINJA_ROOTDIR", [curdir])

    if args.depfiles:
        state.vars.set("ENABLE_DEPFILES", ["1"])

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

    if not args.no_headers_cache:
        headers.load_headers_cache()

    executors.bind_targets(state, search_headers=args.search_type)

    if not args.no_headers_cache:
        headers.save_headers_cache()

    all_target = Target.bind(state, "all")
    all_target.search_for_cycles(verbose=args.verbose)

    state.finish_steps()

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
    commands_cache = {}

    for step in state.build_steps:
        upd_action: UpdatingAction = step[1]
        upd_action.name = f"{upd_action.action.name}{counter}".replace("+", "_")
        counter += 1

        full_cmd, oneliner = upd_action.get_command(state)

        # an optimization for simple rules with one command
        # group similar rules to one
        if upd_action.is_alone():
            found = False
            key = upd_action.action.name

            if key in commands_cache:
                saved = commands_cache[key]

                for name, cached_cmd in saved:
                    if full_cmd == cached_cmd:
                        # no need to create a new rule, we have similar
                        upd_action.name = name
                        found = True
                        break

                if found:
                    continue

            else:
                saved = commands_cache.setdefault(key, [])

            saved.append((upd_action.name, full_cmd))

        if not oneliner and check_windows():
            resp_fn = f"{upd_action.name}$step.bat"

            writer.rule(
                upd_action.name,
                command=f"cmd /C {resp_fn}",
                description=upd_action.description(),
                rspfile=resp_fn,
                rspfile_content=full_cmd,
                restat=upd_action.restat,
                generator=upd_action.generator,
            )
        elif not oneliner and check_vms():
            # rule can be reused from saved, need the unique number for the resp file name
            resp_fn = f"{upd_action.name}$step.com"

            writer.rule(
                upd_action.name,
                command=f"@{resp_fn}",
                description=upd_action.description(),
                rspfile=resp_fn,
                rspfile_content=full_cmd,
                restat=upd_action.restat,
                generator=upd_action.generator,
            )
        else:
            # set depfile if needed
            for t in upd_action.targets:
                depfile = t.vars.get("DEPFILE")
                if depfile:
                    upd_action.depfile = depfile
                    break

            writer.rule(
                upd_action.name,
                full_cmd,
                restat=upd_action.restat,
                generator=upd_action.generator,
                depfile=upd_action.depfile,
                description=upd_action.description(),
            )

    phonies = {}
    gen_headers = {}

    for dep in state.targets["_gen_headers"].depends:
        if dep.boundname:
            gen_headers[dep.boundname] = None

    for target in state.targets.values():
        implicit, order_only = (escape_path(i) for i in target.get_dependency_list(state))
        if target.notfile:
            kwargs = {}
            if target.is_dirs_target:
                kwargs["order_only"] = (implicit | order_only)
            else:
                kwargs["order_only"] = order_only
                kwargs["implicit"] = implicit

            writer.build(target.name, "phony", **kwargs)
            phonies[target.name] = True

    for target in state.targets.values():
        if target.collection is not None:
            if target.collection_name() in phonies:
                continue

            implicit_deps = (escape_path(i) for i in target.collection[0])
            order_only_deps = (escape_path(i) for i in target.collection[1])
            writer.build(target.collection_name(), "phony", implicit=implicit_deps,
                         order_only=order_only_deps)
            phonies[target.collection_name()] = True

    for stepnum, step in enumerate(state.build_steps):
        outputs = OrderedDict()
        targets, upd_action = step

        for target in targets:
            if not target.boundname:
                continue

            outputs[target.boundname] = None

        if len(outputs) == 0:
            continue

        all_implicit = set()
        all_order_only = set()

        for target in targets:
            implicit, order_only = target.get_dependency_list(state, outputs=outputs)
            add_paths(all_implicit, implicit)
            add_paths(all_order_only, order_only)

        inputs = OrderedDict()

        for source in upd_action.sources:
            inputs[escape_path(source.boundname or source.name)] = None

        res_implicit = set()
        res_order_only = set()

        for dep in all_implicit:
            if dep in inputs:
                continue

            if dep in gen_headers:
                res_order_only.add(dep)
            else:
                res_implicit.add(dep)

        for dep in all_order_only:
            if dep in inputs:
                continue

            res_order_only.add(dep)

        variables = None

        if check_vms() or check_windows():
            variables = {"step": stepnum}

        writer.build(
            (escape_path(i) for i in outputs.keys()),
            upd_action.name,
            inputs.keys(),
            implicit=res_implicit,
            order_only=res_order_only,
            variables=variables,
        )

    writer.default("all")


def main_cli(skip_args=False):
    """Command line entrypoint"""

    args = parse_args(skip_args=skip_args)
    if args.profile:
        import cProfile

        ctx = {"args": args, "main_app": main_app}
        cProfile.runctx("main_app(args)", ctx, {})
    else:
        try:
            main_app(args)
        except KeyboardInterrupt:
            print("jamp: interrupted")
