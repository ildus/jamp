import os

from jamp.jam_syntax import parse
from jamp.compile import compile
from jamp.executors import run
from jamp.classes import State
from jamp.jam_builtins import Builtins


def expect_output(expected):
    cp = Builtins.output
    print(cp)
    Builtins.clear_output()
    assert cp == expected


def test_simple_rule_with_assigns():
    rule_t = """
    a = 10 ;

    rule A
    {
        local a = 3 ;
        b = 2 ;
        a = 4 ;
        local c  ;

        Echo "inside a" $(a) ;
        Echo "inside b" $(b) ;
    }

    actions A {
        echo "actions" ;
    }

    Echo "outside a" $(a) ;
    Echo "outside b" $(b) ;

    A ;

    Echo "outside a" $(a) ;
    Echo "outside b" $(b) ;
    Echo "test" "test1" "test2" ;
    """

    state = State()
    ast = parse(rule_t)
    cmds = compile(state, ast)
    run(state, cmds)

    output = """outside a 10
outside b
inside a 4
inside b 2
outside a 10
outside b 2
test test1 test2
"""

    expect_output(output)


def test_rule_targets():
    rule_t = """
    rule A
    {
        Echo $(<) ;
        Echo $(>) ;
        Echo $(1) ;
        Echo $(2) ;
    }

    Echo $(<) ;
    A "one" : two ;
    """

    state = State()
    run(state, state.parse_and_compile(rule_t))
    output = """
one
two
one
two
"""
    expect_output(output)


def test_simple_if():
    rules = """
    a = 4 ;
    b = 4 ;
    c = 4 ;

    if $(a) = $(b)
    {
        local a = "check" ;
        local b = "ok" ;
        Echo $(a) $(b) ;
    }

    Echo $(a) $(b) : $(c) ;
    """

    state = State()
    run(state, state.parse_and_compile(rules))

    output = """check ok
4 4 4
"""

    expect_output(output)


def test_simple_else():
    rules = """
    a = 4 ;
    b = 5 ;

    if $(a) = $(b)
    {
        Echo "equal" ;
    }
    else
    {
        Echo "not equal" ;
    }

    if $(a) = $(b)
    {
        Echo "equal" ;
    }
    else
        Echo "not equal 2" ;
    """

    state = State()
    run(state, state.parse_and_compile(rules))

    output = "not equal\nnot equal 2\n"
    expect_output(output)


def test_comparisons_and_not():
    rules = """
    a = 4 ;
    b = 4 ;
    c = 4 4 ;
    d = 4 4 ;
    e = 5 4 ;

    if ! ( $(a) != $(b) )
    {
        Echo "check 1 ok" ;
    }

    if $(c) > $(b)
    {
        Echo "check 2 ok" ;
    }

    if $(c) >= $(d)
    {
        Echo "check 3 ok" ;
    }

    if $(c) < $(e)
    {
        Echo "check 4 ok" ;
    }

    if $(c) <= $(d)
    {
        Echo "check 5 ok" ;
    }

    if $(c) > $(e) || $(a) = $(b)
    {
        Echo "check 6 ok" ;
    }

    if $(c) > $(e) && $(a) = $(b)
    {
        Echo "check 7 fail" ;
    }

    if ! ( $(c) > $(e) && $(a) = $(b) )
    {
        Echo "check 8 ok" ;
    }

    if $(a) in $(e)
    {
        Echo "check 9 ok" ;
    }

    if $(e) in $(a)
    {
        Echo "check 10 not ok" ;
    }
    """

    state = State()
    run(state, state.parse_and_compile(rules))

    output = """check 1 ok
check 2 ok
check 3 ok
check 4 ok
check 5 ok
check 6 ok
check 8 ok
check 9 ok
"""

    expect_output(output)


def test_while():
    rules = """
    a = 4 ;

    while $(a)
    {
        Echo $(a) ;

        if $(a) = 6
        {
            a = ;
        }

        if $(a) = 5
        {
            a = 6 ;
        }

        if $(a) = 4
        {
            a = 5 ;
        }
    }
    """

    state = State()
    run(state, state.parse_and_compile(rules))

    output = """4\n5\n6\n"""
    expect_output(output)


def test_while_break():
    rules = """
    a = 4 ;

    while $(a)
    {
        Echo $(a) ;

        if $(a) = 6
        {
            break ;
        }

        if $(a) = 5
        {
            a = 6 ;
        }

        if $(a) = 4
        {
            a = 5 ;
        }
    }
    """

    state = State()
    run(state, state.parse_and_compile(rules))

    output = """4\n5\n6\n"""
    expect_output(output)


def test_while_continue():
    rules = """
    a = 4 ;

    while $(a)
    {
        Echo $(a) ;

        if $(a) = 6
        {
            break ;
        }

        if $(a) = 5
        {
            a = 6 ;
            continue ;
            a = 11 ;
        }

        if $(a) = 4
        {
            a = 5 ;
            continue ;
        }

        a = 10 ;
    }
    """

    state = State()
    run(state, state.parse_and_compile(rules))
    expect_output("4\n5\n6\n")


def test_for():
    rules = """
    items = 1 2 3 4 ;

    for item in $(items)
    {
        local a ;

        if ! $(a)
        {
            a = 10 ;
        }

        Echo $(a) ;
        a = $(item) ;
        Echo $(a) ;
    }

    Echo "item" $(item) ;
    """

    state = State()
    run(state, state.parse_and_compile(rules))
    output = """10
1
10
2
10
3
10
4
item 4
"""
    expect_output(output)


def test_switch():
    rules = """
    a = "test1" ;
    switch $(a)
    {
        case ?est2 :
            Echo "test2" ;
        case ?est1 :
            Echo "test1" ;
        case ?est3 :
            Echo "test3" ;
    }
    """
    state = State()
    run(state, state.parse_and_compile(rules))
    output = """test1\n"""
    expect_output(output)


def test_params():
    rules = """
    rule check
    {
        Echo $(<) ;
        Echo $(>) ;
        Echo $(<[2]) $(<[4]) ;
    }

    check "1" "2" "3" "4" "5" : "11" "22" "33" ;
    """
    state = State()
    run(state, state.parse_and_compile(rules))
    output = "1 2 3 4 5\n11 22 33\n2 4\n"
    expect_output(output)


def test_params_only_left():
    rules = """
    rule check
    {
        Echo $(<[2]) $(<[4]) ;
    }

    check "1" "2" "3" "4" "5"  ;
    """
    state = State()
    run(state, state.parse_and_compile(rules))
    output = "2 4\n"
    expect_output(output)


def test_include():
    rules = """
    rule Test
    {
        Echo "1" ;
    }

    Test1 "aaa" ;

    include tests/data/include_test.jam ;

    Test ;
    Test1 "aaa" ;
    """

    state = State()
    run(state, state.parse_and_compile(rules))
    output = "jamp: unknown rule Test1\n1\n2\n"
    expect_output(output)


def test_assign_types():
    rules = """
    a = 1 ;
    local b ;
    local c ;
    a ?= 2 ;
    Echo $(a) ;
    a += 3 ;
    Echo $(a) ;
    b += 4 ;
    Echo $(b) ;
    c += ;
    Echo $(c) ;
    a += 5 ;
    Echo $(a) ;
    d ?= 6 7 ;
    Echo $(d) ;
    e ?= 8 ;
    Echo $(e) ;
    """

    state = State()
    run(state, state.parse_and_compile(rules))
    output = "1\n1 3\n4\n\n1 3 5\n6 7\n8\n"
    expect_output(output)


def test_assign_types_on_target():
    rules = """
    a on test.c = 1 ;
    a on test.c ?= 2 ;
    b on test.c = ;
    c on test.c = ;
    """

    state = State()
    run(state, state.parse_and_compile(rules))
    target = state.get_target("test.c")
    assert target.vars["a"] == ["1"]

    rules = """
    a on test.c += 3 ;
    b on test.c += 1 ;
    c on test.c += 1 5 ;
    """

    run(state, state.parse_and_compile(rules))
    assert target.vars["a"] == ["1", "3"]
    assert target.vars["b"] == ["1"]
    assert target.vars["c"] == ["1", "5"]


def test_on_target():
    rules = """
    a on test.c = "val1" ;
    b on test2.c = "val3" ;
    c = "val2" ;

    on test.c Echo $(a) $(b) $(c) ;
    on test2.c
    {
        Echo $(a) $(b) $(c) ;
    }
    """
    state = State()
    run(state, state.parse_and_compile(rules))
    output = "val1 val2\nval3 val2\n"
    expect_output(output)


def test_func():
    rules = """
    rule some_func
    {
        a = 1 2 ;
        return $(1) $(a) ;
    }

    res = [ some_func "one" ] ;
    Echo $(res) ;
    """
    state = State()
    run(state, state.parse_and_compile(rules))
    output = "one 1 2\n"
    expect_output(output)


def test_rule_cycle_return():
    rules = """
    rule one
    {
        Echo $(<) ;
        a = $(<) $(>) ;

        for i in $(a)
        {
            Echo $(i) ;
        }

        return $(a) $(i) ;
    }

    res = [ one 1 2 : 3 4 : 5 6 ] ;
    echo $(res) ;
    """
    state = State()
    run(state, state.parse_and_compile(rules))
    output = "1 2\n1\n2\n3\n4\n1 2 3 4 4\n"
    expect_output(output)


def test_glob_rule():
    rules = """
    res = [ glob . : *.py *.ini ] ;
    echo $(res) ;
    """
    state = State()
    run(state, state.parse_and_compile(rules))
    expected = set(f".{os.sep}pytest.ini .{os.sep}conftest.py\n".strip().split(" "))
    cp = set(Builtins.output.strip().split(" "))
    Builtins.clear_output()
    assert cp == expected


def test_match_rule():
    rules = r"""
    res = [ match \\d+ ab : 23adf abba adad ] ;
    echo $(res) ;
    """
    state = State()
    run(state, state.parse_and_compile(rules))
    output = "23 ab\n"
    expect_output(output)


def test_expanded_rule_and_empty_result():
    rules = r"""
    rule One
    {
        return ;
    }
    a = ;
    res = [ $(a) "one" "two" ] ;
    Echo $(res) 1 ;
    res = [ One "one" "two" ] ;
    Echo $(res) 2 ;
    """
    state = State()
    run(state, state.parse_and_compile(rules))
    output = "1\n2\n"
    expect_output(output)


def test_expanded_rule():
    rules = r"""
    rule one
    {
        return 1 2 ;
    }
    rule two
    {
        return  ;
    }
    rule three
    {
        return 3 ;
    }

    a = one two three ;
    res = [ $(a) "nothing" ] ;
    Echo $(res) ;
    """
    state = State()
    run(state, state.parse_and_compile(rules))
    assert state.vars.get("res") == ["1", "2", "3"]
    output = "1 2 3\n"
    expect_output(output)


def test_expanded_with_empty():
    rules = r"""
    local a = a1 a2 a3 ;
    local b = ;
    local c = c1 ;
    local d = d1 ;

    Echo "1" "/define=( $(a) )" ;
    Echo "2" "/define=( $(b) )" ;
    Echo "3" "/define=( $(a) $(b) )" ;
    Echo "4" "/define=( $(b) $(a) )" ;
    Echo "5" $(c)$(b) ;
    Echo "6" $(c)$(d) ;
    Echo "7" $(c)$(b)$(d) ;
    Echo "8" $(c)$(d)$(b) ;
    Echo "9" "$(c)$(b)$(d)" ;
    Echo "10" "$(c)$(d)$(b)" ;
    """
    state = State()
    run(state, state.parse_and_compile(rules))
    output = """1 /define=( a1 ) /define=( a2 ) /define=( a3 )
2
3
4
5
6 c1d1
7
8
9
10
"""
    expect_output(output)


def test_assign_empty():
    rules = r"""
    a = "" ;
    b = ;
    """
    state = State()
    run(state, state.parse_and_compile(rules))
    assert state.vars.get("a") == [""]
    assert state.vars.get("b") == []


def test_quoted_empty():
    rules = r"""
    rule Test { return "/define=( $(<:J=,) )" ; }

    local a = ;
    Echo [ Test $(a) ] ;
    """

    state = State()
    run(state, state.parse_and_compile(rules))
    output = "\n"
    expect_output(output)


def test_quoted_non_empty():
    rules = r"""
    rule Test { return "/define=( $(<:J=,) )" ; }

    local a = "inc1:" "inc2:" ;
    Echo [ Test $(a) ] ;
    """

    state = State()
    run(state, state.parse_and_compile(rules))
    output = "/define=( inc1:,inc2: )\n"
    expect_output(output)


def test_on_return():
    rules = """
    AR = ar ;

    actions Archive
    {
        $(AR)
    }

    Archive test.a : test.obj ;
    AR on test.a = "ar ru" ;
    Echo [ on test.a return $(AR) "some" ] ;
    Echo "ok" ;
    """
    state = State()
    run(state, state.parse_and_compile(rules))
    output = "ar ru some\nok\n"
    expect_output(output)


def test_empty_1():
    rules = """a = ;
b = "" ;
c = "" "" ;

Echo $(a)1 ;
Echo $(b)2 ;
Echo $(c)3 ;
    """
    state = State()
    run(state, state.parse_and_compile(rules))
    output = "\n2\n3 3\n"
    expect_output(output)


def test_empty_2():
    rules = """a = ;
b = "" ;
c = "" "" ;
d = $(c) "" ;

Echo $(a)1 ;
Echo $(b)2 ;
Echo $(c)3 ;
Echo $(d)4 ;
    """
    state = State()
    run(state, state.parse_and_compile(rules))
    output = "\n2\n3 3\n4 4 4\n"
    expect_output(output)
