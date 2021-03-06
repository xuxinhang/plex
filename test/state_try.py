import sys
from plex import Lexer
from test_utils import redirect_stdio, restore_stdio


class StateTryLexer(Lexer):
    tokens = ["PLUS", "MINUS", "NUMBER"]

    states = [('comment', 'exclusive')]

    __(r'\+')('PLUS')
    __(r'-')('MINUS')
    __(r'\d+')('NUMBER', lambda _: _)

    @__(r'/\*')
    def t_comment(self, t):
        self.begin('comment')
        print("Entering comment state")

    @__('comment', r'(.|\n)*\*/')
    def t_comment_body_part(self, t):
        t.type = 'body_part'
        t.value = t.text
        print("comment body %s" % t)
        self.begin('INITIAL')

    __(('INITIAL', 'comment'), r'[ \t]')(None)

    @__(('INITIAL', 'comment'), '__error__')
    def t_error(self, t):
        pass


redirect_stdio()

lex = StateTryLexer()
lex.input("3 + 4 /* This is a comment */ + 10")
for tok in lex:
    sys.stdout.write('(%s,%r,%d,%d)\n' % (tok.type, tok.value, tok.lineno, tok.lexpos))

result = sys.stdout.getvalue()
expect = """\
(NUMBER,'3',1,0)
(PLUS,None,1,2)
(NUMBER,'4',1,4)
Entering comment state
comment body LexToken(body_part,' This is a comment */',1,8)
(PLUS,None,1,30)
(NUMBER,'10',1,32)
"""

restore_stdio()
