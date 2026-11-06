import unittest
from fixture_support import record


class Sentinel(unittest.TestCase):
    def test_omitted(self): self.fail("empty hook must remove this case")

def load_tests(loader, standard_tests, pattern):
    record("empty.load_tests")
    return unittest.TestSuite()
