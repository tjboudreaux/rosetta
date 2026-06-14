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


# Output tokens cost far more (price + latency) than input; weight them when an in/out split
# exists. ECI = input + OUTPUT_WEIGHT*output. Avoids hardcoding $ prices while honoring economics.
OUTPUT_WEIGHT = 5
# Efficiency of a broken system is meaningless — don't reward "cheap but wrong". Withhold
# cost-efficiency for any run whose pass-rate is below this gate (CALIBRATION.md Sonnet tier).
EFFICACY_GATE = 80.0


def _run_tokens(run):
    """Return {total, eci, has_split} for a run, summing scenarios or using a run-level block.

    `total` is raw tokens; `eci` weights output at OUTPUT_WEIGHT when an input/output split is
    present (else equals total). Returns None if the run carries no token data at all.
    """
    tot = inp = out = 0
    seen = has_split = False
    for s in run["scenarios"]:
        tk = s.get("tokens")
        if not tk:
            continue
        seen = True
        tot += tk.get("total", (tk.get("input", 0) + tk.get("output", 0)))
        if "input" in tk or "output" in tk:
            has_split = True
            inp += tk.get("input", 0)
            out += tk.get("output", 0)
    if not seen and run.get("tokens"):
        tk = run["tokens"]
        seen = True
        tot = tk.get("total", (tk.get("input", 0) + tk.get("output", 0)))
        if "input" in tk or "output" in tk:
            has_split = True
            inp, out = tk.get("input", 0), tk.get("output", 0)
    if not seen:
        return None
    eci = (inp + OUTPUT_WEIGHT * out) if has_split else tot
    return {"total": tot, "eci": eci, "has_split": has_split}


_PRICING_CACHE = {}


def _load_pricing():
    """Load the sibling pricing.json once. Dollar cost stays out of report.py — it lives in a
    versioned sheet so rates can't silently rot in code (Codex review P0)."""
    if "loaded" not in _PRICING_CACHE:
        p = Path(__file__).resolve().parent / "pricing.json"
        try:
            _PRICING_CACHE["data"] = json.loads(p.read_text()).get("sheets", {})
        except (OSError, ValueError):
            _PRICING_CACHE["data"] = {}
        _PRICING_CACHE["loaded"] = True
    return _PRICING_CACHE["data"]


def _price_base(model, sheet):
    """Map a run model label (e.g. 'sonnet-notools') to the longest matching base model in a sheet."""
    models = sheet.get("models", {})
    cands = [m for m in models if model == m or model.startswith(m + "-")]
    return max(cands, key=len) if cands else None


def _dollar_cost(run):
    """USD cost for a run — only when it carries an input/output split AND a resolvable price.
    Returns None otherwise (we never invent a price-weighted total from total-only tokens)."""
    sheets = _load_pricing()
    sid = run.get("price_sheet_id") or (next(iter(sheets)) if len(sheets) == 1 else None)
    sheet = sheets.get(sid) if sid else None
    if not sheet:
        return None
    base = _price_base(run.get("model", ""), sheet)
    if not base:
        return None
    rate = sheet["models"][base]
    inp = out = 0
    seen = False
    for s in run["scenarios"]:
        tk = s.get("tokens") or {}
        if "input" in tk or "output" in tk:
            seen = True
            inp += tk.get("input", 0)
            out += tk.get("output", 0)
    rtk = run.get("tokens") or {}
    if not seen and ("input" in rtk or "output" in rtk):
        seen, inp, out = True, rtk.get("input", 0), rtk.get("output", 0)
    if not seen:
        return None
    return inp / 1e6 * rate["input"] + out / 1e6 * rate["output"]


def _blended_usd(run):
    """Estimated USD from total tokens × the model's blended rate — used for cross-model value
    comparison when no input/output split exists. Exact in/out pricing (_dollar_cost) wins when present."""
    exact = _dollar_cost(run)
    if exact is not None:
        return exact, False
    sheets = _load_pricing()
    sid = run.get("price_sheet_id") or (next(iter(sheets)) if len(sheets) == 1 else None)
    sheet = sheets.get(sid) if sid else None
    if not sheet:
        return None, True
    tier = run.get("model_tier")
    base = tier if (tier and tier in sheet.get("models", {})) else _price_base(run.get("model", ""), sheet)
    if not base or "blended" not in sheet["models"].get(base, {}):
        return None, True
    tk = _run_tokens(run)
    if not tk:
        return None, True
    return tk["total"] / 1e6 * sheet["models"][base]["blended"], True


def _cost_row(run):
    """Compute the cost/value view for one run, applying the efficacy gate."""
    tk = _run_tokens(run)
    if not tk:
        return None
    passed, done, rate = _rate(run)
    failed = sum(1 for s in run["scenarios"] if s["status"] == "fail")
    gated = rate < EFFICACY_GATE
    # Cost per passed scenario: you pay for failed runs but they don't help the denominator.
    cpps = (tk["eci"] / passed) if passed else None
    usd, usd_est = _blended_usd(run)
    usd_pp = (usd / passed) if (usd is not None and passed) else None
    return {"label": _label(run), "model": run.get("model", "?"),
            "tier": run.get("model_tier", ""), "condition": run.get("condition", ""),
            "sset": run.get("scenario_set", ""), "total": tk["total"], "eci": tk["eci"],
            "has_split": tk["has_split"], "passed": passed, "done": done, "failed": failed,
            "rate": rate, "cpps": cpps, "gated": gated, "usd": usd, "usd_est": usd_est,
            "usd_pp": usd_pp}


_TIER_RANK = {"opus": 3, "sonnet": 2, "haiku": 1}


def value_lenses(runs):
    """Compute the three product-value narratives per scenario_set from the cost rows.
    1) correctness, 2) correctness at token savings (iso-correctness), 3) SoTA-on-cheaper-models."""
    rows = [r for r in (_cost_row(run) for run in runs) if r]
    by_set = {}
    for r in rows:
        by_set.setdefault(r["sset"] or "all", []).append(r)
    lenses = []
    for sset, rs in by_set.items():
        if len(rs) < 2:
            continue
        top = max(r["rate"] for r in rs)
        # Lens 2 — iso-correctness savings: cheapest vs priciest among runs at the top pass-rate.
        iso = [r for r in rs if r["rate"] == top and r["usd_pp"] is not None and not r["gated"]]
        savings = None
        if len(iso) >= 2:
            lo = min(iso, key=lambda r: r["usd_pp"])
            hi = max(iso, key=lambda r: r["usd_pp"])
            if hi["usd_pp"] > 0 and lo is not hi:
                savings = {"set": sset, "rate": top, "cheap": lo, "exp": hi,
                           "mult": hi["usd_pp"] / lo["usd_pp"]}
        # Lens 3 — SoTA on cheaper models: a cheaper tier matching the strongest baseline's correctness.
        baselines = [r for r in rs if r["condition"] == "baseline"]
        sota = max(baselines, key=lambda r: (_TIER_RANK.get(r["tier"], 0), r["rate"]), default=None)
        transfer = None
        if sota:
            for r in rs:
                if (_TIER_RANK.get(r["tier"], 9) < _TIER_RANK.get(sota["tier"], 0)
                        and r["rate"] >= sota["rate"] and not r["gated"]
                        and r["usd_pp"] is not None and sota["usd_pp"]):
                    cand = {"set": sset, "cheap": r, "sota": sota,
                            "mult": sota["usd_pp"] / r["usd_pp"] if r["usd_pp"] else None}
                    if not transfer or (cand["mult"] or 0) > (transfer["mult"] or 0):
                        transfer = cand
        lenses.append({"set": sset, "top": top, "savings": savings, "transfer": transfer})
    return lenses


def _mult_phrase(mult):
    """Small deltas read better as a percentage than as '~1×'."""
    if mult < 1.5:
        return f"~{(mult - 1) * 100:.0f}% less"
    return f"~{mult:.0f}× less"


def _usd_pp_cell(r):
    if r["gated"]:
        return f"⚠️ withheld (<{EFFICACY_GATE:.0f}%)"
    if r["usd_pp"] is None:
        return "—"
    return ("~" if r["usd_est"] else "") + f"${r['usd_pp']:,.3f}"


def cost_md(runs):
    rows = [r for r in (_cost_row(run) for run in runs) if r]
    if not rows:
        return ""
    out = ["## Product value (correctness · token savings · SoTA on cheaper models)",
           "", "_Three lenses on what the product is worth, not what the evals cost. Cost = solver "
           "tokens (the system under test). **$/correct** = cost per *passed* scenario, so failing "
           f"cheap looks expensive, not free, and is **withheld below the {EFFICACY_GATE:.0f}% efficacy "
           "gate**. `~$` = estimated from total tokens × a blended rate (`pricing.json`); exact in/out "
           "pricing is used when a split is present._", ""]
    # Lens summaries first (the narrative), then the backing matrix.
    for L in value_lenses(runs):
        tag = f"`{L['set']}` set" if L["set"] and L["set"] != "all" else "all runs"
        if L["transfer"]:
            t = L["transfer"]
            mult = f"~{t['mult']:.0f}×" if t["mult"] else "lower"
            out.append(f"- **SoTA on a cheaper model ({tag}):** `{t['cheap']['label']}` "
                       f"({t['cheap']['condition']}) matches the {t['sota']['tier']} baseline's "
                       f"{t['sota']['rate']:.0f}% correctness — {t['cheap']['rate']:.0f}% vs "
                       f"{t['sota']['rate']:.0f}% — at **{mult} lower est cost/correct** "
                       f"({_usd_pp_cell(t['cheap'])} vs {_usd_pp_cell(t['sota'])}).")
        if L["savings"]:
            s = L["savings"]
            out.append(f"- **Same correctness, fewer tokens ({tag}):** at {s['rate']:.0f}% both pass, "
                       f"but `{s['cheap']['label']}` costs **{_mult_phrase(s['mult'])} per correct answer** "
                       f"than `{s['exp']['label']}` ({_usd_pp_cell(s['cheap'])} vs {_usd_pp_cell(s['exp'])}).")
    out += ["", "| Run | Tier | Condition | Set | Pass-rate | Failed | Tokens | $/correct |",
            "|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: (r["sset"], -_TIER_RANK.get(r["tier"], 0), r["condition"])):
        out.append(f"| {r['label']} | {r['tier'] or '—'} | {r['condition'] or '—'} | {r['sset'] or '—'} "
                   f"| {r['rate']:.0f}% | {r['failed']} | {r['total']:,} | {_usd_pp_cell(r)} |")
    return "\n".join(out)


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
              cost_md(runs), "", detail_md(runs), ""]
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


def _usd_pp_cell_html(r):
    if r["gated"]:
        return f"<span class=muted>⚠️ withheld (&lt;{EFFICACY_GATE:.0f}%)</span>"
    if r["usd_pp"] is None:
        return "<span class=muted>—</span>"
    return ("~" if r["usd_est"] else "") + f"${r['usd_pp']:,.3f}"


def cost_html(runs):
    rows = [r for r in (_cost_row(run) for run in runs) if r]
    if not rows:
        return ""
    callouts = ""
    for L in value_lenses(runs):
        tag = f"<code>{_esc(L['set'])}</code> set" if L["set"] and L["set"] != "all" else "all runs"
        if L["transfer"]:
            t = L["transfer"]
            mult = f"~{t['mult']:.0f}×" if t["mult"] else "lower"
            callouts += (f"<li><b>SoTA on a cheaper model ({tag}):</b> <code>{_esc(t['cheap']['label'])}</code> "
                         f"matches the {_esc(t['sota']['tier'])} baseline's {t['sota']['rate']:.0f}% correctness "
                         f"at <b>{mult} lower est cost/correct</b> ({_usd_pp_cell_html(t['cheap'])} vs "
                         f"{_usd_pp_cell_html(t['sota'])}).</li>")
        if L["savings"]:
            s = L["savings"]
            callouts += (f"<li><b>Same correctness, fewer tokens ({tag}):</b> at {s['rate']:.0f}% both pass, "
                         f"but <code>{_esc(s['cheap']['label'])}</code> costs <b>{_mult_phrase(s['mult'])} per "
                         f"correct answer</b> than <code>{_esc(s['exp']['label'])}</code>.</li>")
    body = ""
    for r in sorted(rows, key=lambda r: (r["sset"], -_TIER_RANK.get(r["tier"], 0), r["condition"])):
        body += (f"<tr><td><code>{_esc(r['label'])}</code></td><td>{_esc(r['tier'] or '—')}</td>"
                 f"<td>{_esc(r['condition'] or '—')}</td><td>{_esc(r['sset'] or '—')}</td>"
                 f"<td>{r['rate']:.0f}%</td><td>{r['failed']}</td><td>{r['total']:,}</td>"
                 f"<td>{_usd_pp_cell_html(r)}</td></tr>")
    return ("<h2>Product value <span class=muted>— correctness · token savings · SoTA on cheaper models</span></h2>"
            "<p class=muted>Three lenses on what the product is worth, not what the evals cost. "
            "<b>$/correct</b> = cost per <i>passed</i> scenario (failing cheap looks expensive, not free) and is "
            f"<b>withheld below the {EFFICACY_GATE:.0f}% efficacy gate</b>. <code>~$</code> = estimated from total "
            "tokens × a blended rate (<code>pricing.json</code>); exact in/out pricing used when a split is present.</p>"
            + (f"<ul>{callouts}</ul>" if callouts else "")
            + "<table><thead><tr><th>Run</th><th>Tier</th><th>Condition</th><th>Set</th><th>Pass-rate</th>"
            "<th>Failed</th><th>Tokens</th><th>$/correct</th></tr></thead>"
            f"<tbody>{body}</tbody></table>")


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
        f"{cost_html(runs)}"
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
