#!/usr/bin/env python3
"""Run three real local SuiteBridge workflows and retain their full artifacts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PRODUCT = ['suitebridge.py', 'suitebridge_worker.py', 'suitebridge_protocol.py']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True,
                        help='new directory; existing paths are refused')
    parser.add_argument('--frontend-python', type=Path, required=True)
    parser.add_argument('--target-python', type=Path, required=True)
    parser.add_argument('--corpus', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.absolute()
    output.mkdir(parents=True, exist_ok=False)
    corpus = args.corpus.absolute()
    frontend = args.frontend_python.absolute()
    target = args.target_python.absolute()
    expected_corpus = json.loads((ROOT / 'benchmark/corpus-manifest.json').read_text())
    # The portable integration runner validates the entire corpus manifest.
    actual_files = {p.relative_to(corpus).as_posix(): sha(p) for p in corpus.rglob('*')
                    if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}
    if actual_files != expected_corpus:
        raise RuntimeError('Corpus differs from the pinned Markdown source distribution')
    patches = ROOT / 'benchmark/real-corpus-variants.json'
    variant = next(v for v in json.loads(patches.read_text())['variants'] if v['id'] == 'R3')
    pins = {name: sha(ROOT / name) for name in PRODUCT}
    started = time.monotonic()
    cast = (output / 'demo.cast').open('w')
    transcript = (output / 'transcript.txt').open('w')
    cast.write(json.dumps({'version': 2, 'width': 120, 'height': 30,
                          'timestamp': int(time.time()), 'title': 'SuiteBridge actual local demo'}) + '\n')

    def say(message):
        print(message, flush=True)
        transcript.write(message + '\n')
        transcript.flush()
        cast.write(json.dumps([round(time.monotonic() - started, 6), 'o', message + '\r\n']) + '\n')
        cast.flush()

    results = []
    say('SuiteBridge: native unittest outcomes inside module-level pytest reports')
    say('Real corpus: pinned Markdown 3.9 sdist; R3 is an intentionally injected regression.')
    say('The same existing native environment is used for every stage. No timing-gain claim.')
    for name, mutated, selector, expected in [
        ('pristine', False, 'tests', (0, 1024, 5, 0, 31, 0)),
        ('injected-R3', True, 'tests', (1, 1024, 5, 36, 31, 5)),
        ('selected-module', True, 'tests::native-module[test_extensions]', (1, 20, 0, 4, 1, 1)),
    ]:
        stage = output / name
        stage.mkdir()
        work = stage / 'worktree'
        shutil.copytree(corpus, work, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        if mutated:
            for patch in variant['patches']:
                path = work / patch['path']
                if sha(path) != patch['base_sha256']:
                    raise RuntimeError('Unexpected original corpus file: ' + str(path))
                content = path.read_text()
                if content.count(patch['before']) != patch['expected_occurrences']:
                    raise RuntimeError('Patch occurrence mismatch: ' + str(path))
                path.write_text(content.replace(patch['before'], patch['after']))
                if sha(path) != patch['mutated_sha256']:
                    raise RuntimeError('Mutated file hash mismatch: ' + str(path))
        native = stage / 'results/native.json'
        junit = stage / 'pytest.xml'
        command = [str(frontend), '-m', 'pytest', '-p', 'suitebridge', '--assert=plain',
                   '--capture=no', '-p', 'no:warnings', '-p', 'no:cacheprovider',
                   '--native-unittest', 'tests', '--native-python', str(target),
                   '--native-report', str(native), selector, '--junitxml=' + str(junit)]
        env = dict(os.environ)
        for key in ('PYTHONHOME', 'PYGMENTS_VERSION'):
            env.pop(key, None)
        env.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', PYTEST_ADDOPTS='', PYTEST_PLUGINS='',
                   PYTHONPATH=str(ROOT), PYTHONPYCACHEPREFIX=str(stage / 'pycache'))
        say('\n' + name + ': ' + selector)
        say('Running the actual pytest command; complete output is retained in this stage.')
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        wall = time.monotonic()
        with (stage / 'stdout.txt').open('wb') as stdout, (stage / 'stderr.txt').open('wb') as stderr:
            run = subprocess.run(command, cwd=work, env=env, stdout=stdout, stderr=stderr)
        elapsed = time.monotonic() - wall
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        data = json.loads(native.read_text())
        nodes = list(ET.parse(junit).getroot().iter('testcase'))
        failed = [node.attrib.get('name') for node in nodes
                  if node.find('failure') is not None or node.find('error') is not None]
        counts = data['counts']
        observed = (run.returncode, counts['tests_started'], counts['skipped_entries'],
                    counts['assertion_failures'], len(nodes), len(failed))
        valid = (observed == expected and counts['errors'] == 0
                 and counts['unexpected_successes'] == 0
                 and not data['uncompleted_selected_groups'] and data['worker_reaped'])
        receipt = {'command': command, 'cwd': str(work), 'exit_code': run.returncode,
                   'environment': {key: env[key] for key in ('PYTEST_DISABLE_PLUGIN_AUTOLOAD',
                                  'PYTEST_ADDOPTS', 'PYTEST_PLUGINS', 'PYTHONPATH', 'PYTHONPYCACHEPREFIX')},
                   'wall_seconds': elapsed,
                   'process_cpu_seconds': after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime,
                   'native_counts': counts, 'junit_items': len(nodes), 'failed_modules': failed,
                   'omitted_groups': data['omitted_groups'], 'checks_passed': valid,
                   'native_report_sha256': sha(native), 'junit_sha256': sha(junit)}
        (stage / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
        results.append({'stage': name, 'checks_passed': valid, 'receipt': str(stage / 'receipt.json')})
        say(f"Native: {counts['tests_started']} started, {counts['skipped_entries']} skipped, "
            f"{counts['assertion_failures']} assertion failures. JUnit: {len(nodes)} module items, {len(failed)} failing.")
        for group in failed:
            say('  ' + group)
        if data['omitted_groups']:
            say(f"Omitted native groups: {len(data['omitted_groups'])}; they remain unvalidated in this invocation.")
        say('Expected outcome: ' + ('PASS' if valid else 'FAIL'))
        if not valid:
            break
    unchanged = pins == {name: sha(ROOT / name) for name in PRODUCT}
    passed = len(results) == 3 and all(r['checks_passed'] for r in results) and unchanged
    summary = {'passed': passed, 'source_pins': pins, 'sources_unchanged': unchanged,
               'variant_manifest_sha256': sha(patches), 'stages': results,
               'wall_seconds': time.monotonic() - started,
               'notice': 'Actual command transcript, not a screen recording. Local only; no publication.'}
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    say('\nDemo checks: ' + ('PASS' if passed else 'FAIL'))
    say('Full commands, stdout/stderr, native JSON and JUnit XML: ' + str(output))
    transcript.close()
    cast.close()
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
