import tempfile
import os
from os import sep as S

from jamp.classes import Target, State
from jamp.executors import run


def test_global_locate_search():
    state = State()
    target = Target.bind(state, "test.c")
    state.vars.set("LOCATE", ["/tmp"])
    assert target.search(state) == f"{S}tmp{S}test.c"

    state.vars.set("LOCATE", [])

    with tempfile.NamedTemporaryFile() as f:
        target_temp = Target.bind(state, os.path.basename(f.name))
        tempdir = os.path.dirname(f.name)
        state.vars.set("SEARCH", ["/proc", tempdir])
        assert target_temp.search(state) == f.name

    state.vars.set("SEARCH", [])
    assert target.search(state) == "test.c"


def test_target_locate_search():
    state = State()
    target = Target.bind(state, "test.c")
    target.vars["LOCATE"] = ["/tmp"]
    assert target.search(state) == f"{S}tmp{S}test.c"

    target.vars["LOCATE"] = []

    with tempfile.NamedTemporaryFile() as f:
        target_temp = Target.bind(state, os.path.basename(f.name))
        tempdir = os.path.dirname(f.name)
        target_temp.vars["SEARCH"] = ["/proc", tempdir]
        assert target_temp.search(state) == f.name

    target.vars["SEARCH"] = []
    assert target.search(state) == "test.c"


def test_linking_actions():
    rules = """
    rule OneCompile
    {
        rule Second
        {
            Echo $(1) ;
        }

        Clean clean : $(<) ;
        Compile1 $(<) : $(>) ;
        Compile2 $(<) : $(>) ;
    }

    rule Compile1
    {
        Echo "compile 1 called!" ;
    }

    actions Compile1 {
        echo "1"  $(>) $(<)
    }

    actions Compile2 {
        echo "2"  $(>) $(<)
    }

    actions OneCompile {
        echo "3" $(>) $(<) ;
    }

    OneCompile test.c : test.h ;
    Depends all : test.c ;
    Includes test.c : test.h ;
    """

    state = State()
    run(state, state.parse_and_compile(rules))
    print(state.targets)
