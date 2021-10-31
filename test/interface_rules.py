from plex import Lexer


class InterfaceRulesLexer(Lexer):
    options = {'case-insensitive': True}

    states = [('SA', 'inclusive'), ('SB', 'exclusive')]

    __(['SA', 'SB'], r'\d+')('NUMBER_SX', int)
    __(['SA', 'SB'], [r'-', r'_'])('LINE_SX', lambda _: _)
    __(['SA'], r'@')('SYMBOL_AT_SA', None)

    __(r'\d+')('NUMBER', int)
    __(r'[a-z]+')('WORD', lambda _: _)
    __(r'@')('SYMBOL_AT', None)
    __(r'&')('SYMBOL_AND')
    __([r'-', r'_'])('LINE', lambda _: _)

    __('SB', r'&')('SYMBOL_AND_SB', None)

    @__([('SA', r'%'), ('SB', r'\$')])
    def percent_and_dollar(self, t):
        t.type = 'PERCENT_OR_DOLLAR'
        t.value = t.text
        return t

    @__([None, 'SB'], r'\n')
    def next_line(self, t):
        if self._active_state == 'INITIAL':
            self.begin('SA')
        elif self._active_state == 'SA':
            self.begin('SB')
        elif self._active_state == 'SB':
            self.begin('INITIAL')

    __('*', r'.')('OTHER', lambda _: _)


lex = InterfaceRulesLexer()
lex.input('000@&_*Hello\n(%-011@Hi\n$&0)\n-')

result = ''
for tok in lex:
    result += '%s=%r (%d,%d)\n' % (tok.type, tok.value, tok.lineno, tok.lexpos)

expect = """\
NUMBER=0 (1,0)
SYMBOL_AT=None (1,3)
SYMBOL_AND=None (1,4)
LINE='_' (1,5)
OTHER='*' (1,6)
WORD='Hello' (1,7)
OTHER='(' (1,13)
PERCENT_OR_DOLLAR='%' (1,14)
LINE_SX='-' (1,15)
NUMBER_SX=11 (1,16)
SYMBOL_AT_SA=None (1,19)
WORD='Hi' (1,20)
PERCENT_OR_DOLLAR='$' (1,23)
SYMBOL_AND_SB=None (1,24)
NUMBER_SX=0 (1,25)
OTHER=')' (1,26)
LINE='-' (1,28)
"""
