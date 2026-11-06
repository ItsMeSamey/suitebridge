import unittest
from fixture_support import record


def setUpModule():
    record('support_a', "module.setup")
    unittest.addModuleCleanup(record, 'support_a', "module.cleanup")

def tearDownModule():
    record('support_a', "module.teardown")

class Case(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        record('support_a', cls.__name__, "class.setup")
        cls.addClassCleanup(record, 'support_a', cls.__name__, "class.cleanup")

    @classmethod
    def tearDownClass(cls):
        record('support_a', cls.__name__, "class.teardown")

    def setUp(self):
        record('support_a', self.id(), "test.setup")
        self.addCleanup(record, 'support_a', self.id(), "test.cleanup")

    def tearDown(self):
        record('support_a', self.id(), "test.teardown")

    def test_one(self):
        record('support_a', self.id(), "body")
        self.assertEqual(1, 1)

    def test_two(self):
        record('support_a', self.id(), "body")
        self.assertEqual(1, 1)
