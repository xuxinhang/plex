from plex import Lexer


class CalcLexer(Lexer):

    __(r'\+')('PLUS')
    __(r'-')('MINUS')
    __(r'\*')('TIMES')
    __(r'/')('DIVIDE')
    __(r'\(')('LPAREN')
    __(r'\)')('RPAREN')

    @__(r'\d+')
    def t_NUMBER(self, t):
        t.type = 'NUMBER'
        t.value = int(t.value)
        return t

    @__(r'\n+')
    def t_newline(self, t):
        self.lineno += len(t.value)

    __(r'[ \t]')(None)

    @__('__error__')
    def t_error(self, t):
        print("Illegal character '%s'" % t.value[0])
        self.skip(1)


print(CalcLexer._rules)


my_calc_lexer = CalcLexer()

data = '''
3 + 4 * 10
  + -20 *2
'''

my_calc_lexer.input(data)

for tok in my_calc_lexer:
    print(tok)
