import unittest
from fixture_support import record


def load_tests(loader, standard_tests, pattern):
    record("load_tests.before_error")
    raise RuntimeError("deliberate load_tests error")
