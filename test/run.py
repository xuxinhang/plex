import sys
import os.path
import unittest


sys.path.append(os.path.normpath(os.path.join(__file__, '../..')))


def import_case(module):
    loc = {}
    exec(f'from {module} import result, expect', globals(), loc)
    del sys.modules[module]
    return loc['result'], loc['expect']


class LexRunTests(unittest.TestCase):
    def test_lex_hedit(self):
        result, expect = import_case('hedit')
        self.assertEqual(result, expect)

    def test_lex_state_try(self):
        result, expect = import_case('state_try')
        self.assertEqual(result, expect)


class LexInterfaceTests(unittest.TestCase):
    def test_lex_intf_rules(self):
        self.maxDiff = None
        result, expect = import_case('interface_rules')
        self.assertEqual(result, expect)

    def test_lex_intf_less(self):
        result, expect = import_case('interface_less')
        self.assertEqual(result, expect)

    def test_lex_intf_terminate(self):
        result, expect = import_case('interface_terminate')
        self.assertEqual(result, expect)

    def test_lex_interface_definitions(self):
        result, expect = import_case('interface_definitions')
        self.assertEqual(result, expect)


class LexRuntimeTests(unittest.TestCase):
    def test_lex_runtime_eof(self):
        result, expect = import_case('runtime_eof')
        self.assertEqual(result, expect)


class LexOptionTests(unittest.TestCase):
    def test_lex_option_ignorecase(self):
        result, expect = import_case('option_ignorecase')
        self.assertEqual(result, expect)


unittest.main()
