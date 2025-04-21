from jamp.paths import Pathname
from jamp.classes import Vars
from dataclasses import dataclass
from typing import Union
import itertools

MAGIC_COLON = "\x01"
MAGIC_LEFT = "\x02"
MAGIC_RIGHT = "\x03"


def lol_get(lol: list, idx: int):
    if lol and idx < len(lol):
        return lol[idx]

    return []


def var_expand(
    var: str, lol: list | None, state_vars: Union[Vars, dict], keep_max=True
):
    """
    var_expand() - variable-expand input string into list of strings

    Would just copy input to output, performing variable expansion,
    except that since variables can contain multiple values the result
    of variable expansion may contain multiple values (a list).  Properly
    performs "product" operations that occur in "$(var1)xxx$(var2)" or
    even "$($(var2))".

    Returns a newly created list.
    """

    # This gets alot of cases: $(<) and $(>)
    if len(var) == 4 and var[0] == "$" and var[1] == "(" and var[3] == ")":
        if (var[2] == "1") or (var[2] == "<"):
            return lol_get(lol, 0)
        if (var[2] == "2") or (var[2] == ">"):
            return lol_get(lol, 1)

    i = var.find("$(")
    if i == -1:
        return [var] if var else []

    prefix = var[:i]
    depth = 1
    i += 2  # skip $(
    inside = ""

    while i < len(var) and depth:
        match var[i]:
            case "(":
                depth += 1
                inside += var[i]
            case ")":
                depth -= 1
                if depth != 0:
                    inside += var[i]
            case ":":
                inside += MAGIC_COLON
            case "[":
                inside += MAGIC_LEFT
            case "]":
                inside += MAGIC_RIGHT
            case _:
                inside += var[i]
        i += 1

    # Recursively expand variable name & rest of input
    variables = var_expand(inside, lol, state_vars) if len(inside) else []

    has_remainder = i < len(var)
    remainder = var_expand(var[i:], lol, state_vars) if has_remainder else []
    vals_out = []

    # Now produce the result chain
    for var in variables:
        varname = var

        # Look for a : modifier in the variable name
        colon_idx = var.find(MAGIC_COLON)
        edits: Edits = None
        if colon_idx > 0:
            varname = var[:colon_idx]
            edits = var_edit_parse(var[colon_idx + 1 :])

        # Look for [x-y] subscripting
        # sub1 is x (0 default)
        # sub2 is length (-1 means forever)
        left_idx = var.find(MAGIC_LEFT)
        sub1 = 0
        sub2 = 0

        subscript = False

        if left_idx > 0:
            subscript = True
            right_idx = varname[left_idx + 1 :].find(MAGIC_RIGHT)
            parts = varname[left_idx + 1 :][:right_idx].split("-")
            sub1 = int(parts[0]) - 1
            if len(parts) == 1:
                sub2 = sub1 + 1
            elif len(parts) == 2 and parts[1]:
                sub2 = int(parts[1])
            else:
                sub2 = -1

            varname = varname[0:left_idx]

        # Get variable value, specially handling $(<), $(>), $(n)
        value = None

        if varname == "<":
            value = lol_get(lol, 0)
        elif varname == ">":
            value = lol_get(lol, 1)
        elif len(varname) == 1 and varname[0] >= "1" and varname[0] <= "9":
            value = lol_get(lol, int(varname) - 1)
        else:
            value = state_vars.get(varname)
            if value is None:
                value = []

        if not isinstance(value, list):
            value = [value]

        if subscript:
            if sub2 == -1:
                value = value[sub1:]
            else:
                value = value[sub1:sub2]

        if not value and edits and edits.empty is not None:
            value = [edits.empty]

        if value and edits and edits.join is not None:
            value = [edits.join.join(value)]

        for val in value:
            if edits:
                if edits.filemods:
                    val = var_edit_file(val, edits)
                if edits.upshift or edits.downshift:
                    val = var_edit_shift(val, edits)
                if edits.quote:
                    val = var_edit_quote(val)

            vals_out.append(val)

    out = []
    product_args = []

    if prefix:
        product_args.append([prefix])

    product_args.append(vals_out)

    if has_remainder:
        product_args.append(remainder)

    if product_args:
        for pr in itertools.product(*product_args):
            val = "".join(pr)
            out.append(val)

    return out


@dataclass
class Edits:
    f: None | Pathname
    parent: bool = False  # :P -- go to parent directory
    filemods: bool = False  # one of the above applied
    downshift: bool = False  # :L -- downshift result
    upshift: bool = False  # :U -- upshift result
    quote: bool = False  # :Q -- quote
    empty: None | str = None  # E -- default for empties
    join: None | str = None  # J -- join list with char
    zeroed: bool = False


# var_edit_parse() - parse : modifiers into PATHNAME structure
#
# The : modifiers in a $(varname:modifier) currently support replacing
# or omitting elements of a filename, and so they are parsed into a
# PATHNAME structure (which contains pointers into the original string).
#
# Modifiers of the form "X=value" replace the component X with
# the given value.  Modifiers without the "=value" cause everything
# but the component X to be omitted.  X is one of:
#
#  G <grist>
#  D directory name
#  B base name
#  S .suffix
#  M (member)
#  R root directory - prepended to whole path
#
# This routine sets:
#
#  f.xxx = None
#   leave the original component xxx
#
#  f.xxx = string
#   replace component xxx with string
#
#  f.xxx = ""
#   omit component xxx
#
# var_edit_file() below and path_build() obligingly follow this convention.
def var_edit_parse(colon_part: str):
    edits = Edits(f=Pathname())

    def strval(part):
        if len(part) == 0 or part[0] != "=":
            return "", 1

        colon_idx = part.find(MAGIC_COLON)
        if colon_idx > 0:
            return part[1:colon_idx], colon_idx + 2

        return part[1:], len(part[1:]) + 2  # skip modificator + '=' + text

    def fileval(colon_part):
        edits.filemods = True

        if not colon_part or colon_part[0] != "=":
            if not edits.zeroed:
                edits.f.zero()
                edits.zeroed = True

            return None, 1

        val, skip = strval(colon_part)
        return val, skip

    i = 0
    while i < len(colon_part):
        skip = 1
        match colon_part[i]:
            case "L":
                edits.downshift = True
            case "U":
                edits.upshift = True
            case "Q":
                edits.quote = True
            case "P":
                edits.parent = True
                edits.filemods = True
            case "@":
                import pdb

                pdb.set_trace()
            case "E":
                edits.empty, skip = strval(colon_part[i + 1 :])
            case "J":
                edits.join, skip = strval(colon_part[i + 1 :])
            case "G":
                edits.f.grist, skip = fileval(colon_part[i + 1 :])
            case "R":
                edits.f.root, skip = fileval(colon_part[i + 1 :])
            case "D":
                edits.f.directory, skip = fileval(colon_part[i + 1 :])
            case "B":
                edits.f.base, skip = fileval(colon_part[i + 1 :])
            case "S":
                edits.f.suffix, skip = fileval(colon_part[i + 1 :])
            case "M":
                edits.f.member, skip = fileval(colon_part[i + 1 :])
            case _:
                # just ignore for now
                # in original it stops here, but I decided to just skip
                # unexpected chars
                pass

        i += skip

    return edits


# var_edit_file() - copy input target name to output, modifying filename
def var_edit_file(path: str, edits: Edits):
    res_path = Pathname()
    res_path.parse(path)

    # Replace any res_path with edits.f
    if edits.f.grist is not None:
        res_path.grist = edits.f.grist

    if edits.f.root is not None:
        res_path.root = edits.f.root

    if edits.f.directory is not None:
        res_path.directory = edits.f.directory

    if edits.f.base is not None:
        res_path.base = edits.f.base

    if edits.f.suffix is not None:
        res_path.suffix = edits.f.suffix

    if edits.f.member is not None:
        res_path.member = edits.f.member

    # if requested, modify res_path to point to parent
    if edits.parent:
        res_path.keep_only_parent()

    # put filename back together
    return res_path.build()


def var_edit_shift(string: str, edits: Edits):
    # Handle upshifting, downshifting now
    if edits.upshift:
        return string.upper()
    elif edits.downshift:
        return string.lower()


def var_edit_quote(string):
    # Handle quoting now
    return string.replace("\\", "\\\\")


def var_string(var: str, lol: list, state_vars: Union[Vars, dict], alone=False):
    res = ""

    i = 0
    while i < len(var):
        while i < len(var) and var[i].isspace():
            res += var[i]
            i += 1

        begin = i
        dollar_found = False
        while i < len(var) and not var[i].isspace():
            if var[i] == "$" and i < len(var) - 1 and var[i + 1] == "(":
                dollar_found = True
            i += 1

        text = var[begin:i]
        if not dollar_found:
            res += text
        elif alone and text == "$(<)":
            res += "<NINJA_SIGIL>out"
        elif alone and text == "$(>)":
            res += "<NINJA_SIGIL>in <NINJA_SIGIL>n"
        else:
            res += " ".join(var_expand(text, lol, state_vars, keep_max=False))

    return res
