#!/usr/bin/env python3
"""Rosetta collector — resolve, filter, and normalize every agent's transcripts for one project.

The hard problem this solves: the same project lives under many incompatible transcript-storage
schemes (Claude Code, Codex, Factory/Droid, Hermes, Cursor, Gemini, Qwen, opencode, Cline/Roo/Kilo,
Continue, Claude Agent-Mode, Aider, Goose, Crush, Windsurf, Augment), most not project-scoped the
same way, several drifting across CLI versions and across storage *formats* (JSONL, one-JSON-per-
message dirs, nested JSON trees, markdown, sqlite). A naive "read the folder" misses entire agents
and then calls the result ground truth.

This script does the deterministic heavy lifting once — path resolution, cwd filtering, schema-
tolerant parsing, timestamp normalization — and writes:

  <out>/manifest.json                  coverage map (agents, counts, date ranges, gaps)
  <out>/<agent>__<session>.md          one normalized transcript per matched session

so downstream summarizer subagents read clean text, never raw transcripts.

Architecture: an AGENTS registry maps each agent → (resolver, parser). A resolver returns the
"units" (a file, a session-dir, or a sqlite (db, session) pair) that match a project; the agent's
parser turns one unit into normalized messages. The store roots derive from `home()`, which honors
$ROSETTA_HOME — so the whole machine can be sandboxed for tests.

Pure stdlib. Read-only against the agent stores. See references/agent-stores.md for the registry.
"""

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
import sys
from pathlib import Path


# --- machine home (injectable for tests via $ROSETTA_HOME) ---------------------------
def home():
    return Path(os.environ.get("ROSETTA_HOME") or Path.home())


# --- store roots (functions of home(), so tests can sandbox) --------------------------
def claude_root():          return home() / ".claude" / "projects"
def codex_root():           return home() / ".codex" / "sessions"
def factory_root():         return home() / ".factory" / "sessions"
def hermes_root():          return home() / ".hermes" / "sessions"
def cursor_root():          return home() / ".cursor" / "projects"
def gemini_root():          return home() / ".gemini" / "tmp"
def qwen_root():            return home() / ".qwen" / "tmp"
def opencode_msg_root():    return home() / ".local" / "share" / "opencode" / "storage" / "message"
def opencode_session_root():return home() / ".local" / "share" / "opencode" / "storage" / "session"
def goose_root():           return home() / ".local" / "share" / "goose" / "sessions"
def crush_dirs():           return [home() / ".local" / "share" / "crush", home() / ".config" / "crush"]
def continue_root():        return home() / ".continue" / "sessions"
def claude_agentmode_root():return home() / "Library" / "Application Support" / "Claude" / "local-agent-mode-sessions"
def codeium_windsurf_root():return home() / ".codeium" / "windsurf"


def editor_globalstorage_dirs():
    base = home() / "Library" / "Application Support"
    return [base / ed / "User" / "globalStorage"
            for ed in ("Code", "Code - Insiders", "VSCodium", "Cursor", "Windsurf")]


# Cline and its forks share the exact tasks/<id>/api_conversation_history.json layout.
CLINE_FAMILY_EXTS = {
    "cline": "saoudrizwan.claude-dev",
    "roo": "rooveterinaryinc.roo-cline",
    "kilo": "kilocode.kilo-code",
}

# Dotdir/store basenames that ARE supported agents (so the sweep doesn't call them "unknown").
KNOWN_STORE_DIRS = {
    ".claude", ".codex", ".factory", ".droid", ".hermes", ".cursor",
    ".gemini", ".qwen", ".continue", ".aider", ".aider-desk", ".codeium",
    ".cline", ".roo", ".kilocode", ".augment",
    "goose", "crush", "opencode",          # under ~/.config or ~/.local/share
}
# Agent-looking dirs that are NOT transcript stores — excluded from the sweep so it stays quiet.
NON_AGENT_DIRS = {
    ".amplify", ".cursor-tutor", ".claude-squad", ".claude----", ".warp",
    "com.apple.AMPLibraryAgent", "Claude.new_backup", "Claude-3p",
    "dev.warp.Warp-Stable", "dev.warp.Warp-Stable.new_backup",
}
# Matched by prefix (name == hint or name.startswith(hint)), NOT substring — a substring match made
# "droid" hit ".android" and "amp" hit "AMPLibraryAgent".
AGENTISH_HINTS = (
    "aider", "gemini", "cline", "claude", "codex", "factory", "hermes", "cursor",
    "opencode", "continue", "windsurf", "goose", "crush", "amp-", "amp_",
    "roo", "kilo", "augment", "qoder", "qwen", "codeium",
)

MAX_SCAN_BYTES = 8 * 1024 * 1024
CWD_RE = re.compile(r'"cwd"\s*:\s*"([^"]+)"')

HOME = Path.home()   # back-compat alias; resolvers use home()/roots above


def log(msg):
    print(f"[rosetta] {msg}", file=sys.stderr)


# --- timestamp normalization ----------------------------------------------------------
def to_utc_iso(value):
    """Best-effort normalize a timestamp (ISO string or epoch sec/ms) to UTC ISO. None on fail."""
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            ts = float(value)
            if ts > 1e12:        # milliseconds
                ts /= 1000.0
            return dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat()
        if isinstance(value, str):
            s = value.strip()
            if not s:
                return None
            if s.replace(".", "", 1).isdigit():
                return to_utc_iso(float(s))
            s = s.replace("Z", "+00:00")
            d = dt.datetime.fromisoformat(s)
            if d.tzinfo is None:
                d = d.replace(tzinfo=dt.timezone.utc)
            return d.astimezone(dt.timezone.utc).isoformat()
    except Exception:
        return None
    return None


def first_ts(obj):
    for key in ("timestamp", "ts", "created_at", "time"):
        if key in obj:
            t = to_utc_iso(obj[key])
            if t:
                return t
    payload = obj.get("payload")
    if isinstance(payload, dict):
        return first_ts(payload)
    return None


# --- content extraction (schema-tolerant) ---------------------------------------------
def blocks_to_text(content, max_chars):
    """Flatten a content value (str | list-of-blocks | dict) to plain text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        content = [content]
    if not isinstance(content, list):
        return str(content)

    parts = []
    for b in content:
        if isinstance(b, str):
            parts.append(b)
            continue
        if not isinstance(b, dict):
            continue
        bt = b.get("type")
        if bt in ("text", "input_text", "output_text", "reasoning_text", None) and b.get("text"):
            parts.append(b["text"])
        elif bt == "tool_use":
            inp = json.dumps(b.get("input", {}), ensure_ascii=False)
            parts.append(f"[tool_use: {b.get('name', '?')}] {inp[:300]}")
        elif bt == "tool_result":
            res = b.get("content")
            res = blocks_to_text(res, 300) if not isinstance(res, str) else res
            parts.append(f"[tool_result] {res[:300]}")
        elif bt == "thinking" and b.get("thinking"):
            parts.append(f"[thinking] {b['thinking']}")
        elif b.get("text"):
            parts.append(b["text"])
    text = "\n".join(p for p in parts if p)
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n…[truncated {len(text) - max_chars} chars]"
    return text


def normalize_role(role):
    if not role:
        return None
    role = role.lower()
    if role in ("human",):
        return "user"
    if role in ("gemini", "model", "ai"):
        return "assistant"
    return role


def _session_dict(messages, skipped, fallback_first=None, fallback_last=None):
    tstamps = [m["ts"] for m in messages if m["ts"]]
    return {
        "messages": messages,
        "kept": len(messages),
        "skipped": skipped,
        "first_ts": min(tstamps) if tstamps else fallback_first,
        "last_ts": max(tstamps) if tstamps else fallback_last,
    }


def collect_session(path, max_chars):
    """Default parser. JSONL (one object per line) or a single JSON document with a top-level
    "messages" list (Hermes session_*.json) or a bare array of message dicts (Cline). The whole-file
    shape is detected by parsing the entire file first; a JSONL file fails that and falls back."""
    messages = []
    skipped = 0
    with open(path, "r", errors="replace") as fh:
        raw = fh.read()

    records = None
    doc_first = doc_last = None
    try:
        doc = json.loads(raw)
    except Exception:
        doc = None
    if isinstance(doc, dict) and isinstance(doc.get("messages"), list):
        records = doc["messages"]
        doc_first = to_utc_iso(doc.get("session_start"))
        doc_last = to_utc_iso(doc.get("last_updated")) or doc_first
    elif isinstance(doc, list):
        records = doc
    if records is None:
        records = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except Exception:
                skipped += 1

    for obj in records:
        if not isinstance(obj, dict):
            skipped += 1
            continue

        role = content = None
        ts = first_ts(obj)
        payload = obj.get("payload")
        if obj.get("type") == "response_item" and isinstance(payload, dict) and payload.get("type") == "message":
            role, content = normalize_role(payload.get("role")), payload.get("content")
        elif obj.get("type") in ("user", "assistant") and isinstance(obj.get("message"), dict):
            role = normalize_role(obj["message"].get("role") or obj.get("type"))
            content = obj["message"].get("content")
        elif isinstance(obj.get("message"), dict) and "content" in obj["message"]:
            role = normalize_role(obj.get("role") or obj["message"].get("role"))
            content = obj["message"].get("content")
        elif "role" in obj and "content" in obj:
            role, content = normalize_role(obj.get("role")), obj.get("content")
        else:
            skipped += 1
            continue

        if role not in ("user", "assistant"):
            skipped += 1
            continue
        text = blocks_to_text(content, max_chars).strip()
        if not text:
            skipped += 1
            continue
        messages.append({"role": role, "text": text, "ts": ts})

    return _session_dict(messages, skipped, doc_first, doc_last)


# --- format-specific parsers ----------------------------------------------------------
def parse_default(unit, max_chars):
    return collect_session(unit["path"], max_chars)


def parse_gemini(unit, max_chars):
    """Gemini/Qwen JSONL: a header line (sessionId/projectHash), a `{"$set":{"messages":[…]}}`
    seed line, then individual `{type:user|gemini, content, timestamp}` lines; other `$set` lines
    are metadata."""
    records = []
    try:
        with open(unit["path"], "r", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    o = json.loads(line)
                except Exception:
                    continue
                if not isinstance(o, dict):
                    continue
                if isinstance(o.get("$set"), dict):
                    seed = o["$set"].get("messages")
                    if isinstance(seed, list):
                        records.extend(seed)
                    continue
                if o.get("type") in ("user", "gemini", "assistant", "model") and "content" in o:
                    records.append(o)
    except Exception:
        pass
    messages, skipped = [], 0
    for o in records:
        if not isinstance(o, dict):
            skipped += 1
            continue
        role = normalize_role(o.get("type") or o.get("role"))
        if role not in ("user", "assistant"):
            skipped += 1
            continue
        text = blocks_to_text(o.get("content"), max_chars).strip()
        if not text:
            skipped += 1
            continue
        messages.append({"role": role, "text": text, "ts": to_utc_iso(o.get("timestamp"))})
    return _session_dict(messages, skipped)


def parse_opencode(unit, max_chars):
    """opencode: a session is a DIR of one-JSON-per-message files (msg_*.json); role at top,
    text in summary.body (or parts[]), time.created in ms, path.cwd per message."""
    d = unit["path"]
    recs = []
    skipped = 0
    for f in sorted(d.glob("*.json")):
        try:
            recs.append(json.loads(f.read_text(errors="replace")))
        except Exception:
            skipped += 1
    recs.sort(key=lambda o: (o.get("time") or {}).get("created") or 0 if isinstance(o, dict) else 0)
    messages = []
    for o in recs:
        if not isinstance(o, dict):
            skipped += 1
            continue
        role = normalize_role(o.get("role"))
        if role not in ("user", "assistant"):
            skipped += 1
            continue
        body = (o.get("summary") or {}).get("body") if isinstance(o.get("summary"), dict) else None
        if not body and isinstance(o.get("parts"), list):
            body = "\n".join(p.get("text", "") for p in o["parts"] if isinstance(p, dict))
        text = blocks_to_text(body or o.get("content"), max_chars).strip()
        if not text:
            skipped += 1
            continue
        messages.append({"role": role, "text": text,
                         "ts": to_utc_iso((o.get("time") or {}).get("created"))})
    return _session_dict(messages, skipped)


def parse_continue(unit, max_chars):
    """Continue: new format = history:[{message:{role,content}}] or messages:[…]; old format =
    history.timeline[].step (user_input / description). Tolerant of both; dedups repeats."""
    try:
        o = json.loads(Path(unit["path"]).read_text(errors="replace"))
    except Exception:
        return _session_dict([], 1)
    items = []
    hist = o.get("history")
    if isinstance(hist, list):
        for it in hist:
            m = it.get("message") if isinstance(it, dict) else None
            if isinstance(m, dict):
                items.append((normalize_role(m.get("role")), m.get("content")))
    elif isinstance(o.get("messages"), list):
        for m in o["messages"]:
            if isinstance(m, dict):
                items.append((normalize_role(m.get("role")), m.get("content")))
    elif isinstance(hist, dict) and isinstance(hist.get("timeline"), list):
        for it in hist["timeline"]:
            step = it.get("step") or {}
            obs = it.get("observation") or {}
            if obs.get("user_input"):
                items.append(("user", obs["user_input"]))
            name = (step.get("name") or "")
            if name != "User Input" and step.get("description"):
                items.append(("assistant", step["description"]))
    messages, skipped, last = [], 0, None
    for role, content in items:
        if role not in ("user", "assistant"):
            skipped += 1
            continue
        text = blocks_to_text(content, max_chars).strip()
        if not text or (role, text) == last:
            skipped += 1
            continue
        last = (role, text)
        messages.append({"role": role, "text": text, "ts": None})
    sess_ts = to_utc_iso(o.get("session_info", {}).get("date_created") if isinstance(o.get("session_info"), dict) else None)
    return _session_dict(messages, skipped, sess_ts, sess_ts)


def parse_aider(unit, max_chars):
    """Aider .aider.chat.history.md (markdown): `#### ` lines = user turns; `> ` lines = aider's own
    output (skipped); `# aider chat started` = session boundary; other prose = assistant."""
    try:
        text = Path(unit["path"]).read_text(errors="replace")
    except Exception:
        return _session_dict([], 1)
    messages, skipped = [], 0
    cur_role, buf = None, []

    def flush():
        nonlocal buf, cur_role, skipped
        if cur_role and buf:
            t = "\n".join(buf).strip()
            if t:
                messages.append({"role": cur_role, "text": t[:max_chars], "ts": None})
            else:
                skipped += 1
        buf = []

    for line in text.splitlines():
        if line.startswith("# aider chat started"):
            flush(); cur_role = None
        elif line.startswith("#### "):
            if cur_role != "user":
                flush(); cur_role = "user"
            buf.append(line[5:])
        elif line.startswith(">") or line.startswith("#"):
            continue                       # aider echo / headers — not conversation
        else:
            if cur_role != "assistant":
                if not line.strip():
                    continue
                flush(); cur_role = "assistant"
            buf.append(line)
    flush()
    return _session_dict(messages, skipped)


def parse_crush(unit, max_chars):
    """Crush (Charm): sqlite. UNVERIFIED schema — coded against a plausible messages(session_id,
    role, parts|content, created_at) table; refine when real data exists."""
    db, sid = unit["db"], unit["session_id"]
    messages, skipped = [], 0
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        cols = {r[1] for r in con.execute("PRAGMA table_info(messages)")}
        textcol = "parts" if "parts" in cols else ("content" if "content" in cols else None)
        tcol = "created_at" if "created_at" in cols else ("created" if "created" in cols else None)
        q = f"SELECT role, {textcol} AS body, {tcol} AS t FROM messages WHERE session_id=? ORDER BY {tcol}"
        for row in con.execute(q, (sid,)):
            role = normalize_role(row["role"])
            if role not in ("user", "assistant"):
                skipped += 1
                continue
            body = row["body"]
            try:
                parsed = json.loads(body)
                body = blocks_to_text(parsed, max_chars)
            except Exception:
                pass
            text = blocks_to_text(body, max_chars).strip()
            if not text:
                skipped += 1
                continue
            messages.append({"role": role, "text": text, "ts": to_utc_iso(row["t"])})
        con.close()
    except Exception as e:
        log(f"crush: could not read {db}: {e}")
    return _session_dict(messages, skipped)


# --- cwd probing ----------------------------------------------------------------------
def probe_cwd(path):
    try:
        with open(path, "r", errors="replace") as fh:
            head = fh.read(MAX_SCAN_BYTES)
    except Exception:
        return None
    m = CWD_RE.search(head)
    return m.group(1) if m else None


def file_mentions_path(path, needle):
    try:
        with open(path, "r", errors="replace") as fh:
            return needle in fh.read(MAX_SCAN_BYTES)
    except Exception:
        return False


def cwd_matches(cwd, project, include_subdirs):
    if not cwd:
        return False
    cwd = cwd.rstrip("/")
    if cwd == project:
        return True
    if include_subdirs and cwd.startswith(project + "/"):
        return True
    return False


# --- path encoders --------------------------------------------------------------------
def enc_path(project):
    """Claude/Factory encoding: every char outside [A-Za-z0-9] -> '-' (so '.','_','/' all collapse)."""
    return re.sub(r"[^A-Za-z0-9]", "-", project)


def cursor_enc(project):
    """Cursor encoding: strip leading slash, then every non-alphanumeric -> '-'."""
    return re.sub(r"[^A-Za-z0-9]", "-", project.lstrip("/"))


def matching_dirs(root, encoded, include_subdirs):
    if not root.exists():
        return []
    out = []
    for d in root.iterdir():
        if not d.is_dir():
            continue
        if d.name == encoded or (include_subdirs and d.name.startswith(encoded + "-")):
            out.append(d)
    return out


def _file_units(files):
    return [{"id": f.stem, "src": str(f), "path": f} for f in files]


# --- resolvers (return {match_mode, units, extra}) ------------------------------------
def resolve_claude(project, include_subdirs):
    files = []
    for d in matching_dirs(claude_root(), enc_path(project), include_subdirs):
        files.extend(sorted(d.glob("*.jsonl")))
    return {"match_mode": "path-encoded project dir", "units": _file_units(files), "extra": {}}


def resolve_factory(project, include_subdirs):
    files = []
    for d in matching_dirs(factory_root(), enc_path(project), include_subdirs):
        files.extend(sorted(d.glob("*.jsonl")))
    flat = list(factory_root().glob("*.jsonl")) if factory_root().exists() else []
    return {"match_mode": "path-encoded project dir", "units": _file_units(files),
            "extra": {"flat_files_without_cwd": len(flat)}}


def resolve_cursor(project, include_subdirs):
    files = []
    for d in matching_dirs(cursor_root(), cursor_enc(project), include_subdirs):
        files.extend(sorted(d.glob("agent-transcripts/**/*.jsonl")))
    return {"match_mode": "cursor-encoded project dir", "units": _file_units(files), "extra": {}}


def resolve_codex(project, include_subdirs):
    files, no_cwd = [], 0
    if codex_root().exists():
        for f in sorted(codex_root().glob("**/rollout-*.jsonl")):
            cwd = probe_cwd(f)
            if cwd is None:
                no_cwd += 1
            elif cwd_matches(cwd, project, include_subdirs):
                files.append(f)
    return {"match_mode": "scan + cwd filter", "units": _file_units(files),
            "extra": {"sessions_without_cwd": no_cwd}}


def resolve_hermes(project, include_subdirs):
    files, dumps = [], 0
    r = hermes_root()
    if r.exists():
        dumps = len(list(r.glob("request_dump_*.json")))
        for f in sorted(r.glob("*.jsonl")) + sorted(r.glob("session_*.json")):
            if file_mentions_path(f, project):
                files.append(f)
    return {"match_mode": "fuzzy: project path mentioned in transcript", "units": _file_units(files),
            "extra": {"request_dumps_excluded": dumps}}


def _gemini_like(root, project, include_subdirs):
    """Gemini/Qwen: ~/.../tmp/<name-or-hash>/chats/*.jsonl. Attribute to project via projects.json
    (path->name), the directory basename, or the projectHash in the session header."""
    if not root.exists():
        return []
    names = set()
    pj = root.parent / "projects.json"           # ~/.gemini/projects.json
    if pj.exists():
        try:
            mp = json.loads(pj.read_text()).get("projects", {})
            for path, name in mp.items():
                if cwd_matches(path.rstrip("/"), project, include_subdirs):
                    names.add(name)
        except Exception:
            pass
    names.add(Path(project).name)                  # basename fallback
    phash = hashlib.sha256(project.encode()).hexdigest()
    files = []
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        chats = d / "chats"
        if not chats.exists():
            continue
        matched = d.name in names
        if not matched:
            for f in chats.glob("*.jsonl"):        # fall back to projectHash in the header
                try:
                    head = json.loads(open(f, errors="replace").readline())
                    if head.get("projectHash") == phash:
                        matched = True
                        break
                except Exception:
                    continue
        if matched:
            files.extend(sorted(chats.glob("*.jsonl")))
    return _file_units(files)


def resolve_gemini(project, include_subdirs):
    return {"match_mode": "tmp/<project>/chats + projects.json map",
            "units": _gemini_like(gemini_root(), project, include_subdirs), "extra": {}}


def resolve_qwen(project, include_subdirs):
    return {"match_mode": "tmp/<project>/chats (gemini-fork)",
            "units": _gemini_like(qwen_root(), project, include_subdirs), "extra": {}}


def resolve_opencode(project, include_subdirs):
    """opencode: each session is a dir of message files; cwd is in each message's path.cwd."""
    units = []
    root = opencode_msg_root()
    if root.exists():
        for d in sorted(p for p in root.iterdir() if p.is_dir()):
            cwd = None
            for f in d.glob("*.json"):
                try:
                    o = json.loads(f.read_text(errors="replace"))
                    cwd = (o.get("path") or {}).get("cwd")
                except Exception:
                    cwd = None
                if cwd:
                    break
            if cwd_matches((cwd or "").rstrip("/"), project, include_subdirs):
                units.append({"id": d.name, "src": str(d), "path": d})
    return {"match_mode": "session dir; path.cwd per message", "units": units, "extra": {}}


def resolve_continue(project, include_subdirs):
    """Continue has no reliable cwd → fuzzy: keep a session whose JSON mentions the project path
    (or whose workspaceDirectory matches)."""
    units = []
    r = continue_root()
    if r.exists():
        for f in sorted(r.glob("*.json")):
            if f.name == "sessions.json":
                continue
            if file_mentions_path(f, project):
                units.append({"id": f.stem, "src": str(f), "path": f})
    return {"match_mode": "fuzzy: project path mentioned in session", "units": units, "extra": {}}


def resolve_claude_agent_mode(project, include_subdirs):
    """Claude Desktop local agent mode: JSONL transcripts with a cwd field (often synthetic
    /sessions/<slug>); match on cwd."""
    units, root = [], claude_agentmode_root()
    if root.exists():
        for f in sorted(root.glob("**/*.jsonl")):
            if f.name == "audit.jsonl":
                continue
            cwd = probe_cwd(f)
            if cwd_matches((cwd or "").rstrip("/"), project, include_subdirs) or file_mentions_path(f, project):
                units.append({"id": f.stem, "src": str(f), "path": f})
    return {"match_mode": "agent-mode JSONL; cwd field", "units": units, "extra": {}}


def resolve_aider(project, include_subdirs):
    """Aider writes .aider.chat.history.md INTO the project dir → exact, location-based scoping."""
    units = []
    proj = Path(project)
    candidates = [proj / ".aider.chat.history.md"]
    if include_subdirs and proj.exists():
        candidates += list(proj.glob("**/.aider.chat.history.md"))
    for f in candidates:
        if f.exists():
            units.append({"id": f"{proj.name}-{f.parent.name}", "src": str(f), "path": f})
    return {"match_mode": "per-project .aider.chat.history.md", "units": units, "extra": {}}


def resolve_clinefamily(agent):
    """Build a resolver for Cline / Roo / Kilo (identical tasks/<id>/api_conversation_history.json
    layout) across every editor's globalStorage. Scoping is weak → fuzzy path mention."""
    ext = CLINE_FAMILY_EXTS[agent]

    def _resolve(project, include_subdirs):
        units = []
        for gs in editor_globalstorage_dirs():
            tasks = gs / ext / "tasks"
            if not tasks.exists():
                continue
            for d in sorted(p for p in tasks.iterdir() if p.is_dir()):
                hist = d / "api_conversation_history.json"
                if not hist.exists():
                    continue
                meta = d / "task_metadata.json"
                if file_mentions_path(hist, project) or (meta.exists() and file_mentions_path(meta, project)):
                    units.append({"id": f"{gs.parent.parent.parent.name}-{d.name}",
                                  "src": str(hist), "path": hist})
        return {"match_mode": "globalStorage tasks; fuzzy path mention", "units": units, "extra": {}}
    return _resolve


def resolve_goose(project, include_subdirs):
    units, no_cwd = [], 0
    r = goose_root()
    if r.exists():
        for f in sorted(r.glob("*.jsonl")):
            cwd = probe_cwd(f)
            if cwd is None and not file_mentions_path(f, project):
                no_cwd += 1
                continue
            if cwd_matches((cwd or "").rstrip("/"), project, include_subdirs) or file_mentions_path(f, project):
                units.append({"id": f.stem, "src": str(f), "path": f})
    return {"match_mode": "sessions/*.jsonl; cwd in meta or fuzzy", "units": units,
            "extra": {"sessions_without_cwd": no_cwd}}


def resolve_crush(project, include_subdirs):
    """Crush sqlite (UNVERIFIED schema): one unit per session row whose cwd/title matches, else
    fuzzy. Defensive: any schema mismatch yields no units (and a logged note)."""
    units = []
    for base in crush_dirs():
        if not base.exists():
            continue
        for db in base.glob("**/*.db"):
            try:
                con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
                con.row_factory = sqlite3.Row
                tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if "sessions" not in tables:
                    con.close(); continue
                scols = {r[1] for r in con.execute("PRAGMA table_info(sessions)")}
                cwdcol = next((c for c in ("cwd", "working_dir", "directory", "path") if c in scols), None)
                for row in con.execute("SELECT * FROM sessions"):
                    cwd = (row[cwdcol] if cwdcol else None)
                    if cwd_matches((cwd or "").rstrip("/"), project, include_subdirs) or cwd is None:
                        units.append({"id": f"{db.stem}-{row['id']}", "src": f"{db}#{row['id']}",
                                      "db": db, "session_id": row["id"]})
                con.close()
            except Exception as e:
                log(f"crush: skipping {db}: {e}")
    return {"match_mode": "sqlite sessions (UNVERIFIED)", "units": units, "extra": {"unverified": True}}


def resolve_windsurf(project, include_subdirs):
    """Windsurf/Cascade (Codeium) — best-effort, UNVERIFIED. Scan ~/.codeium/windsurf for
    conversation-shaped JSON/JSONL; fuzzy path mention."""
    units, root = [], codeium_windsurf_root()
    if root.exists():
        for f in list(root.glob("**/*.jsonl")) + list(root.glob("**/*conversation*.json")) + list(root.glob("**/cascade*/**/*.json")):
            if f.is_file() and file_mentions_path(f, project):
                units.append({"id": f.stem, "src": str(f), "path": f})
    return {"match_mode": "best-effort scan (UNVERIFIED)", "units": units, "extra": {"unverified": True}}


def resolve_augment(project, include_subdirs):
    """Augment — best-effort, UNVERIFIED. Scan augment.vscode-augment globalStorage for
    conversation-shaped JSON; fuzzy path mention."""
    units = []
    for gs in editor_globalstorage_dirs():
        d = gs / "augment.vscode-augment"
        if not d.exists():
            continue
        for f in list(d.glob("**/*.json")) + list(d.glob("**/*.jsonl")):
            if f.is_file() and file_mentions_path(f, project):
                units.append({"id": f.stem, "src": str(f), "path": f})
    return {"match_mode": "best-effort globalStorage scan (UNVERIFIED)", "units": units,
            "extra": {"unverified": True}}


# --- agent registry: name -> resolver + parser + store presence -----------------------
AGENTS = {
    "claude":       {"resolver": resolve_claude,            "parser": parse_default,  "root": claude_root},
    "codex":        {"resolver": resolve_codex,             "parser": parse_default,  "root": codex_root},
    "factory":      {"resolver": resolve_factory,           "parser": parse_default,  "root": factory_root},
    "hermes":       {"resolver": resolve_hermes,            "parser": parse_default,  "root": hermes_root},
    "cursor":       {"resolver": resolve_cursor,            "parser": parse_default,  "root": cursor_root},
    "gemini":       {"resolver": resolve_gemini,            "parser": parse_gemini,   "root": gemini_root},
    "qwen":         {"resolver": resolve_qwen,              "parser": parse_gemini,   "root": qwen_root},
    "opencode":     {"resolver": resolve_opencode,          "parser": parse_opencode, "root": opencode_msg_root},
    "cline":        {"resolver": resolve_clinefamily("cline"), "parser": parse_default, "root": None},
    "roo":          {"resolver": resolve_clinefamily("roo"),   "parser": parse_default, "root": None},
    "kilo":         {"resolver": resolve_clinefamily("kilo"),  "parser": parse_default, "root": None},
    "continue":     {"resolver": resolve_continue,          "parser": parse_continue, "root": continue_root},
    "claude-agent": {"resolver": resolve_claude_agent_mode, "parser": parse_default,  "root": claude_agentmode_root},
    "aider":        {"resolver": resolve_aider,             "parser": parse_aider,    "root": None},
    "goose":        {"resolver": resolve_goose,             "parser": parse_default,  "root": goose_root},
    "crush":        {"resolver": resolve_crush,             "parser": parse_crush,    "root": None},
    "windsurf":     {"resolver": resolve_windsurf,          "parser": parse_default,  "root": codeium_windsurf_root},
    "augment":      {"resolver": resolve_augment,           "parser": parse_default,  "root": None},
}
DEFAULT_AGENTS = ",".join(AGENTS.keys())


# --- discovery sweep ------------------------------------------------------------------
def discovery_sweep():
    """Report agent-looking dotdirs not in the registry and not on the exclusion list."""
    unknown, candidates = [], []
    h = home()
    for base in (h, h / ".config", h / "Library" / "Application Support"):
        if not base.exists():
            continue
        try:
            candidates += [d for d in base.iterdir() if d.is_dir()]
        except Exception:
            continue
    for d in candidates:
        if d.name in KNOWN_STORE_DIRS or d.name in NON_AGENT_DIRS:
            continue
        name = d.name.lower().lstrip(".")
        if any(name == hbt or name.startswith(hbt) for hbt in AGENTISH_HINTS):
            unknown.append(str(d))
    return sorted(set(unknown))


# --- machine-wide discovery ----------------------------------------------------------
def _mtime_range(files):
    ts = []
    for f in files:
        try:
            t = to_utc_iso(f.stat().st_mtime)
            if t:
                ts.append(t)
        except Exception:
            continue
    return [min(ts), max(ts)] if ts else [None, None]


def codex_cwd_fast(path):
    try:
        with open(path, "r", errors="replace") as fh:
            o = json.loads(fh.readline())
    except Exception:
        return None
    if isinstance(o, dict):
        p = o.get("payload")
        if isinstance(p, dict) and p.get("cwd"):
            return p["cwd"]
        if o.get("cwd"):
            return o["cwd"]
    return None


def discover_all_projects():
    """Map every project with agent history → per-agent session counts + activity range. Cheap:
    counts from globs, activity from mtime; real cwds via probing one session per dir."""
    projects = {}

    def slot(cwd):
        return projects.setdefault(cwd.rstrip("/"), {})

    # path-encoded, one-dir-per-project
    for root_fn, agent in ((claude_root, "claude"), (factory_root, "factory")):
        root = root_fn()
        if not root.exists():
            continue
        for d in sorted(p for p in root.iterdir() if p.is_dir()):
            files = sorted(d.glob("*.jsonl"))
            if not files:
                continue
            cwd = probe_cwd(max(files, key=lambda f: f.stat().st_mtime)) or f"({agent}) {d.name}"
            lo, hi = _mtime_range(files)
            slot(cwd)[agent] = {"sessions": len(files), "first": lo, "last": hi, "store": str(d)}

    # cursor (no per-line cwd)
    cursor_unresolved = []
    if cursor_root().exists():
        for d in sorted(p for p in cursor_root().iterdir() if p.is_dir()):
            files = sorted(d.glob("agent-transcripts/**/*.jsonl"))
            if not files:
                continue
            cursor_unresolved.append(d.name)
            lo, hi = _mtime_range(files)
            slot(f"(cursor) {d.name}")["cursor"] = {"sessions": len(files), "first": lo, "last": hi}

    # codex (date-bucketed; group by cwd)
    codex_no_cwd = 0
    if codex_root().exists():
        groups = {}
        for f in sorted(codex_root().glob("**/rollout-*.jsonl")):
            cwd = codex_cwd_fast(f)
            groups.setdefault(cwd.rstrip("/"), []).append(f) if cwd else None
            if not cwd:
                codex_no_cwd += 1
        for cwd, files in groups.items():
            lo, hi = _mtime_range(files)
            slot(cwd)["codex"] = {"sessions": len(files), "first": lo, "last": hi}

    # gemini / qwen (tmp/<name>/chats; resolve name->path via projects.json)
    for root_fn, agent in ((gemini_root, "gemini"), (qwen_root, "qwen")):
        root = root_fn()
        if not root.exists():
            continue
        name_to_path = {}
        pj = root.parent / "projects.json"
        if pj.exists():
            try:
                for path, name in json.loads(pj.read_text()).get("projects", {}).items():
                    name_to_path[name] = path
            except Exception:
                pass
        for d in sorted(p for p in root.iterdir() if p.is_dir()):
            files = sorted((d / "chats").glob("*.jsonl")) if (d / "chats").exists() else []
            if not files:
                continue
            key = name_to_path.get(d.name, f"({agent}) {d.name}")
            lo, hi = _mtime_range(files)
            slot(key)[agent] = {"sessions": len(files), "first": lo, "last": hi}

    # opencode (group message dirs by path.cwd)
    if opencode_msg_root().exists():
        for d in sorted(p for p in opencode_msg_root().iterdir() if p.is_dir()):
            files = sorted(d.glob("*.json"))
            if not files:
                continue
            cwd = None
            for f in files:
                try:
                    cwd = (json.loads(f.read_text(errors="replace")).get("path") or {}).get("cwd")
                except Exception:
                    cwd = None
                if cwd:
                    break
            lo, hi = _mtime_range(files)
            slot((cwd or f"(opencode) {d.name}").rstrip("/")).setdefault("opencode",
                {"sessions": 0, "first": lo, "last": hi})["sessions"] += 1

    # goose / claude-agent (cwd-bearing jsonl)
    if goose_root().exists():
        for f in sorted(goose_root().glob("*.jsonl")):
            cwd = probe_cwd(f) or "(goose) unscoped"
            e = slot(cwd.rstrip("/")).setdefault("goose", {"sessions": 0, "first": None, "last": None})
            e["sessions"] += 1
    if claude_agentmode_root().exists():
        for f in sorted(claude_agentmode_root().glob("**/*.jsonl")):
            if f.name == "audit.jsonl":
                continue
            cwd = probe_cwd(f) or "(claude-agent) unscoped"
            e = slot(cwd.rstrip("/")).setdefault("claude-agent", {"sessions": 0, "first": None, "last": None})
            e["sessions"] += 1

    # unscoped agents → counts only
    unscoped = {}
    for gs in editor_globalstorage_dirs():
        for agent, ext in CLINE_FAMILY_EXTS.items():
            t = gs / ext / "tasks"
            if t.exists():
                unscoped[agent] = unscoped.get(agent, 0) + sum(
                    1 for d in t.iterdir() if (d / "api_conversation_history.json").exists())
    if continue_root().exists():
        unscoped["continue"] = sum(1 for f in continue_root().glob("*.json") if f.name != "sessions.json")
    hermes_files = (len(list(hermes_root().glob("*.jsonl"))) + len(list(hermes_root().glob("session_*.json")))) if hermes_root().exists() else 0

    return {
        "projects": projects,
        "cursor_unresolved": sorted(set(cursor_unresolved)),
        "codex_sessions_without_cwd": codex_no_cwd,
        "unscoped_agents": unscoped,
        "hermes_note": f"Hermes is not project-scoped; {hermes_files} session files not attributed here.",
    }


# --- main -----------------------------------------------------------------------------
def slugify(s):
    return re.sub(r"[^A-Za-z0-9._-]", "_", s)


def write_session_md(path, agent, src, project, data):
    lines = [
        f"# {agent} session — {Path(src).name}",
        "",
        f"- agent: {agent}",
        f"- source: {src}",
        f"- project: {project}",
        f"- messages: {data['kept']} (skipped {data['skipped']} non-conversational/unparseable lines)",
        f"- date range (UTC): {data['first_ts']} .. {data['last_ts']}",
        "",
        "---",
        "",
    ]
    for m in data["messages"]:
        stamp = f" [{m['ts']}]" if m["ts"] else ""
        lines.append(f"## {m['role']}{stamp}")
        lines.append("")
        lines.append(m["text"])
        lines.append("")
    path.write_text("\n".join(lines))


def main():
    ap = argparse.ArgumentParser(description="Rosetta transcript collector")
    ap.add_argument("--project", default=os.getcwd(), help="project path (default: cwd)")
    ap.add_argument("--out", default=None, help="work dir for manifest + normalized sessions")
    ap.add_argument("--all-projects", action="store_true",
                    help="machine-wide discovery: index every project with agent history (no per-session parse)")
    ap.add_argument("--since", default=None, help="only sessions whose last activity >= YYYY-MM-DD")
    ap.add_argument("--include-subdirs", action="store_true",
                    help="also include sessions whose cwd is UNDER the project (monorepo mode)")
    ap.add_argument("--max-chars", type=int, default=4000, help="truncate each message to N chars")
    ap.add_argument("--agents", default=DEFAULT_AGENTS, help="comma-separated subset of agents to scan")
    args = ap.parse_args()

    if args.all_projects:
        out = Path(args.out) if args.out else (Path.cwd() / ".agents" / "rosetta" / "discovery")
        out.mkdir(parents=True, exist_ok=True)
        disc = discover_all_projects()
        index = {
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "machine_home": str(home()),
            "totals": {"projects": len(disc["projects"])},
            "projects": disc["projects"],
            "cursor_unresolved": disc["cursor_unresolved"],
            "codex_sessions_without_cwd": disc["codex_sessions_without_cwd"],
            "unscoped_agents": disc["unscoped_agents"],
            "hermes_note": disc["hermes_note"],
            "unknown_stores": discovery_sweep(),
        }
        (out / "projects-index.json").write_text(json.dumps(index, indent=2))
        cols = ["claude", "codex", "factory", "gemini", "opencode", "claude-agent"]
        lines = ["# Agent-conversation projects on this machine", "",
                 f"_Discovered {index['generated_at']} · {index['totals']['projects']} projects_", "",
                 "| Project (cwd) | " + " | ".join(cols) + " | last |",
                 "|---|" + "|".join("---" for _ in cols) + "|---|"]
        for cwd in sorted(disc["projects"]):
            ag = disc["projects"][cwd]
            lasts = [v.get("last") for v in ag.values() if isinstance(v, dict) and v.get("last")]
            cells = " | ".join(str(ag[c]["sessions"]) if c in ag else "—" for c in cols)
            lines.append(f"| {cwd} | {cells} | {max(lasts) if lasts else '—'} |")
        if disc["unscoped_agents"]:
            lines += ["", "Unscoped agents (not project-attributable): " +
                      ", ".join(f"{k}={v}" for k, v in sorted(disc["unscoped_agents"].items()))]
        (out / "projects-index.md").write_text("\n".join(lines) + "\n")
        log(f"discovered {index['totals']['projects']} projects → {out / 'projects-index.json'}")
        print(json.dumps(index["totals"]))
        return

    if not args.out:
        ap.error("--out is required (unless --all-projects)")
    project = str(Path(args.project).resolve()).rstrip("/")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    since = to_utc_iso(args.since + "T00:00:00") if args.since else None
    wanted = [a.strip() for a in args.agents.split(",") if a.strip()]

    log(f"project: {project}")
    log(f"out: {out}")

    manifest = {
        "project": project,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "options": {"since": since, "include_subdirs": args.include_subdirs, "max_chars": args.max_chars},
        "agents": {},
        "unknown_stores": discovery_sweep(),
        "totals": {"sessions": 0, "messages": 0, "skipped_lines": 0},
    }

    for agent in wanted:
        spec = AGENTS.get(agent)
        if not spec:
            manifest["agents"][agent] = {"error": "unknown agent (not in registry)"}
            continue
        entry = {"sessions": 0, "messages": 0, "skipped_lines": 0,
                 "date_range": [None, None], "match_mode": None, "extra": {}, "files": []}
        try:
            res = spec["resolver"](project, args.include_subdirs)
        except Exception as e:
            entry["error"] = f"resolver failed: {e}"
            manifest["agents"][agent] = entry
            log(f"{agent}: resolver error: {e}")
            continue
        parser = spec["parser"]
        entry["match_mode"] = res["match_mode"]
        entry["extra"] = res["extra"]

        firsts, lasts = [], []
        for unit in res["units"]:
            try:
                data = parser(unit, args.max_chars)
            except Exception as e:
                log(f"{agent}: parse error on {unit.get('src')}: {e}")
                continue
            if data["kept"] == 0:
                continue
            if since and data["last_ts"] and data["last_ts"] < since:
                continue
            outname = f"{agent}__{slugify(unit['id'])}.md"
            write_session_md(out / outname, agent, unit["src"], project, data)
            entry["files"].append({"source": unit["src"], "normalized": outname,
                                   "messages": data["kept"], "skipped": data["skipped"],
                                   "first_ts": data["first_ts"], "last_ts": data["last_ts"]})
            entry["sessions"] += 1
            entry["messages"] += data["kept"]
            entry["skipped_lines"] += data["skipped"]
            if data["first_ts"]:
                firsts.append(data["first_ts"])
            if data["last_ts"]:
                lasts.append(data["last_ts"])

        entry["date_range"] = [min(firsts) if firsts else None, max(lasts) if lasts else None]
        manifest["agents"][agent] = entry
        manifest["totals"]["sessions"] += entry["sessions"]
        manifest["totals"]["messages"] += entry["messages"]
        manifest["totals"]["skipped_lines"] += entry["skipped_lines"]
        log(f"{agent}: {entry['sessions']} sessions, {entry['messages']} messages "
            f"({res['match_mode']}); extra={res['extra']}")

    with open(out / "manifest.json", "w") as fh:
        json.dump(manifest, fh, indent=2)
    log(f"wrote {out / 'manifest.json'}")
    print(json.dumps(manifest["totals"]))


if __name__ == "__main__":
    main()
