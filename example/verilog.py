"""
   The lexer rules are from PyVerilog (https://github.com/PyHDI/Pyverilog),
   whose license is provided as the following.

   ------------------------------
   Copyright 2013, Shinya Takamaeda-Yamazaki and Contributors

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
"""

import os
import sys
import re
import time
from plex import Lexer


class VerilogLexerPlex(Lexer):
    """ Verilog Lexical Analayzer by Plex"""
    __ = __

    def __init__(self ,error_func):
        super().__init__()
        self.filename = ''
        self.error_func = error_func
        self.directives = []
        self.default_nettype = 'wire'

    def _error(self, msg, token):
        location = self._make_tok_location(token)
        self.error_func(msg, location[0], location[1])
        self.lexer.skip(1)

    def _find_tok_column(self, token):
        i = token.lexpos
        while i > 0:
            if self.lexer.lexdata[i] == '\n':
                break
            i -= 1
        return (token.lexpos - i) + 1

    def _make_tok_location(self, token):
        return (token.lineno, self._find_tok_column(token))

    keywords = (
        'MODULE', 'ENDMODULE', 'BEGIN', 'END', 'GENERATE', 'ENDGENERATE', 'GENVAR',
        'FUNCTION', 'ENDFUNCTION', 'TASK', 'ENDTASK',
        'INPUT', 'INOUT', 'OUTPUT', 'TRI', 'REG', 'LOGIC', 'WIRE', 'INTEGER', 'REAL', 'SIGNED',
        'PARAMETER', 'LOCALPARAM', 'SUPPLY0', 'SUPPLY1',
        'ASSIGN', 'ALWAYS', 'ALWAYS_FF', 'ALWAYS_COMB', 'ALWAYS_LATCH', 'SENS_OR', 'POSEDGE', 'NEGEDGE', 'INITIAL',
        'IF', 'ELSE', 'FOR', 'WHILE', 'CASE', 'CASEX', 'CASEZ', 'UNIQUE', 'ENDCASE', 'DEFAULT',
        'WAIT', 'FOREVER', 'DISABLE', 'FORK', 'JOIN',
    )

    reserved = {}
    for keyword in keywords:
        if keyword == 'SENS_OR':
            reserved['or'] = keyword
        else:
            reserved[keyword.lower()] = keyword

    __([' ', '\t'])(None)

    @__(r'\`.*?\n')
    def t_DIRECTIVE(self, t):
        self.directives.append((self.lexer.lineno, t.value))
        self.lineno += t.value.count("\n")
        m = re.match(r"^`default_nettype\s+(.+)\n", t.value)
        if m:
            self.default_nettype = m.group(1)
        pass

    # Comment
    @__(r'//.*?\n')
    def t_LINECOMMENT(self, t):
        t.type = 'LINECOMMENT'
        self.lineno += t.value.count("\n")
        pass

    @__(r'/\*(.|\n)*?\*/')
    def t_COMMENTOUT(self, t):
        t.type = 'COMMENTOUT'
        self.lineno += t.value.count("\n")
        pass

    # Operator
    __(r'\|\|')('LOR')
    __(r'\&\&')('LAND')

    __(r'~\|')('NOR')
    __(r'~\&')('NAND')
    __(r'~\^')('XNOR')
    __(r'\|')('OR')
    __(r'\&')('AND')
    __(r'\^')('XOR')
    __(r'!')('LNOT')
    __(r'~')('NOT')

    __(r'<<<')('LSHIFTA')
    __(r'>>>')('RSHIFTA')
    __(r'<<')('LSHIFT')
    __(r'>>')('RSHIFT')

    __(r'===')('EQL')
    __(r'!==')('NEL')
    __(r'==')('EQ')
    __(r'!=')('NE')

    __(r'<=')('LE')
    __(r'>=')('GE')
    __(r'<')('LT')
    __(r'>')('GT')

    __(r'\*\*')('POWER')
    __(r'\+')('PLUS')
    __(r'-')('MINUS')
    __(r'\*')('TIMES')
    __(r'/')('DIVIDE')
    __(r'%')('MOD')

    __(r'\?')('COND')
    __(r'=')('EQUALS')

    __(r'\+:')('PLUSCOLON')
    __(r'-:')('MINUSCOLON')

    __(r'@')('AT')
    __(r',')('COMMA')
    __(r';')('SEMICOLON')
    __(r':')('COLON')
    __(r'\.')('DOT')

    __(r'\(')('LPAREN')
    __(r'\)')('RPAREN')
    __(r'\[')('LBRACKET')
    __(r'\]')('RBRACKET')
    __(r'\{')('LBRACE')
    __(r'\}')('RBRACE')

    __(r'\#')('DELAY')
    __(r'\$')('DOLLER')

    bin_number = '[0-9]*\'[bB][0-1xXzZ?][0-1xXzZ?_]*'
    signed_bin_number = '[0-9]*\'[sS][bB][0-1xZzZ?][0-1xXzZ?_]*'
    octal_number = '[0-9]*\'[oO][0-7xXzZ?][0-7xXzZ?_]*'
    signed_octal_number = '[0-9]*\'[sS][oO][0-7xXzZ?][0-7xXzZ?_]*'
    hex_number = '[0-9]*\'[hH][0-9a-fA-FxXzZ?][0-9a-fA-FxXzZ?_]*'
    signed_hex_number = '[0-9]*\'[sS][hH][0-9a-fA-FxXzZ?][0-9a-fA-FxXzZ?_]*'

    decimal_number = '([0-9]*\'[dD][0-9xXzZ?][0-9xXzZ?_]*)|([0-9][0-9_]*)'
    signed_decimal_number = '[0-9]*\'[sS][dD][0-9xXzZ?][0-9xXzZ?_]*'

    exponent_part = r"""([eE][-+]?[0-9]+)"""
    fractional_constant = r"""([0-9]*\.[0-9]+)|([0-9]+\.)"""
    float_number = '((((' + fractional_constant + ')' + \
        exponent_part + '?)|([0-9]+' + exponent_part + ')))'

    simple_escape = r"""([a-zA-Z\\?'"])"""
    octal_escape = r"""([0-7]{1,3})"""
    hex_escape = r"""(x[0-9a-fA-F]+)"""
    escape_sequence = r"""(\\(""" + simple_escape + '|' + octal_escape + '|' + hex_escape + '))'
    string_char = r"""([^"\\\n]|""" + escape_sequence + ')'
    string_literal = '"' + string_char + '*"'

    identifier = r"""(([a-zA-Z_])([a-zA-Z_0-9$])*)|((\\\S)(\S)*)"""

    __(string_literal)('STRING_LITERAL')
    __(float_number)('FLOATNUMBER')
    __(signed_bin_number)('SIGNED_INTNUMBER_BIN')
    __(bin_number)('INTNUMBER_BIN')
    __(signed_octal_number)('SIGNED_INTNUMBER_OCT')
    __(octal_number)('INTNUMBER_OCT')
    __(signed_hex_number)('SIGNED_INTNUMBER_HEX')
    __(hex_number)('INTNUMBER_HEX')
    __(signed_decimal_number)('SIGNED_INTNUMBER_DEC')
    __(decimal_number)('INTNUMBER_DEC')

    @__(identifier)
    def t_ID(self, t):
        t.type = self.reserved.get(t.value, 'ID')
        return t

    @__(r'\n+')
    def t_NEWLINE(self, t):
        self.lineno += t.value.count("\n")
        pass

    @__('__error__')
    def t_error(self, t):
        msg = 'Illegal character %s' % repr(t.value[0])
        self._error(msg, t)


def tokenize_verilog_source(text):
    def my_error_func(msg, a, b):
        sys.write(msg + '\n')
        sys.exit()

    lex = VerilogLexerPlex(error_func=my_error_func)

    time_start = time.time()
    for _ in range(1000):
        ret = []
        lex.input(text)
        while True:
            tok = lex.token()
            if not tok:
                break  # No more input
            ret.append('%s %s %d %d\n' % (tok.value, tok.type, tok.lineno, tok.lexpos))
    time_end = time.time()
    sys.stderr.write(str(time_end - time_start) + '\n')

    return ''.join(ret)


if __name__ == '__main__':
    fname = os.path.normpath(os.path.join(__file__, '../verilog_example_1.v'))
    with open(fname) as fd:
        text = fd.read()

    dump = tokenize_verilog_source(text)
    print(dump)
