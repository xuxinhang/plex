from plex import Lexer


class OptionIgnorecaseLexer(Lexer):
    options = {'case-insensitive': True}

    __(r'{.*?}')('BLOCK', lambda s: s[1:-1])
    __(r'if')('IF', lambda _: _)
    __(r'then')('THEN', lambda _: _)
    __(r'else')('ELSE', lambda _: _)
    __(r'fi')('FI', lambda _: _)
    __(r'\s')(None)


result = ''
expect = """\
IF='If' (1,0)
BLOCK='Condition' (1,3)
THEN='Then' (1,15)
BLOCK='Statement' (1,20)
ELSE='Else' (1,32)
BLOCK='Statement' (1,37)
FI='Fi' (1,49)
"""


lex = OptionIgnorecaseLexer()
lex.input('If {Condition} Then {Statement} Else {Statement} Fi')
for tok in lex:
    result += '%s=%r (%d,%d)\n' % (tok.type, tok.value, tok.lineno, tok.lexpos)
