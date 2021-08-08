import re
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


class LexToken:
    """
    Token class. This class is used to represent the tokens produced.
    """
    def __init__(self):
        self.type = self.value = self.lineno = self.lexpos = None

    def __str__(self):
        return 'LexToken(%s,%r,%d,%d)' % (self.type, self.value, self.lineno, self.lexpos)

    def __repr__(self):
        return str(self)


class LexerAtomRule:
    def __init__(self):
        self.state = None
        self.pattern = ''
        self.token_handler = None
        self.token_type = None
        self.token_value_handler = None

    def __repr__(self):
        s = 'LexerAtomRule(%s, %s)->' % (self.state, self.pattern)
        if self.token_handler:
            s += '(%s)' % (self.token_handler,)
        else:
            s += '(%s, %s)' % (self.token_type, self.token_value_handler)
        return s


def get_constant_pattern(pattern):
    """
    Validate whether the given pattern is a constant pattern.
    If yes, return its constant string. Otherwise, return None.
    """
    try:
        # it's an undocumented module, the extra fallback is provided.
        import sre_parse
        assert callable(sre_parse.parse)
    except Exception:
        return pattern if re.escape(pattern) == pattern else None

    s = ''
    for t in sre_parse.parse(pattern):
        if str(t[0]).upper() != 'LITERAL':
            break
        s += chr(t[1])
    else:
        return s
    return None


def simple_match(pattern, ignorecase, s, start=0, end=None):
    if end is None:
        ss = s[start:start+len(pattern)]
    else:
        ss = s[start:min(start+len(pattern), end)]
    if ignorecase:
        return (ss if pattern.lower() == ss.lower() else None)
    else:
        return (ss if pattern == ss else None)


def _create_rule_adder(lexer, *args):
    rule_list = []

    def append_rule(state, pattern):
        rule = LexerAtomRule()
        rule.pattern, rule.state = pattern, state
        rule_list.append(rule)

    def parse_target(tar):
        if len(tar) == 1:
            pattern, = tar
            if isinstance(pattern, list):
                for t in pattern:
                    parse_target(t if isinstance(t, tuple) else (t,))
            else:
                append_rule(None, pattern)
        elif len(tar) == 2:
            state, pattern = tar
            if isinstance(pattern, list):
                for t in pattern:
                    if isinstance(t, tuple):
                        raise TypeError('Duplicate state assignment.')
                    parse_target((state, t))
            else:
                if isinstance(state, (list, tuple)):
                    for s in state:
                        append_rule(s, pattern)
                else:
                    append_rule(state, pattern)
        else:
            raise TypeError('Invalid value. Accept only "pattern" or "(state, pattern)".')

    parse_target(args)

    def adder(f, value=None):
        f_callable = callable(f)
        if f_callable:
            for r in rule_list:
                r.token_handler = f
        else:
            for r in rule_list:
                if r.pattern == '__error__':
                    raise TypeError('Error handler must be callable.')
                r.token_type = f
                r.token_value_handler = value

        lexer._rules += rule_list
        if f_callable:
            return f

    return adder


def _normalize_states(lexer, state_list):
    try:
        _ = iter(state_list)
    except TypeError:
        raise TypeError("'states' must be iterable.")

    for s in state_list:
        if not isinstance(s, tuple) or len(s) != 2:
            raise TypeError("Invalid state specifier %s. Must be a tuple (statename,'exclusive|inclusive')" % repr(s))
        state_name, state_type = s
        if not (state_type == 'inclusive' or state_type == 'exclusive'):
            raise ValueError("State type for state %s must be 'inclusive' or 'exclusive'" % state_name)
        if state_name in lexer._states:
            raise ValueError("State '%s' already defined" % state_name)
        lexer._states[state_name] = state_type


MATCHER_MATCH_MODE_STR = 1
MATCHER_MATCH_MODE_REG = 2
MATCHER_HANDLER_TYPE_TOKEN = 1
MATCHER_HANDLER_TYPE_TPVAL = 2


def _compile_rules(lexer):
    # translate collected rules to matchers identified by state
    for state in lexer._states:
        state_is_inclusive = lexer._states[state] == 'inclusive'
        matchers, errf, eoff = [], None, None
        for r in lexer._rules:
            if not(r.state == state or (state_is_inclusive and r.state is None)):
                continue
            if r.pattern == '__error__':
                # error handler function
                if not r.token_handler:
                    raise TypeError('Error handler must be a function.')
                if errf is None:
                    errf = r.token_handler
            elif r.pattern == '__eof__':
                # EOF handler
                if eoff is None:
                    if r.token_handler:
                        eoff = (MATCHER_HANDLER_TYPE_TOKEN, r.token_handler, None)
                    else:
                        eoff = (MATCHER_HANDLER_TYPE_TPVAL, r.token_type, r.token_value_handler)
            else:
                # general rules
                constant_pattern = get_constant_pattern(r.pattern)
                if constant_pattern is None:
                    try:
                        regex = re.compile(r.pattern, lexer._reflags)
                    except re.error:
                        raise re.error('Invalid regex pattern for rule %s' % (r,))
                    matcher_match = (MATCHER_MATCH_MODE_REG, r.pattern, regex)
                else:
                    matcher_match = (MATCHER_MATCH_MODE_STR, constant_pattern, None)

                if r.token_handler:
                    matcher_handler = (MATCHER_HANDLER_TYPE_TOKEN, r.token_handler, None)
                else:
                    matcher_handler = (MATCHER_HANDLER_TYPE_TPVAL, r.token_type, r.token_value_handler)

                matchers.append(matcher_match + matcher_handler)

        lexer._compiled[state] = (matchers, errf, eoff)


class LexerStoreProxy:
    def __init__(self):
        self._rules = []


class LexerMeta(type):
    _store_proxies = {}

    @classmethod
    def __prepare__(cls, name, bases):
        proxy = cls._store_proxies[name] = LexerStoreProxy()
        return {'__': lambda *args: _create_rule_adder(proxy, *args)}

    def __init__(self, name, bases, namespace):
        # clean useless attributes
        del self.__

        # collect options into lexer
        self._options = {'ignorecase': False, 'reflags': re.VERBOSE}
        if hasattr(self, 'options'):
            self._options.update(self.options)
            del self.options

        self._reflags = self._options['reflags']\
            | (re.IGNORECASE if self._options['ignorecase'] else 0)

        # collect states into lexer
        self._states = {'INITIAL': 'inclusive'}
        if hasattr(self, 'states'):
            _normalize_states(self, self.states)
            del self.states

        # collect rules into lexer and then compile them
        proxy = self.__class__._store_proxies[name]
        self._rules = proxy._rules
        self._compiled = {}
        _compile_rules(self)


class Lexer(metaclass=LexerMeta):
    def __init__(self):
        cls = self.__class__

        self.lexdata = None           # Actual input data (as a string)
        self.lexlen = 0               # Length of the input text
        self.lexmatch = None
        self.lexpos = 0               # Current position in input text
        self.lineno = 1               # Current line number

        self._active_state = None
        self._active_matchers = []
        self._active_errf = None
        self._active_eoff = None
        self._state_stack = []
        self._activate_state('INITIAL')

        self._reflags_ignorecase = bool(cls._reflags & re.IGNORECASE)

        # shortcuts to lexer class attributes
        self.lexerstates = cls._states
        self.lexeroptions = cls._options
        self.lexerrules = cls._rules

    @property
    def lexstate(self):
        return self._active_state

    def input(self, s):
        """
        Push a new string into the lexer.
        """
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
        self._active_matchers, self._active_errf, self._active_eoff = cls._compiled[state]

    def begin(self, state):
        """
        Change the lexer state.
        """
        return self._activate_state(state)

    def push_state(self, state):
        """
        Save the current lexer state and switch to the new.
        """
        self._state_stack.append(self._active_state)
        self._activate_state(state)

    def pop_state(self):
        """
        Restore and switch to the previous state.
        """
        self._activate_state(self._state_stack.pop())

    def current_state(self):
        """
        Returns the current lexing state.
        """
        return self._active_state

    def skip(self, n):
        """
        Skip the next n characters.
        """
        self.lexpos += n

    def token(self):
        """
        Return the next token.
        TODO: Careful tune for performance is needed.
        """
        reflags_ignorecase = self._reflags_ignorecase
        lexpos = self.lexpos
        lexlen = self.lexlen
        lexdata = self.lexdata

        while lexpos < lexlen:
            # Try to find the best match
            match_obj, match_endpos, match_group, match_len, matcher = None, 0, '', 0, None

            for mr in self._active_matchers:
                match_mode, pattern, regex = mr[0:3]
                if match_mode == MATCHER_MATCH_MODE_STR:
                    m_obj = simple_match(pattern, reflags_ignorecase, lexdata, lexpos)
                    if not m_obj:
                        continue
                    m_group = m_obj
                    m_len = len(m_group)
                    m_endpos = lexpos + m_len
                elif match_mode == MATCHER_MATCH_MODE_REG:
                    m_obj = regex.match(lexdata, lexpos)
                    if not m_obj:
                        continue
                    m_group = m_obj.group()
                    m_len = len(m_group)
                    m_endpos = m_obj.end()

                if match_obj is None or m_len > match_len:
                    match_obj, match_endpos, match_group, match_len, matcher\
                        = m_obj, m_endpos, m_group, m_len, mr

            if match_obj is not None:
                # Create a token as the return value
                tok = LexToken()
                tok.type = None
                tok.value = match_group
                tok.lineno = self.lineno
                tok.lexpos = lexpos

                handler_type = matcher[3]

                if handler_type == MATCHER_HANDLER_TYPE_TOKEN:
                    # Call the token handler
                    self.lexmatch = match_obj
                    self.lexpos = lexpos = match_endpos
                    token_handler = matcher[4]
                    newtok = token_handler(self, tok)
                    if newtok:
                        return newtok
                    # Ignore this token if nothing returned.
                    lexpos = self.lexpos
                    continue

                elif handler_type == MATCHER_HANDLER_TYPE_TPVAL:
                    token_type, token_value_handler = matcher[4:6]
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
            else:
                # No match. There is an error.
                if self._active_errf:
                    tok = LexToken()
                    tok.value = self.lexdata[lexpos:]
                    tok.lineno = self.lineno
                    tok.type = '__error__'
                    tok.lexer = self
                    tok.lexpos = lexpos
                    self.lexpos = lexpos
                    newtok = self._active_errf(self, tok)
                    if lexpos != self.lexpos:
                        lexpos = self.lexpos
                        if not newtok:
                            continue
                        return newtok
                    # Error method didn't change text position at all. This is an error.

                self.lexpos = lexpos
                raise LexError("Illegal character '%s' at index %d" % (lexdata[lexpos], lexpos), lexdata[lexpos:])

        # EOF here
        if self._active_eoff:
            tok = LexToken()
            tok.type = '__eof__'
            tok.lineno = self.lineno
            tok.lexpos = lexpos
            tok.lexer = self

            handler_type, handler_token, _ = self._active_eoff

            if handler_type == MATCHER_HANDLER_TYPE_TOKEN:
                self.lexpos = lexpos
                newtok = handler_token(self, tok)
                if newtok:
                    return newtok
            elif handler_type == MATCHER_HANDLER_TYPE_TPVAL:
                if handler_token is not None:
                    tok.type = handler_token
                    return tok

        self.lexpos = lexpos + 1
        if self.lexdata is None:
            raise RuntimeError('No input string given with input()')
        return None

    # Iterator interface
    def __iter__(self):
        return self

    def __next__(self):
        t = self.token()
        if t is None:
            raise StopIteration
        return t
