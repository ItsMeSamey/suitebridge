# SuiteBridge result

The corrected implementation passes the frozen technical gate: 40 integration cases, 12 transport variants and 16 independent clean-copy checks. The independent final audit recomputed all integration assessments, verified 3,519 artifact hashes and accepted the bounded result. Full evidence remains in this workspace; release summaries are separate exports.

| Workflow | Direct native / atomic wrapper | SuiteBridge |
| --- | --- | --- |
| Pristine pinned Markdown 3.9 sdist | 1,024 starts, 1,019 successes, five skips | Exact native parity; 31 pytest module items |
| Fixed R3 injected regression | 36 native failures; atomic wrapper has one failing item | Same 36 failures, attributed to five of 31 module items |
| Exact `test_extensions` rerun | Selected native reference has 20 tests and four failures | Exact selected-reference parity; one failing module; 30 omitted groups labeled unvalidated |
| Native and frontend interruption | Original native callback prefix retained | Exit 2, named interrupted non-passing group, consistent JUnit counts, prior completed module retained |

The primary native reference, atomic subprocess wrapper and bridge use the identical passing no-Pygments target environment. The frontend uses pytest 9.2.0 in its own environment. Stock pytest collection of the pinned sdist was not equivalent: 1,138 collected items included 114 duplicates and collection failed. The dependency-isolation decision follows retained evidence: a combined environment added 59 skips, while configuring the actual installed Pygments version caused 20 assertion failures and one error. Neither reduced coverage nor fabricated version information was accepted as the primary baseline.

## Source and evidence

Final product SHA-256:

- `suitebridge.py`: `f1ceb8a11520270a6cb1d85f2b50d80b65171a285f7c436fa581de07bcd39507`
- `suitebridge_worker.py`: `85de98cd8e24b4ea6f7e7007f566e1f77c6bd77a3e0d52d07c793ef11dbc730e`
- `suitebridge_protocol.py`: `00f979e2b9c4a10e8669b9c67a6826a31ffc2747571b6864cc0bdad427ad6eb8`

The original preimplementation contract SHA-256 is `08856b4d06531489be6b4738e3935277a3ca285e078324fc8638e5eac7f88ec3`. Its source freeze contains 124 entries. Fixtures and six exact real-corpus variants were fixed before implementation. The Markdown archive SHA-256 is `d2900fe1782bd33bdbbd56859defef70c2e78fc46668f8eb9df3128138f2cb6a`.

Original retained evidence digests (raw workspace records are not bundled):

- Corrected integration summary: `d02dc2d440a9aa7b4918fd0fda01dd1dc18ecbc55c9822179d029c7be8e2339d`.
- Corrected transport summary: `1483b57aa5566eb80c329aff72d5c52fc208c7de6f2b9e46dd9c3faf21b7385f`.
- Initial failed integration summary: `2f96e349143fa20834c4acb716faa621d096e48bd3a4f470bc8f2a5457bbe015`.
- Initial failed transport summary: `733e726cb780db375f258aeebf3bcd36ea29a3bdae04fa506c455bf0b428420d`.

This is an authored public result summary, not a path-redacted raw receipt. The portable runners and unchanged frozen fixtures allow fresh independent verification. Their own release validation is recorded separately.

## Retained failures and limits

The initial candidate failed at 39/40 integration cases and 11/12 transport variants. Interruption XML declared zero tests while containing an anonymous testcase that could appear passed. Those raw artifacts and verdicts remain unchanged. The correction uses pytest's normal reporting lifecycle to produce an explicitly interrupted non-passing item; it does not rewrite XML or invent native callbacks. The atomic wrapper's own interruption reporting deficiency remains visible as a baseline observation.

The earlier ChangeProof impact-selection candidate failed its efficiency gate, using 2.73% more calibration-inclusive CPU at 20 changes. It remains a separate negative experiment. SuiteBridge makes no speed claim.

Acceptance covers Linux, Python 3.14, pytest 9.2, documented strict serial flags, the pinned Markdown sdist and frozen fixture families. The sdist omits upstream repository legacy fixtures. Group-level JUnit items are not individual native tests. Known custom behavior uses an atomic fallback; arbitrary plugin combinations, testmon, xdist, generic semantic soundness and individual native pytest selection are not established. The mutations are known injected regressions, not held-out discoveries.

This technical result does not establish contest entry readiness. No contest submission, placing or payment follows from it.
