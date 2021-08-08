from plex import Lexer


class RuntimeEofLexer(Lexer):
    states = [('comment', 'exclusive')]

    __(r'[ ]')(None)
    __(r'\w+')('WORD')

    @__(r'/\*')
    def t_comment(t):
        t.lexer.begin('comment')

    @__('comment', r'(.|\n)*\*/')
    def t_comment_body_part(t):
        t.type = 'COMMENT'
        t.value = t.value[:-2]
        t.lexer.begin('INITIAL')
        return t

    @__('__eof__')
    def t_eof(t):
        t.type = 'EOF'
        t.lexer.lineno += 1
        return t


output_list = []

lex = RuntimeEofLexer()

lex.input('/* Example: */ Will will not write a real will')

for tok in lex:
    output_list.append('(%s,%r,%d,%d)' % (tok.type, tok.value, tok.lineno, tok.lexpos))
    if tok.type == 'EOF':
        break

lex.input('And /* More... ')

try:
    for tok in lex:
        output_list.append('(%s,%r,%d,%d)' % (tok.type, tok.value, tok.lineno, tok.lexpos))
except Exception:
    output_list.append('An unclosed comment.')


result = '\n'.join(output_list) + '\n'
expect = '''\
(COMMENT,' Example: ',1,2)
(WORD,'Will',1,15)
(WORD,'will',1,20)
(WORD,'not',1,25)
(WORD,'write',1,29)
(WORD,'a',1,35)
(WORD,'real',1,37)
(WORD,'will',1,42)
(EOF,None,1,46)
(WORD,'And',2,0)
An unclosed comment.
'''






