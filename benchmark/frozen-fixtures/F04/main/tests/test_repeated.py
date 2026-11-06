import unittest
from fixture_support import record


class Repeated(unittest.TestCase):
    def test_repeat(self):
        self.calls = getattr(self, "calls", 0) + 1
        record("repeated", self.id(), self.calls)
        self.assertLessEqual(self.calls, 2)

def load_tests(loader, standard_tests, pattern):
    case = Repeated("test_repeat")
    return unittest.TestSuite([case, case])
