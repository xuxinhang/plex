import re
import sys
import types

# This tuple contains known string types
try:
    # Python 2.6
    StringTypes = (types.StringType, types.UnicodeType)
except AttributeError:
    # Python 3.0
    StringTypes = (str, bytes)


# Exception thrown when invalid token encountered and no default error
# handler is defined.
class LexError(Exception):
    def __init__(self, message, s):
        self.args = (message,)
        self.text = s


# Token class.  This class is used to represent the tokens produced.
class LexToken:
    def __init__(self):
        self.type = self.value = self.lineno = self.lexpos = None

    def __str__(self):
        return 'LexToken(%s,%r,%d,%d)' % (self.type, self.value, self.lineno, self.lexpos)

    def __repr__(self):
        return str(self)


# This object is a stand-in for a logging object created by the
# logging module.

class PlyLogger(object):
    def __init__(self, f):
        self.f = f

    def critical(self, msg, *args, **kwargs):
        self.f.write((msg % args) + '\n')

    def warning(self, msg, *args, **kwargs):
        self.f.write('WARNING: ' + (msg % args) + '\n')

    def error(self, msg, *args, **kwargs):
        self.f.write('ERROR: ' + (msg % args) + '\n')

    info = critical
    debug = critical


# Null logger is used when no output is generated. Does nothing.
class NullLogger(object):
    def __getattribute__(self, name):
        return self

    def __call__(self, *args, **kwargs):
        return self


def wrap_list(x):
    if isinstance(x, (tuple, list)):
        return iter(x)
    else:
        return iter([x])


RULE_MATCH_MODE_STR = 1
RULE_MATCH_MODE_REG = 2


class LexerRule:
    def __init__(self):
        self.states = []
        self.patterns = []
        self.match_mode = []
        self.regexes = []
        self.token_handler = None
        self.token_type = None
        self.token_value_handler = None

    def __repr__(self) -> str:
        s = '(%s, %s) -> ' % (self.states, self.patterns)
        if self.token_handler:
            s += '(%s)' % (self.token_handler,)
        else:
            s += '(%s, %s)' % (self.token_type, self.token_value_handler)
        return s


def _complete_rule(rule: LexerRule, *, reflag: int):
    rule.match_mode.clear()
    rule.regexes.clear()
    for p in rule.patterns:
        if re.escape(p) == p:
            rule.match_mode.append(RULE_MATCH_MODE_STR)
            rule.regexes.append(None)
        else:
            rule.match_mode.append(RULE_MATCH_MODE_REG)
            rule.regexes.append(re.compile(p, reflag))


def _create_rule_adder(lexer, *args):
    if len(args) == 1:
        state, pattern = None, args[0]
    elif len(args) == 2:
        state, pattern = args
    elif len(args) == 0:
        raise TypeError('no argument was given')
    else:
        raise TypeError('too much arguments were given')

    if pattern == '__error__':
        return lambda *args: _add_errorf(lexer, state, *args)
    else:
        return lambda *args: _add_rule(lexer, state, pattern, *args)


def _add_rule(lexer, state, pattern, f=None, value=None):
    rule = LexerRule()

    for s in wrap_list(state):
        if s not in rule.states:
            rule.states.append(s)

    for p in wrap_list(pattern):
        rule.patterns.append(p)

    if f is None:
        pass
    elif callable(f):
        rule.token_handler = f
    else:
        rule.token_type = f
        rule.token_value_handler = value

    lexer._rules.append(rule)
    if rule.token_handler:
        return f


def _add_errorf(lexer, state, f):
    if not callable(f):
        raise LexError('Error handler must be a function.')
    for s in wrap_list(state):
        lexer._errorfs[s] = f
    return f


def _add_states(lexer, state_list):
    lexer._states['INITIAL'] = 'inclusive'
    if state_list is None:
        return
    try:
        _ = iter(state_list)
    except TypeError:
        raise TypeError('states must be iterable')

    for s in state_list:
        if not isinstance(s, tuple) or len(s) != 2:
            raise ValueError("Invalid state specifier %s. Must be a tuple (statename,'exclusive|inclusive')" % repr(s))
        state_name, state_type = s
        if not (state_type == 'inclusive' or state_type == 'exclusive'):
            raise ValueError("State type for state %s must be 'inclusive' or 'exclusive'" % state_name)
        if state_name in lexer._states:
            raise ValueError("State '%s' already defined" % state_name)
        lexer._states[state_name] = state_type


class LexerStoreProxy:
    def __init__(self):
        self._rules = []
        self._states = {}
        self._errorfs = {}


class LexerMeta(type):
    _store_proxies = {}

    @classmethod
    def __prepare__(cls, name, bases):
        proxy = cls._store_proxies[name] = LexerStoreProxy()
        return {'__': lambda *args: _create_rule_adder(proxy, *args)}

    def __init__(self, name, bases, namespace):
        proxy = self.__class__._store_proxies[name]
        self._states = proxy._states
        self._rules = proxy._rules
        self._errorfs = proxy._errorfs

        if hasattr(self, 'states'):
            _add_states(self, self.states)
            del self.states
        else:
            _add_states(self, None)

        self._options = {}
        if hasattr(self, 'options'):
            self._options.append(self.options)
            del self.options

        if hasattr(self, 'reflags'):
            self._reflags = self.reflags
            del self.reflags
        else:
            self._reflags = re.VERBOSE  # default value

        for r in self._rules:
            _complete_rule(r, reflag=self._reflags)

        self.__ = lambda *args: _create_rule_adder(self, self._states, *args)


def sample_match(pattern, ignorecase, s, start=0, end=None):
    if end is None:
        ss = s[start:start+len(pattern)]
    else:
        ss = s[start:min(start+len(pattern), end)]

    if ignorecase:
        return (ss if pattern.lower() == ss.lower() else None)
    else:
        return (ss if pattern == ss else None)


class Lexer(metaclass=LexerMeta):
    def __init__(self):
        self.lexre = None             # Master regular expression. This is a list of
        self.lexretext = None         # Current regular expression strings
        self.lexstatere = {}          # Dictionary mapping lexer states to master regexs
        self.lexstateretext = {}      # Dictionary mapping lexer states to regex strings
        self.lexstaterenames = {}     # Dictionary mapping lexer states to symbol names
        self.lexstaterules = {}
        self.lexstate = 'INITIAL'     # Current lexer state
        self.lexstatestack = []       # Stack of lexer states
        self.lexstateinfo = None      # State information
        self.lexstateignore = {}      # Dictionary of ignored characters for each state
        self.lexstateerrorf = {}      # Dictionary of error functions for each state
        self.lexstateeoff = {}        # Dictionary of eof functions for each state
        self.lexreflags = 0           # Optional re compile flags
        self.lexdata = None           # Actual input data (as a string)
        self.lexpos = 0               # Current position in input text
        self.lexlen = 0               # Length of the input text
        self.lexerrorf = None         # Error rule (if any)
        self.lexeoff = None           # EOF rule (if any)
        self.lextokens = None         # List of valid tokens
        self.lexignore = ''           # Ignored characters
        self.lexliterals = ''         # Literal characters that can be passed through
        self.lexmodule = None         # Module
        self.lineno = 1               # Current line number
        self.lexoptimize = False      # Optimized mode

        self._active_state = None
        self._active_patterns = []
        self._active_errorf = None

        self._activate_state('INITIAL')

    # ------------------------------------------------------------
    # input() - Push a new string into the lexer
    # ------------------------------------------------------------
    def input(self, s):
        # Pull off the first character to see if s looks like a string
        if not isinstance(s[:1], StringTypes):
            raise ValueError('Expected a string')
        self.lexdata = s
        self.lexpos = 0
        self.lexlen = len(s)

    def _activate_state(self, state):
        cls = self.__class__

        if state not in cls._states:
            raise ValueError('Undefined state')

        self._active_state = state
        state_is_inclusive = cls._states[state] == 'inclusive'

        self._active_patterns.clear()
        for r in cls._rules:
            if state in r.states or (state_is_inclusive and None in r.states):
                self._active_patterns += \
                    zip(r.match_mode, r.patterns, r.regexes, [r]*len(r.patterns))

        if state in cls._errorfs:
            self._active_errorf = cls._errorfs[state]
        elif state_is_inclusive and None in cls._errorfs:
            self._active_errorf = cls._errorfs[None]
        else:
            self._active_errorf = None

    def begin(self, state):
        return self._activate_state(state)

    def push_state(self, state):
        self.lexstatestack.append(self.lexstate)
        self._activate_state(state)

    def pop_state(self):
        self._activate_state(self.lexstatestack.pop())

    def current_state(self):
        return self.lexstate

    def skip(self, n):
        self.lexpos += n

    def token(self):
        lexpos = self.lexpos
        lexlen = self.lexlen
        lexdata = self.lexdata

        while lexpos <= lexlen:
            match_obj, match_endpos, match_group, match_len, rule = None, 0, '', 0, None

            for mode, pattern, regex, r in self._active_patterns:
                if mode == RULE_MATCH_MODE_STR:
                    m_obj = sample_match(pattern, False, lexdata, lexpos)
                    if not m_obj:
                        continue
                    m_group = m_obj
                    m_len = len(m_group)
                    m_endpos = lexpos + m_len
                elif mode == RULE_MATCH_MODE_REG:
                    m_obj = regex.match(lexdata, lexpos)
                    if not m_obj:
                        continue
                    m_group = m_obj.group()
                    m_len = len(m_group)
                    m_endpos = m_obj.end()

                if match_obj is None or m_len > match_len:
                    match_obj, match_endpos, match_group, match_len, rule = m_obj, m_endpos, m_group, m_len, r

            if match_obj:
                tok = LexToken()
                tok.value = match_group
                tok.lineno = self.lineno
                tok.lexpos = lexpos
                tok.lexer = self

                token_handler = rule.token_handler
                token_type = rule.token_type
                token_value_handler = rule.token_value_handler

                if token_handler:
                    lexpos = match_endpos

                    # If token is processed by a function, call it
                    self.lexmatch = match_obj
                    self.lexpos = lexpos
                    newtok = token_handler(tok)
                    if newtok:
                        return newtok

                    # Every function must return a token, if nothing, we just move to next token
                    lexpos = self.lexpos         # This is here in case user has updated lexpos.
                    lexignore = self.lexignore      # This is here in case there was a state change
                else:
                    # If no token type was set, it's an ignored token
                    if token_type:
                        tok.type = token_type
                        if token_value_handler:
                            tok.value = token_value_handler(tok.value)
                        self.lexpos = match_endpos
                        return tok
                    else:
                        lexpos = match_endpos
                        continue

            elif lexpos == lexlen:
                return None

            else:
                if self._active_errorf:
                    tok = LexToken()
                    tok.value = self.lexdata[lexpos:]
                    tok.lineno = self.lineno
                    tok.type = 'error'
                    tok.lexer = self
                    tok.lexpos = lexpos
                    self.lexpos = lexpos
                    newtok = self._active_errorf(tok)
                    if lexpos == self.lexpos:
                        # Error method didn't change text position at all. This is an error.
                        raise LexError("Scanning error. Illegal character '%s'" % (lexdata[lexpos]), lexdata[lexpos:])
                    lexpos = self.lexpos
                    if newtok:
                        return newtok
                    else:
                        continue

                self.lexpos = lexpos
                raise LexError("Illegal character '%s' at index %d" % (lexdata[lexpos], lexpos), lexdata[lexpos:])

        assert False

    # Iterator interface
    def __iter__(self):
        return self

    def __next__(self):
        t = self.token()
        if t is None:
            raise StopIteration
        return t
