# Project notes
- OS: Windows. Use `python` (not `python3`) and backslash paths,
  e.g. python .claude\skills\ui-ux-pro-max\scripts\search.py
- Virtual env: .venv (already set up).
- Frontend: Streamlit. Do NOT convert to React/HTML.
- Styling priority: 1) .streamlit\config.toml theme, 2) native Streamlit
  layout components, 3) minimal custom CSS only when unavoidable.
- Design system: follow design-system\nutritionrag\MASTER.md.
- Never change RAG, retrieval, or backend logic when doing UI work.