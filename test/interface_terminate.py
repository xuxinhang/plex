from plex import Lexer


class InterfaceTerminateLexer(Lexer):
    __(r'\d+')('DIG', int)

    @__(r'\s+')
    def t_s(self, t):
        if len(t.text) >= 3:
            self.terminate()


lex = InterfaceTerminateLexer()
lex.input('12  3 456   7 8 90')
token_list = []

for tok in lex:
    token_list.append('(%s,%r,%d,%d)' % (tok.type, tok.value, tok.lineno, tok.lexpos))
token_list.append('~')
for tok in lex:
    token_list.append('(%s,%r,%d,%d)' % (tok.type, tok.value, tok.lineno, tok.lexpos))

result = '\n'.join(token_list) + '\n'
expect = '''\
(DIG,12,1,0)
(DIG,3,1,4)
(DIG,456,1,6)
~
(DIG,7,1,12)
(DIG,8,1,14)
(DIG,90,1,16)
'''
