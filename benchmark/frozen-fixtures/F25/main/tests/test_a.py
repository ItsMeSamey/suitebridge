import unittest
from fixture_support import record


import warnings
warnings.simplefilter("error", UserWarning)
record("warning.import", "error")

class WarningChanges(unittest.TestCase):
    def test_01_warning_errors(self):
        record("warning.body", "raise")
        warnings.warn("deliberate runtime warning", UserWarning)
    def test_02_set_ignore(self):
        record("warning.body", "set_ignore")
        warnings.simplefilter("ignore", UserWarning)
        warnings.warn("ignored warning", UserWarning)
