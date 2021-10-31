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
    def __init__(self, *, lexer=None, type=None, text='', leng=None, lineno=None, lexpos=None, value=None):
        self.lexer = lexer
        self.type = type
        self.lexpos = lexpos

        self.leng = len(text) if leng is None else leng  # yyleng
        self.text = text  # yytext
        self.lineno = lineno  # lineno
        self.value = value  # yylval
        self.extra = None  # yyextra
        self.column = NotImplemented  # yycolumn

    def __repr__(self):
        return 'LexToken(%s,%r,%d,%d)' % (self.type, self.value, self.lineno, self.lexpos)


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

    try:
        ts = sre_parse.parse(pattern)
    except re.error:
        raise

    chars = []
    for t in ts:
        if str(t[0]).upper() != 'LITERAL':
            break
        chars.append(t[1])
    else:
        return ''.join((chr(c) for c in chars))
    return None


def match_constant_pattern(pattern, ignorecase, s, start=0, end=None):
    if end is None:
        ss = s[start:start+len(pattern)]
    else:
        ss = s[start:min(start+len(pattern), end)]
    if ignorecase:
        return (ss if pattern.lower() == ss.lower() else None)
    else:
        return (ss if pattern == ss else None)


def inject_pattern_definition(s, d):
    regex = re.compile(r'\{[_a-zA-Z][-_a-zA-Z0-9]*?\}')
    repl = lambda m: '(' + d[m.group()[1:-1]] + ')'  # noqa: E731
    p = ''
    while p != s:
        p, s = s, re.sub(regex, repl, s)
    return s


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
            if (r.state == state or r.state == '*') or\
               (r.state is None and state_is_inclusive):
                pass
            else:
                continue  # this rule is not active under this state

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
                pat = inject_pattern_definition(r.pattern, lexer._definitions)
                try:
                    const_pat = get_constant_pattern(pat)
                except re.error:
                    raise re.error('Invalid regex pattern %s for rule %s' % (pat, r))
                if const_pat is None:
                    try:
                        regex = re.compile(pat, lexer._reflags)
                    except re.error:
                        raise re.error('Invalid regex pattern %s for rule %s' % (pat, r))
                    matcher_match = (MATCHER_MATCH_MODE_REG, pat, regex)
                else:
                    matcher_match = (MATCHER_MATCH_MODE_STR, const_pat, None)

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
        self._options = {'case-insensitive': False, 'reflags': re.VERBOSE}
        if hasattr(self, 'options'):
            self._options.update(self.options)
            del self.options

        self._reflags = self._options['reflags']\
            | (re.IGNORECASE if self._options['case-insensitive'] else 0)

        # collect states into lexer
        self._states = {'INITIAL': 'inclusive'}
        if hasattr(self, 'states'):
            _normalize_states(self, self.states)
            del self.states

        # collect definitions into lexer
        self._definitions = {}
        if hasattr(self, 'definitions'):
            self._definitions.update(self.definitions)
            del self.definitions

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
        self._assigned_next_lexpos = -1
        self._lex_more_buffer = ''
        self._lexpos_current = 0
        self._lex_current_token = None
        self._call_mark_more = False
        self._call_mark_terminate = False

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

    def top_state(self):
        """
        Returns the current lexing state.
        """
        return self._active_state

    def current_state(self):
        return self.top_state()

    def skip(self, n):
        """
        Skip the next n characters.
        """
        self.lexpos += n

    def less(self, n):
        """
        Push back all but the first n characters of the token.
        """
        if self._assigned_next_lexpos == -1:
            self._assigned_next_lexpos = self._lexpos_current
        self._assigned_next_lexpos += n

    def more(self):
        """
        Append the next token to the current one.
        """
        # set the mark
        self._call_mark_more = True

    def terminate(self):
        """
        Terminates the scanner and returns EOF
        """
        self._call_mark_terminate = True

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
            # Find the best match
            match_obj, match_endpos, match_group, match_len, matcher = None, 0, '', 0, None

            for mr in self._active_matchers:
                match_mode, pattern, regex = mr[0:3]

                # match mode 1: simple string match
                if match_mode == MATCHER_MATCH_MODE_STR:
                    m_obj = match_constant_pattern(pattern, reflags_ignorecase, lexdata, lexpos)
                    if not m_obj:
                        continue
                    m_group = m_obj
                    m_len = len(m_group)
                    m_endpos = lexpos + m_len

                # match mode 2: regex match
                elif match_mode == MATCHER_MATCH_MODE_REG:
                    m_obj = regex.match(lexdata, lexpos)
                    if not m_obj:
                        continue
                    m_group = m_obj.group()
                    m_len = len(m_group)
                    m_endpos = m_obj.end()

                # override previous match info
                if match_obj is None or m_len > match_len:
                    match_obj, match_endpos, match_group, match_len, matcher\
                        = m_obj, m_endpos, m_group, m_len, mr

            # Clean values able to be modified from exteral.
            self._assigned_next_lexpos = -1

            if match_obj is not None:
                # There is a match.
                # Create a token as the return value
                tok = LexToken(lexer=self, type=None,
                               text=(self._lex_more_buffer + match_group) if self._lex_more_buffer else match_group,
                               lineno=self.lineno, lexpos=lexpos)
                self._lex_current_token = tok

                handler_type = matcher[3]
                if handler_type == MATCHER_HANDLER_TYPE_TOKEN:
                    # Call the token handler
                    self.lexmatch = match_obj
                    self._lexpos_current = lexpos
                    self.lexpos = lexpos = match_endpos
                    token_handler = matcher[4]
                    handler_return = token_handler(self, tok)

                    # Terminate and return EOF if self.terminate called
                    if self._call_mark_terminate:
                        self._call_mark_terminate = False
                        self.lexpos = lexpos
                        return None

                    # Store tok.text if self.more has been called
                    if self._call_mark_more:
                        self._lex_more_buffer = tok.text
                        self._call_mark_more = False
                    else:
                        self._lex_more_buffer = ''

                    # Use manually assigned next lexpos first
                    if self._assigned_next_lexpos == -1:
                        lexpos = self.lexpos
                    else:
                        lexpos = self._assigned_next_lexpos

                    if handler_return is not tok:
                        tok.type = handler_return
                    if tok.type is None:
                        continue  # ignore this token if the token type as None
                    else:
                        self.lexpos = lexpos
                        return tok  # accept and return the token with a valid token type

                elif handler_type == MATCHER_HANDLER_TYPE_TPVAL:
                    token_type, token_value_handler = matcher[4:6]
                    # If no token type was set, it's an ignored token
                    if token_type is None:
                        lexpos = match_endpos
                        continue
                    else:
                        tok.type = token_type
                        if token_value_handler:
                            tok.value = token_value_handler(tok.text)
                        self.lexpos = match_endpos
                        return tok

            else:
                # No match. There is an error.
                if self._active_errf:
                    tok = LexToken(lexer=self, type='__error__',
                                   text=self.lexdata[lexpos:],
                                   lineno=self.lineno, lexpos=lexpos)
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

        # EOF comes
        if self._active_eoff:
            handler_type, handler_token, _ = self._active_eoff

            tok = LexToken(lexer=self, type='__error__', text='',
                           lineno=self.lineno, lexpos=lexpos)

            if handler_type == MATCHER_HANDLER_TYPE_TOKEN:
                self.lexpos = lexpos
                handler_return = handler_token(self, tok)
                if handler_return is not tok:
                    tok.type = handler_return
                if tok.type is None:
                    return None
                else:
                    return tok

            elif handler_type == MATCHER_HANDLER_TYPE_TPVAL:
                if handler_token is None:
                    return None
                else:
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
