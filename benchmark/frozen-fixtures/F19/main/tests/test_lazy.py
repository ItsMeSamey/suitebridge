import unittest
from fixture_support import record


class LazySuite(unittest.TestSuite):
    _cleanup = False
    def __init__(self):
        super().__init__()
        self.iterations = 0
    def __iter__(self):
        self.iterations += 1
        iteration = self.iterations
        record("lazy.iteration", iteration)
        class Case(unittest.TestCase):
            def test_one(self): record("lazy.body", iteration)
        yield Case("test_one")

def load_tests(loader, standard_tests, pattern):
    return LazySuite()
