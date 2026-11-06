import unittest
from fixture_support import record


import support_a
import support_b

def load_tests(loader, standard_tests, pattern):
    return unittest.TestSuite([
        support_a.Case("test_one"),
        support_b.Case("test_one"),
        support_a.Case("test_two"),
    ])
