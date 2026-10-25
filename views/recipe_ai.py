import streamlit as st

from app_services import load_vector_store

st.header("Pantry-to-Recipe Recommender")
st.write(
    "Tell the AI what ingredients you have, set your preferences, "
    "and it will search our vector database."
)

user_ingredients = st.text_input(
    "What's in your fridge/pantry?",
    placeholder="e.g., Chicken breast, spinach, quinoa",
)

col1, col2 = st.columns(2)
with col1:
    selected_cuisine = st.selectbox(
        "Cuisine Preference",
        ["Flexible", "Bangladeshi", "Italian", "Mexican", "Asian", "Mediterranean"],
    )
with col2:
    selected_diet = st.selectbox(
        "Dietary Goal",
        ["Flexible", "High Protein", "Low Carb", "Keto", "Vegan", "Vegetarian"],
    )

if st.button("Generate Recipe", type="primary"):
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

                st.markdown("### Suggested Recipe")
                st.write(response)
