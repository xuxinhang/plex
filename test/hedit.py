import sys
from plex import Lexer
from test_utils import redirect_stdio, restore_stdio


class HEditLexer(Lexer):
    __(r'[ \t\n]')(None)

    @__(r'\d+H.*')  # This grabs all of the remaining text
    def t_H_EDIT_DESCRIPTOR(self, t):
        i = t.text.index('H')
        n = eval(t.text[:i])
        # Adjust the tokenizing position
        self.lexpos -= len(t.text) - (i+1+n)
        t.value = t.text[i+1:i+1+n]
        t.type = 'H_EDIT_DESCRIPTOR'
        return t

    @__('__error__')
    def t_error(self, t):
        print("Illegal character '%s'" % t.text[0])
        self.skip(1)


redirect_stdio()

lex = HEditLexer()
lex.input('3Habc 10Habcdefghij 2Hxy')
for tok in lex:
    sys.stdout.write('(%s,%r,%d,%d)\n' % (tok.type, tok.value, tok.lineno, tok.lexpos))

result = sys.stdout.getvalue()
expect = '''\
(H_EDIT_DESCRIPTOR,'abc',1,0)
(H_EDIT_DESCRIPTOR,'abcdefghij',1,6)
(H_EDIT_DESCRIPTOR,'xy',1,20)
'''

restore_stdio()
