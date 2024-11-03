#
# glob.py - match a string against a simple pattern
# translated from jam/glob.c
#
# Understands the following patterns:
#
# * any number of characters
# ? any single character
# [a-z] any single character in the range a-z
# [^a-z]    any single character not in the range a-z
# \x    match x

BITLISTSIZE = 16


def check_bit(tab: bytearray, bit: int):
    return tab[int(bit / 8)] & (1 << ((bit) % 8))


def match(pat: str, string: str, ignore_case: bool = False):
    i = 0  # pat index
    j = 0  # string index
    while i <= len(pat):
        if i == len(pat):
            # -1 if we have leftovers for string
            return 0 if j >= len(string) else -1

        match pat[i]:
            case "?":
                # any char
                if j >= len(string):
                    return 1
                i += 1
                j += 1
            case "[":
                if j == len(string):
                    return 1

                # scan for matching
                second_idx = pat[i:].find("]")
                if second_idx == -1:
                    return 1

                # build character class bitlist
                bitlist = globchars(pat[i + 1 : second_idx])
                i = second_idx + 1

                if not check_bit(bitlist, ord(string[j])):
                    return 1
                j += 1
            case "*":
                if j == len(string) and (i + 1) == len(pat):
                    return 0

                jj = len(string)  # backwards index for string
                i += 1
                # Try to match the rest of the pattern in a recursive
                # call.  If the match fails we'll back up chars, retrying.
                while jj != j:
                    if i != len(pat):
                        r = match(pat[i:], string[jj:])
                    else:
                        r = 0 if jj == len(string) else -1

                    if r == 0:
                        return 0
                    elif r < 0:
                        return 1

                    jj -= 1
            case "\\":
                i += 1

                # Force literal match of next char.
                if i == len(pat) or string[j] != pat[i]:
                    return 1

                j += 1
            case _:
                if ignore_case and string[j].lower() != pat[i].lower():
                    return 1
                elif j == len(string) or string[j] != pat[i]:
                    return 1

                j += 1
                i += 1


# globchars() - build a bitlist to check for character group match
def globchars(pat: str):
    neg = False
    bitlist = bytearray(BITLISTSIZE)

    i = 0
    if pat[i] == "^":
        neg = True
        i += 1

    while i < len(pat):
        if i + 2 < len(pat) and pat[1] == "-":
            for c in range(pat[0:3]):
                bitlist[ord(c) / 8] |= 1 << (ord(c) % 8)
            i += 3
        else:
            c = ord(pat[i])
            i += 1
            bitlist[int(c / 8)] |= 1 << (c % 8)

    if neg:
        for i in range(len(bitlist)):
            bitlist[i] ^= 0b11111111

    # Don't include \0 in either $[chars] or $[^chars]
    bitlist[0] &= 0b11111110
    return bitlist
