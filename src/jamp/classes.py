import os
from typing import List, Union, Set
from functools import cache

from jamp.paths import Pathname, check_vms, check_windows
from jamp.headers import target_find_headers, skip_include

PATH_VARS = set(
    ["PATH", "LD_LIBRARY_PATH", "PKG_CONFIG_PATH", "CLASSPATH", "PYTHONPATH"]
)


def is_subdir(path: str, potential_subdir: str):
    # Normalize paths to handle different path structures
    norm_path = os.path.normpath(path).replace(os.sep, "/")
    norm_subdir = os.path.normpath(potential_subdir).replace(os.sep, "/")
    return norm_subdir.startswith(norm_path)


def remove_overlapping(dirs: List):
    # Sort dirs by length in descending order
    dirs_sorted = sorted(dirs, key=len, reverse=True)

    result = []

    for dry in dirs_sorted:
        # Check if dir is not a subdirectory of any existing directory in result
        if not any(is_subdir(d, dry) for d in result):
            result.append(dry)

    return result


class State:
    def __init__(
        self,
        verbose=False,
        debug_headers=False,
        debug_deps=False,
        debug_include=False,
        debug_env=False,
        target=None,
        unwrap_phony=None,
    ):
        self.headers_complained = False
        self.verbose = verbose
        self.vars = Vars(debug_env=debug_env)
        self.rules = {}
        self.actions = {}
        self.targets = {}
        self.current_rule = None
        self.params = None
        self.always_build = set()
        self.build_steps = []
        self.debug_headers = debug_headers
        self.debug_deps = debug_deps
        self.debug_include = debug_include
        self.limit_target = target
        self.unwrap_phony = unwrap_phony

        # reverse location->target map
        self.target_locations = {}

        # skipped from scanning headers, just a cache
        self.scan_skipped = set()

    @cache
    def sub_root(self):
        sub_root = self.vars.get("SUBDIR_ROOT")
        if not sub_root:
            sub_root = self.vars.get("NINJA_ROOTDIR")

        if self.verbose:
            print(f"source root: {sub_root}")

        return sub_root

    def parse_and_compile(self, contents: str, filename=None):
        from jamp.jam_syntax import parse
        from jamp.compile import compile

        ast = parse(contents, filename=filename)
        cmds = compile(self, ast)
        return cmds

    def get_target(self, name):
        return self.targets[name]

    def add_action_for_target(
        self, target, action_name, generator=False, sources=None, params=None
    ):
        sources = sources or []
        params = params or []
        action = self.actions[action_name]
        upd_action = UpdatingAction(action, sources, params)
        upd_action.targets = [target]
        upd_action.generator = generator

        if target.build_step is None:
            step = ([target], upd_action)
            self.build_steps.append(step)
            target.build_step = step
        else:
            prev_upd_action = target.build_step[1]
            prev_upd_action.link(upd_action)

        return upd_action

    def finish_steps(self):
        target = Target.bind(self, "dirs")

        if target.collected_dirs:
            dirs = remove_overlapping(target.collected_dirs)

            for dry in dirs:
                dir_target = Target.bind(self, dry)
                dir_target.boundname = dry
                dir_target.is_dir = True

                self.add_action_for_target(
                    dir_target,
                    "MkDirWhenNotExists",
                    generator=True,
                    params=[dry, target.boundname],
                )
                target.depends.add(dir_target)


class Vars:
    delete_vars = ["LS_COLORS", "GITHUB_TOKEN"]

    def __init__(self, debug_env=False):
        self.debug_env = debug_env
        self.scopes = []
        self.scope = {}
        self.global_scope = self.scope
        self.set_basic_vars()

        # setting current targets will force to using target variables
        self.current_context = []

    def split_path(self, val):
        return val.split(os.path.pathsep)

    def set_basic_vars(self):
        import os
        import platform

        if check_windows():
            import nt
            self.scope.update(nt.environ.copy())
        else:
            self.scope.update(os.environ.copy())

        for v in self.delete_vars:
            if v in self.scope:
                del self.scope[v]

        match platform.system():
            case "Linux" | "Solaris" | "AIX" | "Darwin":
                self.scope["UNIX"] = "1"
            case "OpenVMS":
                self.scope["VMS"] = "1"
            case "Windows":
                self.scope["NT"] = "1"

        self.scope["OSPLAT"] = platform.machine()
        self.scope["OS"] = platform.system().upper()
        self.scope["JAMUNAME"] = platform.uname()
        self.scope["JAMVERSION"] = "2.6.1"

        for k, v in self.scope.items():
            if k in PATH_VARS:
                self.scope[k] = self.split_path(v)

        if self.debug_env:
            for key, val in self.scope.items():
                print(f"{key}={val}")

    def __repr__(self):
        return f"current scope: {self.scope}\nscopes: {self.scopes}"

    def set(self, name: str, value: str | None):
        if not isinstance(name, str):
            raise Exception(f"vars_set: expected str value for key name: got {name}")

        if not isinstance(value, list):
            raise Exception("vars_set: expected list for value")

        if isinstance(value, list) and len(value) and isinstance(value[0], list):
            raise Exception(f"can't store LOL as value for {name}: got {value}")

        if name in self.scope:
            # something local
            self.scope[name] = value
        else:
            # check in upper levels
            for level in reversed(self.scopes):
                if name in level:
                    level[name] = value
                    return

            # not defined, goes to global
            self.global_scope[name] = value

    def get_scope(self, name: str):
        if not isinstance(name, str):
            raise Exception(
                f"vars_get_scope: expected str value for key name: got {name}"
            )

        res_scope = None

        if name in self.scope:
            # something local
            res_scope = self.scope
        else:
            # check in upper levels
            for level in reversed(self.scopes):
                if name in level:
                    res_scope = level
                    break

            # not defined, check global
            if res_scope is None and name in self.global_scope:
                return self.global_scope

        # probably value in symbols, but not read, so read it and set in the current scope
        if res_scope is None:
            value = self.check_vms_symbol(name)
            if value is not None:
                res_scope = self.global_scope

        return res_scope

    def check_vms_symbol(self, name):
        if check_vms():
            import vms.lib

            status, val = vms.lib.get_symbol(name)
            if status == 1:
                self.global_scope[name] = [val]
                if self.debug_env:
                    print(f"{name}={val}")

                return [val]

    def set_local(self, name: str, value: str | None):
        value = value if value is not None else []
        self.scope[name] = value

    def get(self, name: str, on_target=None):
        if not isinstance(name, str):
            raise Exception(f"vars_get: expected str value for key name: got {name}")

        if on_target:
            self.current_context.append(on_target.vars)

        res = None
        if self.current_context:
            for ctx in reversed(self.current_context):
                if name in ctx:
                    res = ctx.get(name)
                    break

        if on_target:
            self.current_context.pop()

        if res is None:
            if name in self.scope:
                res = self.scope.get(name)
            else:
                for level in reversed(self.scopes):
                    if name in level:
                        res = level.get(name)
                        break

        if res is None:
            val = self.check_vms_symbol(name)
            if val is not None:
                return val

        return res if res else []

    def push(self):
        self.scopes.append(self.scope)
        self.scope = {}

    def pop(self):
        self.scope = self.scopes.pop()


class Rule:
    def __init__(self, name: str, params, commands):
        self.name = name
        self.params = params
        self.commands = commands

    def execute(self, state: State):
        from jamp.executors import run

        run(state, self.commands)

    def __repr__(self):
        return f"Rule {self.name}"


class Actions:
    def __init__(self, name: str, flags=None, bindlist=None, commands=None):
        self.name = name
        self.flags = flags
        self.bindlist = bindlist
        self.commands = commands

    def __repr__(self):
        return f"Actions {self.name}"


class Exec:
    """Just a wrapper for function and arguments"""

    def __init__(self, func, args):
        self.func = func
        self.args = args

    def execute(self, state):
        return self.func(state, *self.args)

    def __repr__(self):
        return f"F:{self.func.__name__}"


class UnderTarget:
    def __init__(self, state: State, target):
        self.state = state
        self.target = target

    def __enter__(self):
        self.state.vars.current_context.append(self.target.vars)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.state.vars.current_context.pop()
        return True


class Target:
    existing_paths = {}

    @classmethod
    def bind(cls, state: State, name: str, notfile=False):
        if name in state.targets:
            return state.targets[name]

        target = Target(name, notfile=notfile)
        state.targets[name] = target
        return target

    def overlay(self, state: State):
        return UnderTarget(state, self)

    def is_order_only(self):
        return self.is_output and self.is_header

    def check_if_dir(self):
        if self.is_dir:
            return True

        if self.boundname and check_vms() and self.boundname.endswith("]"):
            return True

        return False

    def __init__(self, name: str, notfile=False):
        self.name: str = name
        self.depends: Set[Target] = set()
        self.includes: Set[Target] = set()
        self.boundname: Union[None, str] = None
        self.updating_actions: List[UpdatingAction] = []
        self.build_step: tuple = None

        # Created my MkDir rule
        self.is_dir = False

        # The suffix was checked and set to True if it's header
        self.is_header = False

        # This target used somewhere as an output
        self.is_output = False

        # True if this is the main 'dirs' target
        self.is_dirs_target = False

        # for mkdir
        self.collected_dirs = None

        # Force generator option to ninja
        self.generated = False

        # Force restat option to ninja
        self.restat = False

        # collection is optimization, if this target is include and it depends on other
        # files just create a phony target with this target and all others
        self.collection = None

        # Dependencies cache after get_dependency_list call without outputs
        self.deps = None

        # Target level variables (ON <target> calls and etc)
        self.vars = {}

        # Temporary rule called on this target
        self.temporary = False

        # NotFile rule called on this target
        self.notfile = notfile  # phony

        # Found headers
        self.headers = None

        # Circular search
        self.circular_visited = False

        # NoCare rule
        self.nocare = False

        # NoUpdate rule
        self.noupdate = False

    def collection_name(self):
        t = self.name

        if check_vms() or check_windows():
            # : is a special escape for VMS paths
            # for Windows - disk drives (C:)
            t = self.name.replace(":", "_").lower()

        return f"_{t}_"

    def get_dependency_list(self, state: State, level=0, outputs=None):
        ''' Ninja level dependency list '''

        implicit, order_only = set(), set()
        use_cached = outputs is None or len(outputs) == 1

        if level == 10:
            # do not go too deep for includes
            return (implicit, order_only)

        if use_cached and self.deps:
            return self.deps

        for t in self.depends:
            depval = None

            if t.notfile:
                if state.unwrap_phony and t.name in state.unwrap_phony:
                    phony_deps_impl, phony_deps_order = t.get_dependency_list(state)
                    implicit |= phony_deps_impl
                    order_only |= phony_deps_order
                else:
                    depval = t.name
            elif t.boundname:
                if not self.is_dirs_target and t.check_if_dir():
                    implicit.add("dirs")
                    continue

                depval = t.boundname
            elif t.nocare:
                continue

            if depval:
                if outputs is not None and depval in outputs:
                    continue
                elif t.noupdate:
                    order_only.add(depval)
                else:
                    implicit.add(depval)

        if not self.notfile:
            for t in self.includes:
                if use_cached and t.collection is not None:
                    implicit.add(t.collection_name())
                    continue

                depval = None
                if t.notfile:
                    depval = t.name
                elif t.boundname and t.boundname in state.target_locations:
                    depval = t.boundname
                #elif t.boundname and os.path.isfile(t.boundname):
                #    depval = t.boundname
                elif t.nocare:
                    continue

                if depval is None:
                    continue

                if outputs and depval in outputs:
                    continue

                if len(t.depends) or len(t.includes):
                    inner_deps_impl, inner_deps_order = t.get_dependency_list(
                        state, level=level + 1, outputs=outputs
                    )

                    if not use_cached:
                        implicit |= inner_deps_impl
                        order_only |= inner_deps_order
                    elif len(inner_deps_impl) or len(inner_deps_order):
                        t.collection = (set((depval,)) | inner_deps_impl, set(inner_deps_order))
                        depval = t.collection_name()

                if t.noupdate:
                    order_only.add(depval)
                else:
                    implicit.add(depval)

            # collect dependencies from sources which are not built
            for dep in self.depends:
                if dep.notfile:
                    continue
                elif dep.build_step is None:
                    built_deps_impl, built_deps_order = dep.get_dependency_list(state, outputs=outputs)
                    implicit |= built_deps_impl
                    order_only |= built_deps_order

        if state.debug_deps:
            if state.limit_target is not None:
                if state.limit_target in self.name:
                    print(self.name, implicit, order_only)
            else:
                print(self.name, implicit, order_only)

        if not use_cached:
            return (implicit, order_only)

        self.deps = (frozenset(implicit), frozenset(order_only))
        return self.deps

    def find_headers(self, state: State, level=0, db=None):
        if level == 10:
            # do not go too deep in searching
            return

        if self.is_output:
            # do not scan output targets
            # if file was already built, then we scan it, and remove that file
            # ninja could fail
            return

        if self.headers is not None:
            # do not search more than one time no each target
            return

        self.headers = []
        found = target_find_headers(state, self, db=db)

        if found:
            for inc in self.includes:
                if skip_include(state, inc.boundname):
                    continue

                inc.find_headers(state, level=level + 1, db=db)

    def bind_location(self, state: State, strict=False):
        """Returns a target if was found the a same location"""

        if not self.boundname:
            self.boundname = self.search(state, strict=strict)

        if self.boundname:
            if self.boundname in state.target_locations:
                return state.target_locations[self.boundname]

            state.target_locations[self.boundname] = self

        if self.is_order_only():
            gen_headers = state.targets.get("_gen_headers")
            if gen_headers:
                gen_headers.depends.add(self)

    def search(self, state: State, strict=False):
        """
        Using SEARCH and TARGET variables on the target try to construct
        the full name.
        Or just return the name of the target if strict is not True
        'strict' argument is used for headers when we need something more correct than
        just a name.
        """

        if self.notfile:
            return None

        if not self.name:
            return None

        path = Pathname()
        path.parse(self.name)

        # remember if it's header
        self.is_header = path.suffix in (".h", ".hpp", ".hh")

        if path.member:
            return None

        # remove the grist part in the filename
        path.grist = ""

        locate = state.vars.get("LOCATE", on_target=self)

        if locate:
            locate_dir = locate[0]
            path.root = locate_dir
            res_path = path.build(binding=True)

            return res_path
        else:
            search = state.vars.get("SEARCH", on_target=self)
            for search_dir in search:
                locate_dir = search_dir
                path.root = locate_dir
                res_path = path.build(binding=True)

                if res_path in state.target_locations:
                    # this could be a generated file, and if it's in targets just return that path
                    return res_path
                elif os.path.exists(res_path):
                    return res_path

        # recreate
        path = Pathname()
        path.parse(self.name)
        path.grist = ""
        res_path = path.build(binding=True)

        if strict and os.path.exists(res_path):
            return res_path

        return res_path if not strict else None

    def add_depends(self, state: State, targets: list):
        for target in targets:
            if isinstance(target, str):
                target = Target.bind(state, target)

            if target == self:
                continue

            self.depends.add(target)

    def add_includes(self, state: State, targets: list):
        for target in targets:
            if isinstance(target, str):
                target = Target.bind(state, target)

            if target == self:
                continue

            self.includes.add(target)

    def search_for_cycles(self, verbose=False, graph=None):
        try:
            import networkx
        except ImportError:
            print("!!! install `networkx` package to fix circular dependency errors")
            return

        if self.circular_visited:
            return

        self.circular_visited = True

        top = False
        if graph is None:
            top = True
            graph = networkx.DiGraph()

        for inc in self.includes:
            graph.add_edge(self, inc)
            inc.search_for_cycles(graph=graph)

        for dep in self.depends:
            dep.search_for_cycles(graph=graph)

        if top:
            for cycle in networkx.simple_cycles(graph):
                if verbose:
                    print(f"removed circular dependency: {cycle[0]} from {cycle[-1]}")

                try:
                    cycle[-1].includes.remove(cycle[0])
                except KeyError:
                    pass

    def __hash__(self):
        return hash(self.name)

    def __repr__(self):
        return f"T:{self.name}"


class UpdatingAction:
    # using undocumented ^T as a delimiter, it worked in Windows 2022
    # if stops working need to use something like " ( cmd ) & ( second cmd) "
    windows_cmd_join = " ^T $\n"

    def __init__(self, action: Actions, sources: list, params: list):
        self.action = action
        self.sources = sources
        self.base = None
        self.next: List[UpdatingAction] = []
        self.params = params
        self.targets = []
        self.command = None
        self.restat = False
        self.generator = False
        self.depfile = None

        # for actions .. bind
        self.bindvars = None
        self.bindparams = None

    def link(self, upd_action):
        self.next.append(upd_action)
        upd_action.base = self

    def bound_params(self):
        res = []
        if self.targets:
            res.append([target.boundname for target in self.targets])
        else:
            res.append([])

        res.append([source.boundname for source in self.sources if source.boundname])
        res += self.params
        return res

    def description(self):
        names = set([self.action.name])
        for n in self.next:
            names.add(n.action.name)

        return " & ".join(names) + " $out"

    def modify_vms_paths(self, state):
        """If path doesn't have directory, make it current"""

        if not self.bindparams:
            return

        for var, value in self.bindparams.items():
            modified = []
            for item in value:
                has_dir = ":" in item or "[" in item
                if has_dir:
                    modified.append(item)
                else:
                    modified.append("[]" + item)

            self.bindparams[var] = modified

    def is_alone(self):
        return not (bool(self.next) or bool(self.base))

    def prepare_lines(self, state, comment_sym="#"):
        from jamp.expand import var_string

        saved_context = state.vars.current_context
        state.vars.current_context = []
        for t in self.targets:
            state.vars.current_context.append(t.vars)

        if self.bindparams:
            state.vars.current_context.append(self.bindparams)

        lines = self.action.commands

        for line in lines.split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith(comment_sym):
                continue

            line = var_string(
                line,
                self.bound_params(),
                state.vars,
                alone=self.is_alone(),
            )
            line = line.replace("$", "$$")
            line = line.replace("<NINJA_SIGIL>", "$")

            if not line:
                continue

            yield line

        state.vars.current_context = saved_context

    def prepare_action(self, state: State):
        quotes = []
        concat = ""

        start_new_command = False
        for line in self.prepare_lines(state):
            if start_new_command:
                concat += " ; $\n "

            start_new_command = False

            # watch for open quotes
            for c in line:
                if c in ["'", '"', "`"]:
                    if quotes and quotes[-1] == c:
                        quotes.pop()
                    else:
                        # a new quote started
                        quotes.append(c)

            if line.endswith("\\"):
                concat += line[:-1]
            elif line.endswith("&&"):
                concat += line + " "
            elif line.endswith(";"):
                concat += line + " "
            elif line.endswith("("):
                concat += line + " "
            elif line.endswith("|"):
                concat += line + " "
            elif line == "then" or line.endswith(" then"):
                concat += line + " "
            elif line == "do" or line.endswith(" do"):
                concat += line + " "
            elif line == "else" or line.endswith(" else"):
                concat += line + " "
            elif len(quotes):
                concat += line + " "
            else:
                concat += line
                start_new_command = True

        return concat, True

    def prepare_windows_action(self, state: State):
        """not tested"""
        quotes = []
        concat = ""

        start_new_command = False

        for line in self.prepare_lines(state, comment_sym="REM"):
            if start_new_command:
                concat += self.windows_cmd_join

            start_new_command = False

            # watch for open quotes
            for c in line:
                if c in ["'", '"']:
                    if quotes and quotes[-1] == c:
                        quotes.pop()
                    else:
                        # a new quote started
                        quotes.append(c)

            if line.endswith("^"):
                concat += line[:-1]
            elif len(quotes):
                concat += line
            else:
                concat += line
                start_new_command = True

        return concat, False

    def prepare_vms_action(self, state: State):
        quotes = []
        concat = "$$ "

        oneliner = True
        add_newline = False
        for line in self.prepare_lines(state, comment_sym="!"):
            # watch for open quotes
            if add_newline:
                oneliner = False
                concat += " $\n$^$$"

            add_newline = False
            for c in line:
                if c in ['"']:
                    if quotes and quotes[-1] == c:
                        quotes.pop()
                    else:
                        # a new quote started
                        quotes.append(c)

            if line.endswith("-"):
                concat += line[:-1]
            elif len(quotes):
                concat += line + " "
            else:
                # $^ is a hack to samurai (github.com/ildus/samurai)
                # which adds a proper newline in a script
                concat += line
                add_newline = True

        return concat, oneliner

    def process_bind_vars(self, state):
        """Set actual boundnames for BIND params in actions"""

        if self.bindparams:
            return

        if not self.bindvars:
            return

        bindparams = {}

        for target in self.targets:
            for var in self.bindvars:
                bind_values = state.vars.get(var, on_target=target)
                if not bind_values:
                    continue

                res = []
                for val in bind_values:
                    bindtarget = Target.bind(state, val)
                    if bindtarget.boundname:
                        bindtarget.bind_location(state)

                    # if bind was successfull
                    if bindtarget.boundname:
                        res.append(bindtarget.boundname)

                if res:
                    bindparams[var] = res

        if bindparams:
            self.bindparams = bindparams

            if check_vms():
                self.modify_vms_paths(state)

    def get_command(self, state: State, force_vms=False, force_windows=False):
        self.process_bind_vars(state)

        still_oneliner = True

        if not self.command:
            if force_vms or check_vms():
                base_lines, oneliner = self.prepare_vms_action(state)
            elif force_windows or check_windows():
                base_lines, oneliner = self.prepare_windows_action(state)
            else:
                base_lines, oneliner = self.prepare_action(state)

            if not oneliner:
                still_oneliner = False

            if self.next:
                still_oneliner = False

                for next_upd_action in self.next:
                    lines, _ = next_upd_action.get_command(state)
                    if check_vms():
                        base_lines += "$\n$^" + lines
                    elif check_windows():
                        base_lines += self.windows_cmd_join + lines
                    else:
                        base_lines += " ; $\n" + lines

            if check_vms():
                # just an empty line at the end
                base_lines += "$\n$^$$"

            self.command = base_lines

        return self.command, still_oneliner
