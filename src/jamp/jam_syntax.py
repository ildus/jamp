#!/usr/bin/env python3

import sys

from jamp.jam_lexer import Lexer, SCAN_NORMAL, keywords
from jamp.yacc import yacc
from enum import Enum

use_colors = False

if not hasattr(sys, "_called_from_test"):
    try:
        import colorama
        from colorama import Fore, Style

        colorama.init()
        use_colors = True
    except ImportError:
        pass


def highlight(text, arg=False):
    if use_colors and not arg:
        return f"{Fore.YELLOW}{text}{Style.RESET_ALL}"
    if use_colors and arg:
        return f"{Fore.CYAN}{text}{Style.RESET_ALL}"
    else:
        return f"{text}"


class Node(Enum):
    ASSIGN = 2
    CALL = 3
    LOL = 4
    ACTIONS = 5
    CASE = 7
    ARG_ON_TARGET = 8
    EXPR = 9
    FUNC = 10
    FUNC_ON = 11
    SWITCH = 12
    RULE = 13
    WHILE = 14
    IF = 15
    FOR = 16
    BREAK = 17
    RETURN = 18
    CONTINUE = 19
    INCLUDE = 20
    ON_TARGET = 21
    LOCAL = 22
    EFLAG = 23
    BINDLIST = 24
    EXPR_BOP = 26
    EXPR_UNARY = 27
    EXPR_BLOCK = 28
    RETURN_ON = 29

    def __repr__(self):
        return highlight(self.name)


tokens = list(keywords.values()) + ["ARG", "STRING"]


precedence = (
    ("left", "BARBAR", "BAR"),
    ("left", "AMPERAMPER", "AMPER"),
    ("left", "EQUALS", "BANG_EQUALS", "IN"),
    ("left", "LANGLE", "LANGLE_EQUALS", "RANGLE", "RANGLE_EQUALS"),
    ("left", "BANG"),
)


# parser begin
# seq - zero or more rules
# rules - one or more rules
# rule - any one of jam's rules
#   right-recursive so rules execute in order.
def p_seq(p):
    """
    block :
    | rules
    """
    if len(p) > 1:
        p[0] = p[1]
    else:
        p[0] = None


def p_rules(p):
    """
    rules : rule
        | rule rules
    """
    if len(p) == 2:
        p[0] = [p[1]]
    elif len(p) == 3:
        p[2].insert(0, p[1])
        p[0] = p[2]


def p_rules_local(p):
    """
    local : LOCAL list SEMICOLON
        | LOCAL list EQUALS list SEMICOLON
    """
    if len(p) == 4:
        p[0] = (Node.LOCAL, p[2], None)
    else:
        p[0] = (Node.LOCAL, p[2], p[4])


def p_block(p):
    """
    rule : rule_block
    | include
    | rule_call
    | arg_assign
    | arg_on_target
    | break
    | continue
    | return
    | for
    | switch
    | if
    | while
    | ruledef
    | on_target
    | actions
    | local
    """
    p[0] = p[1]


def p_rule_on_arg(p):
    """
    on_target : ON arg rule
    """
    p[0] = (Node.ON_TARGET, p[2], p[3])


def p_rule_call(p):
    """
    rule_call : arg lol SEMICOLON
    """
    p[0] = (Node.CALL, p[1], p[2])


def p_rule_include(p):
    """
    include : INCLUDE list SEMICOLON
    """
    p[0] = (Node.INCLUDE, p[2])


def p_rule_break(p):
    """
    break : BREAK list SEMICOLON
    """
    p[0] = (Node.BREAK, p[2])


def p_rule_continue(p):
    """
    continue : CONTINUE list SEMICOLON
    """
    p[0] = (Node.CONTINUE, p[2])


def p_rule_return(p):
    """
    return : RETURN list SEMICOLON
    """
    p[0] = (Node.RETURN, p[2])


def p_rule_for(p):
    """
    for : FOR ARG IN list LBRACE block RBRACE
    """
    p[0] = (Node.FOR, p[2], p[4], p[6])


def p_rule_switch(p):
    """
    switch : SWITCH list LBRACE cases RBRACE
    """
    p[0] = (Node.SWITCH, p[2], p[4])


def p_rule_while(p):
    """
    while : WHILE expr LBRACE block RBRACE
    """

    p[0] = (Node.WHILE, p[2], p[4])


def p_ruledef(p):
    """
    ruledef : RULE ARG params LBRACE block RBRACE
    """
    p[0] = (Node.RULE, p[2], p[3], p[5])


def p_rule_if(p):
    """
    if : IF expr LBRACE block RBRACE
    | IF expr LBRACE block RBRACE ELSE rule
    """
    if len(p) == 6:
        p[0] = (Node.IF, p[2], p[4])
    else:
        p[0] = (Node.IF, p[2], p[4], p[7])


def p_rule_arg_assign(p):
    """
    arg_assign : arg assign_type list SEMICOLON
    """
    p[0] = (Node.ASSIGN, p[1], p[2], p[3])


def p_rule_arg_on_target(p):
    """
    arg_on_target : arg ON list assign_type list SEMICOLON
    """
    p[0] = (Node.ARG_ON_TARGET, p[1], p[3], p[4], p[5])


def p_rule_actions(p):
    """
    actions : ACTIONS eflags ARG bindlist LBRACE STRING RBRACE
    """
    p[0] = (Node.ACTIONS, p[2], p[3], p[4], p[6])


def p_rule_block(p):
    """
    rule_block : LBRACE block RBRACE
    """
    p[0] = p[2]


def p_assign_type(p):
    """
    assign_type : EQUALS
    | PLUS_EQUALS
    | QUESTION_EQUALS
    | DEFAULT EQUALS
    """
    p[0] = p[1]


def p_expr(p):
    """
    expr : arg
    | expr EQUALS expr
    | expr BANG_EQUALS expr
    | expr LANGLE expr
    | expr LANGLE_EQUALS expr
    | expr RANGLE expr
    | expr RANGLE_EQUALS expr
    | expr AMPER expr
    | expr AMPERAMPER expr
    | expr BAR expr
    | expr BARBAR expr
    | arg IN list
    | BANG expr
    | LPAREN expr RPAREN
    """
    if len(p) == 2:
        p[0] = (Node.EXPR, p[1])
    elif len(p) == 3:
        # unary
        p[0] = (Node.EXPR_UNARY, p[1], p[2])
    elif len(p) == 4:
        if p[1] == "(":
            p[0] = (Node.EXPR_BLOCK, p[2])
        else:
            p[0] = (Node.EXPR_BOP, (p[1], p[2], p[3]))


# cases - action elements inside a 'switch'
# case - a single action element inside a 'switch'
# right-recursive rule so cases can be examined in order.
def p_cases(p):
    """
    cases :
    | case cases
    """
    if len(p) == 1:
        p[0] = []
    else:
        p[2].insert(0, p[1])
        p[0] = p[2]


def p_case(p):
    """
    case : CASE ARG COLON block
    """
    p[0] = (Node.CASE, p[2], p[4])


# params - optional parameter names to rule definition
# right-recursive rule so that params can be added in order.
def p_params(p):
    """
    params :
    | ARG COLON params
    | ARG
    """
    if len(p) > 1:
        p[0] = (Node.PARAMS, p[1], p[3] if len(p) > 2 else None)


# lol - list of lists
#    right-recursive rule so that lists can be added in order.
def p_lol(p):
    """
    lol : list
        | list COLON lol
    """
    if len(p) == 2:
        p[0] = (Node.LOL, p[1])
    else:
        p[0] = (Node.LOL, p[1], *p[3][1:])


# list - zero or more args in a LIST
def p_list(p):
    """
    list : listp
    """
    p[0] = p[1]
    # p.lexer.set_scanmode(SCAN_NORMAL)


# listp - list (in puncutation only mode)
def p_listp(p):
    """
    listp :
        | listp arg
    """
    if len(p) == 1:
        pass
        # p.lexer.set_scanmode(SCAN_PUNCT)
    else:
        if p[1] is None:
            p[0] = [p[2]]
        else:
            p[1].append(p[2])
            p[0] = p[1]


class Arg(object):
    def __init__(self, val):
        self.value = val

    def __repr__(self):
        if self.value:
            return highlight(self.value, arg=True)
        else:
            return highlight('""', arg=True)


# arg - one ARG or function call
def p_arg(p):
    """
    arg : ARG
        | LBRACKET func RBRACKET
    """
    if len(p) == 2:
        p[0] = Arg(p[1])
    else:
        p.lexer.set_scanmode(SCAN_NORMAL)
        p[0] = Arg(p[2])


# func - a function call (inside [])
# This needs to be split cleanly out of 'rule'
def p_func(p):
    """
    func : arg lol
        | ON arg arg lol
        | ON arg RETURN list

    """
    if len(p) == 3:
        p[0] = (Node.FUNC, p[1], p[2])
    elif p[3] == 'return':
        p[0] = (Node.RETURN_ON, p[2], p[4])
    else:
        p[0] = (Node.FUNC_ON, p[2], p[3], p[4])


# eflags - zero or more modifiers to 'executes'
def p_eflags(p):
    """
    eflags :
    | eflags eflag
    """
    if len(p) == 1:
        p[0] = []
    else:
        p[1].append(p[2])
        p[0] = p[1]


# eflag - a single modifier to 'executes'
def p_eflag(p):
    """
    eflag : UPDATED
    | TOGETHER
    | IGNORE
    | QUIETLY
    | PIECEMEAL
    | EXISTING
    | MAXLINE ARG
    """
    if len(p) == 2:
        p[0] = (Node.EFLAG, p[1], None)
    else:
        p[0] = (Node.EFLAG, p[1], p[2])


# bindlist - list of variable to bind for an action
def p_bindlist(p):
    """
    bindlist :
    | BIND list
    """
    if len(p) > 1:
        p[0] = (Node.BINDLIST, p[2])
    else:
        p[0] = (Node.BINDLIST, None)


def p_error(p):
    parts = []
    if not p:
        print("Error, but no info, check Jamfile for correct EOF")
        return

    if p.lexer and p.lexer.filename:
        parts.append(p.lexer.filename)

    if p.lexer:
        parts.append(str(p.lexer.current_lineno()))

    if p and p.value is not None:
        print(f"Syntax error at {p.value!r} at line {':'.join(parts)}")
    else:
        print("Syntax error")


def parse(text: str, filename: str = None):
    parser = yacc()
    lexer = Lexer(filename=filename)
    lexer.input(text)
    return parser.parse(lexer=lexer)


def parse_file(fn: str):
    parser = yacc()

    with open(fn) as f:
        data = f.read()

    lexer = Lexer()
    lexer.input(data)
    return parser.parse(lexer=lexer)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        prog="jam parser", description="Checks jam grammar"
    )
    parser.add_argument("--tokens", action="store_true", help="print tokens")
    parser.add_argument("--ast", action="store_true", help="print AST")
    parser.add_argument("filename")
    args = parser.parse_args()

    parser = yacc(debug=True)
    lexer = Lexer()
    with open(args.filename) as f:
        data = f.read()

    lexer.input(data)

    if args.tokens:
        while True:
            tok = lexer.token()
            if not tok:
                break  # No more input

            print(tok)

    if args.ast:
        lexer.restart()
        ast = parser.parse(data, lexer=lexer, tracking=True)
        print(ast)
