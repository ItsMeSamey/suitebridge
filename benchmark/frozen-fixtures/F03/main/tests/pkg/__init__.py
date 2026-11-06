import unittest
from fixture_support import record


def load_tests(loader, standard_tests, pattern):
    record("package.load_tests", "called")
    return unittest.TestSuite([
        loader.loadTestsFromName("pkg.test_b"),
        loader.loadTestsFromName("pkg.test_a"),
    ])
