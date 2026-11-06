import unittest
from fixture_support import record


def setUpModule():
    record('b', "module.setup")
    unittest.addModuleCleanup(record, 'b', "module.cleanup")

def tearDownModule():
    record('b', "module.teardown")

class One(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        record('b', cls.__name__, "class.setup")
        cls.addClassCleanup(record, 'b', cls.__name__, "class.cleanup")

    @classmethod
    def tearDownClass(cls):
        record('b', cls.__name__, "class.teardown")

    def setUp(self):
        record('b', self.id(), "test.setup")
        self.addCleanup(record, 'b', self.id(), "test.cleanup")

    def tearDown(self):
        record('b', self.id(), "test.teardown")

    def test_one(self):
        record('b', self.id(), "body")
        self.assertEqual(1, 1)

    def test_two(self):
        record('b', self.id(), "body")
        self.assertEqual(1, 1)

class Two(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        record('b', cls.__name__, "class.setup")
        cls.addClassCleanup(record, 'b', cls.__name__, "class.cleanup")

    @classmethod
    def tearDownClass(cls):
        record('b', cls.__name__, "class.teardown")

    def setUp(self):
        record('b', self.id(), "test.setup")
        self.addCleanup(record, 'b', self.id(), "test.cleanup")

    def tearDown(self):
        record('b', self.id(), "test.teardown")

    def test_one(self):
        record('b', self.id(), "body")
        self.assertEqual(1, 1)

    def test_two(self):
        record('b', self.id(), "body")
        self.assertEqual(1, 1)
