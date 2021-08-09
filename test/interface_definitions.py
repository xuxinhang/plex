from plex import Lexer


class InterfaceDefinitionsLexer(Lexer):
    definitions = {
        'ws': r'[ \t\f]+',
        'lf': r'\n',
        'cr': r'\r',
        'crlf': r'\r\n',
    }

    __('{crlf}|{cr}|{lf}')('NEWLINE')
    __('^{ws}')(None)
    __(r'[\w ]+')('INLINE')


lex = InterfaceDefinitionsLexer()
lex.input('FireFox\r\nGoogle Chrome\nOpera\rMaxthon')
token_list = []

print(lex._rules)
for tok in lex:
    token_list.append('(%s,%r,%d,%d)\n' % (tok.type, tok.value, tok.lineno, tok.lexpos))

result = ''.join(token_list)
expect = '''\
(INLINE,'FireFox',1,0)
(NEWLINE,'\\r\\n',1,7)
(INLINE,'Google Chrome',1,9)
(NEWLINE,'\\n',1,22)
(INLINE,'Opera',1,23)
(NEWLINE,'\\r',1,28)
(INLINE,'Maxthon',1,29)
'''
