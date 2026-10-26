import importlib

import streamlit as st
from mysql.connector import Error as MySQLError

import database
import nutrition_estimates
import rag_chain
from app_services import initialize_database

_estimate_helpers = (
    "NutritionAssessmentError",
    "assessment_with_explanation",
    "generate_assessment",
    "normalize_assessment",
)
if not all(hasattr(nutrition_estimates, name) for name in _estimate_helpers):
    nutrition_estimates = importlib.reload(nutrition_estimates)

NutritionAssessmentError = nutrition_estimates.NutritionAssessmentError
assessment_with_explanation = nutrition_estimates.assessment_with_explanation
generate_assessment = nutrition_estimates.generate_assessment
normalize_assessment = nutrition_estimates.normalize_assessment


initialize_database()
user_id = st.session_state.get("user_id")
if user_id is None:
    st.error("Please sign in to view your nutrition dashboard.")
    st.stop()

try:
    profile = database.get_user_by_id(user_id)
    if profile is None:
        st.error("The signed-in profile could not be found. Please sign in again.")
        st.stop()
    if not profile["openai_profile_consent"]:
        st.error("OpenAI processing consent is required for your profile estimates.")
        st.stop()
    assessment = database.get_profile_assessment(user_id)
except MySQLError as error:
    st.error(f"Unable to load your profile assessment: {error}")
    st.stop()

assessment_save_warning = None
assessment_model_warning = None
if assessment is None:
    try:
        assessment = generate_assessment(profile)
    except NutritionAssessmentError as error:
        assessment = assessment_with_explanation(
            profile,
            "These formula-based estimates are approximate and are not medical advice.",
        )
        assessment_model_warning = (
            f"{error} Formula-based estimates are shown; the AI explanation is unavailable."
        )
else:
    assessment = normalize_assessment(profile, assessment)

try:
    database.save_profile_assessment(user_id, assessment)
except MySQLError as error:
    assessment_save_warning = (
        "Your estimate is available for this visit, but could not be saved. "
        f"Details: {error}"
    )

st.header(f"Your Nutrify dashboard, {profile['username']}")
st.subheader("Your profile estimates")
st.caption(
    "Formula-based and AI-explained wellness estimates, not medical advice or a diagnosis. "
    "BMI reference ranges and calorie needs are approximate."
)
if assessment_save_warning:
    st.warning(assessment_save_warning)
if assessment_model_warning:
    st.warning(assessment_model_warning)

metric_columns = st.columns(5)
metric_columns[0].metric("BMI", f"{assessment['bmi']:.1f}")
metric_columns[1].metric("BMR estimate", f"{assessment['bmr_kcal']:.0f} kcal/day")
metric_columns[2].metric(
    "Target weight range",
    f"{assessment['target_weight_min_kg']:.1f}-"
    f"{assessment['target_weight_max_kg']:.1f} kg",
)
metric_columns[3].metric("Suggested goal", assessment["goal"])
metric_columns[4].metric(
    "Daily calorie target",
    f"{assessment['daily_calorie_limit_kcal']} kcal/day",
)
if profile.get("sex_for_bmr") not in ("male", "female"):
    st.caption(
        "Because no optional BMR sex input was provided, BMR and calorie target "
        "use a rough midpoint of the two standard Mifflin-St Jeor estimates."
    )
st.write(assessment["explanation"])

st.divider()
st.header("Your daily nutrition")
try:
    totals = database.get_today_totals(user_id)
except MySQLError as error:
    st.error(f"Unable to load today's nutrition totals: {error}")
    st.stop()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Calories", f"{totals['calories']} kcal")
col2.metric("Protein", f"{totals['protein']} g")
col3.metric("Carbs", f"{totals['carbs']} g")
col4.metric("Fat", f"{totals['fat']} g")

st.subheader("Recent daily history")
try:
    history = database.get_daily_history(user_id)
except MySQLError as error:
    st.error(f"Unable to load your meal history: {error}")
else:
    if history:
        st.dataframe(history, hide_index=True, width="stretch")
    else:
        st.info("Your meals will appear here after you log them.")

st.divider()
st.subheader("Generate nutrition critique")
st.write(
    "Get AI feedback based on your logged intake today. "
    "This is informational and does not replace professional advice."
)
if st.button("Synthesize nutrition report", type="primary"):
    with st.spinner("Generating your report..."):
        critique_chain = rag_chain.get_clinical_critique_chain()
        report = critique_chain.invoke(
            {
                "calories": totals["calories"],
                "protein": totals["protein"],
                "carbs": totals["carbs"],
                "fat": totals["fat"],
                "daily_calorie_target": assessment["daily_calorie_limit_kcal"],
                "goal": assessment["goal"],
            }
        )
        st.info(report)
