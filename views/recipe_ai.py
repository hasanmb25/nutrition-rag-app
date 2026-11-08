import streamlit as st

from app_services import load_vector_store
from frontend import render_page_intro, render_section_heading

render_page_intro(
    "Recipe discovery",
    "Pantry-to-recipe recommender",
    "Tell the AI what you have on hand, then refine the recommendation by cuisine and dietary goal.",
    icon=":material/menu_book:",
)

with st.container(border=True):
    render_section_heading(
        "Build a recipe brief",
        "Use ingredients you have on hand and choose the constraints that matter today.",
        icon=":material/tune:",
    )
    with st.form("recipe_discovery", border=False):
        user_ingredients = st.text_input(
            "What is in your fridge or pantry?",
            placeholder="For example: chicken breast, spinach, quinoa",
            help="List ingredients separated by commas for the most useful recommendation.",
        )
        col1, col2 = st.columns(2)
        with col1:
            selected_cuisine = st.selectbox(
                "Cuisine preference",
                ["Flexible", "Indian", "Italian", "Mexican", "Asian", "Mediterranean"],
            )
        with col2:
            selected_diet = st.selectbox(
                "Dietary goal",
                ["Flexible", "High Protein", "Low Carb", "Keto", "Vegan", "Vegetarian"],
            )
        submitted = st.form_submit_button(
            "Generate recipe", type="primary", icon=":material/auto_awesome:"
        )

if submitted:
    if not user_ingredients:
        st.warning("Please enter some ingredients first.")
    else:
        with st.spinner(
            f"Searching ChromaDB and formulating a {selected_cuisine} recipe..."
        ):
            vector_store = load_vector_store()
            if vector_store is None:
                st.error("Vector database is not loaded.")
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

                with st.container(border=True):
                    render_section_heading(
                        "Suggested recipe",
                        "Generated from the ingredients and preferences you provided.",
                        icon=":material/auto_awesome:",
                    )
                    st.write(response)
