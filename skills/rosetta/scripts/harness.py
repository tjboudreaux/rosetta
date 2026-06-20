#!/usr/bin/env python3
"""Rosetta harness export — deterministic docs bridge from machine contract JSON."""
import argparse
import difflib
import json
import re
import sys
from pathlib import Path

START = "<!-- ROSETTA:HARNESS:START -->"
END = "<!-- ROSETTA:HARNESS:END -->"
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def load_contract(path):
    if not path.exists():
        raise SystemExit("missing_harness_json")
    try:
        data = json.loads(path.read_text())
    except Exception as e:
        raise SystemExit(f"invalid_harness_json: {e}")
    if not isinstance(data, dict) or data.get("schema") != "rosetta-harness-export/v1":
        raise SystemExit("invalid_harness_schema")
    return data


def fmt_list(values):
    values = [str(v) for v in (values or [])]
    return ", ".join(values) if values else "none"


def marker_block(title, status, lines):
    body = [START, f"## {title} [{status or 'confirm'}]", ""]
    body.extend(lines or ["[confirm] Missing harness contract section; confirm before relying on this export."])
    body.append(END)
    return "\n".join(body) + "\n"


def render_architecture(architecture):
    if not isinstance(architecture, dict):
        return marker_block("Architecture", "confirm", None)
    status = architecture.get("status") or "confirm"
    lines = [architecture.get("summary") or "[confirm] Missing architecture summary.", "", "### Components"]
    components = architecture.get("components") or []
    if not components:
        lines.append("- [confirm] No components supplied.")
    for comp in components:
        if not isinstance(comp, dict):
            continue
        lines.append(f"- **{comp.get('name') or 'Unnamed component'}** ({comp.get('status') or 'confirm'}): "
                     f"{comp.get('description') or '[confirm] Missing description.'}")
        lines.append(f"  - Paths: {fmt_list(comp.get('paths'))}")
        lines.append(f"  - Decisions: {fmt_list(comp.get('decisions'))}")
    return marker_block("Architecture", status, lines)


def render_mobile(mobile):
    if not isinstance(mobile, dict):
        return marker_block("Mobile", "confirm", None)
    status = mobile.get("status") or "confirm"
    lines = [mobile.get("summary") or "[confirm] Missing mobile summary.", "", "### Facts"]
    facts = mobile.get("facts") or []
    if not facts:
        lines.append("- [confirm] No mobile facts supplied.")
    else:
        lines.extend(f"- {fact}" for fact in facts)
    lines.extend(["", f"Decisions: {fmt_list(mobile.get('decisions'))}"])
    return marker_block("Mobile", status, lines)


def render_domain(domain):
    status = domain.get("status") or "confirm"
    title = domain.get("title") or domain.get("slug") or "Domain"
    lines = [domain.get("summary") or "[confirm] Missing domain summary.", "",
             f"Paths: {fmt_list(domain.get('paths'))}",
             f"Decisions: {fmt_list(domain.get('decisions'))}"]
    return marker_block(title, status, lines)


def validate_target_rel(rel):
    p = Path(rel)
    if p.is_absolute() or ".." in p.parts:
        raise ValueError(f"target escapes project: {rel}")
    if rel in {"ARCHITECTURE.md", "docs/MOBILE.md"}:
        return rel
    parts = p.parts
    if len(parts) == 3 and parts[0] == "domains" and parts[2] == "README.md" and SLUG_RE.match(parts[1]):
        return rel
    raise ValueError(f"target not allowlisted: {rel}")


def ensure_safe_target(project_root, rel):
    rel = validate_target_rel(rel)
    project_real = project_root.resolve()
    target = project_root / rel
    existing = target if target.exists() else target.parent
    try:
        existing_real = existing.resolve()
        existing_real.relative_to(project_real)
    except (ValueError, OSError):
        raise ValueError(f"target resolves outside project: {rel}")
    if target.exists():
        try:
            target.resolve().relative_to(project_real)
        except (ValueError, OSError):
            raise ValueError(f"target resolves outside project: {rel}")
    return target


def build_targets(contract, project_root):
    warnings = []
    targets = []
    targets.append({"path": "ARCHITECTURE.md", "content": render_architecture(contract.get("architecture"))})
    targets.append({"path": "docs/MOBILE.md", "content": render_mobile(contract.get("mobile"))})
    domains = contract.get("domains") or []
    if not isinstance(domains, list):
        warnings.append({"code": "invalid_domains", "message": "domains must be a list"})
        domains = []
    for i, domain in enumerate(domains):
        if not isinstance(domain, dict):
            warnings.append({"code": "invalid_domain", "index": i, "message": "domain must be an object"})
            continue
        slug = domain.get("slug")
        if not isinstance(slug, str) or not SLUG_RE.match(slug):
            warnings.append({"code": "invalid_domain_slug", "index": i, "slug": slug})
            continue
        targets.append({"path": f"domains/{slug}/README.md", "content": render_domain(domain)})
    safe_targets = []
    for target in targets:
        try:
            ensure_safe_target(project_root, target["path"])
        except ValueError as e:
            warnings.append({"code": "unsafe_target", "path": target["path"], "message": str(e)})
            continue
        safe_targets.append(target)
    return safe_targets, warnings


def replace_marked(existing, block):
    start = existing.find(START)
    end = existing.find(END)
    if start == -1 or end == -1 or end < start:
        return None
    end += len(END)
    replacement = block.rstrip("\n")
    return existing[:start] + replacement + existing[end:] + ("" if existing.endswith("\n") else "\n")


def planned_text_for_target(path, block):
    if not path.exists():
        return block
    existing = path.read_text()
    replaced = replace_marked(existing, block)
    return replaced if replaced is not None else block


def diff_for_target(path, rel, new_text):
    old = path.read_text() if path.exists() else ""
    return "".join(difflib.unified_diff(
        old.splitlines(True), new_text.splitlines(True),
        fromfile=f"a/{rel}", tofile=f"b/{rel}", lineterm=""))


def patch_for_targets(project_root, targets):
    chunks = []
    for target in targets:
        path = project_root / target["path"]
        new_text = planned_text_for_target(path, target["content"])
        d = diff_for_target(path, target["path"], new_text)
        if d:
            chunks.append(d)
    return "\n".join(chunks)


def write_json(obj):
    print(json.dumps(obj, indent=2))


def apply_targets(project_root, targets):
    failures = []
    for target in targets:
        path = project_root / target["path"]
        if not path.exists():
            failures.append({"path": target["path"], "reason": "missing_target"})
            continue
        existing = path.read_text()
        if replace_marked(existing, target["content"]) is None:
            failures.append({"path": target["path"], "reason": "missing_markers"})
    if failures:
        patch = patch_for_targets(project_root, targets)
        if patch:
            print(patch, end="" if patch.endswith("\n") else "\n")
        return 3, failures
    applied = []
    for target in targets:
        path = project_root / target["path"]
        new_text = replace_marked(path.read_text(), target["content"])
        path.write_text(new_text)
        applied.append(target["path"])
    write_json({"schema": "rosetta-harness/v1", "owner": "rosetta", "applied": applied})
    return 0, []


def main(argv=None):
    ap = argparse.ArgumentParser(description="Export Rosetta harness docs from JSON")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("export", help="plan, patch, or apply allowlisted harness docs")
    p.add_argument("--project-root", required=True, help="repo/project root")
    p.add_argument("--from-json", default=None,
                   help="contract JSON (default: <project>/.agents/rosetta/harness-export.json)")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--patch", action="store_true", help="print unified diff and write nothing")
    mode.add_argument("--apply", action="store_true", help="update existing marked allowlisted docs")
    args = ap.parse_args(argv)

    project_root = Path(args.project_root).resolve()
    from_json = Path(args.from_json).resolve() if args.from_json else project_root / ".agents/rosetta/harness-export.json"
    contract = load_contract(from_json)
    targets, warnings = build_targets(contract, project_root)

    if args.patch:
        if warnings:
            print(json.dumps({"warnings": warnings}), file=sys.stderr)
        patch = patch_for_targets(project_root, targets)
        print(patch, end="" if patch.endswith("\n") else "\n")
        return 0
    if args.apply:
        if warnings:
            print(json.dumps({"warnings": warnings}), file=sys.stderr)
        code, _failures = apply_targets(project_root, targets)
        return code

    write_json({
        "schema": "rosetta-harness/v1",
        "owner": "rosetta",
        "mode": "dry-run",
        "project_root": str(project_root),
        "from_json": str(from_json),
        "warnings": warnings,
        "targets": [{"path": t["path"], "content": t["content"]} for t in targets],
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
