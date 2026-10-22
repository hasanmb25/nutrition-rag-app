import streamlit as st
import os
from PIL import Image
import database
import vision
import rag_chain

# 1. Page Config (Must be the first Streamlit command)
st.set_page_config(
    page_title="Nutrify | AI Assistant",
    page_icon="🥗",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 2. Custom CSS Injection for larger fonts and colorful headers
st.markdown("""
<style>
    /* Make the main title massive, bold, and vibrant green */
    h1 {
        font-size: 3.5rem !important;
        font-weight: 800 !important;
        color: #27ae60 !important;
        margin-bottom: 0rem !important;
    }
    
    /* Make the tab headers and secondary headers larger */
    h2 {
        font-size: 2.2rem !important;
        font-weight: 700 !important;
        padding-top: 1rem !important;
    }
    
    /* Make the subtitle more readable */
    .subtitle {
        font-size: 1.3rem !important;
        color: #555555;
        margin-bottom: 2rem !important;
    }
    
    /* Make the macro numbers pop on the dashboard */
    div[data-testid="stMetricValue"] {
        font-size: 3rem !important;
        color: #27ae60 !important;
        font-weight: 700 !important;
    }
    
    /* Increase general text size slightly for readability */
    p, li {
        font-size: 1.15rem !important;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def init_system():
    """Initializes the database and loads the vector store only once per session."""
    database.init_db()
    return rag_chain.build_or_load_vector_store()

vector_store = init_system()

# Rebranded Title using standard Markdown with HTML classes for our CSS
st.markdown("<h1>🥗 Nutrify</h1>", unsafe_allow_html=True)
st.markdown('<p class="subtitle">Your Multimodal AI Nutrition Assistant. Track meals, generate recipes, and get health critiques.</p>', unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["📸 Vision Logger", "🍳 Recipe Recommender", "📊 Daily Dashboard"])

with tab1:
    st.header("Log a Meal via Image")
    st.write("Upload a photo of your plate. The AI will identify the food, estimate portion sizes, and calculate your macros.")
    
    uploaded_file = st.file_uploader("Choose an image...", type=["jpg", "jpeg", "png"])
    
    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption="Uploaded Image", use_container_width=True)
        
        if st.button("Analyze & Parse Image", type="primary"):
            with st.spinner("Vision AI is analyzing your food..."):
                temp_path = "temp_upload.jpg"
                with open(temp_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                analysis = vision.analyze_meal_image(temp_path)
                
                if analysis and analysis.items:
                    st.success("✅ Analysis Complete!")
                    for item in analysis.items:
                        with st.expander(f"{item.food_name} ({item.weight_g}g)"):
                            st.write(f"**Calories:** {item.calories} kcal")
                            st.write(f"**Macros:** {item.protein}g Protein | {item.carbs}g Carbs | {item.fat}g Fat")
                            
                            success = database.log_meal(
                                item.food_name, item.weight_g, 
                                item.calories, item.protein, 
                                item.carbs, item.fat
                            )
                            if success:
                                st.caption("💾 *Saved to MySQL Database*")
                            else:
                                st.error("Failed to save to database.")
                else:
                    st.error("Could not parse food items from this image.")
                
                if os.path.exists(temp_path):
                    os.remove(temp_path)

with tab2:
    st.header("Pantry-to-Recipe Recommender")
    st.write("Tell the AI what ingredients you have, set your preferences, and it will search our vector database.")
    
    user_ingredients = st.text_input("What's in your fridge/pantry?", placeholder="e.g., Chicken breast, spinach, quinoa")
    
    col1, col2 = st.columns(2)
    with col1:
        selected_cuisine = st.selectbox(
            "Cuisine Preference", 
            ["Flexible", "Bangladeshi", "Italian", "Mexican", "Asian", "Mediterranean"]
        )
    with col2:
        selected_diet = st.selectbox(
            "Dietary Goal", 
            ["Flexible", "High Protein", "Low Carb", "Keto", "Vegan", "Vegetarian"]
        )
    
    if st.button("Generate Recipe", type="primary"):
        if not user_ingredients:
            st.warning("Please enter some ingredients first.")
        elif vector_store is None:
            st.error("Vector database is not loaded.")
        else:
            with st.spinner(f"Searching ChromaDB and formulating a {selected_cuisine} recipe..."):
                recipe_chain = rag_chain.get_recipe_recommendation_chain(vector_store)
                
                inputs = {
                    "question": user_ingredients,
                    "cuisine": selected_cuisine,
                    "diet_goal": selected_diet
                }
                
                response = recipe_chain.invoke(inputs)
                
                st.markdown("### Suggested Recipe")
                st.write(response)

with tab3:
    st.header("Your Daily Nutrition Dashboard")
    
    totals = database.get_today_totals()
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Calories", f"{totals['calories']} kcal")
    col2.metric("Protein", f"{totals['protein']} g")
    col3.metric("Carbs", f"{totals['carbs']} g")
    col4.metric("Fat", f"{totals['fat']} g")
    
    st.divider()
    
    st.subheader("Generate Clinical Critique")
    st.write("Get professional feedback from the AI (gpt-4o) based on your logged intake today.")
    
    if st.button("Synthesize Health Report", type="primary"):
        with st.spinner("Consulting Clinical AI..."):
            critique_chain = rag_chain.get_clinical_critique_chain()
            
            report = critique_chain.invoke({
                "calories": totals['calories'],
                "protein": totals['protein'],
                "carbs": totals['carbs'],
                "fat": totals['fat']
            })
            
            st.info(report)