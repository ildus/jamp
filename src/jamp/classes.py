import os
from typing import List, Union
from functools import cache

from jamp.paths import Pathname, check_vms, check_windows
from jamp.headers import target_find_headers, skip_include

PATH_VARS = set(
    ["PATH", "LD_LIBRARY_PATH", "PKG_CONFIG_PATH", "CLASSPATH", "PYTHONPATH"]
)


class State:
    def __init__(
        self,
        verbose=False,
        debug_headers=False,
        debug_deps=False,
        debug_include=False,
        debug_env=False,
        target=None,
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

    @cache
    def is_dir(self, n):
        if check_vms() and n.endswith("]"):
            return True

        if os.path.isdir(n):
            return True

        t = self.targets.get(n)
        return t and t.is_dir


class Vars:
    delete_vars = ["LS_COLORS", "GITHUB_TOKEN"]

    def __init__(self, debug_env=False):
        self.debug_env = debug_env
        self.scopes = []
        self.scope = {}
        self.global_scope = self.scope
        self.set_basic_vars()

        # setting current targets will force to using target variables
        self.current_target = []

    def split_path(self, val):
        return val.split(os.path.pathsep)

    def set_basic_vars(self):
        import os
        import platform

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
        self.scope["JAMVERSION"] = "2.5.5"

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
            self.current_target.append(on_target)

        res = None
        if self.current_target:
            for t in reversed(self.current_target):
                if name in t.vars:
                    res = t.vars.get(name)
                    break

        if on_target:
            self.current_target.pop()

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
        from executors import run

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
        self.state.vars.current_target.append(self.target)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.state.vars.current_target.pop()
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

    def __init__(self, name: str, notfile=False):
        self.name = name
        self.depends = set()
        self.includes = set()
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

        # Force generator option to ninja
        self.generated = False

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

    def collection_name(self):
        t = self.name

        if check_vms():
            # : is a special escape for VMS paths
            t = self.name.replace(":", "_").lower()

        return f"_{t}_"

    def get_dependency_list(self, state: State, level=0, outputs=None):
        res = set()
        use_cached = outputs is None or len(outputs) == 1

        if level == 10:
            # do not go too deep for includes
            return res

        if use_cached and self.deps:
            return self.deps

        for t in self.depends:
            depval = None
            if t.notfile:
                depval = t.name
            elif t.boundname:
                if not self.is_dirs_target and state.is_dir(t.boundname):
                    res.add("dirs")
                    continue

                depval = t.boundname

            if depval and outputs is not None and depval in outputs:
                continue
            elif depval:
                res.add(depval)

        if not self.notfile:
            for t in self.includes:
                if use_cached and t.collection is not None:
                    res.add(t.collection_name())
                    continue

                depval = None
                if t.notfile:
                    depval = t.name
                elif t.boundname and t.boundname in state.target_locations:
                    depval = t.boundname
                elif t.boundname and os.path.isfile(t.boundname):
                    depval = t.boundname

                if depval is None:
                    continue

                if outputs and depval in outputs:
                    continue

                if len(t.depends) or len(t.includes):
                    inner_deps = t.get_dependency_list(
                        state, level=level + 1, outputs=outputs
                    )

                    if not use_cached:
                        res |= inner_deps
                    elif len(inner_deps):
                        t.collection = set((depval,))
                        t.collection |= t.get_dependency_list(
                            state, level=level + 1, outputs=outputs
                        )
                        depval = t.collection_name()

                res.add(depval)

            # collect dependencies from sources which not built
            for dep in self.depends:
                if dep.notfile:
                    continue
                elif dep.build_step is None:
                    res |= dep.get_dependency_list(state, outputs=outputs)

        if state.debug_deps:
            if state.limit_target is not None:
                if state.limit_target in self.name:
                    print(self.name, res)
            else:
                print(self.name, res)

        if not use_cached:
            return res

        self.deps = res
        return self.deps

    def find_headers(self, state: State, level=0, db=None):
        if level == 10:
            # do not go too deep in searching
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
        if not self.boundname:
            self.boundname = self.search(state, strict=strict)

            if self.is_output and self.is_header:
                gen_headers = state.targets["_gen_headers"]
                gen_headers.depends.add(self)

        if self.boundname:
            state.target_locations[self.boundname] = self

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
        self.bindvars = None

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
        res += self.params[2:]
        return res

    def description(self):
        names = set([self.action.name])
        for n in self.next:
            names.add(n.action.name)

        targets = " ".join((target.boundname for target in self.targets))
        return " & ".join(names) + " " + targets

    def modify_vms_paths(self, state):
        if not self.bindvars:
            return

        for target in self.targets:
            for var in self.bindvars:
                value = target.vars.get(var)
                if value:
                    modified = []
                    for item in value:
                        has_dir = ":" in item or "[" in item
                        if has_dir:
                            modified.append(item)
                        else:
                            modified.append("[]" + item)

                    target.vars[var] = modified

    def is_alone(self):
        return not (bool(self.next) or bool(self.base))

    def prepare_lines(self, state, comment_sym="#"):
        from jamp.expand import var_string

        lines = self.action.commands

        for line in lines.split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith(comment_sym):
                continue

            old_target = state.vars.current_target
            state.vars.current_target = self.targets
            if check_vms():
                self.modify_vms_paths(state)

            line = var_string(
                line,
                self.bound_params(),
                state.vars,
                alone=self.is_alone(),
            )
            line = line.replace("$", "$$")
            line = line.replace("<NINJA_SIGIL>", "$")
            state.vars.current_target = old_target

            if not line:
                continue

            yield line

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

        return concat

    def prepare_windows_action(self, state: State):
        """not tested"""
        quotes = []
        concat = ""

        add_newline = False
        for line in self.prepare_lines(state, comment_sym="REM"):
            # watch for open quotes
            if add_newline:
                concat += " $\n$^"

            add_newline = False
            for c in line:
                if c in ["'", '"', "`"]:
                    if quotes and quotes[-1] == c:
                        quotes.pop()
                    else:
                        # a new quote started
                        quotes.append(c)

            if line.endswith("^"):
                concat += line[:-1]
            elif len(quotes):
                concat += line + " "
            else:
                # $^ is a hack to samurai (github.com/ildus/samurai)
                # which adds a proper newline in a script
                concat += line
                add_newline = True

        return concat

    def prepare_vms_action(self, state: State):
        quotes = []
        concat = "$$ "

        add_newline = False
        for line in self.prepare_lines(state, comment_sym="!"):
            # watch for open quotes
            if add_newline:
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

        return concat

    def get_command(self, state: State, force_vms=False, force_windows=False):
        if not self.command:
            if force_vms or check_vms():
                base_lines = self.prepare_vms_action(state)
            elif force_windows or check_windows():
                base_lines = self.prepare_windows_action(state)
            else:
                base_lines = self.prepare_action(state)

            if self.next:
                for next_upd_action in self.next:
                    lines = next_upd_action.get_command(state)
                    if check_vms():
                        base_lines += "$\n$^" + lines
                    elif check_windows():
                        base_lines += "$\n$^" + lines
                    else:
                        base_lines += " ; $\n" + lines

            if check_vms():
                # just an empty line at the end
                base_lines += "$\n$^$$"

            self.command = base_lines

        return self.command
