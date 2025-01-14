keywords = {
    "<": "LANGLE",
    "<=": "LANGLE_EQUALS",
    "=": "EQUALS",
    ">": "RANGLE",
    ">=": "RANGLE_EQUALS",
    "|": "BAR",
    "||": "BARBAR",
    ";": "SEMICOLON",
    ":": "COLON",
    "!": "BANG",
    "!=": "BANG_EQUALS",
    "?=": "QUESTION_EQUALS",
    "(": "LPAREN",
    ")": "RPAREN",
    "[": "LBRACKET",
    "]": "RBRACKET",
    "{": "LBRACE",
    "}": "RBRACE",
    "&": "AMPER",
    "&&": "AMPERAMPER",
    "+=": "PLUS_EQUALS",
    "actions": "ACTIONS",
    "bind": "BIND",
    "break": "BREAK",
    "case": "CASE",
    "continue": "CONTINUE",
    "default": "DEFAULT",
    "else": "ELSE",
    "existing": "EXISTING",
    "for": "FOR",
    "if": "IF",
    "ignore": "IGNORE",
    "in": "IN",
    "include": "INCLUDE",
    "local": "LOCAL",
    "maxline": "MAXLINE",
    "on": "ON",
    "piecemeal": "PIECEMEAL",
    "quietly": "QUIETLY",
    "return": "RETURN",
    "rule": "RULE",
    "switch": "SWITCH",
    "together": "TOGETHER",
    "updated": "UPDATED",
    "while": "WHILE",
}

SCAN_NORMAL = "n"
SCAN_STRING = "s"
SCAN_PUNCT = "p"
EOF = -1
EOL = "\n"


class LexerError(Exception):
    pass


class LexerToken(object):
    def __repr__(self):
        return f"LexToken({self.type},{self.value!r},{self.lineno},{self.lexpos})"


class Lexer:
    def __init__(self, filename=None):
        self.restart()
        self.lines = []
        self.filename = filename
        self.prevtoken = None

    def set_scanmode(self, mode):
        self.scanmode = mode

    def input(self, text: str):
        self.lines = text.split("\n")

    def nextline(self):
        self.prevpos = self.pos
        self.pos = 0
        self.prevlineno = self.lineno
        self.lineno += 1
        self.lexpos = 1

    def prev(self):
        self.pos = self.prevpos
        self.lineno = self.prevlineno

    def current_lineno(self):
        return self.lineno + 1

    def getchar(self):
        if self.lineno >= len(self.lines):
            return EOF

        line = self.lines[self.lineno]
        if self.pos >= len(line):
            self.nextline()
            return EOL

        self.prevpos = self.pos
        self.prevlineno = self.lineno
        self.pos += 1
        return line[self.prevpos]

    def get_string(self):
        # If scanning for a string (action's {}'s), look for the
        # closing brace.  We handle matching braces, if they match!
        nest = 1
        c = self.getchar()

        res = ""
        while c != EOF:
            if c == "{":
                nest += 1

            if c == "}":
                nest -= 1
                if nest == 0:
                    break

            res += c
            c = self.getchar()

        # We ate the ending brace -- regurgitate it
        if c != EOF:
            self.prev()

        if nest:
            raise LexerError("unmatched {} in action block")

        tok = LexerToken()
        tok.type = "STRING"
        tok.value = res

        return self.next_token(tok)

    def is_space(self, c):
        return c in set([" ", "\t", EOL, "\f", "\r"])

    def next_token(self, tok=None):
        if tok is None:
            self.finished = True
            return None

        tok.lexpos = self.lexpos
        tok.lexer = self
        tok.lineno = self.lineno + 1
        self.lexpos += 1

        if tok.type == "ACTIONS":
            self.actions_block = True

        if self.actions_block:
            if tok.type == "LBRACE":
                self.set_scanmode(SCAN_STRING)

            if tok.type == "STRING":
                self.set_scanmode(SCAN_NORMAL)
                self.actions_block = False

        self.prevtoken = tok
        return tok

    def restart(self):
        self.scanmode = SCAN_NORMAL

        self.pos = 0
        self.finished = False
        self.lineno = 0
        self.lexpos = 1
        self.prevpos = self.pos
        self.prevlineno = self.lineno
        self.actions_block = False

    def token(self):
        inquote = False

        if self.finished:
            return None

        if self.scanmode == SCAN_STRING:
            return self.get_string()

        c = self.getchar()

        while True:
            # Skip past white space
            while c != EOF and self.is_space(c):
                c = self.getchar()

            # Not a comment?  Swallow up comment line.
            if c != "#":
                break

            self.nextline()
            c = self.getchar()

        # c now points to the first character of a token
        if c == EOF:
            return self.next_token()

        # While scanning the word, disqualify it for (expensive)
        # keyword lookup when we can: $anything, "anything", \anything
        notkeyword = c == "$"

        # look for white space to delimit word */
        # "'s get stripped but preserve white space */
        # \ protects next character */
        res = ""
        while c != EOF and (inquote or not self.is_space(c)):
            if c == '"':
                # begin or end
                inquote = not inquote
                notkeyword = 1
            elif c != "\\":
                # normal char
                res += c
            else:
                c = self.getchar()
                if c == EOF:
                    break

                res += c
                notkeyword = True

            c = self.getchar()

        # Check obvious errors.
        if inquote:
            raise LexerError('unmatched " in string')

        # We looked ahead a character - back up.
        if c != EOF:
            self.prev()

        # scan token table
        # don't scan if it's obviously not a keyword or if its
        # an alphabetic when were looking for punctuation
        tok = LexerToken()
        tok.type = "ARG"
        tok.value = res

        if not notkeyword and not (res[0].isalpha() and self.scanmode == SCAN_PUNCT):
            if res in keywords:
                tok.type = keywords[res]

            if tok.type == "INCLUDE":
                if not (
                    self.prevtoken is None
                    or self.prevtoken.type in ("SEMICOLON", "LBRACE", "RBRACE")
                ):
                    tok.type = "ARG"

        return self.next_token(tok)
