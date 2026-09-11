"""Turn natural-language housing questions into UserCriteria.

Works offline with rule-based parsing (mock). Optionally uses Ollama JSON extraction.
"""

from __future__ import annotations

import json
import re

from lotline.llm import ollama_generate
from lotline.models import UserCriteria
from lotline.tools import DFW_ZIPS

# locality / city phrases → ZIP codes in our frozen snapshot
LOCALITY_ZIPS: dict[str, list[str]] = {
    "downtown": ["75201"],
    "downtown dallas": ["75201"],
    "uptown": ["75204"],
    "highland park": ["75205"],
    "east dallas": ["75206"],
    "bluffview": ["75209"],
    "lakewood": ["75214"],
    "oak lawn": ["75219"],
    "preston hollow": ["75225"],
    "north dallas": ["75230"],
    "far north dallas": ["75248"],
    "addison": ["75001"],
    "plano": ["75024"],
    "frisco": ["75033"],
    "irving": ["75063"],
    "grapevine": ["76051"],
    "fort worth": ["76107"],
    "dallas": [z for z in DFW_ZIPS if z.startswith("75")],
    "dfw": list(DFW_ZIPS),
    "metroplex": list(DFW_ZIPS),
}


def _parse_money(text: str) -> list[float]:
    """Extract dollar amounts like $450k, 450000, 1.2m."""
    amounts: list[float] = []
    for m in re.finditer(
        r"\$?\s*(\d+(?:\.\d+)?)\s*(k|m|million|thousand)?",
        text,
        flags=re.I,
    ):
        n = float(m.group(1))
        suf = (m.group(2) or "").lower()
        if suf in {"k", "thousand"}:
            n *= 1_000
        elif suf in {"m", "million"}:
            n *= 1_000_000
        # ignore bare small numbers that are likely beds/years (e.g. 3, 12, 2025)
        if n >= 50_000 or suf:
            amounts.append(n)
    return amounts


def _parse_beds(text: str) -> tuple[int | None, int | None]:
    t = text.lower()
    # "3 bedroom", "3-bed", "3 beds", "3br"
    m = re.search(r"(\d)\s*(?:-?\s*)?(?:bed(?:room)?s?|br|bhk)\b", t)
    if m:
        b = int(m.group(1))
        return b, b
    m = re.search(r"(\d)\s*to\s*(\d)\s*(?:bed|br)", t)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def _parse_zips(text: str) -> list[str]:
    found = re.findall(r"\b(75\d{3}|76\d{3})\b", text)
    zips = [z for z in found if z in DFW_ZIPS]
    t = text.lower()
    # longer locality names first
    for name in sorted(LOCALITY_ZIPS.keys(), key=len, reverse=True):
        if name in t:
            for z in LOCALITY_ZIPS[name]:
                if z not in zips:
                    zips.append(z)
    return zips


def _parse_sqft(text: str) -> tuple[float | None, float | None]:
    t = text.lower()
    m = re.search(r"(\d{3,5})\s*(?:to|-)\s*(\d{3,5})\s*(?:sq\.?\s*ft|sqft|square feet)", t)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.search(r"(?:over|above|at least|min(?:imum)?)\s*(\d{3,5})\s*(?:sq\.?\s*ft|sqft)", t)
    if m:
        return float(m.group(1)), None
    m = re.search(r"(?:under|below|max(?:imum)?)\s*(\d{3,5})\s*(?:sq\.?\s*ft|sqft)", t)
    if m:
        return None, float(m.group(1))
    return None, None


def parse_question_mock(question: str, default_window_end: str = "2025-08") -> tuple[UserCriteria, str]:
    """Rule-based NL → UserCriteria. Returns (criteria, interpretation note)."""
    t = question.lower()
    price_min, price_max = 150_000.0, 650_000.0
    amounts = _parse_money(question)

    if re.search(r"under|below|less than|max(?:imum)?|up to", t) and amounts:
        price_max = amounts[0]
        price_min = max(80_000.0, price_max * 0.35)
    elif re.search(r"over|above|at least|min(?:imum)?|more than", t) and amounts:
        price_min = amounts[0]
        price_max = max(price_min * 2.2, price_min + 200_000)
    elif len(amounts) >= 2:
        price_min, price_max = sorted(amounts[:2])
    elif len(amounts) == 1:
        # "around 400k"
        price_min = amounts[0] * 0.8
        price_max = amounts[0] * 1.2

    beds_min, beds_max = _parse_beds(question)
    if beds_min is None:
        beds_min, beds_max = 2, 5

    sqft_min, sqft_max = _parse_sqft(question)
    if sqft_min is None:
        sqft_min = 800.0
    if sqft_max is None:
        sqft_max = 4_000.0

    zips = _parse_zips(question)

    # luxury / cheap shortcuts
    if "luxury" in t or "high-end" in t or "high end" in t:
        price_min = max(price_min, 700_000)
        price_max = max(price_max, 1_500_000)
    if "starter" in t or "affordable" in t or "cheap" in t:
        price_max = min(price_max, 350_000)
        price_min = min(price_min, 120_000)

    criteria = UserCriteria(
        price_min=float(price_min),
        price_max=float(price_max),
        beds_min=int(beds_min),
        beds_max=int(beds_max),
        sqft_min=float(sqft_min),
        sqft_max=float(sqft_max),
        zips=zips,
        window_end=default_window_end,
        currency_display="USD",
    )

    where = ", ".join(zips) if zips else "all DFW sample ZIPs"
    note = (
        f"Understood: ${criteria.price_min:,.0f}–${criteria.price_max:,.0f}, "
        f"{criteria.beds_min}–{criteria.beds_max} beds, "
        f"{criteria.sqft_min:.0f}–{criteria.sqft_max:.0f} sqft, area={where}, "
        f"12 months ending {criteria.window_end}."
    )
    return criteria, note


def parse_question_ollama(question: str, default_window_end: str = "2025-08") -> tuple[UserCriteria, str]:
    prompt = {
        "task": "Extract Dallas housing search filters from the user question.",
        "question": question,
        "allowed_zips": DFW_ZIPS,
        "localities": list(LOCALITY_ZIPS.keys()),
        "default_window_end": default_window_end,
        "return_json_keys": [
            "price_min",
            "price_max",
            "beds_min",
            "beds_max",
            "sqft_min",
            "sqft_max",
            "zips",
            "window_end",
            "interpretation",
        ],
    }
    try:
        raw = ollama_generate(
            "You extract structured housing filters. Return JSON only.\n"
            + json.dumps(prompt)
        )
        data = json.loads(raw)
        base, _ = parse_question_mock(question, default_window_end)
        criteria = UserCriteria(
            price_min=float(data.get("price_min", base.price_min)),
            price_max=float(data.get("price_max", base.price_max)),
            beds_min=int(data.get("beds_min", base.beds_min)),
            beds_max=int(data.get("beds_max", base.beds_max)),
            sqft_min=float(data.get("sqft_min", base.sqft_min)),
            sqft_max=float(data.get("sqft_max", base.sqft_max)),
            zips=list(data.get("zips") or base.zips),
            window_end=str(data.get("window_end") or default_window_end),
            currency_display="USD",
        )
        note = str(data.get("interpretation") or "Parsed via Ollama.")
        return criteria, note
    except Exception:
        return parse_question_mock(question, default_window_end)


def parse_question(
    question: str,
    mode: str = "mock",
    default_window_end: str = "2025-08",
) -> tuple[UserCriteria, str]:
    if mode == "ollama":
        return parse_question_ollama(question, default_window_end)
    return parse_question_mock(question, default_window_end)


EXAMPLE_QUESTIONS = [
    "How have 3-bedroom home prices moved in Plano over the last year?",
    "Show 12-month trends for homes under $450k in Dallas",
    "What is the $/sqft trend for 4 bedroom houses in Frisco?",
    "Analyze luxury listings over $800k in Highland Park",
    "Compare affordable starter homes under $300k across DFW",
]
