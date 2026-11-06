import unittest
from fixture_support import record


def setUpModule():
    record('a', "module.setup")
    unittest.addModuleCleanup(record, 'a', "module.cleanup")

def tearDownModule():
    record('a', "module.teardown")

class One(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        record('a', cls.__name__, "class.setup")
        cls.addClassCleanup(record, 'a', cls.__name__, "class.cleanup")

    @classmethod
    def tearDownClass(cls):
        record('a', cls.__name__, "class.teardown")

    def setUp(self):
        record('a', self.id(), "test.setup")
        self.addCleanup(record, 'a', self.id(), "test.cleanup")

    def tearDown(self):
        record('a', self.id(), "test.teardown")

    def test_one(self):
        record('a', self.id(), "body")
        self.assertEqual(1, 1)

    def test_two(self):
        record('a', self.id(), "body")
        self.assertEqual(1, 1)

class Two(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        record('a', cls.__name__, "class.setup")
        cls.addClassCleanup(record, 'a', cls.__name__, "class.cleanup")

    @classmethod
    def tearDownClass(cls):
        record('a', cls.__name__, "class.teardown")

    def setUp(self):
        record('a', self.id(), "test.setup")
        self.addCleanup(record, 'a', self.id(), "test.cleanup")

    def tearDown(self):
        record('a', self.id(), "test.teardown")

    def test_one(self):
        record('a', self.id(), "body")
        self.assertEqual(1, 1)

    def test_two(self):
        record('a', self.id(), "body")
        self.assertEqual(1, 1)
