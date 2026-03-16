"""
app.py — DiseaseWatch Dashboard
Streamlit entry point. All UI features in one file.
Run: streamlit run app.py
"""

import os
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="DiseaseWatch",
    page_icon=":globe_with_meridians:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── lazy import heavy modules ──────────────────────────────────
from analytics.pipeline import run_pipeline
from analytics.epi_engine import estimate_rt, calc_outbreak_score, calc_confidence
from analytics.chatbot import chat, build_context_snippet, generate_disease_card_sentence
from analytics.store import query_diseases_map, query_top_countries, query_available_diseases


# ══════════════════════════════════════════════════════════════
#  DATA LOADING — cached 15 min
# ══════════════════════════════════════════════════════════════
@st.cache_data(ttl=900, show_spinner=False)
def load_data() -> dict:
    return run_pipeline()


# ══════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════
def render_sidebar(data: dict):
    with st.sidebar:
        st.markdown("## DiseaseWatch")
        st.caption("Real-time global disease surveillance")

        threat = data.get("global_threat", {})
        score = threat.get("score", 0)
        level = threat.get("level", "Unknown")
        plain = threat.get("plain_english", "")

        # ── Threat Thermometer ─────────────────────────────
        st.markdown("### Global threat level")
        color_map = {"Critical": "#E24B4A", "Elevated": "#EF9F27",
                     "Moderate": "#378ADD", "Low": "#1D9E75", "Unknown": "#888780"}
        bar_color = color_map.get(level, "#888780")

        thermo_html = f"""
        <div style="display:flex;align-items:center;gap:12px;margin:4px 0 8px">
          <div style="position:relative;width:22px;height:140px;
               background:var(--background-color,#f0f0f0);
               border:1px solid #ccc;border-radius:11px;overflow:hidden">
            <div style="position:absolute;bottom:0;width:100%;
                 height:{score}%;background:{bar_color};
                 border-radius:11px;transition:height 0.8s ease">
            </div>
          </div>
          <div>
            <div style="font-size:28px;font-weight:600;
                 color:{bar_color};line-height:1">{score}</div>
            <div style="font-size:13px;font-weight:500;
                 color:{bar_color}">{level}</div>
            <div style="font-size:11px;color:#888;margin-top:4px">/100</div>
          </div>
        </div>
        <div style="font-size:12px;color:#666;line-height:1.5;margin-bottom:12px">
          {plain}
        </div>
        """
        st.html(thermo_html)

        # ── Confidence badge ───────────────────────────────
        conf = data.get("confidence", {})
        conf_score = conf.get("score", 0)
        conf_color = {"success": "green", "warning": "orange", "danger": "red"}.get(
            conf.get("color", "gray"), "gray"
        )
        st.markdown(
            f"**Data confidence:** :{conf_color}[{conf_score:.0f}%]  \n"
            f"<span style='font-size:11px;color:#888'>{conf.get('plain_english','')}</span>",
            unsafe_allow_html=True,
        )

        st.divider()

        # ── What changed today ─────────────────────────────
        st.markdown("### What changed today")
        changes = data.get("what_changed", [])
        if changes:
            for c in changes[:5]:
                direction = c.get("direction", "stable")
                color = "red" if direction == "up" else "green" if direction == "down" else "gray"
                vel = c.get("velocity", 0)
                sign = "+" if vel > 0 else ""
                arrow = "↑" if direction == "up" else "↓" if direction == "down" else "→"
                st.markdown(
                    f":{color}[{arrow}] **{c['disease']}** · {c['country']}  \n"
                    f"<span style='font-size:12px;color:#888'>{sign}{vel:.1f}% · {c['cases_today']:,} new cases</span>",
                    unsafe_allow_html=True,
                )
        else:
            st.caption("Loading change data...")

        st.divider()

        # ── ProMED live alerts ─────────────────────────────
        st.markdown("### Live outbreak alerts")
        alerts = data.get("promed_alerts", [])
        if alerts:
            for a in alerts[:3]:
                st.markdown(
                    f"**{a.get('title','')[:60]}**  \n"
                    f"<span style='font-size:11px;color:#888'>{a.get('source','')} · "
                    f"{a.get('published','')[:10]}</span>",
                    unsafe_allow_html=True,
                )
                st.markdown("---")
        else:
            st.caption("Fetching alerts...")

        fetched = data.get("fetched_at", "")[:16].replace("T", " ")
        st.caption(f"Last refreshed: {fetched} UTC")


# ══════════════════════════════════════════════════════════════
#  DISEASE CARD
# ══════════════════════════════════════════════════════════════
def render_disease_card(
    disease: str,
    top_row: dict,
    score_row: dict,
    aha_sentence: str,
):
    """
    Disease card with: aha sentence, risk score, plain-language explanation,
    CFR, R_t, cases today — all with progressive disclosure.
    """
    score = score_row.get("score", 0)
    level = score_row.get("level", "Unknown")
    rt = score_row.get("rt", 0)
    velocity = score_row.get("velocity", 0)
    cfr = top_row.get("cfr", 0)
    cases_today = top_row.get("cases_today", 0)
    country = score_row.get("country", "")

    color_map = {"Critical": "#E24B4A", "Elevated": "#EF9F27",
                 "Moderate": "#378ADD", "Low": "#1D9E75"}
    col = color_map.get(level, "#888")

    with st.container(border=True):
        # Header row
        h_col1, h_col2 = st.columns([3, 1])
        with h_col1:
            st.markdown(f"### {disease}")
            st.markdown(
                f"<span style='font-size:13px;font-style:italic;color:#555'>{aha_sentence}</span>",
                unsafe_allow_html=True,
            )
        with h_col2:
            st.markdown(
                f"<div style='text-align:center;padding:8px;border-radius:8px;"
                f"background:{col}18;border:1px solid {col}44'>"
                f"<div style='font-size:22px;font-weight:600;color:{col}'>{score}</div>"
                f"<div style='font-size:11px;color:{col}'>{level}</div>"
                f"<div style='font-size:10px;color:#888'>risk score</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

        # Metrics row
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("New cases today", f"{cases_today:,}",
                      delta=f"{velocity:+.1f}%")
        with m2:
            rt_display = f"{rt:.2f}" if rt else "N/A"
            rt_delta = "Growing" if (rt or 0) > 1 else "Declining"
            st.metric("R_t", rt_display, delta=rt_delta,
                      delta_color="inverse" if (rt or 0) > 1 else "normal")
        with m3:
            st.metric("CFR", f"{cfr:.2f}%")
        with m4:
            st.metric("Top country", country)

        # Simple trust-building explanation — no formulas
        rt_val = rt or 1.0
        if rt_val > 1.2:
            spread_msg = f"spreading — each case leads to more than 1 new case (R_t {rt_val:.2f})"
        elif rt_val > 1.0:
            spread_msg = f"slowly spreading (R_t {rt_val:.2f})"
        elif rt_val > 0:
            spread_msg = f"declining — each case leads to less than 1 new case (R_t {rt_val:.2f})"
        else:
            spread_msg = "transmission rate not available"

        if velocity > 10:
            trend_msg = f"Cases rose {velocity:.0f}% compared to the previous period."
        elif velocity < -10:
            trend_msg = f"Cases fell {abs(velocity):.0f}% compared to the previous period."
        else:
            trend_msg = "Case counts are relatively stable."

        cfr_msg = f"About {cfr:.2f}% of confirmed cases have been fatal." if cfr > 0 else ""

        st.info(
            f"**{disease} is currently {spread_msg}.** "
            f"{trend_msg} {cfr_msg}"
        )

        with st.expander("Why should I trust this score?"):
            st.markdown(
                f"**Risk score {score}/100** combines 4 signals: "
                f"how fast cases are changing ({velocity:+.0f}%), "
                f"how many people each case infects (R_t), "
                f"climate conditions in affected regions, "
                f"and how up-to-date the reporting is. "
                f"A score above 70 means multiple warning signs are active at once."
            )
            conf = calc_confidence()
            st.markdown(
                f"**Data confidence: {conf['score']:.0f}%** — "
                f"{conf['plain_english']}"
            )


# ══════════════════════════════════════════════════════════════
#  WORLD MAP TAB
# ══════════════════════════════════════════════════════════════
def render_map_tab(data: dict):
    st.subheader("Global disease spread")

    # ── Disease + pathogen selector ────────────────────────────
    available = query_available_diseases()

    # Build disease list: DB results first (these have data), then add any extras
    db_diseases_info = {r["disease"]: r for r in available}

    # Full catalogue with colour scales for the map
    DISEASE_COLORS = {
        "COVID-19": "YlOrRd", "Influenza": "Blues", "Malaria": "Greens",
        "Cholera": "Purples", "Tuberculosis": "Oranges", "Dengue": "YlOrRd",
        "HIV/AIDS": "Reds", "Hepatitis B": "YlGn", "Hepatitis C": "BuPu",
        "Mpox": "RdPu", "Zika": "PuBu", "Ebola": "Reds",
        "Yellow Fever": "YlOrBr", "Rabies": "OrRd", "Measles": "PuRd",
        "Polio": "BuGn", "Typhoid": "GnBu", "Meningitis": "PuBuGn",
        "Leprosy": "YlOrBr", "Plague": "Greys",
        "Leishmaniasis": "YlGnBu", "Visceral Leishmaniasis": "RdYlBu",
        "Chagas Disease": "Spectral", "Schistosomiasis": "BrBG",
        "Onchocerciasis": "PRGn", "Lymphatic Filariasis": "PiYG",
        "Trachoma": "RdGy", "Soil-transmitted Helminths": "PuOr",
        "Leptospirosis": "RdBu",
    }

    # All diseases that have data in DB, sorted: live data first
    live = [r["disease"] for r in available if r["total_cases"] > 0]
    all_selectable = live if live else list(DISEASE_COLORS.keys())
    # Ensure COVID-19 is first
    if "COVID-19" in all_selectable:
        all_selectable = ["COVID-19"] + [d for d in all_selectable if d != "COVID-19"]

    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        selected_disease = st.selectbox(
            "Disease",
            options=all_selectable,
            index=0,
            help=f"{len(all_selectable)} diseases available from WHO GHO + disease.sh APIs",
        )

    # Get species + type from DB record or fallback
    db_row = db_diseases_info.get(selected_disease, {})
    species = db_row.get("species") or "See WHO GHO"
    dtype = db_row.get("disease_type", "").title() or "—"
    with col2:
        st.markdown(
            f"<div style='padding:8px 0'>"
            f"<span style='font-size:12px;color:#888'>Pathogen / species</span><br>"
            f"<span style='font-size:14px;font-weight:500'>{species}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            f"<div style='padding:8px 0'>"
            f"<span style='font-size:12px;color:#888'>Type</span><br>"
            f"<span style='font-size:14px;font-weight:500'>{dtype}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # ── Data availability notice ───────────────────────────────
    if selected_disease not in db_diseases_info:
        st.info(
            f"**{selected_disease}** data loads from WHO GHO on first refresh. "
            f"If the map is empty, wait 30s and rerun."
        )

    # ── Fetch map data for selected disease ────────────────────
    countries = query_diseases_map(selected_disease)

    # Fallback: use pipeline data for COVID
    if not countries and selected_disease == "COVID-19":
        countries = data.get("covid_map", [])

    if not countries:
        st.warning(f"No country-level data available for {selected_disease} yet. "
                   f"WHO historical data loads on next refresh cycle.")
        # Show empty world map as placeholder
        fig = px.choropleth(title=f"{selected_disease} — awaiting data")
        fig.update_layout(margin=dict(l=0, r=0, t=40, b=0),
                          geo=dict(showframe=False, showcoastlines=True))
        st.plotly_chart(fig, use_container_width=True)
        return

    df = pd.DataFrame(countries)
    df = df[df["cases_total"] > 0]

    color_scale = DISEASE_COLORS.get(selected_disease, "YlOrRd")

    # Choose colour metric — for WHO annual data use "value" if cases_total=0
    color_col = "cases_total"
    color_label = "Total cases"

    fig = px.choropleth(
        df,
        locations="country",
        locationmode="country names",
        color=color_col,
        hover_name="country",
        hover_data={
            "cases_today": True,
            "cfr": ":.3f",
            "species": True,
        },
        color_continuous_scale=color_scale,
        labels={
            "cases_total": color_label,
            "cases_today": "New today",
            "cfr": "CFR %",
            "species": "Pathogen",
        },
        title=f"{selected_disease} — {species}",
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=50, b=0),
        coloraxis_colorbar=dict(title=color_label),
        geo=dict(showframe=False, showcoastlines=True, bgcolor="rgba(0,0,0,0)"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Stats summary row ──────────────────────────────────────
    total_cases = int(df["cases_total"].sum())
    total_deaths = int(df["deaths_total"].sum()) if "deaths_total" in df else 0
    affected_countries = len(df)
    avg_cfr = round(df["cfr"].mean(), 3) if "cfr" in df else 0

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Total cases", f"{total_cases:,}")
    # Deaths: disease.sh has them, WHO GHO incidence indicators don't
    deaths_label = f"{total_deaths:,}" if total_deaths > 0 else "See WHO mortality data"
    s2.metric("Total deaths", deaths_label, help="WHO incidence indicators don't include death counts. Switch to a mortality indicator or see WHO GHO directly.")
    s3.metric("Countries affected", affected_countries)
    s4.metric("Avg CFR", f"{avg_cfr:.2f}%", help="Case Fatality Rate — only available where both cases and deaths are reported")

    # ── Top 10 table ───────────────────────────────────────────
    st.subheader(f"Top countries — {selected_disease}")
    show_cols = [c for c in
        ["country", "cases_total", "deaths_total", "cases_today", "cfr", "species"]
        if c in df.columns]
    top_df = df[show_cols].head(10).copy()
    top_df.columns = [c.replace("_", " ").title() for c in show_cols]
    st.dataframe(top_df, use_container_width=True, hide_index=True)

    # ── Disease coverage note ──────────────────────────────────
    st.caption(
        f"Data sources: disease.sh (COVID-19 real-time) · "
        f"WHO GHO API (28 disease indicators, historical) · "
        f"CMU Delphi (Influenza US) · ProMED RSS (outbreak signals). "
        f"Pathogen: {species} · Disease type: {dtype}."
    )


# ══════════════════════════════════════════════════════════════
#  DISEASE CARDS TAB
# ══════════════════════════════════════════════════════════════
def render_disease_tab(data: dict):
    st.subheader("Disease intelligence cards")
    st.caption(
        "Each card shows live stats, a plain-language explanation, "
        "and the math behind every number."
    )

    # Show data availability banner
    available = query_available_diseases()
    live_diseases = [r["disease"] for r in available]
    if live_diseases:
        st.success(
            f"Live data loaded for: **{', '.join(live_diseases)}** · "
            f"WHO historical data for Malaria, Cholera, TB · "
            f"Refresh in 15 min for latest."
        )

    top_countries = data.get("top_countries", [])
    scores = data.get("scores", [])

    # Build lookup by country for scores
    score_map = {s["country"]: s for s in scores}

    diseases = ["COVID-19", "Influenza", "Dengue", "Malaria", "Cholera"]

    for i, disease in enumerate(diseases):
        # Get best available row for this disease
        top_row = top_countries[i] if i < len(top_countries) else {}
        score_row = scores[i] if i < len(scores) else {
            "score": 0, "level": "Unknown", "rt": 0,
            "velocity": 0, "country": "Global"
        }

        country = score_row.get("country", "Global")
        cases_today = top_row.get("cases_today", 0) or 0
        velocity = score_row.get("velocity", 0) or 0
        rt = score_row.get("rt") or None

        # Generate Groq aha sentence (cached via session state)
        cache_key = f"aha_{disease}"
        if cache_key not in st.session_state:
            st.session_state[cache_key] = generate_disease_card_sentence(
                disease=disease,
                country=country,
                cases_today=cases_today,
                velocity=velocity,
                rt=rt,
            )
        aha = st.session_state[cache_key]

        render_disease_card(disease, top_row, score_row, aha)
        if i < len(diseases) - 1:
            st.markdown("")


# ══════════════════════════════════════════════════════════════
#  MATH EXPLAINER TAB
# ══════════════════════════════════════════════════════════════
def render_math_tab(data: dict):
    st.subheader("How we calculate what you see")
    st.caption("No formulas. Just plain explanations of how every number on this dashboard is made.")

    # ── What is the risk score ─────────────────────────────────
    with st.container(border=True):
        st.markdown("#### The risk score (0–100)")
        st.markdown(
            "Every country gets a risk score that combines four things we know predict outbreaks:"
        )
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Case speed", "40%", help="How fast are new cases appearing vs last week?")
        c2.metric("Transmission rate", "30%", help="Is each sick person infecting more or less than 1 other person?")
        c3.metric("Climate conditions", "20%", help="High rainfall + heat = more mosquito-borne disease risk")
        c4.metric("Data freshness", "10%", help="How recently did countries report? Stale data lowers confidence")
        st.info(
            "A score above 70 means at least 3 of these 4 signals are all pointing toward risk "
            "at the same time. Below 30 means the situation looks stable."
        )

    st.divider()

    # ── What is R_t ────────────────────────────────────────────
    with st.container(border=True):
        st.markdown("#### The transmission number (R_t)")
        st.markdown("R_t answers one question: **how many people does one sick person infect right now?**")
        rc1, rc2, rc3 = st.columns(3)
        rc1.metric("R_t below 1.0", "Shrinking", delta="Good", delta_color="normal")
        rc2.metric("R_t = 1.0", "Stable", delta="Watch", delta_color="off")
        rc3.metric("R_t above 1.0", "Growing", delta="Concern", delta_color="inverse")
        st.info(
            "We calculate R_t by comparing new cases this week to new cases last week. "
            "If 1,000 people got sick this week vs 800 last week, R_t = 1,000 ÷ 800 = 1.25. "
            "The range shown (e.g. 1.18–1.51) tells you how certain we are — wider range means noisier data."
        )

    st.divider()

    # ── What is CFR ────────────────────────────────────────────
    with st.container(border=True):
        st.markdown("#### Case fatality rate (CFR)")
        st.markdown(
            "CFR = what percentage of confirmed cases have been fatal. "
            "**Important:** this is not the same as the true death risk — "
            "it only counts confirmed cases, which misses mild cases that were never tested."
        )
        st.info(
            "Example: if 100 people tested positive and 2 died, CFR = 2%. "
            "The real death risk is usually lower because many people never got tested. "
            "That's why COVID's CFR looked high early on — most mild cases weren't counted."
        )

    st.divider()

    # ── Confidence ─────────────────────────────────────────────
    with st.container(border=True):
        st.markdown("#### Data confidence")
        conf = data.get("confidence", calc_confidence())
        st.metric("Current confidence", f"{conf['score']:.0f}%")
        st.info(conf["plain_english"])
        st.markdown(
            "Three things reduce our confidence: "
            "districts that haven't reported yet (we estimate their numbers from neighbours), "
            "when our model's past predictions were off, "
            "and when WHO data and national data disagree with each other."
        )

    st.divider()

    # ── Why deaths show 0 ──────────────────────────────────────
    with st.container(border=True):
        st.markdown("#### Why does 'Total deaths' sometimes show 0?")
        st.info(
            "WHO GHO publishes incidence data (case counts) and mortality data as separate indicators. "
            "Most diseases in our dropdown currently pull the incidence indicator — "
            "so death counts appear as 0 even though deaths data exists in WHO's system. "
            "COVID-19 is the exception because disease.sh includes deaths in its real-time feed. "
            "We're aware of this and it's on the fix list — it's a data source limitation, not a bug."
        )


# ══════════════════════════════════════════════════════════════
#  CHATBOT TAB
# ══════════════════════════════════════════════════════════════
def render_chatbot_tab(data: dict):
    st.subheader("Ask DiseaseWatch AI")
    st.caption(
        "Powered by Groq + Llama 3.3 70B. Answers are grounded in live surveillance data. "
        "Not a substitute for professional medical advice."
    )

    # ── Check Groq key upfront ─────────────────────────────────
    groq_key = os.getenv("GROQ_API_KEY", "")
    if not groq_key or groq_key == "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":
        st.warning(
            "**Groq API key not set.** The chatbot needs a free key to work.  \n"
            "1. Go to [console.groq.com](https://console.groq.com) — no credit card needed  \n"
            "2. Create an API key  \n"
            "3. Add it to your `.env` file: `GROQ_API_KEY=your_key_here`  \n"
            "4. Restart Streamlit (`Ctrl+C` then `streamlit run app.py`)"
        )
        return

    # Init chat history
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": (
                    "Hi! I'm DiseaseWatch AI. I can answer questions about current "
                    "outbreak trends, explain epidemiological concepts, or walk you "
                    "through how any of these numbers are calculated. What would you like to know?"
                ),
            }
        ]

    # Render history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Suggested questions
    if len(st.session_state.messages) == 1:
        st.markdown("**Try asking:**")
        suggestions = [
            "Why is dengue spreading faster this season?",
            "What does R_t = 1.34 mean in plain English?",
            "Which country has the highest outbreak risk right now?",
            "Explain how CFR differs from IFR",
        ]
        cols = st.columns(2)
        for i, q in enumerate(suggestions):
            if cols[i % 2].button(q, key=f"sugg_{i}"):
                st.session_state.messages.append({"role": "user", "content": q})
                st.rerun()

    # Chat input
    if prompt := st.chat_input("Ask about any disease, country, or concept..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        context = build_context_snippet(
            top_countries=data.get("top_countries", []),
            global_score=data.get("global_threat", {}),
            alerts=data.get("promed_alerts", []),
        )

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                reply = chat(
                    messages=st.session_state.messages,
                    context=context,
                )
            st.markdown(reply)

        st.session_state.messages.append({"role": "assistant", "content": reply})


# ══════════════════════════════════════════════════════════════
#  ALERTS TAB
# ══════════════════════════════════════════════════════════════
def render_alerts_tab(data: dict):
    st.subheader("Live outbreak alerts")
    alerts = data.get("promed_alerts", [])
    changes = data.get("what_changed", [])

    st.markdown("#### What changed in the last 24 hours")
    if changes:
        for c in changes:
            direction = c.get("direction", "stable")
            color = "red" if direction == "up" else "green" if direction == "down" else "gray"
            arrow = "up" if direction == "up" else "down" if direction == "down" else "right"
            vel = c.get("velocity", 0)
            st.markdown(
                f":{color}[**{c['disease']}** in **{c['country']}** — "
                f"{'rising' if direction=='up' else 'falling' if direction=='down' else 'stable'} "
                f"{abs(vel):.1f}% · {c['cases_today']:,} new cases today]  \n"
                f"<span style='font-size:12px'>{c['plain_english']}</span>",
                unsafe_allow_html=True,
            )
            st.markdown("")
    else:
        st.info("No significant changes detected in the current data.")

    st.divider()
    st.markdown("#### ProMED outbreak alerts")
    if alerts:
        for a in alerts:
            with st.expander(a.get("title", "Alert")[:80]):
                st.markdown(a.get("summary", ""))
                st.markdown(
                    f"**Source:** {a.get('source','')}  \n"
                    f"**Published:** {a.get('published','')[:10]}  \n"
                    f"[Read full report]({a.get('link','')})"
                )
    else:
        st.info("No ProMED alerts loaded yet.")


# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════
def main():
    with st.spinner("Fetching live data from WHO, disease.sh, ProMED..."):
        data = load_data()

    render_sidebar(data)

    st.title("DiseaseWatch")
    st.caption("Real-time global disease surveillance · All math shown · Powered by public health APIs")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "World map",
        "Disease cards",
        "Alerts",
        "How it works",
        "AI chat",
    ])

    with tab1:
        render_map_tab(data)
    with tab2:
        render_disease_tab(data)
    with tab3:
        render_alerts_tab(data)
    with tab4:
        render_math_tab(data)
    with tab5:
        render_chatbot_tab(data)


if __name__ == "__main__":
    main()