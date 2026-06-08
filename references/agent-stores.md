# Agent transcript store registry

Where each coding agent persists conversation transcripts, how transcripts are scoped to a
project, and the per-message schema. `scripts/collect.py` mirrors this table. **Adding a new
agent = add one entry here + one resolver branch in `collect.py`.** Schemas drift across CLI
versions — when the collector reports unexpected gaps, re-verify against this doc first.

Verified on macOS, `/Users/tjboudreaux`, 2026-05-29; encoding + Hermes shapes re-verified
2026-06-07. Paths use `~` for the home dir.

## Summary

| Agent | Root | Scoped by | cwd source | Notes |
|---|---|---|---|---|
| Claude Code | `~/.claude/projects/<enc>/` | project (path-encoded) | per-line `cwd` | `<enc>` = abs path, **every non-alphanumeric** `→ -` (so `.`,`_`,`/` all collapse) |
| Codex | `~/.codex/sessions/YYYY/MM/DD/` | **date** | `session_meta.payload.cwd` / `turn_context.payload.cwd` | two schema generations (see below) |
| Factory / Droid | `~/.factory/sessions/<enc>/` | project (path-encoded) | `session_start.cwd` (line 1) | also has flat UUID files w/o cwd; `~/.droid` is a stub |
| Hermes | `~/.hermes/sessions/` | **none** (timestamped files) | not structured | two shapes: `*.jsonl` + `session_*.json`; match by path mention; `request_dump_*.json` are error dumps (skipped) |
| Cursor | `~/.cursor/projects/<cenc>/agent-transcripts/<uuid>/` | project (own encoding) | none (dir-encoded) | `<cenc>` = abs path w/o leading slash, every non-alphanumeric `→ -` |

### Additional agents (added 2026-06-08; P0 = verified vs real data, P1 = from docs, fixture-tested)

| Agent | Root | Scoped by | Parser | Tier |
|---|---|---|---|---|
| Gemini CLI | `~/.gemini/tmp/<name>/chats/*.jsonl` | dir name + `~/.gemini/projects.json` (path→name) or `projectHash` | `parse_gemini` (`$set.messages` + `type:user\|gemini`) | P0 |
| Qwen Code | `~/.qwen/tmp/<name>/chats/*.jsonl` | same (Gemini fork) | `parse_gemini` | P1 |
| opencode | `~/.local/share/opencode/storage/message/<sid>/*.json` | `path.cwd` per message (session = dir) | `parse_opencode` | P0 |
| Cline | `<editor>/User/globalStorage/saoudrizwan.claude-dev/tasks/<id>/api_conversation_history.json` | fuzzy (path mention; task-id dirs) | default (bare list) | P0 |
| Roo Code | globalStorage `rooveterinaryinc.roo-cline/tasks/…` | fuzzy (Cline fork) | default | P1 |
| Kilo Code | globalStorage `kilocode.kilo-code/tasks/…` | fuzzy (Cline fork) | default | P1 |
| Continue | `~/.continue/sessions/<uuid>.json` | fuzzy (path mention); new `history:[{message}]` or old `history.timeline` | `parse_continue` | P0 |
| Claude Agent-Mode | `~/Library/Application Support/Claude/local-agent-mode-sessions/**/*.jsonl` | per-line `cwd` (often synthetic `/sessions/<slug>`) | default | P0 |
| Aider | per-project `<project>/.aider.chat.history.md` | file location (the project dir) | `parse_aider` (markdown: `####`=user, `>`=skip) | P0 |
| Goose | `~/.local/share/goose/sessions/*.jsonl` | cwd in meta line, else fuzzy | default | P1 |
| Crush | `~/.local/share/crush/**/*.db` (sqlite) | `sessions.cwd` col, else fuzzy | `parse_crush` (**UNVERIFIED** schema) | P1 |
| Windsurf/Cascade | `~/.codeium/windsurf/**` | fuzzy (best-effort) | default (**UNVERIFIED**) | P1 |
| Augment | globalStorage `augment.vscode-augment/**` | fuzzy (best-effort) | default (**UNVERIFIED**) | P1 |

`<editor>` = each of `Code`, `Code - Insiders`, `VSCodium`, `Cursor`, `Windsurf` under
`~/Library/Application Support/.../User/globalStorage/`. Cline/Roo/Kilo share one resolver; Gemini/Qwen
share one parser. Store roots derive from `home()`, overridable via `$ROSETTA_HOME` for testing.

Path encodings:
- **Claude / Factory** `<enc>`: every char outside `[A-Za-z0-9]` → `-`. `/Users/tjboudreaux/Sandbox`
  → `-Users-tjboudreaux-Sandbox`. A project inside a **dotdir** keeps the dots-as-dashes:
  `/Users/tjboudreaux/.claude/skills/rosetta` → `-Users-tjboudreaux--claude-skills-rosetta` (the
  `--` is `/.`). Encoding only `/` silently misses every dotdir project — including this skill's home.
- **Cursor** `<cenc>`: strip the leading slash, then every non-alphanumeric → `-`
  (`/Users/tjboudreaux/Sandbox/app` → `Users-tjboudreaux-Sandbox-app`).

Scope rule (collector default): **exact cwd match only.** `Sandbox` does NOT pull in
`Sandbox/api`. `--include-subdirs` opts into monorepo mode (cwd at or under the project) —
on this machine that flips Factory from ~5 to ~2900 sessions, so it stays off by default.

---

## Claude Code

- **Per-project transcripts:** `~/.claude/projects/<enc>/<sessionUUID>.jsonl`
- **Global history:** `~/.claude/history.jsonl`
- Each line has a top-level `type`. Real turns are `type: "user"` / `type: "assistant"`; the rest
  (`system`, `attachment`, `last-prompt`, `permission-mode`, `file-history-snapshot`, `summary`)
  is non-conversational and counted as skipped.
- Conversational line shape:
  ```json
  {"type":"user","message":{"role":"user","content":"hi"},
   "uuid":"…","timestamp":"2026-05-26T05:05:05.897Z","cwd":"/Users/tjboudreaux/Sandbox",
   "sessionId":"…","gitBranch":"…","version":"2.1.150"}
  ```
- `message.content` is **either a string or a list of blocks** (`text`, `tool_use`, `tool_result`,
  `thinking`). Assistant turns are always block lists.
- `cwd` is present on every conversational line — used for verification.

## Codex (OpenAI)

- **Per-session transcripts:** `~/.codex/sessions/YYYY/MM/DD/rollout-<ISO>-<UUID>.jsonl`
  (date-bucketed, **not** project-bucketed → the collector walks all and filters on cwd).
- **Global history:** `~/.codex/history.jsonl` (`{session_id, ts, text}`).
- **Two schema generations observed:**
  - **New (cli ≥ ~0.135):** line 1 is
    `{"type":"session_meta","payload":{"id","cwd","cli_version",…}}`; messages are
    `{"type":"response_item","payload":{"type":"message","role","content":[{type:"input_text"|"output_text","text"}]}}`;
    `turn_context` lines also carry `cwd`. Roles include `developer`/`system` (noise) plus
    `user`/`assistant` (kept).
  - **Old (cli ~0.x, 2025):** line 1 is `{"id","timestamp","instructions"}`, line 2
    `{"record_type":"state",…}`. **No cwd anywhere** → unmatchable to a project. The collector
    counts these as `sessions_without_cwd` rather than dropping them silently.

## Factory / Droid

- **Per-project transcripts:** `~/.factory/sessions/<enc>/<sessionUUID>.jsonl`
- **Flat UUID files:** `~/.factory/sessions/<sessionUUID>.jsonl` at the root — their
  `session_start` line has **no cwd** (often abandoned/empty sessions). Counted as
  `flat_files_without_cwd`.
- **Global history:** `~/.factory/history.json` (JSON array of `{command, timestamp, type, mode}`).
- Line 1 in a project dir: `{"type":"session_start","id","title","owner","version":2,"cwd":"…"}`.
- `~/.droid/` contains only `skills/` — it delegates to Factory; nothing to scan there.

## Hermes

`~/.hermes/sessions/` mixes **four** file shapes — only two are conversations:
- **JSONL transcripts:** `<YYYYMMDD>_<HHMMSS>_<hex>.jsonl` — line 1 is
  `{"role":"session_meta","tools":[…]}`; messages are flat
  `{"role":"user"|"assistant","content":"…","timestamp":"…"}` (content is a plain string).
- **Single-object transcripts:** `session_<YYYYMMDD>_<HHMMSS>_<hex>.json` — ONE JSON document, not
  JSONL: `{"session_id","model","session_start","last_updated","message_count","messages":[{role,content}…]}`.
  These have no per-message timestamps, so the collector uses `session_start`/`last_updated` for the
  date range. On this machine these are the bulk of Hermes history (~22 files vs 2 `.jsonl`).
- **`request_dump_*.json`** — HTTP request/error dumps (`{timestamp,session_id,reason,request,error}`),
  **not** conversations; skipped (counted as `request_dumps_excluded` in the manifest). They embed a
  `role` inside `request`, so a naive `"role"` grep would wrongly pull them in.
- **`sessions.json`** — an index, not a transcript; ignored.
- **Global history:** `~/.hermes/.hermes_history` (plain text; `# <timestamp>` headers, `+`-prefixed lines).
- **No project scoping, no structured cwd → matching is fuzzy:** the collector keeps a `.jsonl` or
  `session_*.json` file if the literal project path appears in its text. Report Hermes matches as
  lower-confidence in the ground-truth coverage section.

## Cursor

- **Per-project transcripts:** `~/.cursor/projects/<cenc>/agent-transcripts/<sessionUUID>/<sessionUUID>.jsonl`
- Message shape: `{"role":"user"|"assistant","message":{"content":[{"type":"text","text":"…"}]}}`.
- No per-line cwd — scoping is entirely via the directory encoding.

## Stores triaged as NON-agents (excluded from the sweep)

These are flagged-looking but hold no conversation transcripts; they're in `NON_AGENT_DIRS` so the
sweep stays quiet: `~/.amplify` (AWS Amplify CLI cache), `~/.cursor-tutor` (tutorial files),
`~/.claude-squad` (orchestrator — points at `~/.claude`), `~/.warp` + `dev.warp.Warp-Stable`
(config/network logs only; no accessible transcript store found), `com.apple.AMPLibraryAgent`
(Apple Music/Books), and `*.new_backup` / `Claude-3p` app backups.

> **Correction (2026-06-08):** a prior version of this doc claimed Aider, Cline, and Gemini CLI
> "store no usable transcripts." That was wrong — all three DO (Gemini: `~/.gemini/tmp/*/chats`;
> Cline: editor globalStorage `tasks/`; Aider: per-project `.aider.chat.history.md`). They are now
> first-class (see the additional-agents table above). Recorded in ADR 0015.

## Still unsupported / known gaps

- **Qoder** (`~/.qoder/`): not yet parsed — left in `unknown_stores` so the gap stays visible.
- **Desktop app containers** (`~/Library/Application Support/{Claude,Codex,Cursor,Factory,HermesDesktop}`):
  the GUI apps' own storage. Claude's `local-agent-mode-sessions/` subtree IS now parsed (Claude
  Agent-Mode); the rest of these containers are not, and the sweep lists them under `unknown_stores`
  so the coverage gap is loud, not silent. Adding an agent = a row above + a resolver/parser in
  `collect.py` + a fixture in `tests/fixtures/build.py`.
