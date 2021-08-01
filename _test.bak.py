from enum import Enum
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

class MyLexer(Lexer):
    states = set(['HELLO'])
    
    @__(r'[0-9]+')
    def number_handler(t):
        return t
    
    __('fi')('FI')

    pass

@MyLexer.__(r'[a-z]+')
def label_handler(t):
    return t

MyLexer.__('if')('IF')

print(MyLexer._rules)
print(MyLexer._states)
