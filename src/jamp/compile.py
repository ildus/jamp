from jamp.jam_syntax import Node, Arg
from jamp.classes import Rule, Exec, Actions, State
from jamp import executors


class CompilerError(Exception):
    pass


def compile(state: State, node: tuple | list):
    match node:
        case Arg(value=(Node.FUNC, *r)):
            return Exec(executors.exec_rule, r)
        case Arg(value=(Node.FUNC_ON, *r)):
            return Exec(executors.exec_rule_on_target, r)
        case Arg(value=(Node.RETURN_ON, targets, val)):
            return Exec(
                executors.exec_return_on_target,
                (
                    compile(state, targets),
                    compile(state, val),
                ),
            )
        case (Node.RULE, *r):
            return Exec(compile_rule, r)
        case (Node.ASSIGN, *r):
            return Exec(executors.exec_assign, compile(state, r))
        case (Node.ARG_ON_TARGET, target, var, assign_type, assign_list):
            return Exec(
                executors.exec_assign_on_target,
                (
                    (compile(state, target)),
                    compile(state, var),
                    assign_type,
                    compile(state, assign_list),
                ),
            )
        case (Node.LOCAL, name, value):
            return Exec(executors.exec_local_assign, (name, compile(state, value)))
        case (Node.CALL, rule_name, lol):
            return Exec(executors.exec_rule, (rule_name, compile(state, lol)))
        case (Node.ACTIONS, *r):
            return Exec(compile_actions, r)
        case (Node.WHILE, cond, block):
            return Exec(executors.exec_while, (cond, compile(state, block)))
        case (Node.FOR, varname, items, block):
            return Exec(
                executors.exec_for,
                (varname, compile(state, items), compile(state, block)),
            )
        case (Node.LOL, *r):
            return (Node.LOL, *[compile(state, item) for item in r])
        case (Node.BREAK, not_used):
            return Exec(executors.exec_break, (not_used,))
        case (Node.CONTINUE, not_used):
            return Exec(executors.exec_continue, (not_used,))
        case (Node.RETURN, val):
            return Exec(executors.exec_return, (compile(state, val),))
        case (Node.IF, *r):
            return compile_if(state, *r)
        case (Node.SWITCH, *r):
            return compile_switch(state, *r)
        case (Node.INCLUDE, arg):
            return Exec(executors.exec_include, (arg,))
        case (Node.ON_TARGET, target, block):
            return Exec(executors.exec_on_target, (target, compile(state, block)))
        case [*items]:
            # block
            res = []
            for item in items:
                exec_item = compile(state, item)
                if exec_item is not None:
                    res.append(exec_item)

            return res
        case _:
            return node


def compile_rule(state: State, name: str, params: tuple | None, block: tuple):
    state.rules[name] = Rule(name, compile(state, params), compile(state, block))


def compile_actions(state: State, flags, name, bindlist, script):
    if name == "Clean":
        return

    if name not in state.rules:
        compile_rule(state, name, [], [])

    state.actions[name] = Actions(name, flags, bindlist, script)


def compile_if(state: State, expr, true_block, false_block=None):
    return Exec(
        executors.exec_if,
        (
            compile(state, expr),
            compile(state, true_block),
            compile(state, false_block) if false_block else None,
        ),
    )


def compile_switch(state: State, arg, cases):
    return Exec(
        executors.exec_switch,
        (arg, [(item[1], compile(state, item[2])) for item in cases]),
    )
