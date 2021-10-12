from plex import Lexer


class InterfaceLessLexer(Lexer):
    @__(r'\w+\.\s')
    def t_tail_word(self, t):
        self.less(len(t.text) - 2)
        t.type = 'WORD'
        t.value = t.text[:-2]
        return t

    __(r'\.')('DOT')
    __(r'[\.\w]+')('WORD', lambda _: _)
    __(r'\s+')(None)


lex = InterfaceLessLexer()
lex.input('Wow. Flex.js is awesome. ')
token_list = []

for tok in lex:
    token_list.append('(%s,%r,%d,%d)' % (tok.type, tok.value, tok.lineno, tok.lexpos))

result = '\n'.join(token_list) + '\n'
expect = '''\
(WORD,'Wow',1,0)
(DOT,None,1,3)
(WORD,'Flex.js',1,5)
(WORD,'is',1,13)
(WORD,'awesome',1,16)
(DOT,None,1,23)
'''
