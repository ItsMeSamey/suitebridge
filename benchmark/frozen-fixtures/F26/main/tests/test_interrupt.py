import unittest
from fixture_support import record


import sys

class Interrupt(unittest.TestCase):
    def setUp(self):
        record("interrupt.setup")
        self.addCleanup(record, "interrupt.cleanup")
    def test_interrupt(self):
        print("native stdout before interrupt", flush=True)
        sys.stderr.write("native stderr before interrupt\n")
        sys.stderr.flush()
        record("interrupt.body")
        raise KeyboardInterrupt("deliberate native interrupt")
    def tearDown(self): record("interrupt.teardown")
