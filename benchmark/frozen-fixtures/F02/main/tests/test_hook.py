import unittest
from fixture_support import record


class Sentinel(unittest.TestCase):
    def test_should_be_omitted(self):
        record("sentinel", "body")
        self.fail("load_tests must replace this sentinel")

def load_tests(loader, standard_tests, pattern):
    record("load_tests", "called")
    class ParameterizedCase(unittest.TestCase):
        def __init__(self, methodName, value):
            super().__init__(methodName)
            self.value = value
        def test_generated(self):
            record("parameterized", self.value)
            self.assertEqual(self.value, 17)
    return unittest.TestSuite([ParameterizedCase("test_generated", 17)])
