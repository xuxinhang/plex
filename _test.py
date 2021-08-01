from plex import Lexer


# tokens = (
#    'NUMBER',
#    'PLUS',
#    'MINUS',
#    'TIMES',
#    'DIVIDE',
#    'LPAREN',
#    'RPAREN',
# )


class CalcLexer(Lexer):
    states = set(['HELLO'])

    __(r'\+')('PLUS')
    __(r'-')('MINUS')
    __(r'\*')('TIMES')
    __(r'/')('DIVIDE')
    __(r'\(')('LPAREN')
    __(r'\)')('RPAREN')

    @__(r'\d+')
    def t_NUMBER(t):
        t.type = 'NUMBER'
        t.value = int(t.value)
        return t

    @__(r'\n+')
    def t_newline(t):
        t.lexer.lineno += len(t.value)

    __(r'[ \t]')(None)

    @__('__error__')
    def t_error(t):
        print("Illegal character '%s'" % t.value[0])
        t.lexer.skip(1)


print(CalcLexer._rules)


my_calc_lexer = CalcLexer()

data = '''
3 + 4 * 10
  + -20 *2
'''

my_calc_lexer.input(data)

for tok in my_calc_lexer:
    print(tok)
