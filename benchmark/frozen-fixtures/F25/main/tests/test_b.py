import unittest
from fixture_support import record


import warnings

class WarningObserver(unittest.TestCase):
    def test_later_module(self):
        record("warning.later_module", "before")
        warnings.warn("must remain ignored across module boundary", UserWarning)
        record("warning.later_module", "after")
