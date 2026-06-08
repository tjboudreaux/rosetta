# ADR 0005 — Path encoding: every non-alphanumeric → dash

- Status: Accepted
- Date: 2026-06-07
- Decided originally: 2026-06-07
- Decider: Travis
- Sources: `claude · 4b80b004 · 2026-06-07` (found + fixed + verified); code `scripts/collect.py` (`enc_path`)
- Related: ADR 0002; supersedes the original `/`-only `enc_path`

## Context

Claude Code and Factory encode a project's cwd into a directory name. The original `enc_path` replaced
only `/` with `-`. But the real encoder replaces **every** non-alphanumeric character — so
`/Users/u/.claude/skills/rosetta` becomes `-Users-u--claude-skills-rosetta` (note the `--` where
`/.` was). Encoding only `/` produced `…-.claude-…`, which matches no directory. The result:
**any project inside a dotdir was silently invisible — including Rosetta's own home**, which reported
0 sessions for every agent. The 2026-05-29 verification had only tested non-dotdir paths, so the rule
was never exercised (a textbook case for ADR 0004's adversarial pass, which caught it).

## Decision

Encode with `re.sub(r"[^A-Za-z0-9]", "-", project)` for both the Claude and Factory resolvers —
matching the tools' actual scheme (`.`, `_`, `/` all collapse to `-`). Document the dotdir example in
`references/agent-stores.md`.

## Consequences

Positive:
- Projects under dotdirs are found; Rosetta can analyze itself (`~/.claude/skills/rosetta` now
  resolves its real session, verified 0 → 1).
- Non-dotdir paths encode identically to before — no regression.

Negative:
- The encoding is lossy/irreversible (can't recover `.` vs `/` from a `-`), so reverse-decoding a dir
  name to a path is impossible; discovery must probe a session's cwd instead (see ADR 0010).

## Alternatives considered

- **Special-case only the leading `.`** — fragile; the real rule is "all non-alphanumerics," so match
  it exactly.

## Related

- `enc_path()`; `references/agent-stores.md` "Path encodings"; `cursor_enc` carries the same latent
  issue and is flagged for follow-up (no Cursor dotdir history exists today).
