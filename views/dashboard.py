import importlib

import streamlit as st
from mysql.connector import Error as MySQLError

import database
from ai_models import provider_label
import nutrition_estimates
import rag_chain
from app_services import initialize_database
from frontend import (
    render_ai_answer,
    render_metric_row,
    render_page_intro,
    render_section_heading,
)

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
        st.error(f"{provider_label()} processing consent is required for your profile estimates.")
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

render_page_intro(
    "Today's snapshot",
    f"Nutrition dashboard for {profile['username']}",
    "Formula-based and AI-explained wellness estimates, not medical advice or a diagnosis.",
    icon=":material/monitoring:",
)
if assessment_save_warning:
    st.warning(assessment_save_warning, icon=":material/warning:")
if assessment_model_warning:
    st.warning(assessment_model_warning, icon=":material/warning:")

try:
    totals = database.get_today_totals(user_id)
except MySQLError as error:
    st.error(f"Unable to load today's nutrition totals: {error}")
    st.stop()

# Today at a glance: the numbers people check most, above the fold.
with st.container(horizontal=True, vertical_alignment="center", gap="small"):
    st.metric(
        "Calories today",
        f"{totals['calories']} kcal",
        icon=":material/local_fire_department:",
        help=f"Daily target: {assessment['daily_calorie_limit_kcal']} kcal",
        border=True,
    )
    st.metric("Protein", f"{totals['protein']} g", icon=":material/egg:", border=True)
    st.metric("Carbs", f"{totals['carbs']} g", icon=":material/bakery_dining:", border=True)
    st.metric("Fat", f"{totals['fat']} g", icon=":material/water_drop:", border=True)
    st.metric(
        "Daily target",
        f"{assessment['daily_calorie_limit_kcal']} kcal",
        icon=":material/flag:",
        border=True,
    )

today_tab, profile_tab, history_tab = st.tabs(
    [
        ":material/today: Today",
        ":material/person: Profile estimates",
        ":material/history: History",
    ]
)

with today_tab:
    daily_chart, critique_panel = st.columns([3, 2], vertical_alignment="top")
    with daily_chart:
        with st.container(border=True):
            render_section_heading(
                "Macronutrient balance",
                "Grams of protein, carbohydrates and fat logged today.",
                icon=":material/bar_chart:",
            )
            st.bar_chart(
                [
                    {"Macronutrient": "Protein", "Grams": totals["protein"]},
                    {"Macronutrient": "Carbohydrates", "Grams": totals["carbs"]},
                    {"Macronutrient": "Fat", "Grams": totals["fat"]},
                ],
                x="Macronutrient",
                y="Grams",
                x_label="Macronutrient",
                y_label="Grams logged today",
            )
    with critique_panel:
        with st.container(border=True):
            render_section_heading(
                "Nutrition critique",
                "AI feedback on today's intake. Informational only; it does not replace professional advice.",
                icon=":material/clinical_notes:",
            )
            generate_report = st.button(
                "Synthesize nutrition report",
                type="primary",
                icon=":material/auto_awesome:",
                width="stretch",
            )
    if generate_report:
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
        with st.container(border=True):
            render_ai_answer(
                report,
                caption=f"Based on today's logged intake and your {assessment['goal'].lower()} goal.",
            )

with profile_tab:
    render_section_heading(
        "Profile estimates",
        "BMI reference ranges and calorie needs are approximate.",
        icon=":material/person:",
    )
    render_metric_row(
        [
            ("Current weight", f"{float(profile['weight_kg']):.1f} kg"),
            ("BMI", f"{assessment['bmi']:.1f}"),
            ("BMR estimate", f"{assessment['bmr_kcal']:.0f} kcal/day"),
            (
                "Target weight range",
                f"{assessment['target_weight_min_kg']:.1f}-"
                f"{assessment['target_weight_max_kg']:.1f} kg",
            ),
            ("Suggested goal", assessment["goal"]),
            ("Daily calorie target", f"{assessment['daily_calorie_limit_kcal']} kcal/day"),
        ]
    )
    if profile.get("sex_for_bmr") not in ("male", "female"):
        st.caption(
            "Because no optional BMR sex input was provided, BMR and calorie target "
            "use a rough midpoint of the two standard Mifflin-St Jeor estimates."
        )
    with st.container(border=True):
        render_ai_answer(assessment["explanation"])

with history_tab:
    render_section_heading(
        "Recent daily history",
        "Review your logged meals alongside the calorie trend.",
        icon=":material/history:",
    )
    try:
        history = database.get_daily_history(user_id)
    except MySQLError as error:
        st.error(f"Unable to load your meal history: {error}")
    else:
        if history:
            history_columns, chart_columns = st.columns([3, 2], vertical_alignment="top")
            with history_columns:
                with st.container(border=True):
                    st.dataframe(history, hide_index=True, width="stretch")
            with chart_columns:
                with st.container(border=True):
                    st.caption("Calorie trend")
                    st.line_chart(
                        sorted(history, key=lambda entry: entry["log_date"]),
                        x="log_date",
                        y="calories",
                        x_label="Date",
                        y_label="Calories",
                    )
        else:
            st.info(
                "Your meals will appear here after you log them.",
                icon=":material/info:",
            )
