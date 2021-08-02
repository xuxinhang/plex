import re
import sys
from plex import Lexer
from test_utils import redirect_stdio, restore_stdio


class StateTryLexer(Lexer):
    states = [('SA', 'inclusive'), ('SB', 'exclusive')]
    reflags = re.IGNORECASE

    __(['SA', 'SB'], r'\d+')('NUMBER_SX', int)
    __(['SA', 'SB'], [r'-', r'_'])('LINE_SX')
    __(['SA'], r'@')('SYMBOL_AT_SA', None)

    __(r'\d+')('NUMBER', int)
    __(r'[a-z]+')('WORD', None)
    __(r'@')('SYMBOL_AT', None)
    __(r'&')('SYMBOL_AND')
    __([r'-', r'_'])('LINE')

    __('SB', r'&')('SYMBOL_AND_SB', None)

    @__([('SA', r'%'), ('SB', r'\$')])
    def percent_and_dollar(t):
        t.type = 'PERCENT_OR_DOLLAR'
        return t

    @__([None, 'SB'], r'\n')
    def next_line(t):
        if t.lexer._active_state == 'INITIAL':
            t.lexer.begin('SA')
        elif t.lexer._active_state == 'SA':
            t.lexer.begin('SB')
        elif t.lexer._active_state == 'SB':
            t.lexer.begin('INITIAL')
        # sys.__stderr__.write('***\n')
        # sys.__stderr__.write(str(t.lexer._active_matchers))
        # sys.__stderr__.write('\n' + t.lexer._active_state + '\n')


redirect_stdio()

lex = StateTryLexer()

# sys.__stderr__.write(str(lex._rules))
# sys.__stderr__.write('\n')

lex.input('000@&_Hello\n%-011@Hi\n$&0\n-')

for tok in lex:
    sys.stdout.write('%s=%r (%d,%d)\n' % (tok.type, tok.value, tok.lineno, tok.lexpos))

result = sys.stdout.getvalue()
expect = """\
NUMBER=0 (1,0)
SYMBOL_AT='@' (1,3)
SYMBOL_AND='&' (1,4)
LINE='_' (1,5)
WORD='Hello' (1,6)
PERCENT_OR_DOLLAR='%' (1,12)
LINE_SX='-' (1,13)
NUMBER_SX=11 (1,14)
SYMBOL_AT_SA='@' (1,17)
WORD='Hi' (1,18)
PERCENT_OR_DOLLAR='$' (1,21)
SYMBOL_AND_SB='&' (1,22)
NUMBER_SX=0 (1,23)
LINE='-' (1,25)
"""

restore_stdio()