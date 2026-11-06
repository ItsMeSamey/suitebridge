import unittest
from fixture_support import record


class Ignored(unittest.TestCase):
    def test_must_not_be_discovered(self):
        record("ignored", "body")
        self.fail("package load_tests owns child discovery")
