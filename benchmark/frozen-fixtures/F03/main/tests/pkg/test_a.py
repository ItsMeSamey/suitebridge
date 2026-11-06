import unittest
from fixture_support import record


def setUpModule():
    record('pkg.a', "module.setup")
    unittest.addModuleCleanup(record, 'pkg.a', "module.cleanup")

def tearDownModule():
    record('pkg.a', "module.teardown")

class One(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        record('pkg.a', cls.__name__, "class.setup")
        cls.addClassCleanup(record, 'pkg.a', cls.__name__, "class.cleanup")

    @classmethod
    def tearDownClass(cls):
        record('pkg.a', cls.__name__, "class.teardown")

    def setUp(self):
        record('pkg.a', self.id(), "test.setup")
        self.addCleanup(record, 'pkg.a', self.id(), "test.cleanup")

    def tearDown(self):
        record('pkg.a', self.id(), "test.teardown")

    def test_one(self):
        record('pkg.a', self.id(), "body")
        self.assertEqual(1, 1)
