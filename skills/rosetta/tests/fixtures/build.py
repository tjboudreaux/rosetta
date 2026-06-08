#!/usr/bin/env python3
"""Build a synthetic $HOME fixture with a tiny transcript store for EVERY supported agent, all
scoped to one fake project, so the resolver+parser for each can be unit-tested deterministically.

Usage: build(home_path) → returns the absolute project path it scoped everything to.
Run standalone (`python3 build.py <dir>`) to materialize a fixture you can inspect.

Each agent gets one session with a `user` "hello from demo" turn and an `assistant` "hi back" turn,
mirroring that agent's REAL on-disk layout (see references/agent-stores.md). Fuzzy-scoped agents
embed the project path in the text so path-mention matching works.
"""
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import collect  # noqa: E402  (for enc_path / cursor_enc so encodings match exactly)

U, A = "hello from demo", "hi back"
TS0, TS1 = "2026-06-08T00:00:00Z", "2026-06-08T00:00:01Z"
MS0, MS1 = 1765352935842, 1765352935844


def _w(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _jsonl(path, objs):
    _w(path, "\n".join(json.dumps(o) for o in objs) + "\n")


def build(home):
    home = Path(home)
    P = str((home / "proj" / "demo").resolve())
    (home / "proj" / "demo").mkdir(parents=True, exist_ok=True)
    appsup = home / "Library" / "Application Support"

    # Claude Code — path-encoded dir, cwd per line
    _jsonl(home / ".claude" / "projects" / collect.enc_path(P) / "s.jsonl", [
        {"type": "user", "cwd": P, "timestamp": TS0, "message": {"role": "user", "content": U}},
        {"type": "assistant", "cwd": P, "timestamp": TS1,
         "message": {"role": "assistant", "content": [{"type": "text", "text": A}]}},
    ])

    # Codex — date-bucketed, cwd in session_meta, response_item messages
    _jsonl(home / ".codex" / "sessions" / "2026" / "06" / "08" / "rollout-2026-06-08T00-00-00-x.jsonl", [
        {"type": "session_meta", "timestamp": TS0, "payload": {"id": "x", "cwd": P}},
        {"type": "response_item", "payload": {"type": "message", "role": "user",
                                              "content": [{"type": "input_text", "text": U}]}},
        {"type": "response_item", "payload": {"type": "message", "role": "assistant",
                                              "content": [{"type": "output_text", "text": A}]}},
    ])

    # Factory — path-encoded dir, session_start cwd
    _jsonl(home / ".factory" / "sessions" / collect.enc_path(P) / "s.jsonl", [
        {"type": "session_start", "id": "x", "cwd": P},
        {"type": "user", "timestamp": TS0, "message": {"role": "user", "content": U}},
        {"type": "assistant", "timestamp": TS1, "message": {"role": "assistant",
         "content": [{"type": "text", "text": A}]}},
    ])

    # Hermes — single-object session_*.json (fuzzy: mentions P); + a request_dump to be EXCLUDED
    _w(home / ".hermes" / "sessions" / "session_20260608_000000_x.json", json.dumps({
        "session_id": "x", "session_start": TS0, "last_updated": TS1,
        "messages": [{"role": "user", "content": f"{U} in {P}"}, {"role": "assistant", "content": A}],
    }))
    _w(home / ".hermes" / "sessions" / "request_dump_x_y.json",
       json.dumps({"timestamp": TS0, "session_id": "x", "request": {"messages": []}, "error": "boom"}))

    # Cursor — own-encoded dir, agent-transcripts
    _jsonl(home / ".cursor" / "projects" / collect.cursor_enc(P) / "agent-transcripts" / "sid" / "sid.jsonl", [
        {"role": "user", "message": {"content": [{"type": "text", "text": f"{U} {P}"}]}},
        {"role": "assistant", "message": {"content": [{"type": "text", "text": A}]}},
    ])

    # Gemini — tmp/<basename>/chats; header + $set.messages seed + individual gemini line
    _w(home / ".gemini" / "projects.json", json.dumps({"projects": {P: "demo"}}))
    _jsonl(home / ".gemini" / "tmp" / "demo" / "chats" / "session-x.jsonl", [
        {"sessionId": "x", "projectHash": "h", "startTime": TS0, "lastUpdated": TS1},
        {"$set": {"messages": [{"id": "1", "timestamp": TS0, "type": "user",
                                "content": [{"text": U}]}]}},
        {"id": "2", "timestamp": TS1, "type": "gemini", "content": A},
    ])

    # Qwen — Gemini fork (basename match, no projects.json needed)
    _jsonl(home / ".qwen" / "tmp" / "demo" / "chats" / "session-x.jsonl", [
        {"sessionId": "x", "projectHash": "h", "startTime": TS0},
        {"$set": {"messages": [{"id": "1", "timestamp": TS0, "type": "user", "content": [{"text": U}]}]}},
        {"id": "2", "timestamp": TS1, "type": "gemini", "content": A},
    ])

    # opencode — one JSON per message in a session dir; path.cwd per message
    od = home / ".local" / "share" / "opencode" / "storage" / "message" / "ses_demo"
    _w(od / "msg_1.json", json.dumps({"id": "m1", "role": "user", "time": {"created": MS0},
                                      "path": {"cwd": P}, "summary": {"body": U}}))
    _w(od / "msg_2.json", json.dumps({"id": "m2", "role": "assistant", "time": {"created": MS1},
                                      "path": {"cwd": P}, "summary": {"body": A}}))

    # Cline / Roo / Kilo — globalStorage tasks/<id>/api_conversation_history.json (fuzzy mentions P)
    for ed, ext in (("Code", "saoudrizwan.claude-dev"),
                    ("Code", "rooveterinaryinc.roo-cline"),
                    ("Code", "kilocode.kilo-code")):
        _w(appsup / ed / "User" / "globalStorage" / ext / "tasks" / "123" / "api_conversation_history.json",
           json.dumps([{"role": "user", "content": [{"type": "text", "text": f"{U} {P}"}]},
                       {"role": "assistant", "content": [{"type": "text", "text": A}]}]))

    # Continue — new format history:[{message}] (fuzzy mentions P)
    _w(home / ".continue" / "sessions" / "uuid-1.json", json.dumps({
        "history": [{"message": {"role": "user", "content": f"{U} {P}"}},
                    {"message": {"role": "assistant", "content": A}}],
        "session_info": {"date_created": "1717804800"}}))
    _w(home / ".continue" / "sessions" / "sessions.json", json.dumps([{"session_id": "uuid-1"}]))

    # Claude Agent-Mode — Claude-shaped JSONL under Claude app support; cwd field
    _jsonl(appsup / "Claude" / "local-agent-mode-sessions" / "w" / "s" / "local" / ".claude"
           / "projects" / "-sessions-demo" / "uuid.jsonl", [
        {"type": "user", "cwd": P, "timestamp": TS0, "message": {"role": "user", "content": U}},
        {"type": "assistant", "cwd": P, "timestamp": TS1,
         "message": {"role": "assistant", "content": [{"type": "text", "text": A}]}},
    ])

    # Aider — per-project markdown
    _w(Path(P) / ".aider.chat.history.md",
       f"\n# aider chat started at 2026-06-08 00:00:00\n\n#### {U}\n\n{A}\n\n> tokens: 10\n")

    # Goose — sessions/*.jsonl; meta line carries cwd
    _jsonl(home / ".local" / "share" / "goose" / "sessions" / "s.jsonl", [
        {"type": "session", "cwd": P},
        {"role": "user", "content": U},
        {"role": "assistant", "content": A},
    ])

    # Crush — sqlite (UNVERIFIED real schema; fixture matches what parse_crush expects)
    db = home / ".local" / "share" / "crush" / "crush.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, title TEXT, cwd TEXT)")
    con.execute("CREATE TABLE messages (id TEXT, session_id TEXT, role TEXT, parts TEXT, created_at INTEGER)")
    con.execute("INSERT INTO sessions VALUES ('s1','demo',?)", (P,))
    con.executemany("INSERT INTO messages VALUES (?,?,?,?,?)", [
        ("m1", "s1", "user", U, MS0), ("m2", "s1", "assistant", A, MS1)])
    con.commit(); con.close()

    # Windsurf/Cascade — best-effort: a conversation json under ~/.codeium/windsurf (mentions P)
    _w(home / ".codeium" / "windsurf" / "conversation_1.json",
       json.dumps([{"role": "user", "content": f"{U} {P}"}, {"role": "assistant", "content": A}]))

    # Augment — best-effort: json under augment.vscode-augment globalStorage (mentions P)
    _w(appsup / "Code" / "User" / "globalStorage" / "augment.vscode-augment" / "conv.json",
       json.dumps([{"role": "user", "content": f"{U} {P}"}, {"role": "assistant", "content": A}]))

    # Sweep fixtures: a known store (already .gemini), an excluded non-agent, and an unknown agent
    (home / ".amplify").mkdir(parents=True, exist_ok=True)          # excluded (NON_AGENT_DIRS)
    (home / ".windsurfx").mkdir(parents=True, exist_ok=True)        # hint-match, unknown → flagged
    (home / ".totallyrandom").mkdir(parents=True, exist_ok=True)    # no hint → not flagged

    return P


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/rosetta-fixture-home"
    print("project:", build(out))
    print("home:", out)
