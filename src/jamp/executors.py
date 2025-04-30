import os

from jamp.jam_builtins import (
    Builtins,
    expand,
    expand_lol,
    output,
    flatten,
    iter_var,
    lol_get,
)
from jamp.jam_syntax import Arg, Node
from jamp.classes import Rule, State, Exec, Target, UpdatingAction
from typing import Optional, Union
from jamp.pattern import match

builtins = Builtins()
complained_rules = set()

FLOW_BREAK = 1
FLOW_CONTINUE = 2
FLOW_DEBUG = 3


class Result:
    def __init__(self, val):
        self.val = val


def run(state: State, cmds: Union[list, Exec]) -> Optional[int]:
    """Starting point of tasks execution"""

    if cmds:
        if isinstance(cmds, Exec):
            return cmds.execute(state)

        for ex in cmds:
            ret = ex.execute(state)
            if ret:
                # probably we need to break the execution
                if ret in (FLOW_BREAK, FLOW_CONTINUE):
                    return ret
                elif ret == FLOW_DEBUG:
                    import pdb

                    pdb.set_trace()

                elif isinstance(ret, Result):
                    return ret


def bind_targets(state: State, search_headers="base"):
    """Bind target to actual locations"""

    target: Target = None

    for target in state.targets.values():
        target.bind_location(state)

    db = None
    if search_headers == "ripgrep":
        from jamp.headers import scan_ripgrep_output

        pattern = state.vars.get("HDRPATTERN")
        if pattern:
            db = scan_ripgrep_output(state, pattern[0])
    elif search_headers == "grep":
        from jamp.headers import scan_grep_output

        pattern = state.vars.get("HDRPATTERN")
        if pattern:
            db = scan_grep_output(state, pattern[0])

    if search_headers != "none":
        for target in tuple(state.targets.values()):
            # tuple is because targets dict will change while searching
            if target.boundname:
                target.find_headers(state, db=db)

        # now bind found headers
        for target in state.targets.values():
            target.bind_location(state, strict=True)


class ExecutionError(Exception):
    pass


def check_empty_val(assign_list):
    if assign_list and isinstance(assign_list[0], Arg) and assign_list[0].value == "":
        return True

    return False


def exec_assign(
    state: State, name_arg: Arg, assign_type: str, assign_list=None
) -> None:
    """Assign to a global or local variable"""
    names = expand(state, name_arg)

    for name in names:
        assign = False
        if assign_type == "=":
            # normal assign
            assign = True
        elif assign_type == "?=" or assign_type[0] == "d":
            # if variable is defined here, just skip
            scope = state.vars.get_scope(name)
            if scope is None:
                assign = True
            else:
                val = scope.get(name)
                if not val:
                    assign = True

        elif assign_type == "+=":
            # add to variable
            value = expand(state, assign_list)
            curval = state.vars.get(name)
            if curval:
                state.vars.set(name, list(iter_var(curval)) + list(iter_var(value)))
            else:
                assign = True

        if assign:
            value = expand(state, assign_list, skip_empty=False)
            state.vars.set(name, value)


def exec_assign_on_target(
    state: State, name_arg: Arg, targets, assign_type: str, assign_list
):
    """Bind a variable to specific targets"""
    targets_var = expand(state, targets)

    for target_name in iter_var(targets_var):
        target = Target.bind(state, target_name)

        with target.overlay(state):
            # value should be expanded on target influence
            value = expand(state, assign_list, skip_empty=False)
            target_vars = target.vars

            for varname in expand(state, name_arg):
                if assign_type == "=":
                    target_vars[varname] = value
                elif assign_type == "?=":
                    if varname not in target_vars:
                        target_vars[varname] = value
                elif assign_type == "+=":
                    if varname not in target_vars:
                        target_vars[varname] = value
                    else:
                        curval = flatten(target_vars[varname])
                        if curval:
                            target_vars[varname] = list(iter_var(curval)) + list(
                                iter_var(value)
                            )
                        else:
                            target_vars[varname] = value


def exec_break(state: State, arg) -> int:
    return FLOW_BREAK


def exec_continue(state: State, arg) -> int:
    return FLOW_CONTINUE


def exec_return(state: State, retval) -> Result:
    return Result(expand(state, retval))


def exec_local_assign(state: State, names: Union[Arg, list], assign_list):
    names = expand(state, names)
    value = expand(state, assign_list, skip_empty=False)

    for name in names:
        state.vars.set_local(name, value)


def exec_rule_action(state: State, rule: Rule, action_name: str, params: list):
    targets = lol_get(params, 0)
    source_names = lol_get(params, 1)
    action = state.actions[action_name]

    sources = []
    for source_name in source_names:
        source_t = Target.bind(state, source_name)
        sources.append(source_t)

    bindvars = set()
    if action.bindlist and action.bindlist[1]:
        for arg in action.bindlist[1]:
            bindvars.add(arg.value)

    generated = False
    restat = False
    prev_upd_action = None
    build_targets = []
    linking_targets = []
    for target_name in targets:
        target = Target.bind(state, target_name)
        if target.generated:
            generated = True

        if target.restat:
            restat = True

        if target.build_step is not None:
            # there is a build step for this target, this target goes there
            prev_upd_action = target.build_step[1]
            linking_targets.append(target)
        else:
            build_targets.append(target)

        for var in bindvars:
            bind_names = state.vars.get(var, on_target=target)
            if bind_names:
                for val in bind_names:
                    # just in case create targets if ACTIONS BIND params are set
                    if val:
                        Target.bind(state, val[0])

    if prev_upd_action:
        upd_action = UpdatingAction(action, sources, params)
        upd_action.targets = linking_targets
        upd_action.bindvars = bindvars
        prev_upd_action.link(upd_action)

    if build_targets:
        # one build step, can output several targets
        upd_action = UpdatingAction(action, sources, params)
        upd_action.targets = build_targets
        upd_action.generator = generated
        upd_action.bindvars = bindvars
        upd_action.restat = restat

        step = (build_targets, upd_action)
        for target in build_targets:
            target.build_step = step
            target.is_output = True

        state.build_steps.append(step)


def exec_one_rule(state: State, name: str, params: list):
    builtin = getattr(builtins, name.lower(), None)
    if builtin:
        return builtin(state, params)

    rule: Rule = state.rules.get(name)
    if rule is None:
        if state.current_rule is not None:
            # look like an actions call inside some rule
            if name in state.actions and name != state.current_rule.name:
                # create an updating action for targets
                exec_rule_action(state, state.current_rule, name, params)
                return

        if name != "Clean":
            # we just ignore clean rules, ninja will do cleaning part
            if name not in complained_rules:
                output(f"jamp: unknown rule {name}")
                complained_rules.add(name)

        return

    # create an updating action for actions block with the same name as the rule
    if name in state.actions:
        exec_rule_action(state, rule, name, params)

    # execute rule commands
    old_params = state.params
    old_rule = state.current_rule

    state.current_rule = rule
    state.params = params
    ret = exec_block(state, rule.commands)
    state.params = old_params
    state.current_rule = old_rule

    return ret


def exec_rule(state: State, name: Arg, args):
    names = expand(state, name)
    params = expand_lol(state, args)

    res = []
    for name in names:
        rule_res: Optional[Result] = exec_one_rule(state, name, params)
        if isinstance(rule_res, Result):
            res += rule_res.val
        elif rule_res == FLOW_DEBUG:
            import pdb

            pdb.set_trace()

    if res:
        return Result(res)


def exec_include(state: State, location):
    filenames = expand(state, location)

    for filename in filenames:
        t = Target.bind(state, filename)

        with t.overlay(state):
            t.boundname = t.search(state)

        if state.debug_include:
            print(
                f"Including {t.boundname}, target: {filename}, expanded from: {location}"
            )

        if not t.boundname or not os.path.exists(t.boundname):
            print(f"Include failed on file: {t.boundname}")
            exit(1)
        else:
            jamfiles_target = state.targets.get("jamfiles")
            if jamfiles_target:
                jamfiles_target.depends.add(t)

            with open(t.boundname) as f:
                rules = f.read()
                cmds = state.parse_and_compile(rules, filename=t.boundname)

                state.vars.push()
                run(state, cmds)
                state.vars.pop()


def exec_on_target(state: State, targets, cmds):
    """
    on target statement
    run cmds under target vars influence
    """
    for target_name in expand(state, targets):
        target = state.get_target(target_name)

        with target.overlay(state):
            run(state, cmds)


def exec_rule_on_target(state: State, targets, name, args):
    """
    [ on target rule args ]
    exec rules under target vars influence
    """

    res = []
    for target_name in expand(state, targets):
        target = Target.bind(state, target_name)

        rule_res = None
        with target.overlay(state):
            rule_res = exec_rule(state, name, args)

        if isinstance(rule_res, Result):
            res += rule_res.val

    if res:
        return Result(res)


def exec_return_on_target(state: State, targets, val):
    """
    [ on target return val ]
    return vars target vars influence
    """

    res = []
    for target_name in expand(state, targets):
        target = state.get_target(target_name)

        with target.overlay(state):
            res += expand(state, val)

    return Result(res)


def var_bool(var):
    if var is None:
        return False

    if isinstance(var, bool):
        return var
    elif isinstance(var, str):
        return len(var) > 0
    elif isinstance(var, list) and len(var) > 0:
        return len(var[0]) > 0

    return False


def evaluate_expr(state: State, args: tuple):
    match args:
        case (Node.EXPR, arg):
            res = expand(state, arg)
            return res

        case (Node.EXPR_BOP, (left, op, right)):
            if op == "in":
                left = expand(state, left)
                # if len(left):
                right = expand(state, right)
                return set(left).issubset(right)

            left = evaluate_expr(state, left)

            # quick path for AND and OR
            match op:
                case "&&":
                    if not var_bool(left):
                        return False
                case "||":
                    if var_bool(left):
                        return True

            right = evaluate_expr(state, right)
            match op:
                case "=":
                    return left == right
                case ">":
                    return left > right
                case "<":
                    return left < right
                case "!=":
                    return left != right
                case ">=":
                    return left >= right
                case "<=":
                    return left <= right
                case "&&":
                    return var_bool(left) and var_bool(right)
                case "||":
                    return var_bool(left) or var_bool(right)
                case _:
                    raise ExecutionError(f"unexpected binary operation: {op}")
        case (Node.EXPR_UNARY, op, arg):
            arg = evaluate_expr(state, arg)
            match op:
                case "!":
                    return not var_bool(arg)
                case _:
                    raise ExecutionError(f"unexpected unary operation: {op}")
        case (Node.EXPR_BLOCK, block):
            # braced
            return evaluate_expr(state, block)
        case _:
            raise ExecutionError(f"could not match an expression: {args}")


def exec_if(state: State, cond, block, else_block):
    res = var_bool(evaluate_expr(state, cond))

    if res is True:
        return exec_block(state, block)
    else:
        return exec_block(state, else_block)


def exec_while(state: State, cond, block):
    while var_bool(evaluate_expr(state, cond)):
        ret = exec_block(state, block)
        if ret == FLOW_BREAK:
            break
        elif ret == FLOW_CONTINUE:
            continue


def exec_for(state: State, var, items, block):
    items = expand(state, items)
    if isinstance(items, str):
        items = (items,)

    varname = expand(state, var)
    if len(varname) == 0:
        raise ExecutionError(f"got empty argument in for after expanding {var}")

    for item in items:
        state.vars.set(varname[0], [item])
        ret = exec_block(state, block)
        if ret == FLOW_BREAK:
            break
        elif ret == FLOW_CONTINUE:
            continue


def exec_switch(state: State, arg, cases):
    arg = expand(state, arg)
    if arg:
        for pattern, block in cases:
            if match(pattern, arg[0]) == 0:
                if len(block) and isinstance(block[0], list):
                    return exec_block(state, block[0])
                else:
                    return run(state, block)


def exec_block(state, cmds):
    # create a local scope
    state.vars.push()

    ret = run(state, cmds)

    # return the scope
    state.vars.pop()

    return ret
