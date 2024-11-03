from jamp.pattern import match


def test_patterns():
    assert match("one*", "one") == 0
    assert match("one**", "one") == 0
    assert match("one**o", "oneo") == 0
    assert match("one*a*o", "oneo") == 1
    assert match("?a", "da") == 0
    assert match("d?n", "d$n") == 0
    assert match("?aa", "da") == 1
    assert match("?a", "daa") == -1
    assert match("a??", "da") == 1
    assert match("[abd]c", "ac") == 0
    assert match("[abe]c", "dc") == 1
    assert match("[^abd]c", "dc") == 1
    assert match("[^abd]c", "ac") == 1
    assert match("ac*", "aca") == 0
    assert match("ac*d", "aca123d") == 0
    assert match("ac*c", "aca123d") == 1
    assert match("*c*c", "1ca123d") == 1
    assert match("*c*c", "1ca123c") == 0
    assert match("*c*[efg]?", "1ca123cfi") == 0
    assert match("*c*[efg]j", "1ca123cfi") == 1
    assert match("*c*[^efg]j", "1ca123ckj") == 0
