"""
💬 SafetyChat – AI-Powered Safety Assistant

Natural language interface for the Virginia Tech Transportation Safety Index (VTTSI).
Ask questions about intersection safety scores, risk factors, and historical trends.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
import streamlit as st

from app.utils.config import API_URL, API_TIMEOUT, APP_ICON

# Derive the chat base URL from the shared API_URL config.
# API_URL ends with /api/v1/safety/index  →  strip the last segment.
_api_base = "/".join(API_URL.rstrip("/").split("/")[:-2])  # .../api/v1
CHAT_URL = f"{_api_base}/chat/"

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="SafetyChat – AI Safety Assistant",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session state ─────────────────────────────────────────────────────────────

if "chat_history" not in st.session_state:
    st.session_state.chat_history: list[dict] = []

if "chat_error" not in st.session_state:
    st.session_state.chat_error: str | None = None

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("💬 SafetyChat")
    st.markdown(
        "Ask natural language questions about real-time intersection safety. "
        "The assistant queries live VTTSI data to ground every answer."
    )
    st.divider()

    st.subheader("⚙️ Settings")
    alpha = st.slider(
        "RT-SI Weight (α)",
        min_value=0.0,
        max_value=1.0,
        value=0.7,
        step=0.1,
        help="Controls how much the real-time RT-SI score contributes vs the MCDM score.",
    )
    st.caption(f"Blend: {alpha*100:.0f}% RT-SI + {(1-alpha)*100:.0f}% MCDM")

    st.divider()
    st.subheader("💡 Example Questions")
    examples = [
        "Give me a morning safety briefing for all intersections.",
        "Which intersection is the most dangerous right now?",
        "Why is the Glebe–Potomac score elevated?",
        "What is driving risk at E. Broad & N. Washington?",
        "Compare all intersections by VRU count.",
        "What is the historical crash baseline for Birch & Broad?",
        "Which intersection has the lowest risk for emergency vehicle routing?",
    ]
    for example in examples:
        if st.button(example, use_container_width=True, key=f"ex_{example[:20]}"):
            st.session_state.chat_history.append(
                {"role": "user", "content": example}
            )
            st.session_state.chat_error = None
            st.rerun()

    st.divider()
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.chat_error = None
        st.rerun()

    st.divider()
    st.caption(
        "SafetyChat uses GPT-4o via the VTTSI backend API. "
        "All numerical values are fetched live from the safety index database."
    )

# ── Main content ──────────────────────────────────────────────────────────────

st.title(f"{APP_ICON} SafetyChat – AI Safety Assistant")
st.markdown(
    "Ask questions about real-time intersection safety. "
    "The assistant automatically queries live safety index data to ground every response."
)
st.divider()

# Display chat history
chat_container = st.container()

with chat_container:
    if not st.session_state.chat_history:
        st.info(
            "👋 Welcome to SafetyChat! Type a question below or pick an example "
            "from the sidebar to get started."
        )
    else:
        for msg in st.session_state.chat_history:
            if msg["role"] == "user":
                with st.chat_message("user"):
                    st.markdown(msg["content"])
            else:
                with st.chat_message("assistant", avatar="🚦"):
                    st.markdown(msg["content"])

    if st.session_state.chat_error:
        st.error(f"⚠️ {st.session_state.chat_error}")

# ── Chat input ────────────────────────────────────────────────────────────────

user_input = st.chat_input("Ask about intersection safety…")

if user_input:
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    st.session_state.chat_error = None

    # Append alpha context as a hidden system hint appended to the last user message
    messages_to_send = list(st.session_state.chat_history)
    # Inject alpha preference into the last user message unobtrusively
    messages_to_send[-1] = {
        "role": "user",
        "content": (
            f"{user_input}\n"
            f"[User preference: use alpha={alpha} for blended score calculations.]"
        ),
    }

    with st.spinner("SafetyChat is thinking…"):
        try:
            resp = requests.post(
                CHAT_URL,
                json={"messages": messages_to_send},
                timeout=API_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            reply = data.get("reply", "No response received.")
            st.session_state.chat_history.append(
                {"role": "assistant", "content": reply}
            )
        except requests.exceptions.ConnectionError:
            st.session_state.chat_error = (
                "Cannot connect to the VTTSI backend. "
                "Make sure the backend server is running."
            )
        except requests.exceptions.Timeout:
            st.session_state.chat_error = (
                "Request timed out. The backend may be computing a complex query."
            )
        except requests.exceptions.HTTPError as exc:
            detail = ""
            try:
                detail = exc.response.json().get("detail", "")
            except Exception:
                pass
            if exc.response.status_code == 503:
                st.session_state.chat_error = (
                    "SafetyChat is not configured: "
                    + (detail or "OPENAI_API_KEY missing on the backend.")
                )
            else:
                st.session_state.chat_error = (
                    f"Backend error ({exc.response.status_code}): {detail or str(exc)}"
                )
        except Exception as exc:
            st.session_state.chat_error = f"Unexpected error: {exc}"

    st.rerun()
