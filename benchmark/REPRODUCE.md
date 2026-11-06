# Reproduce the integration comparison

Run from an extracted package on Linux with `/proc` available. The harness uses only Python's standard library; the frontend interpreter supplies pytest. Provide two existing isolated virtual environments and the untouched extracted corpus explicitly. The harness does not install packages or access the network.

The evaluated target used Python 3.14.8, PyYAML 6.0.3 and packaging 26.3, without Pygments. The evaluated frontend used Python 3.14.8, pytest 9.2.0, pluggy 1.7.0, iniconfig 2.3.1, packaging 26.3 and Pygments 2.21.0. Its environment also contained PyYAML 6.0.3, coverage 7.17.2 and pytest-testmon 2.3.0; plugin autoload is disabled and testmon is not invoked. Different versions are a new compatibility experiment, not the previously verified environment.

Use the packaged `corpus/markdown-3.9.tar.gz`, SHA-256 `d2900fe1782bd33bdbbd56859defef70c2e78fc46668f8eb9df3128138f2cb6a`. Extract it into a new directory. `--corpus` must name its `markdown-3.9` directory. The harness validates all 386 extracted file hashes against `corpus-manifest.json`; extra or changed files are rejected, excluding Python bytecode caches. The corpus is the licensed sdist, which omits upstream legacy text fixtures.

Replace the example absolute paths below with your actual paths. Keep the venv executable path as written, including any symlink; do not replace it with the resolved system executable. Both interpreter paths must be within a venv's `bin` directory so environment sealing stays bounded. Output must be a new directory outside the corpus, fixture tree and both virtual environments.

```sh
python benchmark/portable_integration.py \
  --target-python /absolute/target-venv/bin/python \
  --frontend-python /absolute/frontend-venv/bin/python \
  --corpus /absolute/extracted/markdown-3.9 \
  --output /absolute/new-preflight-output \
  --preflight
```

Preflight validates frozen inputs, snapshots evaluator/product sources and seals both environments without executing the product. To run the entire comparison, use another new output path and omit `--preflight`:

```sh
python benchmark/portable_integration.py \
  --target-python /absolute/target-venv/bin/python \
  --frontend-python /absolute/frontend-venv/bin/python \
  --corpus /absolute/extracted/markdown-3.9 \
  --output /absolute/new-full-output
```

The full run executes 40 cases in 118 fresh processes: 32 fixture variants, R0-R5 and two explicit module-selection probes. Native, one-item atomic-wrapper and SuiteBridge comparisons use independent fresh copies. Direct module-selection probes compare SuiteBridge with a native subset reference. The fixed strict frontend flags, exact callback/trace comparisons, five-skip pristine corpus coverage gate, XML attribution checks, role-based reporting interpretation and 45-second symmetric experimental watchdog are unchanged from evaluator version 2. A diagnostic `--cases` subset can never produce a full gate pass.

Inspect `summary.json`: `integration_pass` must be true, `complete_scope` true, `cases_run` 40, and `case_failures`, `changed_sources` and `changed_environments` empty. The harness preserves failing attempts; process exit zero alone is not proof of acceptance. All commands, logs, artifacts, hashes and cost receipts are retained. The atomic wrapper's interruption XML defect remains a visible baseline observation under `evidence/public-interruption-addendum.md`; native parity remains mandatory. Transport cases F29-F34 are outside this harness.

Harness-only regression checks execute no product or corpus tests:

```sh
python -m unittest discover -s benchmark/integration_tests -v
```

`portable-source-freeze.json` pins all 109 byte-identical fixture sources, both unchanged native helpers, the exact real-corpus variant manifest and the portable contract copies. Its provenance records the validated original preimplementation freeze. `portability-validation.json` records source-only verification that the comparison, process execution and assessment functions remain unchanged. The only adaptation is explicit locations, bounded venv/input validation, portable evidence filenames and source-seal plumbing. No evaluation threshold or test outcome was changed.

Runtime receipts contain paths supplied on your machine and test diagnostics. Review those generated receipts separately before publishing them. This package does not contain historical private workspace paths.
