import os

import streamlit as st
from mysql.connector import Error as MySQLError
from PIL import Image

import database
import vision
from app_services import initialize_database

initialize_database()
user_id = st.session_state.get("user_id")
if user_id is None:
    st.error("Please sign in to log a meal.")
    st.stop()

st.header("Log a Meal via Image")
st.write(
    "Upload a photo of your plate. The AI will identify the food, estimate "
    "portion sizes, and calculate your macros."
)

uploaded_file = st.file_uploader("Choose an image...", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    image = Image.open(uploaded_file)
    st.image(image, caption="Uploaded Image", width=400, alt="Uploaded meal")

    if st.button("Analyze & Parse Image", type="primary"):
        with st.spinner("Vision AI is analyzing your food..."):
            temp_path = "temp_upload.jpg"
            with open(temp_path, "wb") as image_file:
                image_file.write(uploaded_file.getbuffer())

            analysis = vision.analyze_meal_image(temp_path)

            if analysis and analysis.items:
                st.success("✅ Analysis Complete!")
                for item in analysis.items:
                    with st.expander(f"{item.food_name} ({item.weight_g}g)"):
                        st.write(f"**Calories:** {item.calories} kcal")
                        st.write(
                            f"**Macros:** {item.protein}g Protein | "
                            f"{item.carbs}g Carbs | {item.fat}g Fat"
                        )

                        try:
                            database.log_meal(
                                user_id,
                                item.food_name,
                                item.weight_g,
                                item.calories,
                                item.protein,
                                item.carbs,
                                item.fat,
                            )
                        except MySQLError as error:
                            st.error(f"Unable to save this meal to MySQL: {error}")
                        else:
                            st.caption("💾 *Saved to MySQL Database*")
            else:
                st.error("Could not parse food items from this image.")

            if os.path.exists(temp_path):
                os.remove(temp_path)
