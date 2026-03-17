"""
analytics/chatbot.py
Groq-powered chatbot grounded in live surveillance data.
Uses Llama 3.3 70B at ~800 tok/s — instant responses on a live dashboard.
"""

import os
from groq import Groq
from datetime import datetime, timezone

client: Groq | None = None


def _get_client() -> Groq | None:
    global client
    if client is None:
        key = os.getenv("GROQ_API_KEY", "")
        if key:
            client = Groq(api_key=key)
    return client


SYSTEM_PROMPT = """You are DiseaseWatch AI — an expert epidemiologist assistant
embedded in a real-time disease surveillance dashboard.

You have access to live data injected into each user message as context.
Your job:
1. Answer questions about disease trends, outbreak risk, and public health clearly.
2. Explain epidemiological concepts in plain English (R_t, CFR, herd immunity, etc.).
3. When you cite numbers, reference the live data provided — never make up figures.
4. Keep answers concise (2–4 sentences for simple questions, up to 8 for complex ones).
5. If data is missing or uncertain, say so honestly.
6. You are NOT a medical advisor — always recommend professional health guidance for personal health queries.

Tone: calm, factual, accessible. Like a knowledgeable colleague, not a textbook.
"""


def build_context_snippet(
    top_countries: list[dict],
    global_score: dict,
    alerts: list[dict],
    selected_disease: str = "COVID-19",
) -> str:
    """Build a compact data context to inject into the user message."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    top5 = top_countries[:5]
    country_lines = "\n".join(
        f"  - {c['country']}: {c['cases_today']:,} new cases today, "
        f"CFR {c['cfr']:.2f}%"
        for c in top5
        if c.get("cases_today", 0) > 0
    ) or "  No new case data available."

    alert_lines = "\n".join(
        f"  - [{a['source']}] {a['title'][:80]}"
        for a in alerts[:3]
    ) or "  No recent alerts."

    return (
        f"[LIVE DATA — {now}]\n"
        f"Disease focus: {selected_disease}\n"
        f"Global threat score: {global_score.get('score', 'N/A')}/100 "
        f"({global_score.get('level', 'Unknown')})\n"
        f"Top 5 countries by new cases today:\n{country_lines}\n"
        f"Recent outbreak alerts:\n{alert_lines}\n"
    )


def chat(
    messages: list[dict],
    context: str,
    model: str = "llama-3.3-70b-versatile",
) -> str:
    """
    Send a conversation to Groq and return the assistant reply.

    messages: list of {role, content} dicts (conversation history)
    context: live data snippet injected into the latest user message
    """
    groq = _get_client()
    if groq is None:
        return (
            "Groq API key not configured. Add GROQ_API_KEY to your .env file. "
            "Get a free key at console.groq.com — no credit card needed."
        )

    # Inject live data context into the last user message
    augmented_messages = list(messages)
    if augmented_messages and augmented_messages[-1]["role"] == "user":
        last = augmented_messages[-1]["content"]
        augmented_messages[-1] = {
            "role": "user",
            "content": f"{context}\n\nUser question: {last}",
        }

    try:
        response = groq.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + augmented_messages,
            temperature=0.4,
            max_tokens=512,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error contacting Groq API: {e}"


def generate_disease_card_sentence(
    disease: str,
    country: str,
    cases_today: int,
    velocity: float,
    rt: float | None,
    climate_factor: str = "",
) -> str:
    """
    Generate the one-sentence 'aha' narrative for a disease card.
    Called once on dashboard load per top disease.
    ~0.3s on Groq LPU.
    """
    groq = _get_client()
    if groq is None:
        return f"{disease} is currently active in {country} with {cases_today:,} new cases today."

    direction = "rising" if velocity > 5 else "falling" if velocity < -5 else "stable"
    rt_str = f"R_t = {rt:.2f}" if rt else "R_t unknown"
    climate_str = f" {climate_factor}" if climate_factor else ""

    prompt = (
        f"Write ONE sentence (max 25 words) describing the current {disease} situation in {country}. "
        f"Facts: {cases_today:,} new cases today, trend is {direction} ({velocity:+.1f}%), "
        f"{rt_str}.{climate_str} "
        f"Be specific, factual, and use plain language. No hedging phrases."
    )

    try:
        response = groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=60,
        )
        return response.choices[0].message.content.strip().strip('"')
    except Exception:
        return f"{disease} in {country}: {cases_today:,} new cases today, trend {direction}."
