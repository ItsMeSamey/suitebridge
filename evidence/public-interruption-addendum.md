# Public copy

The following addendum is reproduced without changing its text. Original SHA-256: `c92ddf54fbf9b125a75c2b413c766c4427a68d36b42f4cf124bb42dde0858617`. Historical artifact references identify retained attempts; they do not imply all internal receipts are distributed.

---

# Interruption reporting and baseline-gate interpretation

2026-11-06. Read-only interpretation written after the first complete attempts and before any evaluator adjustment. The frozen fixtures, case counts, native parity requirements and usefulness requirements remain unchanged. Old artifacts and verdicts must not be rewritten.

## Observed evidence

I read the raw F26 native, atomic and bridge reports, traces, receipts and XML under evidence/integration-01/cases/F26/main, plus the initial integration summary. All 40 cases completed on unchanged sources/environments. The retained verdict is 39 passing cases and F26 failing, integration_pass=false.

F26 native execution exits 130 and records interrupted status. Its callback sequence is run_start, one native test start, the corresponding stop, and run_stop. Its fixture trace contains interrupt.setup and interrupt.body, with no invented cleanup or failure callback. Atomic and bridge preserve those native callbacks, trace and interruption semantics; each pytest frontend exits 2. Both XML files declare tests="0" but contain one anonymous empty testcase with no failure, error or skipped child. The two retained harness findings are the atomic and bridge JUnit testcase-count mismatch.

I also read the F32 transport result, public native artifact and raw XML. The frontend exits 2 with interrupted status, one started native-test prefix, no completed group, and the active group correctly listed as uncompleted. Worker reaping and descendant cleanup passed. Its XML has the same zero-count/empty-testcase defect. The initial transport verdict remains 11 of 12 passing variants, with F32 failing truthful-interruption and JUnit-count checks.

These are actual reporting defects. Matching native interruption semantics does not turn the bridge's empty XML testcase into a pass.

## Interpretation of the frozen contract

FROZEN_CONTRACT.md:116-120 and 138 require candidate/native event and fixture parity. Lines 126-132 require distinguishable interruption outcomes, honest group-level reporting, count-consistent JUnit and incomplete status for interrupts. These obligations continue to apply to SuiteBridge after a fix.

The atomic wrapper is a comparison baseline, not the product being qualified. Its F26 JUnit defect is a measured baseline-reporting deficiency and must remain explicitly reported. It is not a native semantic behavior that the candidate should reproduce. It does not invalidate the independently recorded native control when its target environment, native callbacks, fixture trace and exit/interruption semantics still match. Requiring the new product to reproduce a known baseline reporting defect would conflict with the truthful-reporting requirement.

The evaluator may therefore separate three classes of findings before the next attempt:

1. Candidate correctness/reporting issues remain blocking, including every candidate JUnit mismatch or falsely passing interrupted group.
2. Baseline reporting observations remain visible measurements. An atomic-wrapper XML deficiency is included here, without being relabeled a baseline pass or deleted from the result.
3. Reference validity and baseline-fidelity issues remain blocking when they prevent a fair comparison: wrong target interpreter, missing or inconsistent native artifacts, changed sources/environments, native event/fixture mismatch, unexplained process outcomes, incomplete required comparison evidence or harness errors.

This is a role-based interpretation of the existing contract, not an exception for a named inconvenient test. It must not become a blanket rule that ignores all baseline failures. In particular, R3/F28 still require actual evidence of the atomic wrapper's single failure item for the module-attribution comparison; if that evidence is absent, the usefulness comparison is incomplete. The same target coverage gate and all native-control requirements remain mandatory.

Keep integration-01 and transport-checks-initial unchanged and marked failed. Preserve the original evaluator source snapshot and document the revised classification separately. Any new candidate verdict belongs to a new retained attempt using the same frozen cases. No threshold, fixture, native-event normalization or corpus coverage may be relaxed.

## Clean correction for the product

The pinned pytest runner source confirms that KeyboardInterrupt is reraised before an ordinary call report is emitted. Its runtest protocol normally emits call and teardown reports for an ordinary exception, then its main loop stops when session.shouldstop is set. This explains the observed empty JUnit testcase.

An acceptable correction is to handle an actual interruption while a native group is active, retain the existing native interrupted/incomplete artifact and worker cleanup, set the pytest session's stop request, and raise a dedicated ordinary exception representing an interrupted group. Pytest can then emit its normal identified non-passing group report and teardown report before terminating the session with interruption status.

The JUnit failure element in that mapping describes the coarse pytest group failing to complete. Its message must explicitly say INTERRUPTED and that this is not a native assertion failure. The native JSON/JSONL must retain its original interruption status and exact callback prefix, without adding native addFailure, addError, success or cleanup events. Keep the actual native test counts and occurrence identities unchanged. The session must exit 2 for an actual controller interruption, stop later groups, and retain worker/descendant cleanup behavior. Existing failure-stop flags must not accidentally relabel the interruption as an ordinary exit-1 test failure.

Do not fix this by editing XML afterward, deleting the anonymous testcase from a retained artifact, fabricating a native assertion/error callback or marking the active group successful. The normal pytest reporting pipeline should receive a truthful group-level interruption outcome. The frontend owner proposed a dedicated NativeGroupInterrupted exception with explicit explanatory text; that design is acceptable subject to source review and tests.

## Required verification after the correction

Recheck both interruption paths: native KeyboardInterrupt (F26) and externally delivered frontend SIGINT after body readiness (F32). Require a named non-passing pytest group, self-consistent XML counts, exit 2, unchanged native prefix/fixture semantics, no later group execution and successful owned-process cleanup. Retain the deficient atomic F26 XML as baseline evidence. Then complete the remaining frozen regression/evaluation obligations under the new source seal; a targeted fix check alone is not a full product pass.
