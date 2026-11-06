# Public reproduction copy

This is a location-sanitized copy of the preimplementation contract. Original SHA-256: `08856b4d06531489be6b4738e3935277a3ca285e078324fc8638e5eac7f88ec3`. The two historical absolute workspace paths and two local venv labels were replaced with portable placeholders or descriptions; no cases, semantic requirements or gates were changed. References to historical evidence describe the original evaluation and are not claims that every internal receipt is distributed in this package. `benchmark/portable_integration.py` runs F01-F28 (32 variants), R0-R5 and two selection probes. F29-F34 are a separate transport evaluation. Read `public-interruption-addendum.md` for the later reviewed role-based reporting interpretation.

---

# Native unittest bridge: frozen contract proposal

STATUS: ACCEPTED FROZEN PERSISTENT-WORKER CONTRACT. The independent corpus critic accepted the bounded contract and native observer, with final acceptance conditional only on the F29-F34 source hashes now attached below. The primary pristine corpus must retain the strongest established native coverage: 1024 discovered tests, 1019 non-skipped and five upstream skips. The ordinary competitor environment produced 64 skips. A subsequent unchanged-source run using the actual installed Pygments 2.21.0 and upstream-supported PYGMENTS_VERSION=2.21.0 produced 20 assertion failures and one error, with five skips and exit 1. That failed probe is retained; a version override does not establish a passing common environment. The chosen architecture therefore uses the existing pytest frontend environment and a persistent native worker in the existing passing no-Pygments target environment. No new dependency or resource is required. The historical 64-skip lane is secondary evidence and cannot qualify the product.

2026-11-06. Source-only protocol proposal, written before bridge implementation or this experiment. No bridge or corpus test was run by this author. The project path is `<PACKAGE_ROOT>`; recording final source/environment hashes must not change the cases, semantics or gates below. The proposed benefit is faithful use of a native unittest suite inside an ordinary pytest workflow, with useful module-level failure attribution. There is no speed, test-selection, pytest-testmon, per-test pytest-item or general compatibility claim.

This is a distinct mechanism and experiment. The failed ChangeProof efficiency result remains closed and must not be replaced, relabeled or rescored using this protocol.

## Qualification and baselines

The existing competitor collection observation is not a stock-pytest result. It used `pytest tests --collect-only -q -p no:cacheprovider --testmon`, collected 1138 items containing 1024 unique identities and 114 duplicates, and exited 2. A new stock-pytest-only comparator is mandatory before attributing that behavior to pytest itself. Collection alone also does not establish execution or fixture behavior.

Before this proposal was finalized, the independent baseline owner completed the required ordinary-configuration stock-only probe. Readback of the new project's `evidence/baselines/runs.json` confirms plugin autoload was disabled, no testmon was enabled, stock pytest exited 2 with a TestSuite collection error, and the native baseline and atomic wrapper both completed 1024 tests with 64 skips. `native-atomic-parity.json` records equality of all eight compared native fields. These observations are retained as prior baseline evidence. They do not replace the stricter warning/capture contract below; its paired baseline probe has not yet run.

The frozen supported pytest frontend envelope is serial execution with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, empty `PYTEST_ADDOPTS`/`PYTEST_PLUGINS`, `--assert=plain`, `--capture=no`, `-p no:warnings` and `-p no:cacheprovider`, plus the bridge only when testing the bridge. Apply the same frontend flags to the atomic comparator. The child interpreter isolates native tests from pytest hooks; the narrow frontend flags still bound the mixed-session claim. Retain earlier ordinary-configuration observations as such. Do not silently switch configurations after seeing fixture outcomes. The product must document or enforce this envelope and may not claim compatibility with default rewriting/capture/warning plugins from this experiment.

Use four comparators in the pinned frontend/target environment pair and fresh invocations:

1. Native unittest discovery and original whole-suite execution in `<TARGET_PYTHON>`, with an observer-only structured result recorder. This is the authoritative target-environment reference.
2. Stock pytest in the existing the explicitly supplied frontend environment, with pytest-testmon and unrelated plugin autoload disabled. It cannot select an independent target interpreter for its collected unittest cases. Its observed 64-skip, duplicate-collection/error behavior and failed true-version override remain secondary compatibility/environment evidence. They are not a same-target correctness baseline or a speed comparison.
3. A minimal atomic pytest wrapper in the explicitly supplied frontend environment: one pytest item invokes the original entire native suite exactly once in the same target the explicitly supplied target environment interpreter as baseline one and emits the same native event format. It has no module splitting or native-test selection. This is the same-goal baseline, not the earlier in-process 64-skip wrapper.
4. The proposed bridge in the same frontend settings, using one persistent target the explicitly supplied target environment worker and the same recorder schema. It uses ordinary contiguous module groups only where it can preserve semantics. Unsupported structure must preserve the entire original suite atomically or fail explicitly before execution. It may never silently flatten, sort, duplicate, reconstruct or discard tests.

The reference event recorder must be independent of the bridge. Baseline three may share that recorder with baseline one, so any advantage cannot come merely from giving the new tool better logging. Recorder hooks observe outcomes; they may not replace test methods, alter fixture lifecycle, change warning policies or convert the suite into per-test pytest executions. Custom/lazy suites must not be traversed merely to manufacture an inventory if traversal changes their behavior. For those cases record actual native events and fixture traces, label undiscoverable pre-run counts unknown, and preserve the original suite's execution.

The frontend has pytest 9.2 and Pygments 2.21.0. The target has no Pygments and is the existing passing environment with 1024 discovered tests and five skips. Baselines one and three and the bridge must agree on that target environment and coverage. Falling back to frontend execution or accepting 59 extra skips invalidates the primary comparison. Pin both interpreter binaries, dependency distributions, warning configuration, source hashes and command lines before running the bridge comparison.

## Worker architecture and command binding

The frontend command has the concrete interface `python -m pytest -p suitebridge --native-unittest tests --native-python /absolute/target/python --native-report /new/output/native.json tests ordinary_pytest_tests --junitxml /new/output/pytest.xml`, together with the fixed frontend flags above. `--native-root PATH` optionally specifies the native project root; its default is the invocation working directory. `--native-unittest` identifies one native discovery root relative to that project, not every pytest path. Ordinary pytest files outside that root retain ordinary collection. The native root is collected once by the bridge and excluded from stock unittest collection. The worker uses the specified absolute interpreter path, preserving its virtual-environment path rather than resolving a symlink to the system Python. It may not silently substitute the frontend interpreter.

Ordinary group node IDs are `<native-root-relative-path>::native-module[<native-module-name>]`, for example `tests::native-module[test_apis]`. Whole-suite fallback is `tests::native-suite[atomic]`. Native test IDs remain unchanged inside the separate native report. A selected module node denotes an entire native group; it does not denote one native test.

One worker is started per native invocation. It imports/discovers the native suite once, retains its original TestCase objects and suite structure, and returns a finite group plan. After pytest selection, the frontend sends the final selected group list once in native order. Execute each selected group at most once. Preserve target interpreter globals, imports, fixture state and warning-filter semantics across group commands. No worker restart or per-group fresh interpreter may masquerade as equivalent execution. Unsupported custom structures require an original-suite atomic plan before execution.

For exact ordinary unittest.TestSuite wrappers, the planner may copy/prune the suite tree into contiguous module groups while retaining every original TestCase instance and native order. This permits grouping infrastructure, not reconstruction of native cases or bypass of custom suite semantics. A custom/lazy suite or custom TestCase.run/__call__ requires preservation through the original atomic suite or an explicit unsupported result. The frozen fixture traces determine whether the ordinary copied tree is actually equivalent on the supported envelope.

Use an explicit separate inherited pipe/file descriptor for framed command/result messages. Test stdout/stderr must not share the protocol channel. Redirect them to retained files, not undrained pipes that can deadlock on buffer capacity, and associate output with the active group where possible. JSON-looking test output, binary bytes or large output may not corrupt protocol framing. Messages carry schema version, invocation ID, monotonically increasing sequence and group identity; reject duplicates, unknown groups and out-of-order execution rather than rerun a group.

The frozen wire format is a four-byte unsigned big-endian length followed by UTF-8 JSON, with a maximum frame size of 1 MiB. This is a protocol-format bound, not a claimed host resource quota. Bulk event/traceback data stays in files. Inherited descriptor names are SUITEBRIDGE_COMMAND_FD and SUITEBRIDGE_RESPONSE_FD; invocation identity is SUITEBRIDGE_INVOCATION_ID. Every message contains schema_version=1, type, sequence, invocation_id and group_id, using null group_id for nongroup messages. Each direction has its own monotonically increasing sequence starting at zero.

Worker messages begin with `plan`, containing groups with group_id/module_name/test_count/test_occurrences/mode, actual environment and loader errors. Frontend sends `select` with selected_groups, receives `selected`, sends `run` with group_id, and receives `group_result` with status and a relative artifact path plus SHA256. At completion frontend sends `finish` and receives `finished` with final artifact path and SHA256. Invalid requests produce `error` with code invalid_request and nonzero worker termination without extra execution. Artifact paths remain beneath the invocation output directory. Native event JSONL is flushed incrementally so abrupt exit retains its acknowledged prefix. No automatic retry is permitted.

The target process must remove frontend PYTHONPATH/package paths and pytest-specific import configuration from its import environment, then explicitly insert the native project root. Record its actual sys.executable, sys.path, package versions and Pygments absence. Loading the frontend's Pygments into the child to make pytest available is prohibited. The worker uses the target standard library and does not import pytest. The mixed pytest test population runs in the frontend interpreter and is explicitly a separate environment.

Unexpected worker exit/EOF, invalid protocol, partial frame, interruption or failure to write the final native artifact is an incomplete run with nonzero session status. Retain the last acknowledged events and mark every unacknowledged/remaining group incomplete or unexecuted. Do not infer success from an empty response, a prior successful group or a stale output file. The frontend owns the worker process group and terminates/reaps it on cancellation or watchdog expiry; no retry is automatic.

The native report schema is version 1. It records invocation identity, actual target environment, discovery status, overall completion status, planned groups, selected groups, executed groups, native test occurrences and ordered events. Each event has a sequence number, callback/outcome kind, unchanged native ID, parent ID where applicable, occurrence ordinal, group identity, and skip reason or exception type/message where applicable. Repeated native IDs have distinct occurrence ordinals. Fixture events may have no started TestCase occurrence and retain their native error-holder identity. Store all start/stop, success, failure/error, skip, expected failure, unexpected success and subtest callbacks. Preserve raw tracebacks/output separately. Counts distinguish native tests started, skipped entries, expected failures, assertion failures, errors, subtest events and pytest group items. Unknown pre-run custom-suite inventory is null with a reason, never an invented empty inventory.

## Real source-distribution cases

Keep the same pinned BSD-3-Clause Markdown 3.9 PyPI source distribution, archive SHA256 `d2900fe1782bd33bdbbd56859defef70c2e78fc46668f8eb9df3128138f2cb6a`. Its unavailable upstream legacy fixtures remain excluded from the scope claim. Native `load_tests` behavior must be respected. The original ChangeProof corpus outcomes are prior knowledge, not hidden validation data for this experiment.

Freeze these six independent variants against the identical untouched base, with original patch hashes taken from WORKLOAD.json. The combined variant applies both disjoint exact patches. No variant may be dropped or replaced based on outcome:

| ID | Source state | Purpose |
| --- | --- | --- |
| R0 | Untouched pinned sdist | Native discovery, skips and execution parity |
| R1 | Original C01 metadata-key normalization patch | Localized real-suite failure attribution |
| R2 | Original C16 footnote-class patch | A second independent real-suite failure area |
| R3 | C01 and C16 together | Concurrent failure attribution to distinct native modules |
| R4 | Original C15 new discoverable test | Added-test discovery and intentional failure reporting |
| R5 | Original C28 renamed test | Removed-test discovery without stale items |

Native baseline output determines the exact expected events for each variant. Do not infer that R3 has the sum of R1/R2 failures without executing the independent reference. R4 is an intentionally incorrect test expectation, not a discovered production defect. Restore the entire source tree before every comparator. Do not reuse imports, suite objects, bytecode or test-created files across processes.

## Fixed adversarial fixture families

Create these small independent fixture projects and freeze their source hashes before bridge implementation. They are semantic checks, not substitutes for the real library. Their expected callback/fixture trace is specified from native unittest behavior, then verified by the independent reference. All fixture actions append explicit tokens to a trace; capture must not depend on parsing human-readable unittest output.

| ID | Required fixture |
| --- | --- |
| F01 | Two modules, each with two classes and two passing methods; trace module/class/test setup, body, teardown and cleanup order. |
| F02 | Module `load_tests` replaces automatic tests, omits a deliberately failing sentinel and adds a parameterized TestCase instance requiring constructor arguments. Preserve the exact returned instance behavior. |
| F03 | Package `load_tests` controls child discovery and returns an explicit order different from filesystem order. Do not discover its children a second time. |
| F04 | `load_tests` deliberately includes duplicate test IDs and repeated occurrences of a TestCase. Preserve the native occurrence count and order; duplicate IDs are not universally invalid. |
| F05 | Successful module setup/teardown with multiple `addModuleCleanup` callbacks, verifying LIFO cleanup after all module cases. |
| F06 | Module setup raises after registering cleanups; verify zero test bodies, the native error holder, and cleanup execution. |
| F07 | Module setup raises SkipTest after registering cleanups; preserve fixture skip identity and cleanup trace. |
| F08 | Module teardown raises; preserve its error event after all bodies and still execute registered module cleanups. |
| F09 | Class setup raises after registering `addClassCleanup`; no test bodies, correct class error holder and cleanup order. |
| F10 | Class setup skips after registering cleanup; preserve class skip and cleanup behavior. |
| F11 | Class teardown raises; preserve the error and class cleanup trace. |
| F12 | Test setup raises after `addCleanup`; body/teardown and cleanup behavior must match native exactly. |
| F13 | A failing test body followed by a failing teardown and two cleanups, one failing. Retain every distinct event and continue remaining cleanups. |
| F14 | Passing test, decorated skip, expected failure and unexpected success in one module. Preserve all four native outcome kinds; unexpected success must fail the session. |
| F15 | One test with passing, failing, erroring and skipped subtests, including repeated identical subtest labels. Preserve parent identity, occurrence multiplicity, ordering and all events. |
| F16 | Native suite order A1, B1, A2 across modules. Preserve native module re-entry and teardown behavior; do not sort by module or merge noncontiguous segments. Atomic fallback is acceptable. |
| F17 | Noncontiguous classes A1, B1, A2 within one module. Preserve class re-entry and cleanup order. |
| F18 | Custom TestSuite.run adds before/after trace tokens around original native execution. The override must execute exactly once. Atomic fallback is acceptable. |
| F19 | Custom/lazy suite iteration has an observable counter and supplies tests at run time. No extra inventory traversal may consume or change it. Atomic fallback or explicit unsupported rejection is required if faithful execution cannot be established. |
| F20 | Custom TestCase.run observes cumulative result.testsRun before and after each test across modules. Fresh per-module results must not silently reset visible state. Atomic fallback is acceptable. |
| F21 | A test module raises an import-time exception beside a healthy module. Preserve the healthy native execution and failed-test placeholder, explicit loader errors and failure status. Never report an all-pass partial suite. |
| F22 | A syntax-invalid test module beside a healthy module, plus a separate load_tests exception variant. Preserve each discovery error and distinguish it from a passing or empty suite. |
| F23 | Empty discovery, and a separate load_tests-returned-empty-suite variant. No fabricated passing pytest item or native test. Empty-session exit behavior must be explicit. |
| F24 | Three fresh-process versions of one fixture: base, added test, removed test. Inventories and reports must update without stale native IDs or pytest nodes. |
| F25 | Import-time warnings.simplefilter('error') and a later runtime warning, with a second module observing the filter state. Detect pytest warning-context changes that alter native behavior. |
| F26 | Test output on stdout/stderr and fixture output, then a KeyboardInterrupt in a body. Preserve output custody and an interrupted/incomplete result rather than a completed pass. Run this as its own process. |
| F27 | Mixed invocation containing independent ordinary pytest function tests and a bridged native suite. Verify both populations execute exactly once with separate namespaces and honest counts. |
| F28 | Three ordinary native modules with two independently failing modules and one passing module. Verify module-level failure nodes, module-level JUnit attribution and an explicit group-selection invocation selecting only one named native module. |
| F29 | A native case writes JSON-shaped text, non-UTF8 bytes and output larger than an ordinary pipe buffer to stdout/stderr. The dedicated protocol stays valid, raw output is retained, no test is repeated and no undrained-output deadlock occurs. |
| F30 | Controlled unexpected worker exit during a test, plus a separate partial-protocol-frame/EOF variant. Frontend records the acknowledged prefix and incomplete remainder, exits nonzero and never creates a pass for the interrupted group. |
| F31 | Protocol-only fault checks send a duplicate sequence, unknown group, out-of-order group and malformed frame in separate invocations. Reject before an unintended/repeated test body, preserve evidence and terminate/reap the worker. These are local harness faults, not network or cyber tests. |
| F32 | Cancel the frontend after a fixture has entered an observable body. Verify worker process-group cleanup, interruption status and no successful final artifact. Keep this controlled local cancellation separate from ordinary test failures. |
| F33 | Mixed frontend/target environment fixture: ordinary pytest code confirms frontend Pygments availability while the native case confirms its absence and the expected target sys.executable/sys.prefix. Also probe a symlinked venv interpreter path to ensure the child does not escape into system Python. |
| F34 | Nonexistent target interpreter and a regular file supplied as the native project root in separate invocations. Reject before any test body, report the concrete preflight error and never substitute another interpreter or directory. This fixture does not claim coverage of every invalid discovery path or path traversal. |

The listed multi-version families contain only the named variants, not an adaptive search. Any additional fixture needed after a discovered defect is a supplemental regression check and cannot replace an inconvenient frozen case.

A shared TestResult across separately executed module suites is not automatically equivalent to one native outer suite. Its `_previousTestClass` state can cause duplicate teardown after a segment has already performed final teardown. Fresh results have the opposite risk of resetting cumulative counters. Exact traces and F16-F20 must resolve this; an assertion of lifecycle preservation is insufficient.

Native warning-filter changes must persist across native groups as they do during one TextTestRunner invocation, then be restored after the final selected native group inside the target worker. F25 and F27 must also observe frontend warning state from an ordinary pytest test after the native group block: child warning changes must not leak across the process boundary, matching the coarse subprocess baseline. Merely entering a fresh native warnings context for each module is not equivalent. Custom TestCase.run or __call__ overrides may require original-suite atomic fallback to preserve cumulative Result state; the fallback must be visible.

## Comparison contract

For R0-R5 and every supported fixture variant, native and bridge must have identical ordered native occurrence inventories where these can be observed without changing execution. Preserve native duplicate-ID multiplicities. Compare complete event multisets and their chronological parent association, including test start/stop, success, failure, error, skip, expected failure, unexpected success, subtest outcome, fixture error/skip and interruption. Compare exact fixture/cleanup trace order, not only final counts.

Normalize only environmental location differences: the fresh temporary root, clearly identified interpreter/library prefixes in traceback formatting, and duration fields. Do not normalize away test/module names, subtest parameters, exception types/messages, outcome kind, duplicate occurrence, warnings, fixture tokens or ordering. Save original unnormalized artifacts alongside comparisons. Where standard pytest cannot expose a native event, report the field unavailable; do not invent parity from item counts.

The bridge passes a supported case only when every native event and fixture token is preserved, no extra event/body/fixture action is introduced, and the CLI/report outcomes agree with the declared mapping. Skips and expected failures are not ordinary passes. A matching partial result is not a complete reference inventory. For deliberate discovery-error fixtures, a complete evaluation can correctly show a broken collection with explicit loader errors, healthy-case execution and nonzero exit; it cannot claim the underlying inaccessible module's tests were discovered or passed. This is an error-handling contract, not the earlier selector experiment's complete-inventory gate.

For explicitly unsupported custom/lazy cases, rejection must happen before any test body and be visible in terminal, machine-readable report and nonzero exit. Unsupported rejection is truthful but does not establish compatibility. Count and list it separately. Ordinary module/class lifecycle, standard load_tests, all standard outcome types, real R0-R5 and mixed pytest integration may not be rejected to obtain a pass. Prefer original-suite atomic fallback for opaque structures; report that fallback and its coarse pytest granularity.

## CLI and report semantics

Freeze the CLI option names, output schema and aggregation mapping before implementation. A native assertion failure, error, unexpected success or discovery-error placeholder must yield pytest failure status, never exit 0. Pytest usage errors, interruption, internal plugin errors and empty selection must remain distinguishable. A pytest collection failure may legitimately use a different numeric exit from native unittest; record that difference explicitly instead of pretending numeric parity. Zero native tests is zero, even where native unittest and pytest have different empty-session exit conventions.

Ordinary pytest node IDs represent native module groups, not individual native tests. Terminal and reports must label that unit. `-k`, node selection and any supported rerun operation act at that same group granularity; unsupported per-native-test operations must fail clearly. No pytest-testmon, xdist, per-native-test fixture injection or arbitrary plugin compatibility is claimed without a separate experiment.

Standard pytest `--junitxml` reports one testcase per actual pytest item, including group items. Its tests/failures/errors/skipped attributes must agree with the actual XML child elements and the declared group-level mapping. Parse the XML with an independent XML parser; do not inspect only a screenshot or string fragment. Attach or link a separate native event artifact carrying every native test/subtest/fixture identity and outcome. If a separate per-native-test XML report is offered, validate its counts and multiple-event representation independently; never relabel coarse pytest group XML as native per-test XML.

A mixed group may pass as a group while containing native skips or expected failures, but no UI field may describe those native cases as passed. An all-skipped or zero-execution group must not be presented as containing successful native tests. Failure details must name the native failing identities and exception types, including failures that occur in module/class fixtures without a started TestCase. Deliberate interrupts and infrastructure errors must leave a valid incomplete-status artifact or an explicit report-generation error, not a stale successful artifact from an earlier invocation.

Each invocation writes to a new output directory and refuses overwrite. Seal fixture/project/environment/tool source and preserve stdout, stderr, command, exit, status, wall/CPU time, all native events, fixture trace, pytest collection/outcome events and parsed JUnit summary. A symmetric watchdog may identify a hang as an incomplete experimental outcome; do not invent a user/provider resource quota. No retries or exclusions chosen after seeing results.

## Correctness and usefulness gates

Correctness requires zero lost, duplicated, reclassified or invented native events and zero fixture-trace differences on all mandatory supported cases and R0-R5. Every rejected/fallback case is reported. No known incorrect native behavior may be hidden behind a matching aggregate pytest item count. An independent reviewer must verify retained artifacts and rerun the documented product workflow after implementation, using the same frozen environment.

Usefulness requires all of the following, measured against the three baselines:

1. A real same-environment stock-pytest-only incompatibility must be observed and accurately localized, or another concrete native-suite integration limitation established. The old testmon-enabled collection count is insufficient.
2. One ordinary pytest invocation must execute both native-discovered tests and independent pytest function tests without rewriting the third-party tests, dropping native load_tests behavior or double collection.
3. The bridge must expose distinct failing native module groups as actionable pytest node IDs and standard JUnit entries on the real concurrent-failure probe R3 and F28. The atomic wrapper's single failure node is the comparison. Nested native identities must remain complete for both tools.
4. An explicit module-group selection must run exactly the selected native group under the same declared lifecycle semantics and leave omitted groups visibly unexecuted. It must not pretend that pytest selected individual native cases.
5. The installation/configuration and invocation must be reproducible from a clean documented environment. No application-specific edits to the Markdown tests are allowed apart from the frozen probes.
6. The pytest frontend must retain its existing dependencies while native execution retains the stronger target coverage of 1019 non-skipped tests and five upstream skips. Both native and coarse-subprocess references must verify the same target behavior. No extra 59-skip lane, changed golden output or hidden dependency replacement may satisfy this gate.

Generic JUnit generation alone is not sufficient: existing native unittest XML-reporting tools already provide that function. A generic subprocess wrapper or atomic pytest item already offers a shared pytest command and output capture. If the bridge cannot add reliable, actionable module-level integration while preserving native behavior, reject its claimed usefulness. Also reject a success obtained by requiring wholesale atomic fallback on the real corpus or by recreating individual native TestCases as pytest items.

Meeting these gates would establish a bounded interoperability improvement over the measured stock pytest and atomic-wrapper behavior. It would not establish novelty, broad ecosystem compatibility, superior speed, a contest win or likely cash payment. The independent critic may still reject a technically correct implementation if the integration advantage is too small to justify the project.

## Literal source freeze

Before bridge implementation, the protocol author materialized 32 independent project variants covering F01-F28, totaling 109 files, under the new project's `benchmark/frozen-fixtures/`. `benchmark/fixtures.py` is the literal source generator; `manifest.json` contains every generated source hash. All generated Python sources were AST-parsed without importing or executing any fixture; F22/syntax's intentionally invalid module was checked to raise SyntaxError. The F19 construction note records a pre-execution correction that moved a required-argument TestCase definition inside lazy iteration so default loading would not instantiate it before the hook. No observed fixture outcome motivated that correction.

- Generator SHA256: `58e708fa0af913517062e5b5805f70a30935ae117e61b6994caf9f83ceecf644`.
- Generated fixture manifest SHA256: `3b1352b6d148bf9588123590b1f2350baadeb197308a4e27d53ec22a7105b735`.
- `benchmark/real-corpus-variants.json`, containing exact frozen R0-R5 patches: `474be8ec4c3bc7b2d0947d2ea43d96f399a6354842a4bcca401681eb0eb7064a`.
- `benchmark/fixture-source-freeze.json`: `f96ca1807b6f66b026f40c8957987e798c3becefc90e265656be88157d4f3267`.

F29-F34 transport sources were frozen by the independent baseline/transport author before bridge implementation. Readback verified `benchmark/transport_fixtures.py` SHA256 `4fdbd8008d10d0b1aae180d345f8417583cb3ffed3a98f5d8b942bc61bdbbd4c` and `evidence/transport-fixtures-manifest.json` SHA256 `8b67c230391377c5f584aec2473172ff085bc3c6ced2b3679a85581ead0964c4`. They cover six families and 12 explicit variants, with source/AST and deterministic output-byte checks only; no transport fixture was executed. F33 has two declared variants: the existing copied venv interpreter and a fixture-owned symlink facade, both retaining existing dependencies. Their creation actions and provenance are in the transport manifest.

The stronger direct-native/coarse-subprocess baseline has also completed. Readback of `evidence/baselines/strong_subprocess/parity.json` confirms equality of all eight compared native fields. Both target runs discovered 1024 tests, skipped five and had no failures; the coarse frontend produced one pytest/JUnit item. The earlier 64-skip in-process and failed true-version probes remain retained. Rich callback/fixture-trace checks still require the independent native observer; the eight-field baseline is not substituted for those checks.

A parser/execution harness may be written afterward against these fixed sources and the fixed interface; it cannot alter fixture bodies, variants or expected parity rules based on bridge outcomes. The implementation's code is not frozen by this preimplementation contract; its source must be separately sealed before comparative execution.
