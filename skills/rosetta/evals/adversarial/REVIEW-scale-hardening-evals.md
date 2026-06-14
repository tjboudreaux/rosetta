# Hostile adversarial review: scale, hardening, eval calibration

Scope read before writing: `skills/rosetta/scripts/collect.py`, `decisions.py`, `ingest.py`, `SKILL.md`, all files under `skills/rosetta/decisions/`, all named adversarial eval files, and all source files under `skills/rosetta/tests/`.

## Goal 1: Scale to 10k-50k ADRs

Verdict: NOT MET.

The project has some linear mechanics, but the end-to-end decision-library workflow is not designed for 10k-50k ADRs. `validate` is not the feared O(n^2) supersede resolver, but `index`, `new`, and the agent workflow still assume a small markdown library.

1. `decisions.py validate` complexity: PARTIALLY OK. It reads each record's full file text one at a time (`skills/rosetta/scripts/decisions.py:103`) and stores parsed records in a list (`skills/rosetta/scripts/decisions.py:132`), but it does not retain full record bodies after parsing. ID collection is one pass into a dict/set (`skills/rosetta/scripts/decisions.py:244`, `skills/rosetta/scripts/decisions.py:254`). Supersede resolution compiles a label regex, not an all-ID regex (`skills/rosetta/scripts/decisions.py:256`), then scans each record's small `Status`/`Supersedes`/`Related` text (`skills/rosetta/scripts/decisions.py:270`) and checks membership in `all_ids` (`skills/rosetta/scripts/decisions.py:272`). That is O(n + total link text), not O(n^2). It still holds all parsed record metadata in memory.

2. `decisions.py index`: NOT MET. `cmd_index` parses every record (`skills/rosetta/scripts/decisions.py:216`), builds all table rows in memory (`skills/rosetta/scripts/decisions.py:197`, `skills/rosetta/scripts/decisions.py:209`), reads the whole README if present (`skills/rosetta/scripts/decisions.py:222`), and rewrites the whole README with a plain `write_text` (`skills/rosetta/scripts/decisions.py:233`). At 50k rows, this is an O(n) full rewrite every time, with no atomicity. This directly fails ADR 0017's write pattern: temp file then `os.replace()` (`skills/rosetta/scripts/collect.py:996`, `skills/rosetta/scripts/collect.py:1003`).

3. `decisions.py new`: NOT MET. Each `new` call scans all existing files in the type directory (`skills/rosetta/scripts/decisions.py:163`), computes `max(used) + 1` (`skills/rosetta/scripts/decisions.py:167`), then writes the new file (`skills/rosetta/scripts/decisions.py:191`). Building a library by repeated `new` is O(n^2). The only collision guard is `out.exists()` before write (`skills/rosetta/scripts/decisions.py:172`), with no lock or exclusive create. Concurrent calls can allocate the same number; different titles produce duplicate numbers, same title can overwrite by race.

4. `number_width=4` past 9999: FUNCTIONALLY OK, with a documentation mismatch. `zfill(width)` does not truncate (`skills/rosetta/scripts/decisions.py:168`, `skills/rosetta/scripts/decisions.py:199`), headings parse arbitrary digit counts (`skills/rosetta/scripts/decisions.py:51`, `skills/rosetta/scripts/decisions.py:115`), filename parsing accepts arbitrary digit counts (`skills/rosetta/scripts/decisions.py:164`, `skills/rosetta/scripts/decisions.py:267`), and timeline sorting uses numeric `number` (`skills/rosetta/scripts/decisions.py:198`). A 10000th record should be `10000-title.md` and still parse/sort. The warning text still says `NNNN-kebab-slug.md` (`skills/rosetta/scripts/decisions.py:268`), so the contract is misleading, not broken.

5. `SKILL.md` workflow: NOT MET for huge decision libraries. The skill has a transcript-scaling strategy: collect first, then fan out subagents over normalized `.md` batches (`skills/rosetta/SKILL.md:94`, `skills/rosetta/SKILL.md:96`, `skills/rosetta/SKILL.md:97`). It also has an incremental transcript delta strategy (`skills/rosetta/SKILL.md:66`, `skills/rosetta/SKILL.md:67`, `skills/rosetta/SKILL.md:68`). It does not provide an analogous chunk/search/index strategy for an existing 10k-50k ADR library. The decision-record step simply says to distill into a decision library (`skills/rosetta/SKILL.md:187`, `skills/rosetta/SKILL.md:189`) and then run `decisions.py index` and `validate` (`skills/rosetta/SKILL.md:199`). `allowed-tools` includes Grep (`skills/rosetta/SKILL.md:6`), but the workflow never says how to retrieve, shard, or avoid reading massive ADR history.

6. `collect.py` at scale: PARTIALLY OK algorithmically, NOT HARDENED. It is mostly O(total files + bytes), not obviously O(n^2), but it has unbounded memory and full-rewrite behavior. `collect_session` reads the whole session file (`skills/rosetta/scripts/collect.py:211`, `skills/rosetta/scripts/collect.py:212`), attempts whole-file JSON parse (`skills/rosetta/scripts/collect.py:217`), and for JSONL stores every parsed line before message extraction (`skills/rosetta/scripts/collect.py:227`, `skills/rosetta/scripts/collect.py:233`). The normalized output is built as a full in-memory `lines` list (`skills/rosetta/scripts/collect.py:970`, `skills/rosetta/scripts/collect.py:982`, `skills/rosetta/scripts/collect.py:988`). The ledger is read and written as one full JSON object (`skills/rosetta/scripts/collect.py:1028`, `skills/rosetta/scripts/collect.py:1040`), and the manifest is accumulated in memory and rewritten whole (`skills/rosetta/scripts/collect.py:1109`, `skills/rosetta/scripts/collect.py:1186`). This will strain tens of thousands of sessions or a huge ledger, even if it does not become quadratic.

## Goal 2: Hardening after ADR 0017

Verdict: NOT MET.

### P0 findings

1. Non-atomic README index rewrite can truncate/corrupt the decision index.
Problem: `cmd_index` writes the whole index with plain `index_path.write_text(new)` (`skills/rosetta/scripts/decisions.py:233`). Why it matters: ADR 0017 explicitly chose temp+replace for durability-critical files (`skills/rosetta/scripts/collect.py:996`, `skills/rosetta/scripts/collect.py:1003`), and the decision index is a user-facing library artifact, not a disposable cache. A process kill can leave a truncated README. Fix direction: move `decisions.py` onto an atomic write helper shared with `collect.py`; write the README temp file in the same directory and `os.replace`.

2. `new` can allocate duplicate numbers or overwrite by race.
Problem: `new` scans existing files (`skills/rosetta/scripts/decisions.py:163`), chooses `max(used)+1` (`skills/rosetta/scripts/decisions.py:167`), checks existence (`skills/rosetta/scripts/decisions.py:172`), then performs a plain write (`skills/rosetta/scripts/decisions.py:191`). Why it matters: two concurrent agents can create the same ADR number; if titles differ, validation later sees duplicate numbers; if titles match, last writer can win. Fix direction: use a lock file or atomic exclusive create (`open(..., "x")`) around allocation and write; re-check after acquiring the lock.

3. `validate` can pass a library while skipping unparseable records.
Problem: a record with no parseable H1 returns `None` (`skills/rosetta/scripts/decisions.py:110`, `skills/rosetta/scripts/decisions.py:113`), `collect_records` logs a warning and continues (`skills/rosetta/scripts/decisions.py:139`, `skills/rosetta/scripts/decisions.py:141`, `skills/rosetta/scripts/decisions.py:142`), and `cmd_validate` only validates the remaining records (`skills/rosetta/scripts/decisions.py:238`, `skills/rosetta/scripts/decisions.py:259`). Why it matters: a broken ADR file can be omitted from validation and still allow a zero-error exit. That is silent library corruption masked as success. Fix direction: make unparseable records validation errors, not warnings, when the command is `validate`; `index` may warn/skip, but `validate` must fail closed.

4. `ingest.py` has no idempotence or race-safe deduplication.
Problem: `next_number` scans existing files (`skills/rosetta/scripts/ingest.py:39`) and returns the next padded number (`skills/rosetta/scripts/ingest.py:43`); the main loop allocates and writes each record (`skills/rosetta/scripts/ingest.py:117`, `skills/rosetta/scripts/ingest.py:122`). The only duplicate guard is exact `out.exists()` (`skills/rosetta/scripts/ingest.py:119`), but repeated ingest of the same title gets a new number before the same path can collide. Why it matters: retrying the same external extraction duplicates records; concurrent ingests can allocate the same number. Fix direction: add an idempotency key from source/title/date, hold a lock during allocation, and use exclusive atomic create for record files.

### P1 findings

5. `decisions.py` config can write/read outside the decision root.
Problem: config values replace top-level defaults wholesale (`skills/rosetta/scripts/decisions.py:77`, `skills/rosetta/scripts/decisions.py:80`); record dirs are joined directly under root (`skills/rosetta/scripts/decisions.py:158`); index path is joined directly (`skills/rosetta/scripts/decisions.py:217`); templates may be absolute paths (`skills/rosetta/scripts/decisions.py:91`). Why it matters: a malformed or hostile `config.json` can make `new`/`index` read templates or write records/README outside the intended decisions root. Fix direction: normalize resolved paths and reject paths outside the configured root unless an explicit trusted flag is used.

6. `validate` does not validate body completeness, dates, or truncated-after-frontmatter records.
Problem: validation checks required fields and status (`skills/rosetta/scripts/decisions.py:259`, `skills/rosetta/scripts/decisions.py:263`), filename shape (`skills/rosetta/scripts/decisions.py:267`), and supersede references (`skills/rosetta/scripts/decisions.py:270`). It never checks required body sections, date format, or whether the record was truncated after valid frontmatter. Why it matters: a half-file ADR with valid `Status`, `Date`, and `Decider` can validate. Fix direction: validate required body headings and date syntax from the schema, and fail if a record ends before required sections.

7. Encoding is locale-dependent across production writes and reads.
Problem: `decisions.py` reads config/templates/records and writes records/index without `encoding="utf-8"` (`skills/rosetta/scripts/decisions.py:73`, `skills/rosetta/scripts/decisions.py:103`, `skills/rosetta/scripts/decisions.py:175`, `skills/rosetta/scripts/decisions.py:191`, `skills/rosetta/scripts/decisions.py:233`). `ingest.py` does the same (`skills/rosetta/scripts/ingest.py:96`, `skills/rosetta/scripts/ingest.py:122`). `collect.py` also omits explicit encoding in both direct and atomic paths (`skills/rosetta/scripts/collect.py:211`, `skills/rosetta/scripts/collect.py:988`, `skills/rosetta/scripts/collect.py:1001`). Why it matters: the corpus uses non-ASCII punctuation in headings and citations; locale-dependent IO can fail or corrupt on non-UTF-8 environments. Fix direction: use `encoding="utf-8"` everywhere; decide explicitly where invalid bytes are errors vs replacement.

8. Several parser paths silently drop unreadable or malformed source data.
Problem: `parse_gemini` drops malformed JSON lines without incrementing `skipped` (`skills/rosetta/scripts/collect.py:287`, `skills/rosetta/scripts/collect.py:290`) and swallows whole-file read errors with `pass` (`skills/rosetta/scripts/collect.py:300`, `skills/rosetta/scripts/collect.py:301`). `probe_cwd` returns `None` on read errors (`skills/rosetta/scripts/collect.py:469`, `skills/rosetta/scripts/collect.py:473`), and `file_mentions_path` returns `False` on read errors (`skills/rosetta/scripts/collect.py:479`, `skills/rosetta/scripts/collect.py:483`). The main loop silently drops sessions with `data["kept"] == 0` (`skills/rosetta/scripts/collect.py:1145`, `skills/rosetta/scripts/collect.py:1146`). Why it matters: coverage can be understated without a manifest error, especially for fuzzy/path-mention stores. Fix direction: record per-agent parse/read/drop counters in the manifest and log paths for dropped sessions.

9. Concurrent collectors can lose ledger updates.
Problem: one process loads the ledger once (`skills/rosetta/scripts/collect.py:1102`), mutates entries in memory (`skills/rosetta/scripts/collect.py:1163`), and saves the whole ledger at the end (`skills/rosetta/scripts/collect.py:1188`). Atomic replace prevents torn files, not last-writer-wins lost updates. Why it matters: two overlapping runs against the same project can erase each other's processed-session entries, defeating incremental behavior. Fix direction: lock the ledger during load/modify/save or use append-only per-session receipts merged atomically.

10. Oversized inputs are read wholesale with no size guard.
Problem: `ingest.py` reads all input JSON or stdin into memory (`skills/rosetta/scripts/ingest.py:96`) then `json.loads` it (`skills/rosetta/scripts/ingest.py:98`). `collect_session` reads full transcript files (`skills/rosetta/scripts/collect.py:211`, `skills/rosetta/scripts/collect.py:212`). `load_ledger` reads the full ledger (`skills/rosetta/scripts/collect.py:1028`). Why it matters: a huge meeting extraction, transcript, or ledger can spike memory or hang the CLI. Fix direction: add documented size limits and streaming parsers where practical; at minimum fail loudly over a max input size.

### P2 findings

11. Normalized session Markdown is still non-atomic.
Problem: `write_session_md` writes direct to destination (`skills/rosetta/scripts/collect.py:988`). ADR 0017 deliberately excludes per-run session `.md` from atomic writes (`skills/rosetta/decisions/architecture-decisions/0017-crash-safe-writes-and-resilience.md:24`, `skills/rosetta/decisions/architecture-decisions/0017-crash-safe-writes-and-resilience.md:25`). Why it matters: HYPOTHESIS: if a downstream process reads the out dir after an interrupted run, it can consume a partial normalized session. Fix direction: either make session writes atomic too, or write to a staging dir and only publish after manifest success.

12. Test/eval artifact writers also use non-atomic `write_text`.
Problem: eval bundles write prompt/gold/anchors/corpus/manifest/project/git log with direct `write_text` (`skills/rosetta/evals/adversarial/run_evals.py:242`, `skills/rosetta/evals/adversarial/run_evals.py:250`, `skills/rosetta/evals/adversarial/run_evals.py:254`, `skills/rosetta/evals/adversarial/run_evals.py:256`, `skills/rosetta/evals/adversarial/run_evals.py:264`, `skills/rosetta/evals/adversarial/run_evals.py:270`). Fixtures use `_w` with direct write (`skills/rosetta/evals/adversarial/fixtures.py:31`, `skills/rosetta/evals/adversarial/fixtures.py:33`). Why it matters: these are not production user data, but interrupted bundle emission can produce misleading eval artifacts. Fix direction: reuse the atomic writer for generated eval artifacts too.

## Goal 3: Eval calibration from Haiku to Opus

Verdict: NOT MET.

100% on Opus is meaningful only as a tool-enabled ceiling check for a capable solver. It is not calibrated across Haiku/Sonnet/Opus, and it does not establish a model-quality curve.

1. Tier-B scenario difficulty is mixed, with many pass-regardless cases. Easy/pass-regardless examples: `cold-project` only requires reporting zero history and code/docs (`skills/rosetta/evals/adversarial/dataset.json:27`, `skills/rosetta/evals/adversarial/dataset.json:34`); `negative-control` requires not inventing a conflict (`skills/rosetta/evals/adversarial/dataset.json:243`, `skills/rosetta/evals/adversarial/dataset.json:254`); `proposed-not-shipped` has a TODO-only implementation (`skills/rosetta/evals/adversarial/fixtures.py:369`, `skills/rosetta/evals/adversarial/fixtures.py:372`); `coverage-unmatchable-codex` is mostly manifest-counter reading (`skills/rosetta/evals/adversarial/dataset.json:178`, `skills/rosetta/evals/adversarial/dataset.json:188`). HYPOTHESIS: these likely do not separate Haiku from Sonnet from Opus strongly. More discriminative scenarios are `prompt-injection-transcript` (`skills/rosetta/evals/adversarial/dataset.json:210`, `skills/rosetta/evals/adversarial/dataset.json:222`), `false-precision-citation` (`skills/rosetta/evals/adversarial/dataset.json:227`, `skills/rosetta/evals/adversarial/dataset.json:238`), `composite-realistic` (`skills/rosetta/evals/adversarial/dataset.json:279`, `skills/rosetta/evals/adversarial/dataset.json:295`), `multi-hop-reconciliation` (`skills/rosetta/evals/adversarial/dataset.json:349`, `skills/rosetta/evals/adversarial/dataset.json:363`), and the size-drift supersession family (`skills/rosetta/evals/adversarial/dataset.json:436`, `skills/rosetta/evals/adversarial/dataset.json:449`).

2. The size-drift family tests tool-use retrieval, not long-context recall. The results file says the solver had `grep`/`Bash` and that the run therefore means "retrieval-with-tools," not pure long-context reading (`skills/rosetta/evals/adversarial/RESULTS.md:60`, `skills/rosetta/evals/adversarial/RESULTS.md:61`, `skills/rosetta/evals/adversarial/RESULTS.md:62`, `skills/rosetta/evals/adversarial/RESULTS.md:63`). The implemented drift sizes top out at 250 ADRs (`skills/rosetta/evals/adversarial/dataset.json:454`, `skills/rosetta/evals/adversarial/dataset.json:458`), not 10k-50k. HYPOTHESIS: this is easier for a weaker model with shell search than for the same model forced to reconcile a large library in-context.

3. `judge_prompt.md` is not calibrated for a weak judge. The judge must extract atomic claims (`skills/rosetta/evals/adversarial/judge_prompt.md:26`), classify them (`skills/rosetta/evals/adversarial/judge_prompt.md:30`), verify support against corpus/code/git/gold (`skills/rosetta/evals/adversarial/judge_prompt.md:33`), enforce global must/must_not/citation rules (`skills/rosetta/evals/adversarial/judge_prompt.md:42`, `skills/rosetta/evals/adversarial/judge_prompt.md:47`), and default ambiguous evidence to unsupported (`skills/rosetta/evals/adversarial/judge_prompt.md:85`). That is itself a high-judgment task. The reported judges were the same Opus model family (`skills/rosetta/evals/adversarial/RESULTS.md:97`, `skills/rosetta/evals/adversarial/RESULTS.md:100`, `skills/rosetta/evals/adversarial/RESULTS.md:101`). HYPOTHESIS: a Haiku judge will produce false passes/fails unless judge accuracy is separately benchmarked.

4. There is no per-model baseline or adaptive pass/fail threshold. `dataset.json` defines Tier A and Tier B, not model tiers (`skills/rosetta/evals/adversarial/dataset.json:4`, `skills/rosetta/evals/adversarial/dataset.json:6`). `run_evals.py` produces binary pass/fail per scenario (`skills/rosetta/evals/adversarial/run_evals.py:228`) and totals pass/fail/skip (`skills/rosetta/evals/adversarial/run_evals.py:286`, `skills/rosetta/evals/adversarial/run_evals.py:302`). `judge_prompt.md` also defines binary pass semantics (`skills/rosetta/evals/adversarial/judge_prompt.md:55`, `skills/rosetta/evals/adversarial/judge_prompt.md:56`). There is no expected Haiku/Sonnet/Opus score table, no confidence interval, and no threshold by model tier. Therefore 100% on Opus says "Opus can pass this suite once under these conditions," not "the eval is calibrated."

5. Determinism split: Tier A is model-independent; Tier B is not deterministic. Tier A is explicitly deterministic substrate checking (`skills/rosetta/evals/adversarial/run_evals.py:4`, `skills/rosetta/evals/adversarial/run_evals.py:5`, `skills/rosetta/evals/adversarial/run_evals.py:17`) and CI wiring says it does not grade model judgment (`skills/rosetta/tests/test_adversarial_evals.py:2`, `skills/rosetta/tests/test_adversarial_evals.py:4`). Tier B is manual/model-judged and outside CI (`skills/rosetta/evals/adversarial/DESIGN.md:41`, `skills/rosetta/evals/adversarial/DESIGN.md:47`, `skills/rosetta/evals/adversarial/DESIGN.md:48`). The README instructs humans to have a solver and judge model run the task (`skills/rosetta/evals/adversarial/README.md:66`, `skills/rosetta/evals/adversarial/README.md:68`, `skills/rosetta/evals/adversarial/README.md:69`) but specifies no seed, temperature, sampling count, or retry policy. The results acknowledge one solver model and one run (`skills/rosetta/evals/adversarial/RESULTS.md:102`, `skills/rosetta/evals/adversarial/RESULTS.md:103`). Variance risk is real and unmeasured.

## Priority summary

### Goal 1: scale

Top 3 changes:
1. Replace README-as-primary-index with a machine-readable index/store that supports incremental updates; generate README as a derived artifact.
2. Make `new` allocation O(1) or locked via a metadata counter/ledger rather than glob-scanning every file.
3. Add a decision-library retrieval strategy to `SKILL.md`: search/chunk/index rules for existing ADR libraries, with explicit 10k+ behavior.

Single most important fix: stop full README rewrites in `cmd_index` and move to atomic, incremental index generation.

### Goal 2: hardening

Top 3 changes:
1. Port `decisions.py` and `ingest.py` writes to atomic temp+replace or exclusive-create primitives.
2. Make `validate` fail closed on unparseable records and truncated/missing required body sections.
3. Add locks/idempotency keys for `new`, `ingest`, `index`, and the processed-session ledger.

Single most important fix: make decision-library mutation (`new`/`ingest`/`index`) atomic and lock-protected.

### Goal 3: eval calibration

Top 3 changes:
1. Run Tier B across Haiku/Sonnet/Opus with repeated samples and publish per-scenario score distributions.
2. Add model-tier baselines and thresholds instead of a single binary "100%" headline.
3. Split tool-use retrieval evals from no-tools long-context evals, especially for decision-history drift.

Single most important fix: add a real model calibration matrix with fixed run settings, repeated samples, and independent judge validation per model tier.
