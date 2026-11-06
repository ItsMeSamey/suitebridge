# SuiteBridge

Run a native `unittest` suite inside a pytest workflow while keeping its native discovery, fixtures and individual outcomes. SuiteBridge runs the suite in your project's Python environment and reports native module groups through pytest and JUnit. A separate JSON report retains each native test, subtest and fixture outcome.

The verified Markdown 3.9 source distribution has 1,024 native test entries and five skips. SuiteBridge preserves that population and produces 31 module reports. With two deliberately injected regressions, it attributes 36 native failures to five modules; a whole-suite wrapper produces one failing item. You can rerun a reported module and see exactly which other groups were omitted.

## Use with your project

Keep the three `suitebridge*.py` files together. The frontend needs pytest 9.2.0. The target interpreter needs your normal test dependencies and does not need pytest. Linux with Python 3.14 is the verified platform. First establish that your target environment runs `python -m unittest discover -s tests` correctly.

From your project's root:

```sh
env PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTEST_ADDOPTS= PYTEST_PLUGINS= \
  PYTHONPATH=/absolute/path/to/suitebridge \
  /absolute/path/to/frontend/bin/python -m pytest \
  -p suitebridge --assert=plain --capture=no \
  -p no:warnings -p no:cacheprovider \
  --native-unittest tests \
  --native-python /absolute/path/to/project-env/bin/python \
  --native-report /tmp/new-native-run/native.json \
  tests --junitxml=/tmp/new-native-run.xml
```

The report's parent directory must not exist. SuiteBridge creates and owns it for this invocation. Give the target venv's executable path directly; the worker preserves that path. Ordinary pytest tests can be added as another positional directory and run in the frontend environment.

Replace the `tests` positional argument with an exact reported module node to rerun it, for example `'tests::native-module[test_extensions]'`. Use a fresh report directory. Other native groups are explicitly omitted and unvalidated. These are module groups, not individual pytest test items.

## Results and failures

`native.json` contains the actual target environment, discovery, selection, completion and ordered native events. Worker files retain stdout, stderr, group results and an event prefix for incomplete runs. Native assertions, errors and unexpected successes fail their module group. An all-skipped group becomes a skipped pytest item. A group with passing and skipped native tests is a passing group with its native skips recorded separately. Native and JUnit skip counts therefore use different units.

Interruption produces an explicitly interrupted non-passing group and exit status 2. Earlier completed modules remain recorded. Missing interpreters, invalid roots, protocol errors and incomplete results produce diagnostics and nonzero outcomes. There is no automatic interpreter fallback or retry. `--native-timeout SECONDS` adds an optional caller-selected watchdog; it is unset by default.

Detected custom suites, custom `run` behavior and noncontiguous module order use the original suite as an atomic group. This preserves the tested native behavior while exposing one coarse pytest item. Individual native pytest selection, testmon, xdist, arbitrary plugin combinations and universal semantic preservation are outside the demonstrated scope. No speed improvement is claimed.

## Reproduce the demo

The package includes the unmodified BSD-licensed Markdown 3.9 source distribution. It omits some legacy fixtures present in the upstream repository. The counts here describe complete native discovery of this pinned source distribution, not the complete upstream repository.

Use separate target and frontend environments. Their dependency versions are listed in `requirements-target.txt` and `requirements-frontend.txt`. If you need to create them, these commands require downloading packages:

```sh
python3.14 -m venv --copies /tmp/suitebridge-target
python3.14 -m venv /tmp/suitebridge-frontend
/tmp/suitebridge-target/bin/python -m pip install -r requirements-target.txt
/tmp/suitebridge-frontend/bin/python -m pip install -r requirements-frontend.txt
```

These are version pins, not a claim of byte-identical fresh installation. The original target used existing installed PyYAML and packaging files. Release validation uses the same existing target and frontend interpreters as the original evidence. Do not put Pygments in the target: the original combined environment added 59 skips; configuring its actual Pygments version instead exposed 20 assertion failures and one error against unchanged upstream expectations.

From the extracted package root, choose new output directories and set the two interpreter paths:

```sh
SB_TARGET=/absolute/path/to/target/bin/python
SB_FRONTEND=/absolute/path/to/frontend/bin/python
python3.14 demo/extract_corpus.py --output /tmp/new-suitebridge-corpus
python3.14 demo/run_demo.py \
  --target-python "$SB_TARGET" --frontend-python "$SB_FRONTEND" \
  --corpus /tmp/new-suitebridge-corpus/markdown-3.9 \
  --output /tmp/new-suitebridge-demo
```

The demo runs three actual invocations: pristine, the fixed R3 injected regression, and one failing module rerun. It checks their expected outcomes and retains full commands, stdout/stderr, native JSON, JUnit XML, a text transcript and an asciicast transcript. The cast is a recording of the demo command's output, not a screen recording. R3 is a known injected workload, not a newly discovered upstream defect.

An actual release-validation run is included as `demo/recorded-transcript.txt` and `demo/recorded-demo.cast`. Only its output-directory path was replaced with `<local-demo-output>`; raw and exported hashes are recorded in `evidence/release-validation.json`.

## Reproduce the correctness checks

`benchmark/REPRODUCE.md` documents the portable full integration runner. It compares the same target environment through direct native execution, a one-item atomic pytest wrapper, and SuiteBridge for all 40 frozen cases. `benchmark/PORTABLE_TRANSPORT.md` documents the separate 12-variant transport runner and its regular-file target interpreter requirement. The release files include their independent fixtures and source pins. A full run usually takes several minutes; timing is recorded without a performance threshold.

See `evidence/RESULT.md` for the original accepted result and retained failed attempts. Local raw evidence was independently audited across 3,519 artifact hashes. The packaged portable runners also passed all 40 integration cases and 12 transport variants from a clean archive extraction, with unchanged product and environment hashes; `evidence/release-validation.json` records that separate run. Public result summaries exclude machine-specific paths; they do not pretend to be the complete original raw archive.

## License and credits

New work began on 2026-11-06. SuiteBridge's new code is MIT-licensed. OpenAI Codex assistance was used for implementation, fixtures, documentation and reviews. Third-party source, dependency provenance and licenses are listed in `THIRD_PARTY_NOTICES.md`. The bundled corpus keeps its upstream license. No contest placement, payment, novelty or generic compatibility claim is made.
