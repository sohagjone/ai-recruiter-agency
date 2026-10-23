"""Design system for the app: CSS theme plus small HTML/SVG components.

Every piece of text that comes from a resume or an AI answer goes through esc()
before it is placed in HTML, so a resume can never inject markup into the page.
"""

import html as _html
import math
from typing import Dict, Iterable, List, Optional

import streamlit as st

PRIMARY = "#4F46E5"
GOOD, WARN, BAD = "#10B981", "#F59E0B", "#EF4444"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
  --primary:#4F46E5; --primary-2:#7C3AED; --accent:#06B6D4;
  --good:#10B981; --warn:#F59E0B; --bad:#EF4444;
  --ink:#0F172A; --muted:#64748B; --soft:#94A3B8;
  --bg:#F5F7FB; --card:#FFFFFF; --border:#E6EAF3; --track:#EAEEF7;
  --shadow:0 1px 2px rgba(15,23,42,.04), 0 8px 24px rgba(15,23,42,.06);
}

.stApp { background: var(--bg); font-family:'Inter',-apple-system,'Segoe UI',Roboto,sans-serif; color:var(--ink); }
.stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp p,.stApp label,.stApp li { font-family:inherit; }
.block-container { max-width:1180px; padding:1.4rem 2rem 4rem; }
#MainMenu, footer { visibility:hidden; }
[data-testid="stHeader"] { background:transparent; }

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] { background:linear-gradient(185deg,#0B1020 0%,#1B1650 100%); border-right:0; }
[data-testid="stSidebar"] * { color:#E2E8F0; }
[data-testid="stSidebar"] hr { border-color:rgba(255,255,255,.10); }
[data-testid="stSidebar"] .stButton>button {
  width:100%; background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.18); color:#fff; border-radius:12px; font-weight:600;
}
[data-testid="stSidebar"] .stButton>button:hover { background:rgba(255,255,255,.16); border-color:rgba(255,255,255,.35); }
.brand { display:flex; align-items:center; gap:12px; padding:6px 4px 14px; }
.brand-logo { width:42px; height:42px; border-radius:12px; display:grid; place-items:center; font-weight:800; color:#fff!important;
  background:linear-gradient(135deg,#6366F1,#06B6D4); box-shadow:0 6px 18px rgba(99,102,241,.45); letter-spacing:.5px; }
.brand-t { font-weight:800; font-size:1.05rem; line-height:1.1; color:#fff!important; }
.brand-s { font-size:.74rem; color:#A5B4FC!important; letter-spacing:.4px; }
.side-card { background:rgba(255,255,255,.07); border:1px solid rgba(255,255,255,.12); border-radius:14px; padding:14px; margin-top:8px; }
.side-card .n { font-weight:700; color:#fff!important; font-size:.95rem; }
.side-card .m { font-size:.78rem; color:#A5B4FC!important; margin-top:2px; }
.side-foot { font-size:.72rem; color:#94A3B8!important; padding:14px 4px 0; line-height:1.5; }

/* ---------- Hero ---------- */
.hero { position:relative; overflow:hidden; border-radius:22px; padding:30px 34px; color:#fff; margin-bottom:22px;
  background: radial-gradient(900px 300px at 100% 0%, rgba(6,182,212,.55), transparent 60%),
              radial-gradient(700px 300px at 0% 100%, rgba(124,58,237,.65), transparent 60%),
              linear-gradient(135deg,#312E81 0%,#4F46E5 55%,#6366F1 100%);
  box-shadow:0 18px 40px rgba(79,70,229,.30); }
.hero h1 { font-size:2rem; font-weight:800; margin:0 0 6px; color:#fff; letter-spacing:-.4px; padding:0; }
.hero p { margin:0; color:#E0E7FF; font-size:1.02rem; max-width:680px; }
.hero-pills { display:flex; flex-wrap:wrap; gap:8px; margin-top:16px; }
.hero-pill { background:rgba(255,255,255,.16); border:1px solid rgba(255,255,255,.28); padding:6px 12px; border-radius:999px; font-size:.8rem; font-weight:600; color:#fff; backdrop-filter:blur(4px); }

/* ---------- Cards & text ---------- */
.card { background:var(--card); border:1px solid var(--border); border-radius:18px; padding:20px 22px; box-shadow:var(--shadow); margin-bottom:16px; }
.card.tight { padding:16px 18px; }
.card-h { display:flex; align-items:center; gap:10px; font-weight:700; font-size:1.02rem; color:var(--ink); margin-bottom:4px; }
.card-h .ic { width:30px; height:30px; border-radius:9px; display:grid; place-items:center; background:#EEF2FF; font-size:1rem; }
.card-sub { color:var(--muted); font-size:.86rem; margin:0 0 14px; }
.sec-t { font-size:1.15rem; font-weight:800; color:var(--ink); margin:22px 0 4px; letter-spacing:-.2px; }
.sec-s { color:var(--muted); font-size:.9rem; margin-bottom:12px; }
.muted { color:var(--muted); }
.small { font-size:.82rem; }

/* ---------- KPI ---------- */
.kpi-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:14px; margin-bottom:16px; }
.kpi { background:var(--card); border:1px solid var(--border); border-radius:16px; padding:14px 16px; display:flex; gap:12px; align-items:center; box-shadow:var(--shadow); }
.kpi-ic { width:42px; height:42px; border-radius:12px; display:grid; place-items:center; font-size:1.2rem; flex:none; }
.kpi-l { font-size:.74rem; font-weight:600; color:var(--muted); text-transform:uppercase; letter-spacing:.5px; }
.kpi-v { font-size:1.45rem; font-weight:800; line-height:1.15; color:var(--ink); letter-spacing:-.4px; }
.kpi-s { font-size:.76rem; color:var(--soft); margin-top:1px; }

/* ---------- Bars, chips, pills ---------- */
.bar-row { display:grid; grid-template-columns:150px 1fr 56px; gap:12px; align-items:center; margin:9px 0; font-size:.88rem; }
.bar-row .l { color:#334155; font-weight:600; }
.bar-row .r { text-align:right; color:var(--muted); font-weight:700; font-variant-numeric:tabular-nums; }
.wide-labels .bar-row { grid-template-columns:270px 1fr 56px; }
.track { height:9px; background:var(--track); border-radius:999px; overflow:hidden; }
.fill { height:100%; border-radius:999px; }
.chip { display:inline-block; padding:4px 11px; margin:3px 5px 3px 0; border-radius:999px; font-size:.78rem; font-weight:600; border:1px solid transparent; }
.chip.ok { background:#ECFDF5; color:#047857; border-color:#A7F3D0; }
.chip.part { background:#FFFBEB; color:#B45309; border-color:#FDE68A; }
.chip.miss { background:#FEF2F2; color:#B91C1C; border-color:#FECACA; }
.chip.neutral { background:#EEF2FF; color:#4338CA; border-color:#C7D2FE; }
.chip.grey { background:#F1F5F9; color:#475569; border-color:#E2E8F0; }
.pill { display:inline-flex; align-items:center; gap:5px; padding:4px 10px; border-radius:8px; font-size:.76rem; font-weight:600; background:#F1F5F9; color:#334155; margin:0 6px 6px 0; }
.pill.good { background:#ECFDF5; color:#047857; } .pill.warn { background:#FFFBEB; color:#B45309; }
.pill.bad { background:#FEF2F2; color:#B91C1C; } .pill.brand { background:#EEF2FF; color:#4338CA; }
.cat-h { font-size:.74rem; font-weight:700; letter-spacing:.6px; text-transform:uppercase; color:var(--soft); margin:12px 0 2px; }

/* ---------- Candidate header ---------- */
.cand { display:flex; align-items:center; gap:18px; flex-wrap:wrap; }
.avatar { width:62px; height:62px; border-radius:18px; display:grid; place-items:center; color:#fff; font-weight:800; font-size:1.3rem;
  background:linear-gradient(135deg,#4F46E5,#06B6D4); box-shadow:0 8px 20px rgba(79,70,229,.3); flex:none; }
.cand-n { font-size:1.35rem; font-weight:800; letter-spacing:-.3px; }
.cand-h { color:var(--muted); font-size:.95rem; }

/* ---------- Job cards ---------- */
.job { display:flex; gap:18px; align-items:flex-start; background:var(--card); border:1px solid var(--border); border-left:5px solid var(--primary);
  border-radius:16px; padding:18px 20px; margin-bottom:14px; box-shadow:var(--shadow); }
.job-main { flex:1; min-width:0; }
.job-t { font-size:1.08rem; font-weight:800; color:var(--ink); letter-spacing:-.2px; }
.job-s { color:var(--muted); font-size:.86rem; margin:2px 0 10px; }
.mini { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-top:12px; }
.mini .t { display:flex; justify-content:space-between; font-size:.72rem; color:var(--muted); font-weight:600; margin-bottom:4px; }
.mini .track { height:6px; }
.rank { font-size:.72rem; font-weight:800; color:var(--soft); text-transform:uppercase; letter-spacing:.8px; }

/* ---------- Lists ---------- */
.row-item { display:flex; gap:10px; align-items:flex-start; padding:9px 0; border-bottom:1px dashed var(--border); font-size:.9rem; color:#1E293B; }
.row-item:last-child { border-bottom:0; }
.dot { width:22px; height:22px; border-radius:50%; flex:none; display:grid; place-items:center; font-size:.72rem; font-weight:800; margin-top:1px; }
.dot.ok { background:#D1FAE5; color:#047857; } .dot.no { background:#FEE2E2; color:#B91C1C; }
.dot.warn { background:#FEF3C7; color:#B45309; } .dot.info { background:#E0E7FF; color:#4338CA; }
.row-w { margin-left:auto; color:var(--soft); font-size:.76rem; font-weight:700; white-space:nowrap; }
.steps { counter-reset:s; }
.step { display:flex; gap:12px; padding:10px 0; align-items:flex-start; font-size:.92rem; }
.step:before { counter-increment:s; content:counter(s); width:26px; height:26px; border-radius:50%; background:linear-gradient(135deg,#4F46E5,#7C3AED); color:#fff; font-weight:800; font-size:.78rem; display:grid; place-items:center; flex:none; }

/* ---------- Tables ---------- */
table.t { width:100%; border-collapse:collapse; font-size:.88rem; border:0; }
table.t th, table.t td { border-left:0; border-right:0; }
table.t th { text-align:left; font-size:.72rem; text-transform:uppercase; letter-spacing:.5px; color:var(--muted); padding:8px 10px; border-bottom:1px solid var(--border); }
table.t td { padding:10px; border-bottom:1px solid #F1F5F9; vertical-align:middle; }
table.t tr:last-child td { border-bottom:0; }
.num { font-variant-numeric:tabular-nums; font-weight:700; }

/* ---------- Roadmap ---------- */
.road { display:flex; flex-wrap:wrap; gap:10px; align-items:stretch; }
.road-step { flex:1; min-width:150px; background:#F8FAFF; border:1px solid #DDE3FB; border-radius:14px; padding:12px 14px; }
.road-step .k { font-size:.7rem; font-weight:800; color:var(--primary); letter-spacing:.7px; text-transform:uppercase; }
.road-step .s { font-weight:800; margin:3px 0; font-size:.98rem; }
.road-step .d { font-size:.8rem; color:var(--muted); }
.road-step .g { font-weight:800; color:var(--good); font-size:.86rem; }
.road-arrow { align-self:center; color:var(--soft); font-weight:800; }

/* ---------- Stepper (progress) ---------- */
.stepper { display:flex; gap:10px; flex-wrap:wrap; }
.sp { flex:1; min-width:150px; background:var(--card); border:1px solid var(--border); border-radius:14px; padding:12px 14px; display:flex; gap:10px; align-items:center; font-size:.86rem; font-weight:600; color:var(--muted); }
.sp .c { width:26px; height:26px; border-radius:50%; display:grid; place-items:center; background:#EEF2FF; color:#6366F1; font-size:.78rem; font-weight:800; flex:none; }
.sp.done { color:#047857; border-color:#A7F3D0; background:#F0FDF9; } .sp.done .c { background:#10B981; color:#fff; }
.sp.run { color:var(--primary); border-color:#C7D2FE; background:#F5F7FF; } .sp.run .c { background:var(--primary); color:#fff; animation:pulse 1.1s infinite; }
@keyframes pulse { 0%{box-shadow:0 0 0 0 rgba(79,70,229,.5)} 70%{box-shadow:0 0 0 9px rgba(79,70,229,0)} 100%{box-shadow:0 0 0 0 rgba(79,70,229,0)} }

/* ---------- Notices ---------- */
.note { border-radius:14px; padding:12px 16px; font-size:.88rem; margin-bottom:14px; border:1px solid; display:flex; gap:10px; }
.note.info { background:#EEF2FF; border-color:#C7D2FE; color:#3730A3; }
.note.warn { background:#FFFBEB; border-color:#FDE68A; color:#92400E; }
.verdict { display:flex; align-items:center; gap:22px; flex-wrap:wrap; }
.verdict-t { font-size:1.5rem; font-weight:800; letter-spacing:-.4px; }
.legend { display:flex; gap:8px; flex-wrap:wrap; margin-top:10px; }

/* ---------- Streamlit widgets ---------- */
[role="tablist"] { gap:6px; background:#fff; padding:6px; border-radius:14px; border:1px solid var(--border); box-shadow:var(--shadow); margin-bottom:12px; }
[role="tab"] { height:44px; border-radius:10px; padding:0 20px; background:transparent!important; }
[role="tab"] p { font-weight:700; font-size:.95rem; margin:0; color:var(--muted)!important; }
[role="tab"][aria-selected="true"] { background:linear-gradient(135deg,#4F46E5,#7C3AED)!important; box-shadow:0 6px 16px rgba(79,70,229,.35); }
[role="tab"][aria-selected="true"] p { color:#fff!important; }
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"], .react-aria-SelectionIndicator { display:none!important; }
/* sidebar navigation (st.radio) */
[data-testid="stSidebar"] [role="radiogroup"] { gap:4px; }
[data-testid="stSidebar"] [data-testid="stRadioOption"] { padding:10px 14px; border-radius:10px; cursor:pointer; width:100%; }
[data-testid="stSidebar"] [data-testid="stRadioOption"]:hover { background:rgba(255,255,255,.08); }
[data-testid="stSidebar"] [data-testid="stRadioOption"] > div > div:first-child { display:none; }
[data-testid="stSidebar"] [data-testid="stRadioOption"] p { font-weight:600; font-size:.92rem; }
[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] { background:linear-gradient(135deg,#4F46E5,#7C3AED); box-shadow:0 6px 16px rgba(79,70,229,.4); }
[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] p { color:#fff; }
button[kind="primary"], button[data-testid="stBaseButton-primary"] {
  background:linear-gradient(135deg,#4F46E5,#7C3AED); border:0; border-radius:12px; font-weight:700; padding:.6rem 1.2rem; box-shadow:0 8px 20px rgba(79,70,229,.30); }
button[kind="primary"]:hover, button[data-testid="stBaseButton-primary"]:hover { filter:brightness(1.07); }
button[kind="secondary"], button[data-testid="stBaseButton-secondary"] { border-radius:12px; font-weight:600; border-color:var(--border); }
[data-testid="stFileUploaderDropzone"] { border:2px dashed #C7D2FE; background:#F8FAFF; border-radius:16px; }
[data-testid="stExpander"] { background:#fff; border:1px solid var(--border)!important; border-radius:14px; box-shadow:none; }
[data-testid="stExpander"] summary p { font-weight:700; }
[data-testid="stMetric"] { background:#fff; border:1px solid var(--border); border-radius:14px; padding:12px 16px; }
[data-testid="stVerticalBlockBorderWrapper"] { border-radius:16px; }
@media (max-width:760px){ .block-container{padding:1rem 1rem 3rem;} .hero{padding:22px;} .hero h1{font-size:1.5rem;}
  .bar-row{grid-template-columns:100px 1fr 44px;} .mini{grid-template-columns:repeat(2,1fr);} .job{flex-direction:column;} }
</style>
"""


# --------------------------------------------------------------------------- helpers
def esc(value) -> str:
    return _html.escape(str(value if value is not None else ""), quote=True)


def squash(markup: str) -> str:
    """Remove indentation and blank lines so Streamlit's markdown never turns HTML into a code block."""
    return "\n".join(line.strip() for line in markup.splitlines() if line.strip())


def render(markup: str) -> None:
    st.markdown(squash(markup), unsafe_allow_html=True)


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def score_color(value: float) -> str:
    return GOOD if value >= 70 else WARN if value >= 50 else BAD


def money(n: Optional[float]) -> str:
    if n is None:
        return "-"
    return f"${n / 1000:,.0f}k" if n >= 1000 else f"${n:,.0f}"


def salary_text(sal: Optional[Dict[str, float]]) -> str:
    if not sal:
        return "Not listed"
    return money(sal["min"]) if sal["min"] == sal["max"] else f"{money(sal['min'])} - {money(sal['max'])}"


# --------------------------------------------------------------------------- components
def hero(title: str, subtitle: str, pills: Iterable[str]) -> str:
    chips = "".join(f'<span class="hero-pill">{esc(p)}</span>' for p in pills)
    return f'<div class="hero"><h1>{esc(title)}</h1><p>{esc(subtitle)}</p><div class="hero-pills">{chips}</div></div>'


def section(title: str, sub: str = "") -> str:
    s = f'<div class="sec-s">{esc(sub)}</div>' if sub else ""
    return f'<div class="sec-t">{esc(title)}</div>{s}'


def card_open(title: str, icon: str = "", sub: str = "") -> str:
    ic = f'<span class="ic">{icon}</span>' if icon else ""
    s = f'<div class="card-sub">{esc(sub)}</div>' if sub else '<div style="height:10px"></div>'
    return f'<div class="card"><div class="card-h">{ic}{esc(title)}</div>{s}'


CARD_CLOSE = "</div>"


def kpi(label: str, value, sub: str = "", icon: str = "", tint: str = "#EEF2FF") -> str:
    s = f'<div class="kpi-s">{esc(sub)}</div>' if sub else ""
    return (f'<div class="kpi"><div class="kpi-ic" style="background:{tint}">{icon}</div>'
            f'<div><div class="kpi-l">{esc(label)}</div><div class="kpi-v">{esc(value)}</div>{s}</div></div>')


def kpi_grid(items: List[str]) -> str:
    return f'<div class="kpi-grid">{"".join(items)}</div>'


def ring(value: float, size: int = 130, stroke: int = 11, color: Optional[str] = None, caption: str = "") -> str:
    value = max(0, min(100, value))
    color = color or score_color(value)
    r = size / 2 - stroke
    c = 2 * math.pi * r
    cx = size / 2
    cap = (f'<text x="{cx}" y="{cx + size * 0.20}" text-anchor="middle" font-size="{size * 0.095:.1f}" '
           f'font-weight="600" fill="#64748B">{esc(caption)}</text>') if caption else ""
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" role="img" aria-label="{esc(caption)} {value:.0f} out of 100">'
        f'<circle cx="{cx}" cy="{cx}" r="{r}" fill="none" stroke="#EAEEF7" stroke-width="{stroke}"/>'
        f'<circle cx="{cx}" cy="{cx}" r="{r}" fill="none" stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" '
        f'stroke-dasharray="{c:.2f}" stroke-dashoffset="{c * (1 - value / 100):.2f}" transform="rotate(-90 {cx} {cx})"/>'
        f'<text x="{cx}" y="{cx - (size * 0.02 if caption else 0)}" text-anchor="middle" dominant-baseline="central" '
        f'font-size="{size * 0.30:.1f}" font-weight="800" fill="#0F172A">{value:.0f}</text>{cap}</svg>'
    )


def radar(dims: Dict[str, float], size: int = 340) -> str:
    labels = list(dims.keys())
    n = len(labels)
    cx = cy = size / 2
    R = size * 0.27

    def pt(i: int, frac: float):
        a = -math.pi / 2 + 2 * math.pi * i / n
        return cx + R * frac * math.cos(a), cy + R * frac * math.sin(a)

    grid = ""
    for f in (0.25, 0.5, 0.75, 1.0):
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i, f) for i in range(n)))
        grid += f'<polygon points="{pts}" fill="none" stroke="#E2E8F0" stroke-width="1"/>'
    axes = "".join(f'<line x1="{cx}" y1="{cy}" x2="{pt(i, 1)[0]:.1f}" y2="{pt(i, 1)[1]:.1f}" stroke="#E2E8F0"/>' for i in range(n))
    vals = [max(0, min(100, dims[l])) / 100 for l in labels]
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i, v) for i, v in enumerate(vals)))
    dots = "".join(f'<circle cx="{pt(i, v)[0]:.1f}" cy="{pt(i, v)[1]:.1f}" r="4.5" fill="#fff" stroke="#4F46E5" stroke-width="2.5"/>' for i, v in enumerate(vals))
    text = ""
    for i, l in enumerate(labels):
        x, y = pt(i, 1.36)
        anchor = "middle" if abs(x - cx) < 8 else ("start" if x > cx else "end")
        text += (f'<text x="{x:.1f}" y="{y - 3:.1f}" text-anchor="{anchor}" font-size="12.5" font-weight="700" fill="#334155">{esc(l)}</text>'
                 f'<text x="{x:.1f}" y="{y + 13:.1f}" text-anchor="{anchor}" font-size="12" font-weight="800" fill="#4F46E5">{dims[l]:.0f}</text>')
    return (f'<svg viewBox="-50 0 {size + 100} {size}" width="100%" style="max-width:{size + 100}px;display:block;margin:0 auto" role="img" aria-label="Resume strength radar chart">'
            f'{grid}{axes}<polygon points="{poly}" fill="rgba(79,70,229,.16)" stroke="#4F46E5" stroke-width="2.5" stroke-linejoin="round"/>{dots}{text}</svg>')


def bar_row(label: str, value: float, right: str = "", color: Optional[str] = None) -> str:
    color = color or score_color(value)
    return (f'<div class="bar-row"><div class="l">{esc(label)}</div>'
            f'<div class="track"><div class="fill" style="width:{max(2, min(100, value)):.0f}%;background:{color}"></div></div>'
            f'<div class="r">{esc(right or f"{value:.0f}")}</div></div>')


def chips(items: Iterable[str], kind: str = "neutral") -> str:
    return "".join(f'<span class="chip {kind}">{esc(i)}</span>' for i in items)


def pill(text: str, kind: str = "") -> str:
    return f'<span class="pill {kind}">{esc(text)}</span>'


def row_item(text: str, kind: str = "ok", symbol: str = "", weight: str = "") -> str:
    sym = symbol or {"ok": "✓", "no": "✕", "warn": "!", "info": "i"}.get(kind, "•")
    w = f'<span class="row-w">{esc(weight)}</span>' if weight else ""
    return f'<div class="row-item"><span class="dot {kind}">{sym}</span><span>{esc(text)}</span>{w}</div>'


def note(text: str, kind: str = "info", icon: str = "ℹ️") -> str:
    return f'<div class="note {kind}"><span>{icon}</span><span>{esc(text)}</span></div>'


def initials(name: str) -> str:
    parts = [p for p in (name or "").replace(".", " ").split() if p[:1].isalpha()]
    return ("".join(p[0] for p in parts[:2]).upper() or "AI")


def stepper(states: Dict[str, str], labels: Dict[str, str]) -> str:
    out = []
    for i, (key, label) in enumerate(labels.items(), 1):
        s = states.get(key, "wait")
        mark = "✓" if s == "done" else i
        cls = {"done": "done", "run": "run"}.get(s, "")
        out.append(f'<div class="sp {cls}"><span class="c">{mark}</span>{esc(label)}</div>')
    return f'<div class="stepper">{"".join(out)}</div>'


def job_card(rank: int, r: Dict, salary_note: str = "") -> str:
    job, score = r["job"], r["score"]
    color = score_color(score)
    comp = r["components"]
    bars = "".join(
        f'<div><div class="t"><span>{esc(k)}</span><span>{v}%</span></div>'
        f'<div class="track"><div class="fill" style="width:{max(2, v)}%;background:{score_color(v)}"></div></div></div>'
        for k, v in comp.items()
    )
    skill_chips = chips(r["matched"], "ok") + chips(r["partial"], "part") + chips(r["missing"], "miss")
    flags = "".join(pill(f, "warn") for f in r["flags"])
    meta = (pill("💰 " + salary_text(r["salary"]), "brand") + (salary_note or "") + pill(r["label"], "good" if score >= 60 else "warn" if score >= 40 else "bad") + flags)
    return (
        f'<div class="job" style="border-left-color:{color}"><div class="job-main">'
        f'<div class="rank">Rank #{rank}</div><div class="job-t">{esc(job["title"])}</div>'
        f'<div class="job-s">{esc(job["company"])} · {esc(job["location"])} · {esc(job["type"])} · {esc(job["experience_level"])}</div>'
        f'<div>{meta}</div><div style="margin-top:4px">{skill_chips}</div><div class="mini">{bars}</div></div>'
        f'<div>{ring(score, 92, 9, color, "match")}</div></div>'
    )


def table(headers: List[str], rows: List[List[str]]) -> str:
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return f'<table class="t"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'
