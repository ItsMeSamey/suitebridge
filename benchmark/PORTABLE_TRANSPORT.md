# Reproduce the frozen transport checks

These checks cover Linux with Python 3.14. They require two existing virtual environments: a pytest frontend with the pinned frontend requirements, and a separate target with the pinned target requirements and no pytest or Pygments. Create the target virtual environment with `--copies`. The first environment fixture requires a regular executable; the second creates and checks its own symlink alias without modifying either supplied environment.

From the extracted release root, run:

```sh
/path/to/frontend/bin/python -B benchmark/portable_transport.py \
  --frontend-python /path/to/frontend/bin/python \
  --target-python /path/to/target/bin/python \
  --output /path/to/new-transport-results
```

The output directory must not already exist. Interpreter arguments retain their absolute lexical paths, including the alias created for F33. No dependency installation or network operation is performed by this harness. All generated test projects, traces, raw streams, source snapshots and reports are written below the requested output directory. It checks both existing environments for changes before and after the run.

The default run executes all 12 frozen F29-F34 variants and four independent native reference processes. `summary.json` is authoritative only after the batch finishes: it records scope, completion, source stability, environment stability and the overall result. A deliberate abrupt exit, rejected protocol request or cancellation is expected to return nonzero inside its fixture; that is distinct from the harness's overall pass/fail status. Every failure is retained. The 45-second process watchdog and cancellation cleanup checks are unchanged from the original experiment.

The optional `--case F32/cancel_owned_worker` form performs a disclosed targeted recheck. It is not a substitute for the default complete batch; the summary records that the full frozen set was not requested.

## Portable adaptation

This release changes configuration and artifact placement only. The original frozen fixture source hash is `4fdbd8008d10d0b1aae180d345f8417583cb3ffed3a98f5d8b942bc61bdbbd4c`. The exact literal fixture files, expected behaviors, all 12 case assertions and F31 protocol-fault driver are preserved. `transport-fixtures-manifest.json` retains their original hashes and wire contract. The portable harness validates those values before executing a case.

- Interpreter locations are supplied explicitly instead of referring to development workspace siblings.
- The caller supplies a new result directory instead of using the development evidence directory.
- F33 uses the supplied Python 3.14 virtual environments and creates the same isolated target alias beneath its generated project.
- The frozen F30 partial-frame shim contains a historical `/usr/bin/python` shebang. Its bytes remain unchanged. A generated POSIX shell launcher executes that file using the supplied frontend interpreter, passing the original arguments unchanged. This removes a dependency on that historical interpreter location while preserving the shim's partial frame, EOF and exit status 24. The launcher and shim are included in each case's source manifests.
- Source snapshots and receipts describe the caller's actual paths and interpreter hashes. The distributed source itself contains no development workspace paths.

Required release files are `suitebridge.py`, `suitebridge_worker.py`, `suitebridge_protocol.py`, `evidence/public-contract.md`, and `benchmark/portable_transport.py`, `benchmark/transport_fixtures.py`, `benchmark/transport-fixtures-manifest.json`, `benchmark/native_observer.py`. This transport batch does not require the Markdown corpus; the separate real-corpus checks do.
