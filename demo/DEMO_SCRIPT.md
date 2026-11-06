# Two-minute demonstration script

This script accompanies `run_demo.py`. The recorded command output comes from actual subprocesses; full diagnostic logs remain in the chosen output directory. The local asciicast is not a YouTube/Vimeo video or a screen recording.

**0:00-0:20**

"This project runs a native unittest suite inside pytest without replacing its native loader. The example is the licensed Markdown 3.9 source distribution. The native environment and the pytest environment are separate. The report counts native tests and pytest module groups separately."

Start the documented `demo/run_demo.py` command with the existing target and frontend interpreter paths and the extracted corpus.

**0:20-0:45**

"The untouched suite starts 1,024 native tests, with five skips. SuiteBridge reports 31 native modules through pytest. The detailed JSON keeps the individual native identities and outcomes."

Show the `pristine` summary and its generated `results/native.json` counts.

**0:45-1:20**

"Now the demo applies two fixed, deliberately injected regressions. They are known benchmark changes, not newly discovered upstream bugs. The same native suite records 36 assertion failures. Instead of one failing whole-suite wrapper item, JUnit identifies five failing modules."

Show the actual five module names and open `injected-R3/pytest.xml` or its stdout log to inspect a failure. The full native failure details remain in the group artifacts.

**1:20-1:45**

"The final invocation reruns the reported test_extensions module. It executes 20 native tests, including four failures. The other 30 groups are explicitly omitted and unvalidated. This is module selection, not automatic impact selection."

Show the exact node selector and selected-module summary.

**1:45-2:00**

"The frozen checks cover native discovery, fixtures, subtests, failures, interruption and worker errors. Custom suite behavior uses an atomic fallback. The verified result is clearer module reporting with preserved native outcomes for these cases; there is no speed or arbitrary-plugin compatibility claim."

Point to `benchmark/REPRODUCE.md` for independent full comparison commands and `evidence/RESULT.md` for the retained negative attempts and precise scope.
