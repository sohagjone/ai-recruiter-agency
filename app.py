# Streamlit Web Application - AI Recruiter Agency
import asyncio
import json
from datetime import datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()  # lets a local .env file provide GEMINI_API_KEY / GROQ_API_KEY

st.set_page_config(
    page_title="AI Recruiter Agency",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

from agents.orchestrator import OrchestratorAgent  # noqa: E402
from db.database import JobDatabase  # noqa: E402
from utils import scoring, ui  # noqa: E402
from utils.exceptions import ResumeProcessingError  # noqa: E402
from utils.logger import setup_logger  # noqa: E402
from utils.report import build_markdown_report  # noqa: E402

logger = setup_logger()
ui.inject_css()

SAMPLES_DIR = Path(__file__).parent / "resumes"
STAGE_LABELS = {
    "extraction": "Reading resume",
    "analysis": "Analyzing profile",
    "matching": "Matching jobs",
    "screening": "Screening",
    "recommendation": "Building plan",
}
PALETTE = ["#4F46E5", "#06B6D4", "#10B981", "#F59E0B", "#EC4899", "#8B5CF6", "#14B8A6", "#F97316", "#64748B"]


# --------------------------------------------------------------------------- pipeline
def run_pipeline(resume_data: dict, stepper_slot) -> dict:
    states: dict = {}

    def progress(stage: str, state: str) -> None:
        states[stage] = "run" if state == "running" else "done"
        stepper_slot.markdown(ui.squash(ui.stepper(states, STAGE_LABELS)), unsafe_allow_html=True)

    return asyncio.run(OrchestratorAgent().process_application(resume_data, progress=progress))


def reset_analysis() -> None:
    for key in [k for k in st.session_state if k == "analysis" or k.startswith(("jm_", "wi_", "th_"))]:
        del st.session_state[key]


# --------------------------------------------------------------------------- sidebar
def sidebar() -> str:
    with st.sidebar:
        ui.render(
            '<div class="brand"><div class="brand-logo">AI</div><div><div class="brand-t">Recruiter Agency</div>'
            '<div class="brand-s">RESUME INTELLIGENCE</div></div></div>'
        )
        selected = st.radio("Navigation", ["📊  Analyze Resume", "ℹ️  About"], label_visibility="collapsed", key="nav")
        selected = "About" if "About" in selected else "Analyze Resume"
        state = st.session_state.get("analysis")
        if state:
            res = state["result"]
            name = res["extracted_data"]["profile"].get("name") or "Candidate"
            ui.render(
                f'<div class="side-card"><div class="n">{ui.esc(name)}</div>'
                f'<div class="m">{ui.esc(state["filename"])}</div>'
                f'<div class="m">Screening {res["screening_results"]["screening_score"]}/100 · '
                f'Best match {res["job_matches"]["best_score"]}%</div></div>'
            )
            st.button("↻  New analysis", on_click=reset_analysis, key="side_reset")
        ui.render(
            '<div class="side-foot">Scores are decision-support estimates calculated from the resume text '
            'and sample job listings.</div>'
        )
    return selected


# --------------------------------------------------------------------------- upload page
def page_upload() -> None:
    n_jobs = len(JobDatabase().get_unique_jobs())
    ui.render(ui.hero(
        "Hire smarter with resume intelligence",
        "Upload a resume and get a calculated analysis, job matches, a transparent screening score and a personal action plan.",
        ["5 specialised AI agents", f"{n_jobs} job listings scored", "20+ calculated metrics", "PDF is never saved"],
    ))

    left, right = st.columns([1.15, 1], gap="large")
    with left:
        with st.container(border=True):
            ui.render('<div class="card-h"><span class="ic">📄</span>Upload a resume</div>'
                      '<div class="card-sub">PDF with selectable text (not a scanned image), up to 10 MB.</div>')
            uploaded = st.file_uploader("Resume PDF", type=["pdf"], label_visibility="collapsed")
            samples = sorted(SAMPLES_DIR.glob("*.pdf")) if SAMPLES_DIR.exists() else []
            sample_name = None
            if samples:
                choice = st.selectbox(
                    "…or try a sample resume",
                    ["None"] + [p.stem.replace("_", " ") for p in samples],
                    key="sample_choice",
                )
                if choice != "None":
                    sample_name = choice
            ready = bool(uploaded) or bool(sample_name)
            go = st.button("🚀  Analyze resume", type="primary", disabled=not ready, use_container_width=True)

    with right:
        items = [
            ("📊", "Analysis", "Resume strength score, skills map, ATS health check and career timeline."),
            ("💼", "Job Matches", "Weighted match % per role, skill gaps, salary band and a job-posting fit checker."),
            ("🎯", "Screening", "A transparent 100-point score with red and green flags and interview questions."),
            ("💡", "Recommendation", "Skill priorities, a learning roadmap and a what-if score simulator."),
        ]
        body = "".join(
            f'<div class="row-item"><span class="kpi-ic" style="background:#EEF2FF;width:38px;height:38px">{i}</span>'
            f'<span><b>{t}</b><br><span class="muted small">{d}</span></span></div>' for i, t, d in items
        )
        ui.render(ui.card_open("What you will get", "✨") + body + ui.CARD_CLOSE)
        ui.render(ui.note(
            "Your PDF is processed in memory and not stored. The extracted text is sent to the configured AI "
            "provider (Gemini or Groq) to read the resume.", "info", "🔒"))

    if not go:
        return

    if uploaded:
        data, filename = uploaded.getvalue(), uploaded.name
    else:
        match = next(p for p in samples if p.stem.replace("_", " ") == sample_name)
        data, filename = match.read_bytes(), match.name

    slot = st.empty()
    slot.markdown(ui.squash(ui.stepper({}, STAGE_LABELS)), unsafe_allow_html=True)
    try:
        result = run_pipeline({"file_bytes": data, "filename": filename,
                               "submission_timestamp": datetime.now().isoformat()}, slot)
    except ResumeProcessingError as e:
        slot.empty()
        st.error(str(e))
        return
    except Exception as e:
        slot.empty()
        stage = getattr(e, "stage", "processing")
        logger.error(f"Pipeline failed at {stage}: {e}", exc_info=True)
        st.error(f"Something went wrong while {STAGE_LABELS.get(stage, stage).lower()}: {e}")
        return
    logger.info(f"Analysis completed for {filename}")
    st.session_state["analysis"] = {"result": result, "filename": filename}
    st.rerun()


# --------------------------------------------------------------------------- results: shared
def verdict_word(v: float) -> str:
    return "Excellent" if v >= 80 else "Strong" if v >= 65 else "Decent" if v >= 50 else "Needs work"


def results_header(profile, analysis, matches, screening) -> None:
    c = analysis["contacts"]
    pills = "".join(ui.pill(x, "") for x in (
        ("✉️ " + c["email"]) if c.get("email") else "",
        ("📞 " + c["phone"]) if c.get("phone") else "",
        ("📍 " + profile["location"]) if profile.get("location") else "",
    ) if x)
    sub = " · ".join(x for x in (profile.get("headline"), analysis["experience_level"]) if x)
    rings = (
        f'<div style="text-align:center">{ui.ring(analysis["resume_strength"], 84, 8)}<div class="small muted">Resume</div></div>'
        f'<div style="text-align:center">{ui.ring(screening["screening_score"], 84, 8)}<div class="small muted">Screening</div></div>'
        f'<div style="text-align:center">{ui.ring(matches["best_score"], 84, 8)}<div class="small muted">Best match</div></div>'
    )
    ui.render(
        f'<div class="card tight"><div class="cand"><div class="avatar">{ui.esc(ui.initials(profile.get("name", "")))}</div>'
        f'<div style="flex:1;min-width:220px"><div class="cand-n">{ui.esc(profile.get("name") or "Candidate")}</div>'
        f'<div class="cand-h">{ui.esc(sub)}</div><div style="margin-top:8px">{pills}</div></div>'
        f'<div style="display:flex;gap:14px">{rings}</div></div></div>'
    )


# --------------------------------------------------------------------------- tab 1
def tab_analysis(profile, analysis) -> None:
    dims, weights = analysis["dimensions"], analysis["dimension_weights"]
    strength = analysis["resume_strength"]
    upside = sorted(dims, key=lambda k: -(100 - dims[k]) * weights[k])
    exp, edu, imp = analysis["experience"], analysis["education"], analysis["impact"]

    c1, c2 = st.columns([1, 1.15], gap="medium")
    with c1:
        ui.render(
            ui.card_open("Resume strength", "🏆", "Weighted score across six dimensions")
            + f'<div class="verdict">{ui.ring(strength, 150, 13, caption="of 100")}'
              f'<div><div class="verdict-t">{verdict_word(strength)}</div>'
              f'<div class="muted" style="margin-top:6px">Biggest opportunity:<br><b>{ui.esc(upside[0])}</b> '
              f'(scores {dims[upside[0]]}/100)</div></div></div>'
            + '<div style="margin-top:14px">' + "".join(ui.bar_row(k, v, f"{v}") for k, v in dims.items()) + '</div>' + ui.CARD_CLOSE
        )
    with c2:
        ui.render(ui.card_open("Strength profile", "🕸️") + ui.radar(dims) + ui.CARD_CLOSE)

    ui.render(ui.kpi_grid([
        ui.kpi("Experience", f"{analysis['years_of_experience']:g} yrs", analysis["experience_level"], "💼", "#EEF2FF"),
        ui.kpi("Skills found", len(analysis["skills"]), f"{len(analysis['skill_groups'])} categories", "🧩", "#ECFEFF"),
        ui.kpi("Education", edu["level"], "highest detected", "🎓", "#ECFDF5"),
        ui.kpi("Quantified bullets", imp["quantified"], f"{imp['action_verbs']} action-verb bullets", "📈", "#FFFBEB"),
        ui.kpi("Resume length", f"{analysis['word_count']}", "words", "📝", "#FDF2F8"),
        ui.kpi("Extraction confidence", f"{analysis['confidence_score']:.0%}", "fields read correctly", "🎯", "#F5F3FF"),
    ]))

    c3, c4 = st.columns(2, gap="medium")
    with c3:
        counts = analysis["category_counts"]
        top = max((n for _, n in counts), default=1)
        bars = "".join(ui.bar_row(cat, n / top * 100, str(n), PALETTE[i % len(PALETTE)]) for i, (cat, n) in enumerate(counts))
        groups = "".join(
            f'<div class="cat-h">{ui.esc(cat)}</div>{ui.chips(skills, "neutral")}'
            for cat, skills in sorted(analysis["skill_groups"].items(), key=lambda kv: -len(kv[1]))
        )
        ui.render(ui.card_open("Skill portfolio", "🧩", "Skills detected by category") + bars + groups + ui.CARD_CLOSE)
    with c4:
        checks = "".join(
            ui.row_item(c["label"] if c["passed"] else f"{c['label']} - {c['tip']}", "ok" if c["passed"] else "no",
                        weight=f"+{c['weight']}" if c["passed"] else f"{c['weight']} pts")
            for c in analysis["ats_checks"]
        )
        ui.render(
            ui.card_open("Resume health check", "✅", "ATS readiness: ten checks, 100 points")
            + f'<div style="display:flex;gap:18px;align-items:center;margin-bottom:6px">{ui.ring(analysis["ats_score"], 96, 9, caption="ATS")}'
              f'<div class="muted small">Readability {analysis["readability"]["score"]}/100<br>'
              f'avg {analysis["readability"]["avg_words_per_line"]} words per line</div></div>' + checks + ui.CARD_CLOSE
        )

    # career timeline
    rows = []
    for e in profile.get("experience", []):
        s, en = scoring.parse_date(e.get("start")), scoring.parse_date(e.get("end"), True)
        if s and en and en >= s:
            rows.append((e, (en.year - s.year) * 12 + en.month - s.month, s, en))
    body = ""
    if rows:
        longest = max(m for _, m, _, _ in rows) or 1
        for e, months, s, en in rows[:8]:
            label = f"{e.get('title', 'Role')}" + (f" · {e['company']}" if e.get("company") else "")
            span = f"{s:%b %Y} - {'Present' if en >= scoring.TODAY else format(en, '%b %Y')}"
            body += (f'<div class="bar-row" style="grid-template-columns:1.6fr 1.4fr 70px"><div class="l">{ui.esc(label)}'
                     f'<div class="muted small" style="font-weight:500">{ui.esc(span)}</div></div>'
                     f'<div class="track"><div class="fill" style="width:{max(4, months / longest * 100):.0f}%;background:#4F46E5"></div></div>'
                     f'<div class="r">{months / 12:.1f} yrs</div></div>')
    else:
        body = f'<div class="muted">Years were estimated from {ui.esc(analysis["experience_source"])}.</div>'
    for g in exp["gaps"][:3]:
        body += ui.row_item(f"Gap of {g['months']} months between {g['from']} and {g['to']}", "warn")
    meta = (ui.pill(f"Avg tenure {exp['avg_tenure']:g} yrs", "brand") + ui.pill(f"Longest {exp['longest_tenure']:g} yrs", "brand")) if exp["roles"] else ""
    ui.render(ui.card_open("Career timeline", "🗓️", f"{exp['roles']} role(s) · total {analysis['years_of_experience']:g} years") + meta + body + ui.CARD_CLOSE)

    extra = ""
    if profile.get("summary"):
        extra += f'<p style="margin:0 0 10px">{ui.esc(profile["summary"])}</p>'
    if profile.get("certifications"):
        extra += '<div class="cat-h">Certifications</div>' + ui.chips(profile["certifications"], "grey")
    if profile.get("languages"):
        extra += '<div class="cat-h">Languages</div>' + ui.chips(profile["languages"], "grey")
    if extra:
        ui.render(ui.card_open("Profile details", "👤") + extra + ui.CARD_CLOSE)

    with st.expander("How is the resume strength score calculated?"):
        rows_html = [[ui.esc(k), f"{int(weights[k] * 100)}%", f'<span class="num">{dims[k]}</span>', f'<span class="num">{dims[k] * weights[k]:.1f}</span>'] for k in dims]
        rows_html.append(["<b>Total</b>", "100%", "", f'<span class="num"><b>{strength}</b></span>'])
        ui.render(ui.table(["Dimension", "Weight", "Score", "Points"], rows_html))


# --------------------------------------------------------------------------- tab 2
def tab_matches(matches, ranked, cand) -> None:
    strong = sum(1 for r in ranked if r["score"] >= 60)
    est = matches.get("salary_estimate")
    ui.render(ui.kpi_grid([
        ui.kpi("Roles scored", matches["number_of_jobs_scored"], f"{matches['number_of_matches']} above 30%", "🗂️", "#EEF2FF"),
        ui.kpi("Strong matches", strong, "60% or higher", "🔥", "#FEF2F2"),
        ui.kpi("Best match", f"{matches['best_score']}%", ranked[0]["job"]["title"] if ranked else "", "🏅", "#FFFBEB"),
        ui.kpi("Top-5 average", f"{matches['top5_average']:g}%", "overall market fit", "📊", "#ECFDF5"),
        ui.kpi("Salary band", f"{ui.money(est['min'])}-{ui.money(est['max'])}" if est else "-",
               f"from {est['based_on']} best matches" if est else "no salary data", "💰", "#ECFEFF"),
    ]))

    with st.container(border=True):
        f1, f2, f3, f4 = st.columns([1.2, 1, 1, 1.2])
        min_score = f1.slider("Minimum match %", 0, 90, 30, 5, key="jm_min")
        top_n = f2.select_slider("Show top", options=[3, 5, 8, 10, 15, 20], value=5, key="jm_n")
        sort_by = f3.selectbox("Sort by", ["Best match", "Highest salary", "Experience fit"], key="jm_sort")
        expected = f4.number_input("Expected salary (USD/yr)", 0, 1_000_000, 0, 5_000, key="jm_salary",
                                   help="Optional. Shows whether each listed range fits your expectation.")
        remote_only = st.toggle("Remote roles only", key="jm_remote")

    pool = [r for r in ranked if r["score"] >= min_score and (not remote_only or "remote" in r["job"]["location"].lower())]
    if sort_by == "Highest salary":
        pool.sort(key=lambda r: -(r["salary"]["mid"] if r["salary"] else 0))
    elif sort_by == "Experience fit":
        pool.sort(key=lambda r: (-r["components"]["Experience"], -r["score"]))
    shown = pool[:top_n]

    if not shown:
        ui.render(ui.note("No roles meet these filters. Lower the minimum match or turn off 'Remote roles only'.", "warn", "⚠️"))
    else:
        overview = "".join(ui.bar_row(f"{r['job']['title']} · {r['job']['company']}", r["score"], f"{r['score']}%") for r in shown[:10])
        ui.render(ui.card_open("Match overview", "📊", f"{len(pool)} role(s) pass your filters") + f'<div class="wide-labels">{overview}</div>' + ui.CARD_CLOSE)
        for i, r in enumerate(shown, 1):
            note = ""
            if expected and r["salary"]:
                s = r["salary"]
                note = (ui.pill("✓ Above your expectation", "good") if expected < s["min"] else
                        ui.pill("✓ Within your expectation", "good") if expected <= s["max"] else
                        ui.pill("Above this range", "warn"))
            ui.render(ui.job_card(i, r, note))
        ui.render('<div class="small muted">Chips: <span class="chip ok">matched</span><span class="chip part">partial</span>'
                  '<span class="chip miss">missing</span></div>')

    with st.expander("How are match scores calculated?"):
        ui.render(ui.table(["Component", "Weight", "What it measures"], [
            ["Skills", "60%", "Share of the role's required skills found in the resume (partial matches count half)."],
            ["Experience", "20%", "Your years of experience against the role's minimum."],
            ["Level", "10%", "How close your seniority is to the role's level."],
            ["Title", "10%", "Overlap between the job title and your past titles."],
        ]) + '<p class="muted small" style="margin-top:10px">Experience, level and title only count once at least half of the skills match, so unrelated jobs cannot score well on seniority alone.</p>')

    with st.expander("🎯 Check your fit for a specific job posting"):
        jd = st.text_area("Paste a job description", height=170, key="jm_jd", placeholder="Paste the full job description here…")
        if jd.strip():
            fit = scoring.jd_fit(jd, cand)
            if not fit:
                ui.render(ui.note("Paste a longer description (at least ~15 words with some skills) to get a fit score.", "warn", "⚠️"))
            else:
                yrs = ""
                if fit["required_years"]:
                    yrs = ui.row_item(f"Requires {fit['required_years']}+ years - you have {cand['years']:g}", "ok" if fit["years_ok"] else "warn")
                none = '<span class="muted">None</span>'
                ui.render(
                    f'<div class="card"><div class="verdict">{ui.ring(fit["score"], 120, 11, caption="fit")}<div>'
                    f'<div class="verdict-t">{ui.esc(fit["label"])}</div>'
                    f'<div class="muted">{len(fit["matched"])} of {len(fit["matched"]) + len(fit["missing"])} detected skills matched</div></div></div>'
                    f'<div class="cat-h">Skills you have</div>{ui.chips(fit["matched"], "ok") or none}'
                    f'<div class="cat-h">Skills to add or highlight</div>{ui.chips(fit["missing"], "miss") or none}'
                    f'<div class="cat-h">Keywords already in your resume</div>{ui.chips(fit["keywords_hit"], "grey") or none}'
                    f'<div class="cat-h">Keywords missing from your resume</div>{ui.chips(fit["keywords_missing"], "part") or none}{yrs}</div>'
                )


# --------------------------------------------------------------------------- tab 3
def tab_screening(screening, ranked) -> None:
    score = screening["screening_score"]
    c1, c2 = st.columns([1, 1.2], gap="medium")
    with c1:
        legend = "".join(ui.pill(t, k) for t, k in (("80+ Strong shortlist", "good"), ("65-79 Good", "brand"), ("50-64 Potential", "warn"), ("<50 Weak", "bad")))
        ui.render(
            ui.card_open("Screening verdict", "🎯", "Calculated, not estimated")
            + f'<div class="verdict">{ui.ring(score, 150, 13, caption="of 100")}<div>'
              f'<div class="verdict-t">{ui.esc(screening["verdict"])}</div>'
              f'<div class="muted" style="margin-top:4px">{ui.esc(screening["action"])}</div></div></div>'
              f'<div class="legend">{legend}</div>' + ui.CARD_CLOSE
        )
    with c2:
        body = "".join(
            ui.bar_row(b["label"], b["score"], f"{b['points']}/{b['weight']}")
            + f'<div class="muted small" style="margin:-4px 0 4px 162px">{ui.esc(b["detail"])}</div>'
            for b in screening["breakdown"]
        )
        ui.render(ui.card_open("Score breakdown", "🧮", "Points earned out of each factor's weight") + body
                  + f'<div class="row-item"><b>Total</b><span class="row-w" style="font-size:1rem;color:#0F172A">{score} / 100</span></div>' + ui.CARD_CLOSE)

    with st.container(border=True):
        ui.render('<div class="card-h"><span class="ic">🎚️</span>Shortlist threshold check</div>'
                  '<div class="card-sub">Set the score your team requires and see how far this candidate is.</div>')
        threshold = st.slider("Required score to shortlist", 40, 90, 65, key="th_value")
        gap = threshold - score
        potential = sorted(((b["label"], b["weight"] * (100 - b["score"]) / 100) for b in screening["breakdown"]), key=lambda x: -x[1])
        m1, m2 = st.columns([1, 2])
        m1.metric("Result", "Shortlist ✓" if gap <= 0 else "Below threshold", f"{-gap:+d} pts vs threshold")
        upside_rows = "".join(
            ui.bar_row(label, pts / max(potential[0][1], 0.1) * 100, f"+{pts:.1f}", "#4F46E5") for label, pts in potential[:3] if pts > 0
        ) or '<div class="muted">Nothing left to gain.</div>'
        with m2:
            ui.render('<div class="cat-h" style="margin-top:0">Where the score can still grow (points available)</div>' + upside_rows)

    c3, c4 = st.columns(2, gap="medium")
    kind = {"green": ("ok", "Green flags"), "amber": ("warn", "Watch-outs"), "red": ("no", "Red flags")}
    with c3:
        body = ""
        for t, (k, title) in kind.items():
            items = [f["text"] for f in screening["flags"] if f["type"] == t]
            if items:
                body += f'<div class="cat-h">{title}</div>' + "".join(ui.row_item(x, k) for x in items)
        ui.render(ui.card_open("Flags", "🚩", "Rule-based checks on the resume") + (body or '<div class="muted">No flags raised.</div>') + ui.CARD_CLOSE)
    with c4:
        n = screening["narrative"]
        src = "AI-written note" if screening["narrative_source"] == "ai" else "Rule-based note"
        ui.render(
            ui.card_open("Recruiter note", "📝", src) + f'<p style="margin:0 0 8px">{ui.esc(n["summary"])}</p>'
            + ('<div class="cat-h">Strengths</div>' + "".join(ui.row_item(x, "ok") for x in n["strengths"]) if n["strengths"] else "")
            + ('<div class="cat-h">Concerns</div>' + "".join(ui.row_item(x, "warn") for x in n["concerns"]) if n["concerns"] else "")
            + ui.CARD_CLOSE
        )
    if screening["narrative"]["interview_questions"]:
        qs = "".join(f'<div class="step"><span>{ui.esc(q)}</span></div>' for q in screening["narrative"]["interview_questions"])
        ui.render(ui.card_open("Suggested interview questions", "🎤") + f'<div class="steps">{qs}</div>' + ui.CARD_CLOSE)

    rows = [[ui.esc(r["job"]["title"] + " · " + r["job"]["company"]), f'<span class="num">{r["score"]}%</span>',
             ui.chips(r["missing"][:3], "miss") or '<span class="muted">-</span>'] for r in ranked[:3]]
    ui.render(ui.card_open("Role alignment (top 3)", "🧭", "Feeds 35% of the screening score") + ui.table(["Role", "Match", "Missing skills"], rows) + ui.CARD_CLOSE)


# --------------------------------------------------------------------------- tab 4
def tab_recommendation(res, ranked, cand) -> None:
    rec = res["final_recommendation"]
    n = rec["narrative"]
    src = "AI-written plan" if rec["narrative_source"] == "ai" else "Rule-based plan"
    steps = "".join(f'<div class="step"><span>{ui.esc(s)}</span></div>' for s in n["next_steps"])
    path = f'<p class="muted" style="margin:8px 0 0">{ui.esc(n["career_path"])}</p>' if n.get("career_path") else ""
    ui.render(ui.card_open("Recommendation", "💡", src) + f'<div class="verdict-t" style="font-size:1.2rem;margin-bottom:6px">{ui.esc(n["headline"])}</div>'
              f'<div class="steps">{steps}</div>{path}' + ui.CARD_CLOSE)

    ready = [r for r in ranked if r["score"] >= 60][:4]
    reach = [r for r in ranked if 30 <= r["score"] < 60][:4]

    def role_list(items, empty):
        if not items:
            return f'<div class="muted">{empty}</div>'
        return "".join(
            f'<div class="row-item"><span class="dot ok">{r["score"]}</span><span><b>{ui.esc(r["job"]["title"])}</b> · {ui.esc(r["job"]["company"])}'
            + (f'<br><span class="muted small">Closest gap: {ui.esc(r["missing"][0])}</span>' if r["missing"] else "") + "</span></div>"
            for r in items)

    a, b = st.columns(2, gap="medium")
    with a:
        ui.render(ui.card_open("Apply now", "✅", "Matches of 60% or more") + role_list(ready, "No role reaches 60% yet - follow the roadmap below.") + ui.CARD_CLOSE)
    with b:
        ui.render(ui.card_open("Within reach", "🎯", "30-59%: close the gaps first") + role_list(reach, "No stretch roles found.") + ui.CARD_CLOSE)

    pr = rec["priorities"][:8]
    if pr:
        top = max(p["impact"] for p in pr) or 1
        rows = [[f"<b>{ui.esc(p['skill'])}</b>",
                 f'<div class="track" style="width:120px;display:inline-block;vertical-align:middle"><div class="fill" style="width:{max(4, p["impact"] / top * 100):.0f}%;background:#4F46E5"></div></div> <span class="num">+{p["impact"]:g}</span>',
                 f'<span class="num">{p["unlocked"]}</span>', f'<span class="num">{p["demand"]}</span>',
                 f'<span class="num">{ui.money(p["avg_salary"])}</span>'] for p in pr]
        ui.render(ui.card_open("Skill priorities", "🧠", "Impact = points added to your top-5 average match if you learn the skill")
                  + ui.table(["Skill", "Impact", "Roles unlocked (60%+)", "Listings requiring it", "Avg listed salary"], rows) + ui.CARD_CLOSE)

    if rec["roadmap"]:
        parts = [f'<div class="road-step"><div class="k">Today</div><div class="s">{rec["roadmap"][0]["avg_before"]:g}%</div><div class="d">top-5 average</div></div>']
        for i, s in enumerate(rec["roadmap"], 1):
            parts.append('<div class="road-arrow">→</div>')
            parts.append(f'<div class="road-step"><div class="k">Step {i}</div><div class="s">+ {ui.esc(s["skill"])}</div>'
                         f'<div class="g">{s["avg_after"]:g}% (+{s["avg_after"] - s["avg_before"]:.1f})</div></div>')
        ui.render(ui.card_open("Learning roadmap", "🗺️", "Greedy plan: each step adds the skill that lifts your matches the most")
                  + f'<div class="road">{"".join(parts)}</div>' + ui.CARD_CLOSE)

    if rec["priorities"]:
        with st.container(border=True):
            ui.render('<div class="card-h"><span class="ic">🧪</span>What-if simulator</div>'
                      '<div class="card-sub">Pick skills you could learn and see how every score would change.</div>')
            options = [p["skill"] for p in rec["priorities"]]
            key_of = {p["skill"]: p["key"] for p in rec["priorities"]}
            default = [s["skill"] for s in rec["roadmap"][:2] if s["skill"] in options]
            chosen = st.multiselect("Skills to add", options, default=default, key="wi_skills")
            after = scoring.rank_jobs([r["job"] for r in ranked], scoring.with_skills(cand, [key_of[c] for c in chosen]))
            before_est, after_est = scoring.salary_estimate(ranked), scoring.salary_estimate(after)
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Best match", f"{after[0]['score']}%", f"{after[0]['score'] - ranked[0]['score']:+d}")
            m2.metric("Top-5 average", f"{scoring.top_avg(after):g}%", f"{scoring.top_avg(after) - scoring.top_avg(ranked):+.1f}")
            sb, sa = sum(1 for r in ranked if r["score"] >= 60), sum(1 for r in after if r["score"] >= 60)
            m3.metric("Strong matches", sa, f"{sa - sb:+d}")
            if before_est and after_est:
                m4.metric("Salary estimate", ui.money(after_est["mid"]), f"{(after_est['mid'] - before_est['mid']) / 1000:+.0f}k",
                          help="Average listed pay of your five best matches. It can fall if lower-paid roles move into your top five.")
            else:
                m4.metric("Salary estimate", "-")

    mk = rec["market"]
    demand = "".join(ui.chips([f"{d['skill']} ({d['count']})"], "ok" if d["have"] else "miss") for d in mk["top_demand"])
    c1, c2 = st.columns([1, 1.6], gap="medium")
    with c1:
        ui.render(ui.card_open("Market coverage", "🌐", "Skills demanded by your top 8 roles") + f'<div style="text-align:center">{ui.ring(mk["coverage"], 130, 12, caption="covered")}</div>' + ui.CARD_CLOSE)
    with c2:
        ui.render(ui.card_open("Most requested skills", "📌", "Green = you have it · red = missing · (number of roles)") + demand + ui.CARD_CLOSE)

    if rec["resume_fixes"]:
        fixes = "".join(ui.row_item(f["tip"], "info", weight=f"+{f['weight']} ATS pts") for f in rec["resume_fixes"])
        ui.render(ui.card_open("Resume fixes", "🛠️", "Failed checks, biggest payoff first") + fixes + ui.CARD_CLOSE)

    d1, d2, _ = st.columns([1, 1, 2])
    d1.download_button("⬇️  Report (Markdown)", build_markdown_report(res), "candidate_report.md", "text/markdown", use_container_width=True)
    safe = {k: v for k, v in res.items() if k != "extracted_data"}
    safe["extracted_data"] = {"profile": res["extracted_data"]["profile"], "extraction_mode": res["extracted_data"]["extraction_mode"]}
    d2.download_button("⬇️  Data (JSON)", json.dumps(safe, indent=2, default=str), "candidate_data.json", "application/json", use_container_width=True)


# --------------------------------------------------------------------------- results page
def page_results(state) -> None:
    res = state["result"]
    profile = res["extracted_data"]["profile"]
    analysis, matches = res["analysis_results"], res["job_matches"]
    screening, ranked = res["screening_results"], res["job_matches"]["matched_jobs"]
    cand = scoring.make_candidate(profile, analysis, res["extracted_data"]["raw_text"])

    top_l, top_r = st.columns([5, 1.2])
    with top_l:
        ui.render('<div class="sec-t" style="margin-top:4px">Candidate report</div>')
    with top_r:
        st.button("↻  New analysis", on_click=reset_analysis, key="top_reset", use_container_width=True)

    results_header(profile, analysis, matches, screening)
    for w in res.get("warnings", []):
        ui.render(ui.note(w, "warn", "⚠️"))

    t1, t2, t3, t4 = st.tabs(["📊 Analysis", "💼 Job Matches", "🎯 Screening", "💡 Recommendation"])
    with t1:
        tab_analysis(profile, analysis)
    with t2:
        tab_matches(matches, ranked, cand)
    with t3:
        tab_screening(screening, ranked)
    with t4:
        tab_recommendation(res, ranked, cand)


# --------------------------------------------------------------------------- about
def page_about() -> None:
    ui.render(ui.hero("About AI Recruiter Agency", "Calculated scores you can explain, plus AI-written commentary.",
                      ["Streamlit", "Gemini / Groq", "SQLite job database"]))
    agents = [("📄", "Extractor", "Reads the PDF and structures it with AI (rule-based fallback)."),
              ("🔍", "Analyzer", "Calculates experience, skills, education, impact and ATS metrics."),
              ("💼", "Matcher", "Scores every job with a weighted skills / experience / level / title formula."),
              ("🎯", "Screener", "Builds a transparent 100-point screening score and flags."),
              ("💡", "Recommender", "Ranks skills by impact, plans a roadmap and writes next steps.")]
    body = "".join(f'<div class="row-item"><span class="kpi-ic" style="background:#EEF2FF;width:38px;height:38px">{i}</span>'
                   f'<span><b>{t}</b><br><span class="muted small">{d}</span></span></div>' for i, t, d in agents)
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        ui.render(ui.card_open("The five agents", "🤖") + body + ui.CARD_CLOSE)
    with c2:
        ui.render(ui.card_open("Good to know", "ℹ️")
                  + ui.row_item("Every number is calculated with fixed rules, so the same resume always gets the same scores.", "ok")
                  + ui.row_item("AI is used to read the resume and to write the notes. If it is unavailable the app still works.", "info")
                  + ui.row_item("Your PDF is not saved. The extracted text is sent to the AI provider you configured.", "info")
                  + ui.row_item("Salaries and jobs come from sample listings in the database, not live postings.", "warn")
                  + ui.row_item("Scores support a decision; they are not a hiring decision.", "warn") + ui.CARD_CLOSE)


def main() -> None:
    page = sidebar()
    if page == "About":
        page_about()
    elif "analysis" in st.session_state:
        page_results(st.session_state["analysis"])
    else:
        page_upload()


if __name__ == "__main__":
    main()
