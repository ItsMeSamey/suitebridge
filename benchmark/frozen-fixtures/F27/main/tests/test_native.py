import unittest
from fixture_support import record


def setUpModule():
    record('mixed.native', "module.setup")
    unittest.addModuleCleanup(record, 'mixed.native', "module.cleanup")

def tearDownModule():
    record('mixed.native', "module.teardown")

class One(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        record('mixed.native', cls.__name__, "class.setup")
        cls.addClassCleanup(record, 'mixed.native', cls.__name__, "class.cleanup")

    @classmethod
    def tearDownClass(cls):
        record('mixed.native', cls.__name__, "class.teardown")

    def setUp(self):
        record('mixed.native', self.id(), "test.setup")
        self.addCleanup(record, 'mixed.native', self.id(), "test.cleanup")

    def tearDown(self):
        record('mixed.native', self.id(), "test.teardown")

    def test_one(self):
        record('mixed.native', self.id(), "body")
        self.assertEqual(1, 1)
