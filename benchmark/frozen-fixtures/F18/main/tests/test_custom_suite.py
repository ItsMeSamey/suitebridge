import unittest
from fixture_support import record


class Case(unittest.TestCase):
    def test_one(self): record("body")

class CustomSuite(unittest.TestSuite):
    def run(self, result, debug=False):
        record("custom_suite.before")
        try:
            return super().run(result, debug)
        finally:
            record("custom_suite.after")

def load_tests(loader, standard_tests, pattern):
    return CustomSuite([Case("test_one")])
