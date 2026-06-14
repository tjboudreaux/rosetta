#!/usr/bin/env python3
"""Render eval results (rosetta-eval-results/v1) into a visual report: a Markdown scorecard, a
scenario×run pass/fail matrix, an inline SVG drift curve (pass-rate vs decision-library size, one
series per run/model tier), and a discrimination panel. Optionally a self-contained HTML dashboard.

Pure stdlib — SVG/HTML/Markdown are just text, so there is no plotting dependency. Deterministic
(no timestamps), so its output is testable.

Usage:
  python3 report.py results.json [more-results.json ...] --out REPORT.md [--html REPORT.html]

Each input file is rosetta-eval-results/v1 with a top-level "runs" list; multiple files merge
(e.g. the deterministic Tier-A run from run_evals.py --report, plus Tier-B / multi-model runs).
"""
import argparse
import json
from pathlib import Path

# Dark-mode theme — the SVG carries its own dark background so it reads correctly everywhere
# (GitHub markdown, the HTML dashboard, any viewer), not just where the page is dark.
PALETTE = ["#60a5fa", "#4ade80", "#f87171", "#c084fc", "#fb923c", "#22d3ee"]
BG = "#0d1117"        # page/chart background (GitHub-dark-ish)
PANEL = "#161b22"     # card / panel
FG = "#e6edf3"        # primary text
MUTED = "#8b949e"     # axes / secondary
GRID = "#30363d"      # gridlines
BORDER = "#30363d"


def load_runs(paths):
    runs = []
    for p in paths:
        doc = json.loads(Path(p).read_text())
        if doc.get("schema") != "rosetta-eval-results/v1":
            raise SystemExit(f"{p}: not a rosetta-eval-results/v1 file")
        runs.extend(doc.get("runs", []))
    return runs


def _label(run):
    return f"{run.get('tier', '?')}:{run.get('model', '?')}"


def _rate(run):
    sc = run["scenarios"]
    done = [s for s in sc if s["status"] in ("pass", "fail")]
    passed = sum(1 for s in sc if s["status"] == "pass")
    return passed, len(done), (100.0 * passed / len(done) if done else 0.0)


def _scoring_kind(s):
    """How was this scenario's pass/fail actually established? (provenance, weakest→strongest)"""
    prov = str(s.get("provenance", "")).lower()
    if "read-verified" in prov or "manual" in prov:
        return "read-verified"     # a human eyeballed it; no machine score
    if s.get("judge"):
        return "llm-judged"        # an LLM judge returned a verdict
    try:
        if int(s.get("checks", 0)) > 0:
            return "auto-scored"   # deterministic score.py checks ran
    except (TypeError, ValueError):
        pass
    return "self-asserted"         # a status with no checks/judge/provenance behind it


def _provenance_mix(run):
    """Count a run's scenarios by how their pass/fail was established."""
    mix = {}
    for s in run["scenarios"]:
        if s["status"] in ("pass", "fail"):
            k = _scoring_kind(s)
            mix[k] = mix.get(k, 0) + 1
    return mix


def calibration_verdict(runs):
    """Apply CALIBRATION.md's own contract to the data and return a blunt verdict.

    A suite where everything passes and nothing separates the tiers is mis-calibrated *by
    definition* (CALIBRATION.md: "if nothing discriminates ... the suite is mis-calibrated").
    This makes that judgment instead of letting five green cards imply success.
    """
    b_runs = [r for r in runs if r.get("tier") == "B"]
    reasons = []
    # 1. Discrimination — do any scenarios separate the runs?
    ids = {s["id"] for r in runs for s in r["scenarios"]}
    by_run = [{s["id"]: s["status"] for s in r["scenarios"]} for r in runs]
    co_tested = [sid for sid in ids if sum(1 for br in by_run if br.get(sid) in ("pass", "fail")) >= 2]
    discriminating = [sid for sid in co_tested
                      if len({br.get(sid) for br in by_run if br.get(sid) in ("pass", "fail")}) > 1]
    status = "UNKNOWN"
    if len(b_runs) < 2:
        reasons.append(f"Only {len(b_runs)} judgment (Tier-B) run(s) — need ≥2 tiers to assess discrimination.")
    elif not co_tested:
        reasons.append("Tiers ran *disjoint* scenario sets — no scenario was run by ≥2 tiers, so "
                       "discrimination is unmeasured. " +
                       ", ".join(f"{_label(r)}={_rate(r)[1]}" for r in b_runs) + ".")
    else:
        ratio = len(discriminating) / len(co_tested)
        if not discriminating:
            status = "NO"
            reasons.append(f"0 of {len(co_tested)} co-tested scenarios separate any two tiers "
                           "(CALIBRATION.md requires ≥1/4). Nothing discriminates → mis-calibrated.")
        elif ratio < 0.25:
            status = "NO"
            reasons.append(f"Only {len(discriminating)}/{len(co_tested)} co-tested scenarios "
                           "discriminate (<1/4 gate).")
        else:
            status = "YES"
            reasons.append(f"{len(discriminating)}/{len(co_tested)} co-tested scenarios discriminate (≥1/4).")
    # 2. Provenance — is the green actually verified?
    verified = 0
    total_done = 0
    for r in runs:
        for s in r["scenarios"]:
            if s["status"] in ("pass", "fail"):
                total_done += 1
                if _scoring_kind(s) in ("auto-scored", "llm-judged"):
                    verified += 1
    if total_done and verified / total_done < 0.5:
        if status == "UNKNOWN":
            status = "NO"
        reasons.append(f"{total_done - verified}/{total_done} reported results are self-asserted or "
                       "read-verified (not auto-scored or LLM-judged) — green over-states confidence.")
    # 3. Regression proof — has the suite ever gone red?
    any_fail = any(s["status"] == "fail" for r in runs for s in r["scenarios"])
    if not any_fail:
        reasons.append("No run has ever failed — every result is a pass, and even a no-guidance "
                       "ablation passed (REVIEW-ablation.md). The suite has not yet been shown to "
                       "catch a bad output, so green can't yet mean 'validated'.")
        if status in ("UNKNOWN", "YES"):
            status = "NO" if status == "UNKNOWN" else status
    return {"status": status, "reasons": reasons,
            "discriminating": discriminating, "co_tested": co_tested}


def _prov_summary(run):
    mix = _provenance_mix(run)
    order = ["auto-scored", "llm-judged", "read-verified", "self-asserted"]
    return ", ".join(f"{mix[k]} {k}" for k in order if mix.get(k)) or "—"


def calibration_md(runs):
    v = calibration_verdict(runs)
    head = {"YES": "✅ CALIBRATED: YES", "NO": "🛑 CALIBRATED: NO",
            "UNKNOWN": "⚠️ CALIBRATED: UNKNOWN"}[v["status"]]
    out = [f"> ## {head}", ">",
           "> _Verdict applies CALIBRATION.md's own gates to the data below — a green pass-rate is "
           "not the same as a working eval._", ">"]
    for r in v["reasons"]:
        out.append(f"> - {r}")
    return "\n".join(out)


def scorecard_md(runs):
    out = ["## Scorecard", "",
           "| Run | Passed | Pass-rate | How scored |", "|---|---|---|---|"]
    for run in runs:
        p, n, rate = _rate(run)
        out.append(f"| {_label(run)} | {p}/{n} | {rate:.0f}% | {_prov_summary(run)} |")
    return "\n".join(out)


def antipattern_md(runs):
    # use the run with the most anti_pattern coverage (the deterministic Tier-A run)
    run = max(runs, key=lambda r: sum(1 for s in r["scenarios"] if s.get("anti_pattern")), default=None)
    if not run:
        return ""
    aps = {}
    for s in run["scenarios"]:
        ap = s.get("anti_pattern")
        if ap:
            aps.setdefault(ap, []).append(s["status"])
    if not aps:
        return ""
    out = ["## Anti-pattern coverage", "", f"_{len(aps)} anti-patterns in `{_label(run)}`_", ""]
    for ap in sorted(aps):
        sts = aps[ap]
        ok = sum(1 for s in sts if s == "pass")
        out.append(f"- `{ap}` — {ok}/{len(sts)}")
    return "\n".join(out)


def matrix_md(runs):
    ids = []
    for run in runs:
        for s in run["scenarios"]:
            if s["id"] not in ids:
                ids.append(s["id"])
    glyph = {"pass": "✓", "fail": "✗", "skipped": "–"}
    head = "| Scenario | " + " | ".join(_label(r) for r in runs) + " |"
    sep = "|---|" + "|".join("---" for _ in runs) + "|"
    rows = [head, sep]
    by_run = [{s["id"]: s["status"] for s in r["scenarios"]} for r in runs]
    for sid in ids:
        cells = " | ".join(glyph.get(br.get(sid), "·") for br in by_run)
        rows.append(f"| {sid} | {cells} |")
    return "## Scenario × run matrix\n\n" + "\n".join(rows)


def discrimination_md(runs):
    if len(runs) < 2:
        return ("## Discrimination\n\n_Only one run present — no cross-tier discrimination yet. "
                "Add runs from more model tiers (Haiku/Sonnet/Opus) to see which scenarios separate them._")
    ids = {s["id"] for r in runs for s in r["scenarios"]}
    by_run = [{s["id"]: s["status"] for s in r["scenarios"]} for r in runs]
    discriminating = []
    for sid in sorted(ids):
        outcomes = {br.get(sid) for br in by_run if br.get(sid) in ("pass", "fail")}
        if len(outcomes) > 1:
            discriminating.append(sid)
    body = ("\n".join(f"- {sid}" for sid in discriminating)
            if discriminating else "_No scenario separates the runs (all agree)._")
    return f"## Discrimination ({len(discriminating)} scenarios separate runs)\n\n{body}"


def drift_svg(runs):
    """SVG line chart: x = decision-library size (drift_size), y = pass-rate %, one series per run.

    Tier-A is excluded: it is the *substrate* check (was the N-ADR fixture built?), not a
    judgment result, so plotting it on a judgment-pass-rate axis is misleading.
    """
    series = []
    for run in runs:
        if run.get("tier") == "A":
            continue
        pts = [(s["drift_size"], s["status"]) for s in run["scenarios"] if s.get("drift_size")]
        if pts:
            pts.sort(key=lambda t: t[0])
            series.append((_label(run), pts))
    if not series:
        return None
    sizes = sorted({d for _, pts in series for d, _ in pts})
    W, H, ml, mr, mt, mb = 560, 300, 52, 130, 20, 44
    pw, ph = W - ml - mr, H - mt - mb
    xi = {s: i for i, s in enumerate(sizes)}

    def x(i):
        return ml + (pw * i / (len(sizes) - 1) if len(sizes) > 1 else pw / 2)

    def y(pct):
        return mt + ph * (1 - pct / 100.0)

    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
         f'font-family="sans-serif" font-size="11" role="img" aria-label="Eval drift curve">',
         f'<rect x="0" y="0" width="{W}" height="{H}" rx="8" fill="{BG}"/>',
         f'<text x="{ml}" y="13" fill="{FG}" font-weight="bold">Pass-rate vs decision-library size</text>',
         f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt+ph}" stroke="{MUTED}"/>',
         f'<line x1="{ml}" y1="{mt+ph}" x2="{ml+pw}" y2="{mt+ph}" stroke="{MUTED}"/>']
    for pct in (0, 50, 100):
        yy = y(pct)
        p.append(f'<line x1="{ml}" y1="{yy:.1f}" x2="{ml+pw}" y2="{yy:.1f}" stroke="{GRID}"/>')
        p.append(f'<text x="{ml-8}" y="{yy+3:.1f}" fill="{MUTED}" text-anchor="end">{pct}%</text>')
    for s in sizes:
        xx = x(xi[s])
        p.append(f'<text x="{xx:.1f}" y="{mt+ph+16}" fill="{MUTED}" text-anchor="middle">N={s}</text>')
    for k, (label, pts) in enumerate(series):
        col = PALETTE[k % len(PALETTE)]
        poly = " ".join(f"{x(xi[d]):.1f},{y(100 if st == 'pass' else 0):.1f}" for d, st in pts)
        p.append(f'<polyline points="{poly}" fill="none" stroke="{col}" stroke-width="2"/>')
        for d, st in pts:
            p.append(f'<circle cx="{x(xi[d]):.1f}" cy="{y(100 if st == "pass" else 0):.1f}" '
                     f'r="3.5" fill="{col}"/>')
        ly = mt + 16 * k + 8
        p.append(f'<rect x="{ml+pw+14}" y="{ly-8}" width="10" height="10" fill="{col}"/>')
        p.append(f'<text x="{ml+pw+28}" y="{ly+1}" fill="{FG}">{label}</text>')
    p.append("</svg>")
    return "\n".join(p)


def detail_entries(runs):
    """Flatten every scenario that carries per-test detail (expected/actual/judge) across runs."""
    out = []
    for run in runs:
        for s in run["scenarios"]:
            if any(k in s for k in ("expected", "actual", "judge")):
                j = s.get("judge") or {}
                out.append({
                    "id": s["id"], "model": _label(run), "anti_pattern": s.get("anti_pattern", ""),
                    "status": s.get("status", ""),
                    "expected": s.get("expected", ""), "actual": s.get("actual", ""),
                    "judge_decision": j.get("decision", s.get("status", "")),
                    "judge_reasoning": j.get("reasoning", ""),
                })
    return out


def _glyph(status):
    return {"pass": "✓ PASS", "fail": "✗ FAIL", "skipped": "– SKIP"}.get(status, status)


def detail_md(runs):
    entries = detail_entries(runs)
    if not entries:
        return ""
    parts = ["## Per-test detail",
             "", "_Each test: what it probes, the expected result, what the model actually produced, "
             "and the LLM-as-judge's decision + reasoning trace._", ""]
    for e in entries:
        parts += [
            f"### {e['id']} — `{e['model']}` — {_glyph(e['status'])}",
            f"- **Anti-pattern:** {e['anti_pattern']}",
            f"- **Expected:** {e['expected']}",
            f"- **Actual:** {e['actual']}",
            f"- **Judge — {_glyph(e['judge_decision'])}:** {e['judge_reasoning']}",
            "",
        ]
    return "\n".join(parts)


def build_markdown(runs, svg_ref):
    parts = ["# Rosetta eval report", "",
             "_Generated by `report.py` from `rosetta-eval-results/v1` data — do not hand-edit._", "",
             calibration_md(runs), "",
             scorecard_md(runs), ""]
    if svg_ref:
        parts += ["## Drift curve",
                  "", "_Tier-A (substrate) excluded — it measures whether the fixture was built, not "
                  "judgment. A flat line here is a ceiling check, not evidence of quality._",
                  "", f"![drift curve]({svg_ref})", ""]
    parts += [antipattern_md(runs), "", matrix_md(runs), "", discrimination_md(runs), "",
              detail_md(runs), ""]
    return "\n".join(pt for pt in parts if pt is not None) + "\n"


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def detail_html(runs):
    entries = detail_entries(runs)
    if not entries:
        return ""
    rows = ["<h2>Per-test detail</h2>",
            "<p class=muted>Each test: what it probes, the expected result, the model's actual output, "
            "and the LLM-as-judge's decision + reasoning.</p>"]
    for e in entries:
        ok = e["status"] == "pass"
        badge = ("pass" if ok else "fail")
        rows.append(
            f"<details class=detail><summary><span class='badge {badge}'>{_glyph(e['status'])}</span> "
            f"<code>{_esc(e['id'])}</code> <span class=muted>· {_esc(e['model'])} · "
            f"{_esc(e['anti_pattern'])}</span></summary>"
            f"<div class=kv><b>Expected</b><div>{_esc(e['expected'])}</div></div>"
            f"<div class=kv><b>Actual</b><div>{_esc(e['actual'])}</div></div>"
            f"<div class=kv><b>Judge — {_glyph(e['judge_decision'])}</b>"
            f"<div>{_esc(e['judge_reasoning'])}</div></div></details>")
    return "\n".join(rows)


def calibration_html(runs):
    v = calibration_verdict(runs)
    cls = {"YES": "cal-yes", "NO": "cal-no", "UNKNOWN": "cal-unknown"}[v["status"]]
    head = {"YES": "CALIBRATED: YES", "NO": "CALIBRATED: NO",
            "UNKNOWN": "CALIBRATED: UNKNOWN"}[v["status"]]
    reasons = "".join(f"<li>{_esc(r)}</li>" for r in v["reasons"])
    return (f"<div class='cal {cls}'><div class=cal-head>{head}</div>"
            "<div class=muted>Applies CALIBRATION.md's own gates to the data — a green pass-rate is "
            f"not the same as a working eval.</div><ul>{reasons}</ul></div>")


def scorecard_html(runs):
    rows = "".join(
        f"<tr><td><code>{_esc(_label(r))}</code></td><td>{_rate(r)[0]}/{_rate(r)[1]}</td>"
        f"<td>{_rate(r)[2]:.0f}%</td><td class=muted>{_esc(_prov_summary(r))}</td></tr>"
        for r in runs)
    return ("<h2>Scorecard</h2><table><thead><tr><th>Run</th><th>Passed</th><th>Pass-rate</th>"
            f"<th>How scored</th></tr></thead><tbody>{rows}</tbody></table>")


def discrimination_html(runs):
    v = calibration_verdict(runs)
    n_disc, n_co = len(v["discriminating"]), len(v["co_tested"])
    if not n_co:
        body = ("<p class=muted>No scenario was run by ≥2 tiers, so discrimination is unmeasured. "
                "Run the same scenario set across Haiku/Sonnet/Opus to populate this.</p>")
    elif not v["discriminating"]:
        body = (f"<p class=muted>0 of {n_co} co-tested scenarios separate any two tiers — the suite "
                "does not discriminate model quality (CALIBRATION.md requires ≥1/4).</p>")
    else:
        body = "<ul>" + "".join(f"<li><code>{_esc(s)}</code></li>" for s in v["discriminating"]) + "</ul>"
    return f"<h2>Discrimination ({n_disc}/{n_co} co-tested scenarios separate tiers)</h2>{body}"


def matrix_html(runs):
    ids = []
    for run in runs:
        for s in run["scenarios"]:
            if s["id"] not in ids:
                ids.append(s["id"])
    glyph = {"pass": "<span class='badge pass'>✓</span>", "fail": "<span class='badge fail'>✗</span>",
             "skipped": "<span class=muted>–</span>"}
    by_run = [{s["id"]: s["status"] for s in r["scenarios"]} for r in runs]
    head = "".join(f"<th>{_esc(_label(r))}</th>" for r in runs)
    body = ""
    for sid in ids:
        cells = "".join(f"<td>{glyph.get(br.get(sid), '<span class=muted>·</span>')}</td>" for br in by_run)
        body += f"<tr><td><code>{_esc(sid)}</code></td>{cells}</tr>"
    return ("<details class=detail><summary>Scenario × run matrix</summary>"
            f"<table><thead><tr><th>Scenario</th>{head}</tr></thead><tbody>{body}</tbody></table></details>")


def build_html(runs, svg_inline):
    cards = "".join(
        f'<div class=card><div class=big>{_rate(r)[2]:.0f}%</div>'
        f'<div>{_esc(_label(r))} — {_rate(r)[0]}/{_rate(r)[1]}</div>'
        f'<div class="muted prov">{_esc(_prov_summary(r))}</div></div>' for r in runs)
    return (
        "<!doctype html><html lang=en><meta charset=utf-8>"
        "<meta name=color-scheme content='dark'><title>Rosetta eval report</title>"
        f"<style>:root{{color-scheme:dark}}body{{font:14px/1.5 system-ui,sans-serif;margin:2rem;"
        f"max-width:900px;background:{BG};color:{FG}}}h1,h2{{color:{FG}}}.muted{{color:{MUTED}}}"
        f"code{{color:{PALETTE[0]}}}"
        f".cards{{display:flex;gap:1rem;flex-wrap:wrap}}.card{{border:1px solid {BORDER};"
        f"border-radius:8px;padding:1rem 1.4rem;background:{PANEL}}}.prov{{font-size:.75rem;margin-top:.3rem}}"
        f".big{{font-size:2rem;font-weight:700;color:{PALETTE[1]}}}"
        f".cal{{border:1px solid {BORDER};border-left-width:6px;border-radius:8px;background:{PANEL};"
        f"padding:.8rem 1.1rem;margin:0 0 1.4rem}}.cal-head{{font-size:1.3rem;font-weight:700}}"
        f".cal ul{{margin:.5rem 0 0;padding-left:1.1rem}}.cal li{{margin:.25rem 0}}"
        f".cal-no{{border-left-color:{PALETTE[2]}}}.cal-no .cal-head{{color:{PALETTE[2]}}}"
        f".cal-yes{{border-left-color:{PALETTE[1]}}}.cal-yes .cal-head{{color:{PALETTE[1]}}}"
        f".cal-unknown{{border-left-color:{PALETTE[4]}}}.cal-unknown .cal-head{{color:{PALETTE[4]}}}"
        f"table{{border-collapse:collapse;width:100%;margin:.5rem 0}}"
        f"th,td{{border:1px solid {BORDER};padding:.3rem .6rem;text-align:left}}th{{color:{MUTED}}}"
        f".detail{{border:1px solid {BORDER};border-radius:8px;background:{PANEL};margin:.5rem 0;"
        f"padding:.5rem .9rem}}.detail summary{{cursor:pointer}}"
        f".kv{{margin:.5rem 0}}.kv b{{display:block;color:{MUTED};font-size:.8rem;"
        f"text-transform:uppercase;letter-spacing:.04em}}"
        f".badge{{font-weight:700;padding:.05rem .4rem;border-radius:4px}}"
        f".badge.pass{{color:{PALETTE[1]}}}.badge.fail{{color:{PALETTE[2]}}}"
        f"a{{color:{PALETTE[0]}}}svg{{max-width:100%}}</style>"
        f"<h1>Rosetta eval report</h1>"
        f"{calibration_html(runs)}"
        f"<div class=cards>{cards}</div>"
        f"{scorecard_html(runs)}"
        "<h2>Drift curve</h2><p class=muted>Tier-A (substrate) excluded — it measures whether the "
        "fixture was built, not judgment. A flat line is a ceiling check, not evidence of quality.</p>"
        f"{svg_inline or '<p>No judgment-tier drift data.</p>'}"
        f"{discrimination_html(runs)}"
        f"{matrix_html(runs)}"
        f"{detail_html(runs)}</html>")


def main():
    ap = argparse.ArgumentParser(description="Render rosetta eval results into a visual report")
    ap.add_argument("results", nargs="+", help="one or more rosetta-eval-results/v1 JSON files")
    ap.add_argument("--out", required=True, help="output Markdown path")
    ap.add_argument("--html", default=None, help="also write a self-contained HTML dashboard")
    args = ap.parse_args()

    runs = load_runs(args.results)
    if not runs:
        raise SystemExit("no runs found in inputs")

    out = Path(args.out)
    svg = drift_svg(runs)
    svg_ref = None
    if svg:
        svg_ref = out.with_suffix(".drift.svg").name
        (out.parent / svg_ref).write_text(svg + "\n")
    out.write_text(build_markdown(runs, svg_ref))
    print(f"wrote {out}" + (f" + {svg_ref}" if svg_ref else ""))
    if args.html:
        Path(args.html).write_text(build_html(runs, svg))
        print(f"wrote {args.html}")


if __name__ == "__main__":
    main()
