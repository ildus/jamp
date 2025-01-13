from os import sep as S

from jamp.expand import var_expand, var_edit_parse, MAGIC_COLON as MC
from jamp.paths import Pathname


def test_nested():
    assert var_expand("$(a)", [], {"a": "1"}) == ["1"]
    assert var_expand("$($(a))", [], {"a": "b", "b": "1"}) == ["1"]
    assert var_expand("$($($(a)))", [], {"a": "b", "b": "c", "c": "1"}) == ["1"]


def test_params():
    lol = [["i", str(i + 1)] for i in range(10)]
    assert var_expand("$(<)", ["a", "b"], None) == "a"
    assert var_expand("$(>)", ["a", "b"], None) == "b"
    assert var_expand("$(1)", ["a", "b", "c"], None) == "a"
    assert var_expand("$(2)", ["a", "b", "c"], None) == "b"
    assert var_expand("$(3)", lol, None) == ["i", "3"]
    assert var_expand("$(4)", lol, None) == ["i", "4"]
    assert var_expand("$(8)", lol, None) == ["i", "8"]
    assert var_expand("$(9)", lol, None) == ["i", "9"]
    assert var_expand("$(10)", ["a", "b"], {"10": "tt"}) == ["tt"]
    assert var_expand("$(a[2-])", [], {"a": ["1", "2", "3", "4"]}) == ["2", "3", "4"]
    assert var_expand("$(a[2])", [], {"a": ["1", "2", "3"]}) == ["2"]
    assert var_expand("$(a[2-2])", [], {"a": ["1", "2", "3", "4"]}) == ["2"]
    assert var_expand("$(a[2-1])", [], {"a": ["1", "2", "3", "4"]}) == []
    assert var_expand("$(a[2-6])", [], {"a": ["1", "2", "3", "4"]}) == ["2", "3", "4"]
    assert var_expand("$(a[2-3])", [], {"a": ["1", "2", "3", "4"]}) == ["2", "3"]
    assert var_expand("$(a[1])", [], {"a": ["1", "2", "3", "4"]}) == ["1"]
    assert var_expand("$(a[4])", [], {"a": ["1", "2", "3", "4"]}) == ["4"]
    assert var_expand("$(a[5])", [], {"a": ["1", "2", "3", "4"]}) == []
    assert var_expand("ad$(a[4])da", [], {"a": ["1", "2", "3", "4"]}) == ["ad4da"]
    assert var_expand("ad$(a)da", [], {"a": ["1", "2"]}) == ["ad1da", "ad2da"]
    assert var_expand("ad$(a)da$(b)gh", [], {"a": ["1", "2"], "b": ["3", "4"]}) == [
        "ad1da3gh",
        "ad1da4gh",
        "ad2da3gh",
        "ad2da4gh",
    ]


def test_empty_val():
    assert var_expand("-$(a)", [], {}) == []
    assert var_expand("-$(a)$(b)", [], {}) == []
    assert var_expand("-$(a)-", [], {}) == []
    assert var_expand("-$(a)$(b)", [], {"b": "1"}) == []
    assert var_expand("$(a)$(b)$(c)", [], {"a": ["1"], "b": [], "c": ["3"]}) == []
    assert var_expand("$(a)$(b)$(c)", [], {"a": ["1"], "b": [""], "c": ["3"]}) == ["13"]


def test_expand2():
    assert var_expand("-$(h)", [], {"h": ["val1", "val2"]}) == ["-val1", "-val2"]
    assert var_expand("-$(h)-", [], {"h": ["val1", "val2"]}) == ["-val1-", "-val2-"]
    assert var_expand("-$($(h))", [], {"h": ["a", "b"], "a": "1", "b": "2"}) == [
        "-1",
        "-2",
    ]
    assert var_expand("-$(a)$($(h))", [], {"h": ["a", "b"], "a": "1", "b": "2"}) == [
        "-11",
        "-12",
    ]
    assert var_expand("-$(c)$($(h))", [], {"h": ["a", "b"], "a": "1", "b": "2"}) == []


def test_edits():
    edits = var_edit_parse("L")
    assert edits.downshift
    assert not edits.upshift
    assert not edits.filemods

    edits = var_edit_parse("UP")
    assert not edits.downshift
    assert edits.upshift
    assert edits.parent
    assert edits.filemods

    edits = var_edit_parse("UQ")
    assert not edits.downshift
    assert edits.upshift
    assert edits.quote

    edits = var_edit_parse("QE=ab")
    assert edits.quote
    assert edits.empty == "ab"
    assert not edits.filemods

    edits = var_edit_parse(f"QE=ab{MC}J=ca")
    assert edits.quote
    assert edits.empty == "ab"
    assert edits.join == "ca"
    assert not edits.downshift

    edits = var_edit_parse(f"QE={MC}J=cad{MC}G=add")
    assert edits.quote
    assert edits.empty == ""
    assert edits.join == "cad"
    assert not edits.downshift

    edits = var_edit_parse(f"Q{MC}RG=acd{MC}M=baa{MC}U")
    assert edits.quote
    assert edits.f.root is None
    assert edits.f.grist == "acd"
    assert edits.f.member == "baa"
    assert edits.upshift
    assert edits.join is None
    assert edits.f.base == ""
    assert edits.filemods

    edits = var_edit_parse(f"QG=acd{MC}M=baa")
    assert edits.quote
    assert edits.f.root is None
    assert edits.f.grist == "acd"
    assert edits.f.member == "baa"
    assert edits.f.base is None
    assert edits.filemods

    edits = var_edit_parse(f"Q{MC}GB=bac{MC}S=sad{MC}D=dir{MC}U")
    assert edits.quote
    assert edits.upshift
    assert edits.filemods
    assert edits.join is None
    assert edits.f.grist is None
    assert edits.f.base == "bac"
    assert edits.f.suffix == "sad"
    assert edits.f.directory == "dir"

    edits = var_edit_parse(f"Q{MC}GB=bac{MC}S=sad{MC}D")
    assert edits.quote
    assert not edits.upshift
    assert edits.filemods
    assert edits.join is None
    assert edits.f.grist is None
    assert edits.f.base == "bac"
    assert edits.f.suffix == "sad"
    assert edits.f.directory is None


def test_paths():
    p = Pathname()
    orig = f"{S}one{S}two{S}three{S}file.c"
    p.parse(orig)
    assert p.build() == orig
    p.keep_only_parent()
    assert p.build() == f"{S}one{S}two{S}three"

    orig = f"<g1>one{S}two{S}three{S}file.c<mem>"
    p.parse(orig)
    assert p.build() == orig
    p.root = f"{S}add{S}"
    assert p.build() == f"<g1>{S}add{S}one{S}two{S}three{S}file.c<mem>"


def test_var_edits():
    assert var_expand("$(a:U)", [], {"a": ["ab"]}) == ["AB"]
    assert var_expand("$(a:E=cd)", [], {"a": []}) == ["cd"]
    assert var_expand("$(a:Q)", [], {"a": ["ab\\cd"]}) == ["ab\\\\cd"]
    assert var_expand("$(a:L)", [], {"a": ["AB", "CD"]}) == ["ab", "cd"]
    assert var_expand("$(a:L)e", [], {"a": ["AB", "CD"]}) == ["abe", "cde"]
    assert var_expand("y$(a:L)e", [], {"a": ["AB", "CD"]}) == ["yabe", "ycde"]
    assert var_expand("$(a:J=!) $(b)", [], {"a": ["AB", "CD"], "b": ["ab", "cd"]}) == [
        "AB!CD ab",
        "AB!CD cd",
    ]


def test_vms_paths_parent():
    p = Pathname(is_vms=True)
    orig = "src:[one]file.c"
    p.parse(orig)
    assert p.build() == orig
    p.keep_only_parent()
    assert p.build() == "src:[one]"

    p = Pathname(is_vms=True)
    orig = "src:[one]"
    p.parse(orig)
    assert p.build() == orig
    p.keep_only_parent()
    assert p.build() == "src:[000000]"

    p = Pathname(is_vms=True)
    orig = "src:[one.two]"
    p.parse(orig)
    assert p.build() == orig
    p.keep_only_parent()
    assert p.build() == "src:[one]"

    p = Pathname(is_vms=True)
    orig = "src:[000000]"
    p.parse(orig)
    assert p.build() == orig
    p.keep_only_parent()
    assert p.build() == "src:[000000]"

    p = Pathname(is_vms=True)
    orig = "<g1>dev:[one.two.three]file.c<mem>"
    p.parse(orig)
    assert p.build() == orig
    p.root = "[add:"
    assert p.build() == "<g1>dev:[one.two.three]file.c<mem>"


def test_vms_paths_root():
    p = Pathname(is_vms=True)
    orig = "[.one.two.three]file.c"
    p.parse(orig)
    assert p.build() == orig
    p.root = "src:[add]"
    assert p.build() == "src:[add.one.two.three]file.c"

    p = Pathname(is_vms=True)
    orig = "[one.two.three]file.c"
    p.parse(orig)
    assert p.build() == orig
    p.root = "src:"
    assert p.build() == "src:[one.two.three]file.c"

    p = Pathname(is_vms=True)
    orig = "one.c"
    p.parse(orig)
    assert p.build() == orig
    p.root = "src:"
    assert p.build() == "src:one.c"

    p = Pathname(is_vms=True)
    orig = "[.rel]"
    p.parse(orig)
    assert p.build() == orig
    p.root = "src:[one]"
    assert p.build() == "src:[one.rel]"

    p = Pathname(is_vms=True)
    orig = "[.rel]file.c;1"
    p.parse(orig)
    assert p.build() == orig
    p.root = "src:[one]"
    assert p.build() == "src:[one.rel]file.c;1"
