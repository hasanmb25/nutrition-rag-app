"""Reusable presentation primitives for Nutrify's Streamlit interface.

This module intentionally contains no data access, session-state mutation, or
application logic. It keeps the visual system consistent across Streamlit pages.
"""

from collections.abc import Sequence

import streamlit as st


def render_global_styles() -> None:
    """Apply visual-only application tokens around Streamlit's native theme.

    Color values intentionally resolve through Streamlit variables so the same
    components remain legible when a person switches between light and dark
    mode in the built-in settings menu.
    """
    st.html(
        """
        <style>
        :root {
          --nutrify-space-1: 0.25rem;
          --nutrify-space-2: 0.5rem;
          --nutrify-space-3: 0.75rem;
          --nutrify-space-4: 1rem;
          --nutrify-space-5: 1.5rem;
          --nutrify-space-6: 2rem;
          --nutrify-space-8: 3rem;
          --nutrify-radius-card: 0.5rem;
          --nutrify-border: 1px solid var(--border-color);
          --nutrify-shadow-1: 0 1px 2px rgba(15, 30, 22, 0.05);
          --nutrify-shadow-2: 0 8px 24px rgba(15, 30, 22, 0.06);
          --nutrify-duration-fast: 160ms;
          --nutrify-duration-standard: 220ms;
        }

        .stApp,
        [data-testid="stAppViewContainer"] {
          background: var(--background-color);
        }

        [data-testid="stMainBlockContainer"] {
          max-width: 82rem;
          padding-top: var(--nutrify-space-6);
          padding-bottom: var(--nutrify-space-8);
        }

        [data-testid="stHeading"] h1,
        [data-testid="stHeading"] h2,
        [data-testid="stHeading"] h3 {
          letter-spacing: -0.025em;
        }

        [data-testid="stCaptionContainer"] p {
          letter-spacing: 0.04em;
          font-size: 0.72rem;
          font-weight: 650;
        }

        [data-testid="stVerticalBlockBorderWrapper"],
        [data-testid="stMetric"] {
          border-radius: var(--nutrify-radius-card);
          border-color: var(--border-color);
          box-shadow: var(--nutrify-shadow-1);
        }

        [data-testid="stVerticalBlockBorderWrapper"] {
          padding: var(--nutrify-space-2);
        }

        [data-testid="stMetric"] {
          min-width: 10rem;
          padding: var(--nutrify-space-4);
        }

        [data-testid="stMetricLabel"] {
          letter-spacing: 0.025em;
          text-transform: uppercase;
        }

        [data-testid="stMetricValue"] {
          font-variant-numeric: tabular-nums;
          letter-spacing: -0.035em;
        }

        [data-testid="stButton"] > button,
        [data-testid="stFormSubmitButton"] > button,
        [data-testid="stPageLink"] a {
          min-height: 2.75rem;
          transition: border-color var(--nutrify-duration-fast) ease,
            box-shadow var(--nutrify-duration-fast) ease,
            transform var(--nutrify-duration-fast) ease;
        }

        [data-testid="stButton"] > button:hover,
        [data-testid="stFormSubmitButton"] > button:hover,
        [data-testid="stPageLink"] a:hover {
          border-color: var(--primary-color);
          box-shadow: var(--nutrify-shadow-2);
          transform: translateY(-1px);
        }

        [data-testid="stButton"] > button:active,
        [data-testid="stFormSubmitButton"] > button:active,
        [data-testid="stPageLink"] a:active {
          box-shadow: none;
          transform: translateY(0);
        }

        button:focus-visible,
        a:focus-visible,
        input:focus-visible,
        textarea:focus-visible,
        [role="combobox"]:focus-visible {
          outline: 3px solid color-mix(in srgb, var(--primary-color) 45%, transparent);
          outline-offset: 2px;
        }

        [data-testid="stTextInput"] input,
        [data-testid="stNumberInput"] input,
        [data-testid="stSelectbox"] [data-baseweb="select"] > div,
        [data-testid="stFileUploader"] section {
          min-height: 2.75rem;
          border-radius: calc(var(--nutrify-radius-card) - 2px);
        }

        [data-testid="stDataFrame"] {
          border-radius: var(--nutrify-radius-card);
          overflow: hidden;
          border: var(--nutrify-border);
        }

        [data-testid="stNavigation"] {
          border-bottom: var(--nutrify-border);
          margin-bottom: var(--nutrify-space-3);
        }

        [data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] {
          box-shadow: none;
        }

        @media (max-width: 640px) {
          [data-testid="stMainBlockContainer"] {
            padding-top: var(--nutrify-space-5);
            padding-right: var(--nutrify-space-4);
            padding-left: var(--nutrify-space-4);
          }

          [data-testid="stMetric"] {
            min-width: 100%;
          }
        }

        @media (prefers-reduced-motion: reduce) {
          *, *::before, *::after {
            scroll-behavior: auto !important;
            transition-duration: 0.01ms !important;
            animation-duration: 0.01ms !important;
            animation-iteration-count: 1 !important;
          }
        }
        </style>
        """
    )


def render_brand() -> None:
    """Render the persistent app identity above the active view."""
    st.title("Nutrify", icon=":material/nutrition:")
    st.caption(
        "NUTRITION INTELLIGENCE · PRIVATE, PRACTICAL, DATA-LED"
    )


def render_page_intro(
    eyebrow: str, title: str, description: str, *, icon: str
) -> None:
    """Render a compact, consistently ordered page introduction."""
    st.caption(eyebrow.upper())
    st.header(title, icon=icon)
    st.markdown(description)


def render_section_heading(
    title: str, description: str | None = None, *, icon: str | None = None
) -> None:
    """Render a native Streamlit section heading with optional context."""
    st.subheader(title, icon=icon)
    if description:
        st.caption(description)


def render_metric_row(metrics: Sequence[tuple[str, str]]) -> None:
    """Render responsive, consistently bordered metric cards."""
    with st.container(horizontal=True, vertical_alignment="center", gap="small"):
        for label, value in metrics:
            st.metric(label, value, border=True)
