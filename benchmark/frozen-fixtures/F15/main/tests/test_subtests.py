import unittest
from fixture_support import record


class Subtests(unittest.TestCase):
    def test_values(self):
        for action in ["pass", "failure", "error", "skip", "failure", "skip"]:
            with self.subTest(label="same"):
                record("subtest", action)
                if action == "failure": self.fail("subtest failure")
                if action == "error": raise ValueError("subtest error")
                if action == "skip": self.skipTest("subtest skip")
