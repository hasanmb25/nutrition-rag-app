import streamlit as st

from app_services import load_vector_store
from frontend import (
    render_ai_answer,
    render_page_intro,
    render_section_heading,
    render_user_prompt,
)

# UI-only history so earlier answers survive reruns on this page.
if "recipe_conversation" not in st.session_state:
    st.session_state["recipe_conversation"] = []

render_page_intro(
    "Recipe discovery",
    "Pantry-to-recipe recommender",
    "Tell the AI what you have on hand, then refine the recommendation by cuisine and dietary goal.",
    icon=":material/menu_book:",
)

brief_panel, answer_panel = st.columns([2, 3], vertical_alignment="top")

with brief_panel:
    with st.container(border=True):
        render_section_heading(
            "Build a recipe brief",
            "Use ingredients you have on hand and choose the constraints that matter today.",
            icon=":material/tune:",
        )
        with st.form("recipe_discovery", border=False):
            user_ingredients = st.text_area(
                "What is in your fridge or pantry?",
                placeholder="For example: chicken breast, spinach, quinoa",
                help="List ingredients separated by commas for the most useful recommendation.",
                height=100,
            )
            selected_cuisine = st.selectbox(
                "Cuisine preference",
                ["Flexible", "Indian", "Italian", "Mexican", "Asian", "Mediterranean"],
            )
            selected_diet = st.selectbox(
                "Dietary goal",
                ["Flexible", "High Protein", "Low Carb", "Keto", "Vegan", "Vegetarian"],
            )
            submitted = st.form_submit_button(
                "Generate recipe",
                type="primary",
                icon=":material/auto_awesome:",
                width="stretch",
            )
        st.caption("Recipes are retrieved from the recipe database, then written by AI.")

with answer_panel:
    with st.container(border=True):
        with st.container(horizontal=True, vertical_alignment="center"):
            render_section_heading("Suggested recipes", icon=":material/chat:")
            if st.session_state["recipe_conversation"]:
                if st.button(
                    "Clear",
                    icon=":material/delete:",
                    type="tertiary",
                    width="content",
                ):
                    st.session_state["recipe_conversation"] = []
                    st.rerun()

        for turn in st.session_state["recipe_conversation"]:
            render_user_prompt(turn["prompt"])
            render_ai_answer(turn["answer"], caption=turn["caption"])

        if submitted:
            if not user_ingredients:
                st.warning("Please enter some ingredients first.", icon=":material/warning:")
            else:
                prompt_text = (
                    f"{user_ingredients}  \n"
                    f":green-badge[{selected_cuisine}] :orange-badge[{selected_diet}]"
                )
                render_user_prompt(prompt_text)
                with st.spinner(
                    f"Searching ChromaDB and formulating a {selected_cuisine} recipe..."
                ):
                    vector_store = load_vector_store()
                    if vector_store is None:
                        # Don't cache the failure, so the next click tries again.
                        load_vector_store.clear()
                        st.error(
                            "The recipe database could not be built. If you are on a free "
                            "AI plan, wait a minute and try again. Details are in the terminal."
                        )
                    else:
                        import rag_chain

                        recipe_chain = rag_chain.get_recipe_recommendation_chain(vector_store)

                        response = recipe_chain.invoke(
                            {
                                "question": user_ingredients,
                                "cuisine": selected_cuisine,
                                "diet_goal": selected_diet,
                            }
                        )

                        caption = "Generated from the ingredients and preferences you provided."
                        render_ai_answer(response, caption=caption)
                        st.session_state["recipe_conversation"].append(
                            {"prompt": prompt_text, "answer": response, "caption": caption}
                        )
        elif not st.session_state["recipe_conversation"]:
            st.caption(
                "Your recipe suggestions will appear here. Start by listing a few ingredients."
            )
