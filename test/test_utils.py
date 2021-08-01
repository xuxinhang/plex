import sys
import io as StringIO


def run_lexer(lexer, data):
    lex = lexer()
    lex.input(data)
    return list(lex)


def redirect_stdio():
    sys.stderr = StringIO.StringIO()
    sys.stdout = StringIO.StringIO()


def restore_stdio():
    sys.stderr = sys.__stderr__
    sys.stdout = sys.__stdout__
