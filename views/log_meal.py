import os

import streamlit as st
from mysql.connector import Error as MySQLError
from PIL import Image

import database
import vision
from app_services import initialize_database
from frontend import render_metric_row, render_page_intro, render_section_heading

initialize_database()
user_id = st.session_state.get("user_id")
if user_id is None:
    st.error("Please sign in to log a meal.")
    st.stop()

render_page_intro(
    "Meal analysis",
    "Log a meal from a photo",
    "Upload a clear photo of your plate. Nutrify will identify foods, estimate portions, and calculate macros.",
    icon=":material/add_a_photo:",
)

upload_panel, guide_panel = st.columns([3, 2], vertical_alignment="top")
with upload_panel:
    with st.container(border=True):
        render_section_heading(
            "Upload a photo",
            "JPG and PNG files are supported.",
            icon=":material/photo_camera:",
        )
        uploaded_file = st.file_uploader(
            "Choose a meal image",
            type=["jpg", "jpeg", "png"],
            help="JPG and PNG files are supported.",
        )
        if uploaded_file is not None:
            image = Image.open(uploaded_file)
            st.image(image, caption="Image ready for analysis", width="stretch")

with guide_panel:
    with st.container(border=True):
        if uploaded_file is None:
            render_section_heading(
                "Tips for a good estimate",
                icon=":material/lightbulb:",
            )
            st.markdown(
                "- Shoot from above with the whole plate in frame.\n"
                "- Use good light and avoid heavy shadows.\n"
                "- Keep separate foods visibly apart where possible."
            )
            st.caption("Detected items are saved to your meal history automatically.")
            analyze_submitted = False
        else:
            render_section_heading(
                "Ready to analyze",
                "Nutrify will identify foods, estimate portions, and calculate macros from this photo.",
                icon=":material/biotech:",
            )
            analyze_submitted = st.button(
                "Analyze meal photo",
                type="primary",
                icon=":material/document_scanner:",
                width="stretch",
            )

if uploaded_file is not None:
    if analyze_submitted:
        with st.spinner("Vision AI is analyzing your food..."):
            temp_path = "temp_upload.jpg"
            with open(temp_path, "wb") as image_file:
                image_file.write(uploaded_file.getbuffer())

            analysis = vision.analyze_meal_image(temp_path)

            if analysis and analysis.items:
                st.success("Analysis complete.", icon=":material/check_circle:")
                with st.container(border=True):
                    render_section_heading(
                        "Meal total",
                        "Sum of every detected item below.",
                        icon=":material/receipt_long:",
                    )
                    render_metric_row(
                        [
                            ("Calories", f"{sum(i.calories for i in analysis.items):.0f} kcal"),
                            ("Protein", f"{sum(i.protein for i in analysis.items):.1f} g"),
                            ("Carbs", f"{sum(i.carbs for i in analysis.items):.1f} g"),
                            ("Fat", f"{sum(i.fat for i in analysis.items):.1f} g"),
                        ]
                    )
                render_section_heading(
                    "Detected items",
                    "Expand an item to review its estimated serving and macronutrients.",
                    icon=":material/restaurant:",
                )
                for index, item in enumerate(analysis.items):
                    # 1. Conditionally add the piece count to the expander title
                    piece_label = f"{item.pieces} pieces, " if item.pieces is not None else ""
                    expander_title = f"{item.food_name} ({piece_label}{item.weight_g}g)"

                    with st.expander(
                        expander_title, expanded=index == 0, icon=":material/restaurant:"
                    ):
                        # 2. Build the metrics list dynamically so "Count" only shows if it exists
                        metrics = []
                        # if item.pieces is not None:
                        #     metrics.append(("Count", str(item.pieces)))
                        
                        metrics.extend([
                            ("Serving", f"{item.weight_g} g"),
                            ("Calories", f"{item.calories} kcal"),
                            ("Protein", f"{item.protein} g"),
                            ("Carbs", f"{item.carbs} g"),
                            ("Fat", f"{item.fat} g"),
                        ])
                        
                        render_metric_row(metrics)

                        try:
                            # Note: database.log_meal currently doesn't accept item.pieces!
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
                            st.caption("Saved to your meal history.")
            else:
                st.error("Could not parse food items from this image.")

            if os.path.exists(temp_path):
                os.remove(temp_path)
