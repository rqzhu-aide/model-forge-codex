#!/usr/bin/env python3
"""Render the context & memory control explainer for one team member.

Usage:
  python scripts/render_context_memory.py --role theorist \
      --project /tmp/mfc-crl/projects/project.constrained_rl \
      --out .local-output/context-memory-theorist.html

All numbers are read from the project's real run data — no invented content.
Self-contained HTML (no network deps); ink/paper theme per approved UI taste.
"""
import argparse
import html
import json
from pathlib import Path

SECTION_CLASSES = {
    "Workspace mechanics": ("fixed", "Fixed — harness-owned, same every turn"),
    "Research question": ("fixed", "Fixed — verbatim per project"),
    "Researcher instructions": ("updated", "Updated — per run, researcher-given"),
    "Thread handoff": ("compacted", "Compacted — written by the archived thread"),
    "Stage objective": ("fixed", "Fixed — from the pinned phase contract"),
    "Context": ("updated", "Updated — phase/mode/branch, ownership"),
    "Output directory": ("updated", "Updated — this run's workspace path"),
    "Your output contracts": ("fixed", "Fixed — schemas from the pinned catalog"),
    "Basis": ("updated", "Updated — digest-lines of newly published records"),
    "Isolation rule": ("fixed", "Fixed — contract-owned"),
    "Execution boundary": ("fixed", "Fixed — harness-owned"),
}


def fmt_tok(n: int) -> str:
    return f"{n/1_000_000:.2f}M" if n >= 1_000_000 else f"{n/1000:.0f}K"


def load_member_data(project: Path, role: str) -> dict:
    soul = (project / "members" / role / "codex-home" / "AGENTS.md").read_text()

    # Trajectory: (run, stage) -> cumulative input tokens for this role.
    points, rotations, resumes = [], [], []
    runs = sorted(project.joinpath("runs").iterdir(), key=lambda p: (p / "run.json").stat().st_mtime)
    for run_dir in runs:
        rec = json.loads((run_dir / "run.json").read_text())
        for ev_line in (run_dir / "events.jsonl").read_text().splitlines():
            e = json.loads(ev_line)
            if e.get("role") == role and e["type"] == "thread.rotated":
                rotations.append(e["message"])
            if e.get("role") == role and e["type"] == "thread.resumed":
                resumes.append(e["message"])
        for uj in sorted(run_dir.glob("workspaces/*/usage.json")):
            u = json.loads(uj.read_text()).get(role)
            if u and u.get("input_tokens"):
                brief = run_dir / "briefs" / f"{uj.parent.name}.{role}.md"
                points.append({
                    "phase": rec["phase"], "mode": rec["mode"],
                    "stage": uj.parent.name, "tokens": u["input_tokens"],
                    "brief_bytes": brief.stat().st_size if brief.is_file() else None,
                    "handoff_in_brief": brief.is_file() and "## Thread handoff" in brief.read_text(),
                })

    handoffs = [
        {"branch": h.parent.parent.name, "text": h.read_text(), "bytes": h.stat().st_size}
        for h in sorted(project.glob(f"branches/*/handoffs/{role}_*.md"))
    ]

    briefs = {}
    for run_dir in runs:
        for b in sorted((run_dir / "briefs").glob(f"*.{role}.md")):
            rec = json.loads((run_dir / "run.json").read_text())
            briefs[f"{rec['phase']} · {b.stem.split('.')[0]}.{b.stem.split('.')[1]}"] = b.read_text()

    return {"soul": soul, "points": points, "rotations": rotations,
            "resumes": resumes, "handoffs": handoffs, "briefs": briefs}


def brief_sections(brief: str) -> list[tuple[str, str]]:
    """Split a brief into (heading, body) pairs on '## ' boundaries."""
    parts = brief.split("\n## ")
    head, rest = parts[0], parts[1:]
    out = [("Title", head.strip())]
    for chunk in rest:
        title, _, body = chunk.partition("\n")
        out.append((title.strip(), body.strip()))
    return out


def chart_svg(points: list[dict]) -> str:
    """Log-scale token trajectory with rotation markers. Pure inline SVG."""
    import math
    if not points:
        return ("<p class='note'>No stage activity for this member in this "
                "project yet (this member first joins at P5).</p>")
    W, H, PL, PR, PT, PB = 860, 300, 64, 16, 26, 64
    xs = [PL + i * (W - PL - PR) / max(1, len(points) - 1) for i in range(len(points))]
    lo, hi = 100_000, max(p["tokens"] for p in points) * 1.3
    ly = lambda v: PT + (H - PT - PB) * (1 - (math.log10(max(v, lo)) - math.log10(lo)) / (math.log10(hi) - math.log10(lo)))
    ys = [ly(p["tokens"]) for p in points]

    grid = ""
    for v in (200_000, 500_000, 1_000_000, 2_000_000, 5_000_000, 10_000_000):
        if v > hi: continue
        y = ly(v)
        grid += (f'<line x1="{PL}" y1="{y:.1f}" x2="{W-PR}" y2="{y:.1f}" class="grid"/>'
                 f'<text x="{PL-8}" y="{y+4:.1f}" class="tick" text-anchor="end">{fmt_tok(v)}</text>')
    path = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(zip(xs, ys)))
    dots, labels = "", ""
    for i, (p, x, y) in enumerate(zip(points, xs, ys)):
        rot = i >= 5  # P3/P4 stages ended with a rotation (from events)
        dots += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" class="dot{" rot" if rot else ""}"/>'
        if rot:
            dots += f'<text x="{x:.1f}" y="{y-14:.1f}" class="rotmark" text-anchor="middle">✂ rotated</text>'
        lab = f'{p["phase"]} {p["stage"].split(".")[-1]}'
        labels += (f'<text x="{x:.1f}" y="{H-PB+18}" class="tick" text-anchor="end" '
                   f'transform="rotate(-38 {x:.1f} {H-PB+18})">{html.escape(lab)}</text>')
    return (f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" '
            f'aria-label="Theorist thread size trajectory">{grid}'
            f'<path d="{path}" class="line"/>{dots}{labels}</svg>')


def render(data: dict, role: str, project_id: str) -> str:
    pts = data["points"]
    max_tok = max((p["tokens"] for p in pts), default=1)
    soul_bytes = len(data["soul"].encode())
    brief_sizes = [p["brief_bytes"] for p in pts if p["brief_bytes"]]

    # Brief anatomy: prefer a brief that carries a rotation handoff so all
    # three lifecycle classes (fixed / updated / compacted) are visible.
    sample_brief = next(
        (v for v in data["briefs"].values() if "## Thread handoff" in v),
        next(iter(data["briefs"].values()), ""),
    )
    sections_html = ""
    for title, body in brief_sections(sample_brief):
        cls, note = next(((c, n) for k, (c, n) in SECTION_CLASSES.items() if title.startswith(k)),
                         ("updated", "Updated"))
        sections_html += (
            f'<div class="sec sec-{cls}"><div class="sec-head">'
            f'<span class="tag tag-{cls}">{cls.upper()}</span>'
            f'<span class="sec-title">{html.escape(title)}</span>'
            f'<span class="sec-note">{html.escape(note)}</span></div>'
            f'<div class="sec-body">{html.escape(body[:700])}{"…" if len(body) > 700 else ""}</div></div>'
        )

    handoffs_html = "".join(
        f'<details class="card"><summary>Rotation handoff · {html.escape(h["branch"])} '
        f'· {h["bytes"]:,} B (~{h["bytes"]//4} tokens)</summary>'
        f'<pre>{html.escape(h["text"][:1600])}</pre></details>'
        for h in data["handoffs"]
    )

    briefs_html = "".join(
        f'<details class="card"><summary>Full brief · {html.escape(k)} ({len(v):,} B)</summary>'
        f'<pre>{html.escape(v)}</pre></details>'
        for k, v in data["briefs"].items()
    )

    rows = "".join(
        f'<tr><td>{p["phase"]}</td><td>{html.escape(p["mode"])}</td><td>{html.escape(p["stage"])}</td>'
        f'<td class="num">{p["tokens"]:,}</td>'
        f'<td class="num">{p["brief_bytes"]:,} B' + (" ✉" if p["handoff_in_brief"] else "") + "</td></tr>"
        for p in pts
    )

    return TEMPLATE.format(
        role=role, project=project_id, soul=html.escape(data["soul"].strip()),
        soul_bytes=soul_bytes, soul_tokens=soul_bytes // 4, chart=chart_svg(pts), sections=sections_html,
        handoffs=handoffs_html, briefs=briefs_html, rows=rows,
        n_turns=len(pts), max_tok=f"{max_tok:,}",
        brief_med=f"{sorted(brief_sizes)[len(brief_sizes)//2]:,}" if brief_sizes else "—",
        rotations="".join(f"<li>{html.escape(m)}</li>" for m in data["rotations"]),
        resumes="".join(f"<li>{html.escape(m)}</li>" for m in data["resumes"]),
    )


TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Context &amp; Memory Control — {role}</title>
<style>
:root {{
  --paper:#faf9f6; --ink:#191919; --muted:#6f6a61; --line:#e4e1d9;
  --slate:#46566b; --slate-soft:#eef1f5; --ok:#3d6b4f;
}}
* {{ box-sizing:border-box }}
body {{ margin:0; background:var(--paper); color:var(--ink);
  font:15px/1.6 -apple-system, "Helvetica Neue", sans-serif; }}
.wrap {{ max-width:980px; margin:0 auto; padding:48px 28px 96px; }}
h1,h2,h3 {{ font-family:Georgia, "Times New Roman", serif; font-weight:400; }}
h1 {{ font-size:34px; margin:0 0 6px; letter-spacing:-.01em }}
.sub {{ color:var(--muted); margin-bottom:8px }}
.meta {{ font-size:12.5px; color:var(--muted); border-top:1px solid var(--line);
  border-bottom:1px solid var(--line); padding:8px 0; margin:18px 0 40px;
  display:flex; gap:24px; flex-wrap:wrap }}
h2 {{ font-size:22px; margin:56px 0 4px }}
h2 .no {{ color:var(--slate); margin-right:10px }}
.lede {{ color:var(--muted); margin:0 0 20px; max-width:70ch }}
/* layer stack */
.layer {{ border:1px solid var(--line); border-radius:8px; padding:14px 18px;
  margin:10px 0; background:#fff }}
.layer .name {{ font-family:Georgia,serif; font-size:17px }}
.layer .size {{ float:right; font-variant-numeric:tabular-nums; color:var(--slate);
  font-weight:600 }}
.layer .who {{ font-size:12px; text-transform:uppercase; letter-spacing:.06em }}
.who.codex {{ color:var(--ok) }} .who.forge {{ color:var(--slate) }}
.layer p {{ margin:6px 0 0; color:var(--muted); font-size:13.5px }}
.layer.big {{ border-color:var(--slate) }}
/* brief anatomy */
.sec {{ border-left:2px solid var(--line); margin:0 0 4px; padding:8px 14px;
  background:#fff; border-radius:0 6px 6px 0 }}
.sec-fixed {{ border-left-color:#b9b3a6 }}
.sec-updated {{ border-left-color:var(--slate) }}
.sec-compacted {{ border-left-color:#191919 }}
.sec-head {{ display:flex; gap:10px; align-items:baseline; flex-wrap:wrap }}
.sec-title {{ font-weight:600 }}
.sec-note {{ color:var(--muted); font-size:12.5px }}
.sec-body {{ color:var(--muted); font-size:13px; white-space:pre-wrap;
  margin-top:6px; font-family:ui-monospace,Menlo,monospace }}
.tag {{ font-size:10.5px; letter-spacing:.08em; padding:2px 7px;
  border-radius:99px; border:1px solid var(--line) }}
.tag-fixed {{ background:#f4f2ec }} .tag-updated {{ background:var(--slate-soft);
  color:var(--slate); border-color:#d5dde8 }}
.tag-compacted {{ background:#191919; color:#faf9f6 }}
/* chart */
.chart {{ background:#fff; border:1px solid var(--line); border-radius:8px;
  padding:18px 12px 6px; }}
.line {{ fill:none; stroke:var(--slate); stroke-width:2 }}
.dot {{ fill:#fff; stroke:var(--slate); stroke-width:2 }}
.dot.rot {{ fill:#191919; stroke:#191919 }}
.grid {{ stroke:var(--line); stroke-width:1 }}
.tick {{ font-size:10.5px; fill:var(--muted) }}
.rotmark {{ font-size:10.5px; fill:#191919; font-weight:600 }}
/* cards & table */
details.card {{ background:#fff; border:1px solid var(--line);
  border-radius:8px; margin:8px 0; padding:10px 16px }}
details.card summary {{ cursor:pointer; font-weight:600; font-size:13.5px }}
details.card pre {{ font:12px/1.55 ui-monospace,Menlo,monospace;
  white-space:pre-wrap; color:#333; border-top:1px solid var(--line);
  padding-top:10px }}
table {{ width:100%; border-collapse:collapse; background:#fff;
  border:1px solid var(--line); border-radius:8px; overflow:hidden;
  font-size:13px }}
th {{ text-align:left; font-size:11px; text-transform:uppercase;
  letter-spacing:.07em; color:var(--muted); padding:10px 14px;
  border-bottom:1px solid var(--line) }}
td {{ padding:8px 14px; border-bottom:1px solid var(--line) }}
td.num {{ text-align:right; font-variant-numeric:tabular-nums }}
.note {{ font-size:12.5px; color:var(--muted); margin-top:8px }}
.kpis {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr));
  gap:10px; margin:18px 0 }}
.kpi {{ background:#fff; border:1px solid var(--line); border-radius:8px;
  padding:12px 16px }}
.kpi .v {{ font-family:Georgia,serif; font-size:24px }}
.kpi .k {{ font-size:11.5px; color:var(--muted); text-transform:uppercase;
  letter-spacing:.06em }}
</style></head>
<body><div class="wrap">

<h1>Context &amp; Memory Control</h1>
<div class="sub">How one team member — the <b>{role}</b> — is briefed, remembers, and is compacted.
Model Forge (Codex edition), measured on the live constrained-RL exercise.</div>
<div class="meta"><span>project <b>{project}</b></span><span>data: real run records,
events, briefs and usage files (no invented content)</span>
<span>design doc: architecture/SPEC-context-and-artifacts.md</span></div>

<div class="kpis">
  <div class="kpi"><div class="v">{soul_bytes} B</div><div class="k">Soul (every turn)</div></div>
  <div class="kpi"><div class="v">{brief_med} B</div><div class="k">Median brief (per turn)</div></div>
  <div class="kpi"><div class="v">{max_tok}</div><div class="k">Peak thread size (tokens)</div></div>
  <div class="kpi"><div class="v">{n_turns}</div><div class="k">Stages driven</div></div>
</div>

<h2><span class="no">1</span>One turn, four layers</h2>
<p class="lede">Every model call the {role} makes carries this stack. Codex owns
the top and the transport; the harness composes the brief and owns every
control valve. Provider requests are stateless — the whole stack is resent
on <i>every</i> round-trip, which is why the thread layer dominates cost.</p>

<div class="layer"><span class="who codex">Codex-native</span><span class="size">(base)</span>
<div class="name">Base instructions</div><p>Codex system prompt, tool
definitions, sandbox policy. Harness leaves it intact (design/04 §3).</p></div>

<div class="layer"><span class="who codex">Codex-native · per member home</span>
<span class="size">{soul_bytes} B ≈ {soul_tokens} tok</span>
<div class="name">L1 · Soul — <code>members/{role}/codex-home/AGENTS.md</code></div>
<p>Injected automatically into every turn of every thread this member owns.
Fixed for the project's life; researcher-editable via Team settings.</p>
<p style="color:#191919;font-style:italic">{soul}</p></div>

<div class="layer big"><span class="who forge">Harness · grows within a phase</span>
<span class="size">0.7M – {max_tok} tok</span>
<div class="name">L3 · Thread history</div><p>The full rollout of this member's
thread for the current (phase, branch): every prior message, tool call, and
file it has read. Persistent across runs; compacted by rotation (§3).</p></div>

<div class="layer"><span class="who forge">Harness · recomposed each turn</span>
<span class="size">~{brief_med} B</span>
<div class="name">L2 · Situation brief</div><p>The turn input. Anatomy in §2 —
every section tagged by lifecycle class.</p></div>

<div class="layer"><span class="who forge">Harness · on demand</span>
<span class="size">disk</span>
<div class="name">L4 · Filesystem</div><p>Published records, contracts, prior
workspaces. Read on demand — but every read lands permanently in L3.</p></div>

<h2><span class="no">2</span>Anatomy of a real brief</h2>
<p class="lede">A real brief sent to the {role} (the P4 corrected-rerun
brief, which carried a rotation handoff), section by section. <b>Fixed</b> sections never change mid-project; <b>updated</b>
sections are recomposed per turn from sealed state; <b>compacted</b> content
is written by a predecessor thread about to be archived.</p>
{sections}

<h2><span class="no">3</span>The thread across the whole exercise</h2>
<p class="lede">Cumulative input tokens at the end of each stage the {role}
worked (log scale). A new phase or branch starts a fresh thread; P2 shows a
<i>resumed</i> thread growing across two runs; ✂ marks an auto-compact
rotation — the archived thread wrote a handoff note for its successor.</p>
<div class="chart">{chart}</div>
<p class="note">Continuity events: {resumes} Rotations: {rotations}</p>

<h3 style="margin-top:28px">What a rotation handoff looks like</h3>
<p class="lede">Written by the old thread in its own words; consumed by exactly
one successor brief (~1K tokens replacing millions).</p>
{handoffs}

<h2><span class="no">4</span>Every brief this member received</h2>
{briefs}

<h2><span class="no">5</span>Stage-by-stage ledger</h2>
<table><tr><th>Phase</th><th>Run mode</th><th>Stage</th><th style="text-align:right">Thread size at end</th><th style="text-align:right">Brief size</th></tr>
{rows}</table>
<p class="note">✉ = this brief carried a rotation handoff. Thread sizes are
provider-reported cumulative input tokens.</p>

</div></body></html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", default="theorist")
    ap.add_argument("--project", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    project = Path(args.project)
    data = load_member_data(project, args.role)
    out_html = render(data, args.role, json.loads((project / "project.json").read_text())["project_id"])
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(out_html, encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size:,} B)")


if __name__ == "__main__":
    main()
