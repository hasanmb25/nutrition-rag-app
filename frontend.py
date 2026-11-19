"""Reusable presentation primitives for Nutrify's Streamlit interface.

This module intentionally contains no data access, session-state mutation, or
application logic. It keeps the visual system consistent across Streamlit pages.
"""

from collections.abc import Sequence

import streamlit as st


def render_global_styles() -> None:
    """Apply the few visual rules that `.streamlit/config.toml` cannot express.

    Colors, fonts, radii, borders and the sidebar all come from the theme in
    config.toml. This is the single place for custom CSS, and it deliberately
    avoids Streamlit's internal class names / test ids so it survives upgrades:

    - Raleway ships old-style figures by default; force lining, tabular
      numerals so calories and macros line up and read cleanly.
    - Visible keyboard focus ring on interactive elements (a11y).
    - Honor prefers-reduced-motion.
    """
    st.html(
        """
        <style>
        body {
          font-variant-numeric: lining-nums tabular-nums;
        }

        button:focus-visible,
        a:focus-visible,
        input:focus-visible,
        textarea:focus-visible,
        [role="tab"]:focus-visible,
        [role="combobox"]:focus-visible {
          outline: 3px solid color-mix(in srgb, var(--primary-color, #047857) 55%, transparent);
          outline-offset: 2px;
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
    """Render the compact app identity row above the active view."""
    with st.container(horizontal=True, vertical_alignment="center", gap="small"):
        st.markdown(":material/nutrition: **Nutrify**", width="content")
        st.badge("Nutrition intelligence", color="green", width="content")


def render_page_intro(
    eyebrow: str, title: str, description: str, *, icon: str
) -> None:
    """Render the page's single h1 with a short eyebrow and summary line."""
    st.badge(eyebrow, color="orange")
    st.title(title, icon=icon)
    st.caption(description)


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


def render_user_prompt(text: str) -> None:
    """Show what the person asked for as a chat bubble."""
    with st.chat_message("user", avatar=":material/person:"):
        st.markdown(text)


def render_ai_answer(markdown_text: str, *, caption: str | None = None) -> None:
    """Show an AI/RAG answer as an assistant chat bubble with a source note."""
    with st.chat_message("assistant", avatar=":material/nutrition:"):
        st.markdown(markdown_text)
        if caption:
            st.caption(caption)
