"""Criteria Agent — normalize user filters; apply Critic revisions."""

from __future__ import annotations

import json

from lotline.llm import ollama_generate
from lotline.models import Critique, CritiqueAction, QueryPlan, UserCriteria
from lotline.tools import criteria_to_plan, shift_month


def _apply_actions(plan: QueryPlan, actions: list[CritiqueAction]) -> QueryPlan:
    data = plan.model_dump()
    notes = list(plan.notes)
    for a in actions:
        if a.action == "widen_price_max":
            data["price_max"] = float(data["price_max"]) * float(a.value or 1.15)
            notes.append(f"Widened price_max → {data['price_max']:.0f} ({a.reason})")
        elif a.action == "widen_price_min":
            data["price_min"] = float(data["price_min"]) * float(a.value or 0.9)
            notes.append(f"Lowered price_min → {data['price_min']:.0f} ({a.reason})")
        elif a.action == "expand_zips":
            # add neighboring ZIPs not already present — simple: keep all DFW if subset
            from lotline.tools import DFW_ZIPS

            current = set(data["zips"])
            for z in DFW_ZIPS:
                if z not in current:
                    current.add(z)
                    if len(current) >= len(plan.zips) + int(a.value or 3):
                        break
            data["zips"] = sorted(current)
            notes.append(f"Expanded ZIP set to {len(data['zips'])} codes ({a.reason})")
        elif a.action == "relax_beds":
            data["beds_min"] = max(1, int(data["beds_min"]) - 1)
            data["beds_max"] = min(5, int(data["beds_max"]) + 1)
            notes.append(f"Relaxed beds to {data['beds_min']}-{data['beds_max']} ({a.reason})")
        elif a.action == "widen_sqft":
            data["sqft_min"] = float(data["sqft_min"]) * 0.9
            data["sqft_max"] = float(data["sqft_max"]) * 1.1
            notes.append("Widened sqft band")
        else:
            notes.append(f"Ignored unknown action {a.action}")
    data["notes"] = notes
    data["revision_round"] = int(plan.revision_round) + 1
    # keep window consistent
    data["window_start"] = shift_month(data["window_end"], -11)
    return QueryPlan(**data)


def run_criteria_mock(
    criteria: UserCriteria,
    critique: Critique | None = None,
    prior: QueryPlan | None = None,
) -> QueryPlan:
    if prior is None:
        plan = criteria_to_plan(criteria, revision_round=0)
    else:
        plan = prior
    if critique and critique.status.value == "revise":
        plan = _apply_actions(plan, critique.actions)
    return plan


def run_criteria_ollama(
    criteria: UserCriteria,
    critique: Critique | None = None,
    prior: QueryPlan | None = None,
) -> QueryPlan:
    """Ask local LLM to propose a plan; fall back to deterministic mock on failure."""
    base = prior or criteria_to_plan(criteria)
    prompt = {
        "task": "Normalize housing search criteria into a QueryPlan JSON.",
        "user_criteria": criteria.model_dump(),
        "current_plan": base.model_dump(),
        "critique": critique.model_dump() if critique else None,
        "rules": [
            "Return ONLY JSON matching QueryPlan fields",
            "If critique asks to revise, apply concrete widen/expand actions",
            "Keep window_end unchanged unless critique requires otherwise",
        ],
    }
    try:
        raw = ollama_generate(
            "You are the Criteria Agent for Dallas housing analytics.\n"
            + json.dumps(prompt)
            + "\nRespond with JSON only."
        )
        data = json.loads(raw)
        # merge safely onto base
        merged = base.model_dump()
        for k in [
            "price_min",
            "price_max",
            "beds_min",
            "beds_max",
            "sqft_min",
            "sqft_max",
            "zips",
            "notes",
        ]:
            if k in data:
                merged[k] = data[k]
        if critique and critique.status.value == "revise":
            merged["revision_round"] = base.revision_round + 1
            # still apply structured actions so dependency is real even if LLM is vague
            plan = QueryPlan(**merged)
            return _apply_actions(plan, critique.actions)
        return QueryPlan(**merged)
    except Exception:
        return run_criteria_mock(criteria, critique, prior)
