# Agents & discovery

Rosetta reads transcripts from **18 agent stores**. Each agent stores conversations differently —
path-encoded directories, date buckets, one-JSON-per-message trees, markdown, sqlite — so each has a
small resolver (where its sessions live + how they map to a project) and a parser (how to read one).

## Supported agents

| Agent | Where it stores transcripts | Scoped to a project by | Tier |
|---|---|---|---|
| **Claude Code** | `~/.claude/projects/<enc>/*.jsonl` | path-encoded dir + per-line `cwd` | ✅ verified |
| **Claude Agent-Mode** (Desktop) | `~/Library/Application Support/Claude/local-agent-mode-sessions/**/*.jsonl` | per-line `cwd` | ✅ verified |
| **Codex** (OpenAI) | `~/.codex/sessions/YYYY/MM/DD/*.jsonl` | `session_meta.cwd` (scan + filter) | ✅ verified |
| **Factory / Droid** | `~/.factory/sessions/<enc>/*.jsonl` | path-encoded dir + `session_start.cwd` | ✅ verified |
| **Cursor** | `~/.cursor/projects/<cenc>/agent-transcripts/**` | own directory encoding | ✅ verified |
| **Gemini CLI** | `~/.gemini/tmp/<name>/chats/*.jsonl` | dir name + `projects.json` map / `projectHash` | ✅ verified |
| **opencode** (sst) | `~/.local/share/opencode/storage/message/<sid>/*.json` | `path.cwd` per message | ✅ verified |
| **Cline** | `<editor>/globalStorage/saoudrizwan.claude-dev/tasks/<id>/` | fuzzy (path mention) | ✅ verified |
| **Continue** | `~/.continue/sessions/<uuid>.json` | fuzzy (path mention) | ✅ verified |
| **Aider** | per-project `.aider.chat.history.md` (markdown) | the project dir the file lives in | ✅ verified |
| **Hermes** | `~/.hermes/sessions/*.jsonl` + `session_*.json` | fuzzy (path mention) | ✅ verified |
| **Qwen Code** | `~/.qwen/tmp/<name>/chats/*.jsonl` | Gemini fork | ⚙️ from docs |
| **Roo Code** | globalStorage `rooveterinaryinc.roo-cline/tasks/` | Cline fork | ⚙️ from docs |
| **Kilo Code** | globalStorage `kilocode.kilo-code/tasks/` | Cline fork | ⚙️ from docs |
| **Goose** (Block) | `~/.local/share/goose/sessions/*.jsonl` | cwd in meta, else fuzzy | ⚙️ from docs |
| **Crush** (Charm) | `~/.local/share/crush/**/*.db` (sqlite) | `sessions.cwd` col, else fuzzy | ⚙️ unverified |
| **Windsurf / Cascade** | `~/.codeium/windsurf/**` | fuzzy (best-effort) | ⚙️ unverified |
| **Augment** | globalStorage `augment.vscode-augment/**` | fuzzy (best-effort) | ⚙️ unverified |

`<editor>` = any of `Code`, `Code - Insiders`, `VSCodium`, `Cursor`, `Windsurf`. **Verified** = tested
against real data on a dev machine. **From docs** = implemented to the documented format and tested
against synthetic fixtures; **unverified** ones (schema inferred) ship flagged and refine when real
data appears. The canonical, machine-checked registry is
[`references/agent-stores.md`](../references/agent-stores.md).

## How scoping works

Three strategies, by store design:

- **Path-encoded** (Claude, Factory, Cursor) — the project's absolute path is encoded into the
  directory name. Rosetta encodes the same way: **every non-alphanumeric → `-`** (so a project under a
  dotdir like `~/.claude/skills/rosetta` encodes to `-Users-…--claude-skills-rosetta`). Getting this
  wrong silently misses dotdir projects — a real bug Rosetta caught in itself.
- **cwd filter** (Codex, opencode, Goose, Claude Agent-Mode) — the store isn't project-scoped, so
  Rosetta reads each session's recorded working directory and keeps exact matches (`--include-subdirs`
  for monorepos).
- **Fuzzy** (Hermes, Cline/Roo/Kilo, Continue, Windsurf, Augment) — no structured cwd, so a session is
  kept when the project path appears in its text. Treated as lower-confidence.

## Loud coverage, not silent gaps

Every run emits a `manifest.json` with, per agent: sessions, messages, date range, match mode, and
`extra` counters for history it *couldn't* attribute (`sessions_without_cwd`, `flat_files_without_cwd`,
`request_dumps_excluded`). A discovery sweep also lists agent-looking directories that aren't in the
registry under `unknown_stores`. The point: a gap you can see beats a confident summary that quietly
missed an entire agent.

## Not agents (excluded)

Look-alike directories that hold no conversations are excluded so the sweep stays quiet: AWS Amplify
cache, Cursor tutorial, Apple Music library agent, app backups, and orchestrators like Claude Squad.
Genuinely-unsupported tools (e.g. Qoder) and desktop-app containers stay flagged so the gap is visible.

## Adding an agent

A registry row + a resolver, reusing a parser where the format matches. See
[CONTRIBUTING.md](../CONTRIBUTING.md#add-support-for-a-new-agent).
