import sys
from plex import Lexer
from test_utils import redirect_stdio, restore_stdio


class StateTryLexer(Lexer):
    tokens = [
        "PLUS",
        "MINUS",
        "NUMBER",
        ]

    states = [('comment', 'exclusive')]

    __(r'\+')('PLUS')
    __(r'-')('MINUS')
    __(r'\d+')('NUMBER')

    @__(r'/\*')
    def t_comment(t):
        t.lexer.begin('comment')
        print("Entering comment state")

    @__('comment', r'(.|\n)*\*/')
    def t_comment_body_part(t):
        t.type = 'body_part'
        print("comment body %s" % t)
        t.lexer.begin('INITIAL')

    __(('INITIAL', 'comment'), r'[ \t]')(None)

    @__(('INITIAL', 'comment'), '__error__')
    def t_error(t):
        pass


redirect_stdio()

lex = StateTryLexer()
lex.input("3 + 4 /* This is a comment */ + 10")
for tok in lex:
    sys.stdout.write('(%s,%r,%d,%d)\n' % (tok.type, tok.value, tok.lineno, tok.lexpos))

result = sys.stdout.getvalue()
expect = """\
(NUMBER,'3',1,0)
(PLUS,'+',1,2)
(NUMBER,'4',1,4)
Entering comment state
comment body LexToken(body_part,' This is a comment */',1,8)
(PLUS,'+',1,30)
(NUMBER,'10',1,32)
"""

restore_stdio()
