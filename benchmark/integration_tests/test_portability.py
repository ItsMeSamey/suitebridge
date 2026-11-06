"""Portable input/seal regressions; no product or corpus execution."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('portable_harness', Path(__file__).resolve().parents[1] / 'portable_integration.py')
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)


class PortabilityTests(unittest.TestCase):
    def test_all_literal_fixture_sources_are_pinned(self):
        manifest = harness.read(harness.ROOT / 'benchmark/frozen-fixtures/manifest.json')
        freeze = harness.read(harness.ROOT / 'benchmark/portable-source-freeze.json')
        expected = {'benchmark/frozen-fixtures/' + case['project_key'] + '/' + name: digest
                    for case in manifest['projects'] for name, digest in case['source_sha256'].items()}
        self.assertEqual(len(expected), 109)
        self.assertEqual(len(manifest['projects']), 32)
        for name, digest in expected.items():
            self.assertEqual(freeze['files'][name], digest)
            self.assertEqual(harness.sha(harness.ROOT / name), digest)

    def test_freeze_rejects_changed_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'benchmark').mkdir()
            corpus = root / 'corpus'
            corpus.mkdir()
            source = root / 'source.py'
            source.write_text('unchanged')
            (root / 'benchmark/portable-source-freeze.json').write_text(json.dumps({'files': {'source.py': harness.sha(source)}}))
            (root / 'benchmark/corpus-manifest.json').write_text('{}')
            with patch.object(harness, 'ROOT', root), patch.object(harness, 'CORPUS', corpus):
                harness.validate_freeze()
                source.write_text('changed')
                with self.assertRaisesRegex(ValueError, 'frozen source changed'):
                    harness.validate_freeze()

    def test_freeze_rejects_added_corpus_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'benchmark').mkdir()
            corpus = root / 'corpus'
            corpus.mkdir()
            (root / 'benchmark/portable-source-freeze.json').write_text('{"files": {}}')
            (root / 'benchmark/corpus-manifest.json').write_text('{}')
            (corpus / 'extra.txt').write_text('extra')
            with patch.object(harness, 'ROOT', root), patch.object(harness, 'CORPUS', corpus):
                with self.assertRaisesRegex(ValueError, 'Pinned real corpus differs'):
                    harness.validate_freeze()

    def test_cli_requires_explicit_locations(self):
        with patch('sys.argv', ['portable_integration.py', '--output', '/unused/output']):
            with self.assertRaises(SystemExit) as error:
                harness.main()
            self.assertEqual(error.exception.code, 2)


if __name__ == '__main__':
    unittest.main()
