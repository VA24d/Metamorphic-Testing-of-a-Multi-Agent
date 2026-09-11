"""MetroMorph — chat-first multi-agent DFW housing analytics."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lotline.chat_parser import EXAMPLE_QUESTIONS, parse_question
from lotline.llm import ollama_available, resolve_mode
from lotline.orchestrator import run_pipeline
from lotline.tools import load_listings

st.set_page_config(
    page_title="MetroMorph · Ask DFW Housing",
    page_icon="⌂",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,700&family=Source+Sans+3:wght@400;500;600;700&display=swap');

:root {
  --ink: #14212b;
  --muted: #5c6b76;
  --panel: rgba(255,252,247,0.92);
  --line: #d5cdc0;
  --accent: #0f6e56;
  --accent-2: #c45c26;
}

html, body, [class*="css"] {
  font-family: "Source Sans 3", sans-serif;
  color: var(--ink);
}

.stApp {
  background:
    radial-gradient(1200px 600px at 10% -10%, #d7e8e2 0%, transparent 55%),
    radial-gradient(900px 500px at 100% 0%, #f0dcc8 0%, transparent 50%),
    linear-gradient(180deg, #f7f3ea 0%, #ebe4d7 100%);
}

[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #1a2a33 0%, #122028 100%);
  border-right: 1px solid #0b151b;
}
[data-testid="stSidebar"] * { color: #e8eef2 !important; }

.brand {
  font-family: Fraunces, Georgia, serif;
  font-size: 2.6rem;
  line-height: 1;
  letter-spacing: -0.03em;
  margin: 0;
}
.brand span { color: var(--accent); }
.tagline { color: var(--muted); margin: 0.4rem 0 1rem 0; max-width: 44rem; }

.kpi {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 1rem 1.1rem;
}
.kpi .label { color: var(--muted); font-size: 0.85rem; font-weight: 600; }
.kpi .value {
  font-family: Fraunces, Georgia, serif;
  font-size: 1.75rem;
  margin-top: 0.2rem;
}
.kpi .delta { font-size: 0.88rem; margin-top: 0.15rem; color: var(--muted); }
.delta.up { color: var(--accent); }
.delta.down { color: var(--accent-2); }

.section-title {
  font-family: Fraunces, Georgia, serif;
  font-size: 1.35rem;
  margin: 0.6rem 0 0.5rem 0;
}
.trace {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.8rem;
  background: #14212b;
  color: #d7ece4;
  border-radius: 14px;
  padding: 0.9rem 1rem;
}
.mode-pill {
  display: inline-block;
  padding: 0.22rem 0.6rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
}
.mode-mock { background: #f3e0c7; color: #7a3e10; }
.mode-ollama { background: #d8eee6; color: #0f6e56; }
.agent-card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 0.85rem 1rem;
  margin-bottom: 0.65rem;
}
.agent-card .agent-name {
  font-weight: 700;
  color: var(--accent);
  font-size: 0.95rem;
}
.agent-card .agent-iter {
  color: var(--muted);
  font-size: 0.8rem;
  margin-left: 0.35rem;
}
.agent-card .agent-summary { margin-top: 0.35rem; }
.badge {
  display: inline-block;
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  padding: 0.12rem 0.45rem;
  border-radius: 999px;
  margin-left: 0.35rem;
}
.badge-pass { background: #d8eee6; color: #0f6e56; }
.badge-revise { background: #f3e0c7; color: #7a3e10; }
.badge-ok { background: #e8eef2; color: #334155; }
</style>
""",
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def get_data():
    return load_listings()


def money(v: float, currency: str) -> str:
    if currency == "USD_THOUSANDS":
        return f"${v:,.1f}k"
    return f"${v:,.0f}"


def build_trend_figure(months, currency: str):
    labels = [m.month for m in months]
    prices = [m.median_price for m in months]
    ppsf = [m.median_price_per_sqft for m in months]
    counts = [m.active_count for m in months]

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        specs=[[{"secondary_y": True}], [{"secondary_y": False}]],
        row_heights=[0.62, 0.38],
        vertical_spacing=0.1,
        subplot_titles=("Median list price & $/sqft", "Active listings"),
    )
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=prices,
            name="Median price",
            mode="lines+markers",
            line=dict(color="#0f6e56", width=3),
            marker=dict(size=8),
        ),
        row=1,
        col=1,
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=ppsf,
            name="$/sqft",
            mode="lines+markers",
            line=dict(color="#c45c26", width=2.5, dash="dot"),
            marker=dict(size=7),
        ),
        row=1,
        col=1,
        secondary_y=True,
    )
    fig.add_trace(
        go.Bar(
            x=labels,
            y=counts,
            name="Listings",
            marker_color="rgba(20,33,43,0.55)",
        ),
        row=2,
        col=1,
    )
    fig.update_layout(
        height=520,
        margin=dict(l=20, r=20, t=50, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,252,247,0.65)",
        font=dict(family="Source Sans 3", color="#14212b"),
        legend=dict(orientation="h", yanchor="bottom", y=1.12, x=0),
        hovermode="x unified",
    )
    fig.update_yaxes(title_text=f"Price ({currency})", gridcolor="#e5ddd0", row=1, col=1, secondary_y=False)
    fig.update_yaxes(title_text="$/sqft", showgrid=False, row=1, col=1, secondary_y=True)
    fig.update_yaxes(title_text="Count", gridcolor="#e5ddd0", row=2, col=1)
    fig.update_xaxes(gridcolor="#e5ddd0")
    return fig


def render_agent_steps(result):
    st.markdown('<div class="section-title">All 5 agents — step-by-step results</div>', unsafe_allow_html=True)
    st.caption(
        "Criteria → Scanner → Analyst → Critic → Report. "
        "If Critic says REVISE, Criteria runs again with a changed plan (feedback loop)."
    )

    # Final snapshot of each agent (last occurrence), plus full timeline below
    order = ["Criteria", "Scanner", "Analyst", "Critic", "Report"]
    latest = {}
    for step in result.agent_steps:
        latest[step.agent] = step

    cols = st.columns(5)
    for col, name in zip(cols, order):
        step = latest.get(name)
        with col:
            if not step:
                st.info(f"{name}: n/a")
                continue
            badge = {"pass": "badge-pass", "revise": "badge-revise"}.get(step.status, "badge-ok")
            st.markdown(
                f'<div class="agent-card">'
                f'<div><span class="agent-name">{name}</span>'
                f'<span class="agent-iter">iter {step.iteration}</span>'
                f'<span class="badge {badge}">{step.status}</span></div>'
                f'<div class="agent-summary">{step.summary}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )

    with st.expander("Full agent timeline (every iteration)", expanded=True):
        for step in result.agent_steps:
            badge = {"pass": "badge-pass", "revise": "badge-revise"}.get(step.status, "badge-ok")
            st.markdown(
                f'<div class="agent-card">'
                f'<div><span class="agent-name">{step.agent}</span>'
                f'<span class="agent-iter">iteration {step.iteration}</span>'
                f'<span class="badge {badge}">{step.status}</span></div>'
                f'<div class="agent-summary">{step.summary}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )
            st.json(step.details)


def render_analytics(result):
    report = result.report
    trend = report.trend
    plan = report.query_plan
    mode_cls = "mode-ollama" if report.mode == "ollama" else "mode-mock"
    first, last = trend.months[0], trend.months[-1]
    yoy = trend.yoy_pct_change
    yoy_cls = "up" if (yoy or 0) >= 0 else "down"
    yoy_txt = f"{yoy:+.1f}% vs first month" if yoy is not None else "n/a"

    st.markdown(
        f'<span class="mode-pill {mode_cls}">{report.mode}</span>'
        f'&nbsp; <span style="color:#5c6b76">{report.iterations} agent iteration(s)</span>',
        unsafe_allow_html=True,
    )
    st.markdown(f'<div class="section-title">{report.headline}</div>', unsafe_allow_html=True)
    st.write(report.narrative)

    # Show all agent results first for clarity
    render_agent_steps(result)

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(
            f'<div class="kpi"><div class="label">Latest median</div>'
            f'<div class="value">{money(last.median_price, plan.currency_display)}</div>'
            f'<div class="delta {yoy_cls}">{yoy_txt}</div></div>',
            unsafe_allow_html=True,
        )
    with k2:
        st.markdown(
            f'<div class="kpi"><div class="label">Latest $/sqft</div>'
            f'<div class="value">${last.median_price_per_sqft:,.0f}</div>'
            f'<div class="delta">from ${first.median_price_per_sqft:,.0f}</div></div>',
            unsafe_allow_html=True,
        )
    with k3:
        st.markdown(
            f'<div class="kpi"><div class="label">Matched listings</div>'
            f'<div class="value">{result.filtered_count:,}</div>'
            f'<div class="delta">coverage {trend.coverage_score:.2f}</div></div>',
            unsafe_allow_html=True,
        )
    with k4:
        st.markdown(
            f'<div class="kpi"><div class="label">ZIP codes used</div>'
            f'<div class="value">{len(plan.zips)}</div>'
            f'<div class="delta">rev #{plan.revision_round}</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-title">Twelve-month analytics</div>', unsafe_allow_html=True)
    st.plotly_chart(build_trend_figure(trend.months, plan.currency_display), use_container_width=True)

    left, right = st.columns((1.25, 1))
    with left:
        st.markdown('<div class="section-title">Monthly detail</div>', unsafe_allow_html=True)
        table = pd.DataFrame(
            [
                {
                    "Month": m.month,
                    "Median price": m.median_price,
                    "$/sqft": m.median_price_per_sqft,
                    "Active listings": m.active_count,
                }
                for m in trend.months
            ]
        )
        st.dataframe(
            table.style.format({"Median price": "{:,.0f}", "$/sqft": "{:,.1f}"}),
            use_container_width=True,
            hide_index=True,
        )
    with right:
        st.markdown('<div class="section-title">Raw execution trace</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="trace">{"<br/>".join(report.trace)}</div>',
            unsafe_allow_html=True,
        )

    with st.expander("Sample matched listings"):
        if result.listings_preview:
            st.dataframe(pd.DataFrame(result.listings_preview), use_container_width=True, hide_index=True)
        else:
            st.warning("No listings matched.")


def main():
    df = get_data()
    ollama_ok = ollama_available()
    default_end = sorted(df["list_month"].unique().tolist())[-1]

    if "messages" not in st.session_state:
        st.session_state.messages = []  # {role, content, result?}

    with st.sidebar:
        st.markdown("### Chat settings")
        mode_choice = st.selectbox(
            "Agent mode",
            options=["auto", "mock", "ollama"],
            index=0,
            help="Mock works without LLM. Ollama uses your teammate's local model.",
        )
        max_iter = st.slider("Max critic iterations", 1, 5, 3)
        if st.button("Clear chat", use_container_width=True):
            st.session_state.messages = []
            st.rerun()
        st.markdown("---")
        st.caption(
            f"**{len(df):,}** DFW listings · "
            f"Ollama {'online' if ollama_ok else 'offline'}"
        )
        st.caption("Ask in plain English. Example localities: Plano, Frisco, Uptown, Highland Park.")

    st.markdown(
        '<h1 class="brand">Metro<span>Morph</span></h1>'
        '<p class="tagline">Ask a question about Dallas–Fort Worth housing. '
        "Agents translate your question into search criteria, scan the local listings, "
        "compute a 12-month trend, and show analytics.</p>",
        unsafe_allow_html=True,
    )

    # Example chips
    st.markdown("**Try asking:**")
    cols = st.columns(len(EXAMPLE_QUESTIONS))
    for i, q in enumerate(EXAMPLE_QUESTIONS):
        with cols[i]:
            if st.button(q, key=f"ex_{i}", use_container_width=True):
                st.session_state._pending_question = q

    # Replay history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("interpretation"):
                st.caption(msg["interpretation"])
            if msg.get("result") is not None:
                render_analytics(msg["result"])

    pending = st.session_state.pop("_pending_question", None)
    user_text = st.chat_input(
        "Ask about DFW housing trends… e.g. 3-bed homes under $450k in Plano"
    )
    question = pending or user_text

    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        mode = resolve_mode(None if mode_choice == "auto" else mode_choice)
        with st.chat_message("assistant"):
            with st.spinner("Understanding your question → running agents…"):
                criteria, interpretation = parse_question(
                    question, mode=mode, default_window_end=default_end
                )
                result = run_pipeline(
                    criteria, df=df, mode=mode, max_iterations=max_iter
                )
            st.markdown(
                "Here’s what I found from the DFW dataset after the multi-agent run."
            )
            st.caption(interpretation)
            render_analytics(result)

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": "Here’s what I found from the DFW dataset after the multi-agent run.",
                "interpretation": interpretation,
                "result": result,
            }
        )


if __name__ == "__main__":
    main()
