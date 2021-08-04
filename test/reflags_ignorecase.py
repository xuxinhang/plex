import re
import sys
from plex import Lexer
from test_utils import redirect_stdio, restore_stdio


class ReflagsIgnorecaseLexer(Lexer):
    reflags = re.IGNORECASE

    __(r'{.*?}')('BLOCK', lambda s: s[1:-1])
    __(r'if')('IF')
    __(r'then')('THEN')
    __(r'else')('ELSE')
    __(r'fi')('FI')
    __(r'\s')(None)


redirect_stdio()

lex = ReflagsIgnorecaseLexer()
lex.input('If {Condition} Then {Statement} Else {Statement} Fi')
for tok in lex:
    sys.stdout.write('%s=%r (%d,%d)\n' % (tok.type, tok.value, tok.lineno, tok.lexpos))

result = sys.stdout.getvalue()
expect = """\
IF='If' (1,0)
BLOCK='Condition' (1,3)
THEN='Then' (1,15)
BLOCK='Statement' (1,20)
ELSE='Else' (1,32)
BLOCK='Statement' (1,37)
FI='Fi' (1,49)
"""

restore_stdio()
