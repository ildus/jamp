from jamp.jam_syntax import parse


def test_simple_assign_sequence():
    rule_t = """
    rule One
    {
        a = 1 ;
        b = 2 ;
        c = 3 ;
    }

    rule Two
    {
        c = 1 ;
        d = 2 ;
        e = 3 ;
    }
    """
    ast = parse(rule_t)
    assert str(ast) == (
        "[(RULE, 'One', None, [(ASSIGN, a, '=', [1]), (ASSIGN, b, '=', [2]), "
        "(ASSIGN, c, '=', [3])]), (RULE, 'Two', None, [(ASSIGN, c, '=', [1]),"
        " (ASSIGN, d, '=', [2]), (ASSIGN, e, '=', [3])])]"
    )


def test_rule_if_with_call():
    rule_t = """
    rule R1
    {
        C1 $(1) ;

        if $(a) = .$(ext)
        {
            NOUPDATE $(a) ;
        }
        C2 $(<) : $(>) : : $(<:S=.$(L)) ;
        local V = [ C3 $(>:S=.$(O)) ] ;
    }
    """
    ast = parse(rule_t)
    assert str(ast) == (
        "[(RULE, 'R1', None, "
        "[(CALL, C1, (LOL, [$(1)])), "
        "(IF, (EXPR_BOP, ((EXPR, $(a)), '=', (EXPR, .$(ext)))), "
        "[(CALL, NOUPDATE, (LOL, [$(a)]))]), "
        "(CALL, C2, (LOL, [$(<)], [$(>)], None, [$(<:S=.$(L))])), "
        "(LOCAL, [V], [(FUNC, C3, (LOL, [$(>:S=.$(O))]))])])]"
    )


def test_rule_with_local_and_assign():
    rule_t = """
    rule One
    {
        local a = 1 ;
        b = 2 ;
        local c  ;
    }
    """

    ast = parse(rule_t)
    assert (
        str(ast)
        == "[(RULE, 'One', None, [(LOCAL, [a], [1]), (ASSIGN, b, '=', [2]), (LOCAL, [c], None)])]"
    )


def test_rule_with_params():
    rule_t = """
    rule One
    {
        local a = 1 ;
        b = 2 ;
        local c  ;
    }
    """

    ast = parse(rule_t)
    assert (
        str(ast)
        == "[(RULE, 'One', None, [(LOCAL, [a], [1]), (ASSIGN, b, '=', [2]), (LOCAL, [c], None)])]"
    )


def test_args():
    patterns = [
        ("a = $(a) ;", "[(ASSIGN, a, '=', [$(a)])]"),
        ('a = $(a;J=" ") ;', "[(ASSIGN, a, '=', [$(a;J= )])]"),
        ('a ?= "some text" ;', "[(ASSIGN, a, '?=', [some text])]"),
        ('a += "some text" ;', "[(ASSIGN, a, '+=', [some text])]"),
        (
            "b default = $(a) $(b) ;",
            "[(ASSIGN, b, 'default', [$(a), $(b)])]",
        ),
    ]

    for text, expected in patterns:
        parsed = parse(text)
        assert str(parsed) == expected


def test_call():
    patterns = [
        ("LINK some ;", "[(CALL, LINK, (LOL, [some]))]"),
    ]

    for text, expected in patterns:
        parsed = parse(text)
        assert str(parsed) == expected


def test_block():
    text = """
    {
        Echo "1" ;
    }
    """

    ast = parse(text)
    assert str(ast) == "[[(CALL, Echo, (LOL, [1]))]]"


def test_if_with_block():
    text = """
    if $(a)
    {
        Echo "1" ;
    }
    """

    ast = parse(text)
    assert str(ast) == "[(IF, (EXPR, $(a)), [(CALL, Echo, (LOL, [1]))])]"


def test_if_with_else():
    """the third Echo should be outside of if block"""
    text = """
    if $(a)
    {
        Echo "1" ;
    }
    else
        Echo "2" ;
        Echo "3" ;
    """

    ast = parse(text)
    assert (
        str(ast)
        == "[(IF, (EXPR, $(a)), [(CALL, Echo, (LOL, [1]))], (CALL, Echo, (LOL, [2]))),"
        " (CALL, Echo, (LOL, [3]))]"
    )


def test_actions():
    patterns = [
        (
            'actions one  { echo "1" }',
            """[(ACTIONS, [], 'one', (BINDLIST, None), ' echo "1" ')]""",
        ),
    ]

    for text, expected in patterns:
        parsed = parse(text)
        assert str(parsed) == expected


def test_switch():
    text = """
    a = "test1" ;
    switch $(a)
    {
        case ?est1 :
            Echo "test1" ;
        case ?est2 :
            Echo "test2" ;
        case ?est3 :
            Echo "test3" ;
    }
    """

    ast = parse(text)
    assert str(ast) == (
        "[(ASSIGN, a, '=', [test1]), "
        "(SWITCH, [$(a)], ["
        "(CASE, '?est1', [(CALL, Echo, (LOL, [test1]))]), "
        "(CASE, '?est2', [(CALL, Echo, (LOL, [test2]))]), "
        "(CASE, '?est3', [(CALL, Echo, (LOL, [test3]))])])]"
    )


def test_arg_on_target():
    text = """
    rule Object
    {
        Clean clean : $(<) ;
        SEARCH on $(>) = $(SEARCH_SOURCE) ;
    }
    """
    ast = parse(text)
    assert str(ast) == (
        "[(RULE, 'Object', None, "
        "[(CALL, Clean, (LOL, [clean], [$(<)])), "
        "(ARG_ON_TARGET, SEARCH, [$(>)], '=', [$(SEARCH_SOURCE)])])]"
    )


def test_on_target():
    text = """
    a on test.c = "val1" ;
    b on test2.c = "val3" ;
    c = "val2" ;

    on test.c Echo $(a) $(b) $(c) ;
    on test2.c Echo $(a) $(b) $(c) ;
    """
    ast = parse(text)
    assert (
        "[(ARG_ON_TARGET, a, [test.c], '=', [val1]), "
        "(ARG_ON_TARGET, b, [test2.c], '=', [val3]), "
        "(ASSIGN, c, '=', [val2]), "
        "(ON_TARGET, test.c, (CALL, Echo, (LOL, [$(a), $(b), $(c)]))), "
        "(ON_TARGET, test2.c, (CALL, Echo, (LOL, [$(a), $(b), $(c)])))]"
    ) == str(ast)


def test_func():
    text = """
    rule one
    {
        a = 1 2 ;
        return $(1) $(a) ;
    }

    res = [ one "one" ] ;
    Echo $(res) ;
    """
    ast = parse(text)
    assert str(ast) == (
        "[(RULE, 'one', None, "
        "[(ASSIGN, a, '=', [1, 2]), "
        "(RETURN, [$(1), $(a)])]), "
        "(ASSIGN, res, '=', [(FUNC, one, (LOL, [one]))]), "
        "(CALL, Echo, (LOL, [$(res)]))]"
    )


def test_parse_assign_empty():
    text = """
    a = "" ;
    b = ;
    """
    ast = parse(text)
    assert str(ast) == """[(ASSIGN, a, '=', [""]), (ASSIGN, b, '=', None)]"""


def test_parse_assign_optional():
    text = """
    C++FLAGS ?= /NAMES=UPPER ;
    """
    ast = parse(text)
    assert str(ast) == "[(ASSIGN, C++FLAGS, '?=', [/NAMES=UPPER])]"


def test_on_arg_return():
    text = """
    Archive test.a : test.obj ;
    AR on test.a = "ar ru" ;
    Echo [ on test.a return $(AR) ] ;
    """
    ast = parse(text)
    assert str(ast) == (
        "[(CALL, Archive, (LOL, [test.a], [test.obj])), "
        "(ARG_ON_TARGET, AR, [test.a], '=', [ar ru]), "
        "(CALL, Echo, (LOL, [(RETURN_ON, test.a, [$(AR)])]))]"
    )
