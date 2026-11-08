import streamlit as st
from mysql.connector import Error as MySQLError

import database
from account_security import (
    ACTIVITY_FACTORS,
    hash_password,
    validate_profile,
    verify_password,
)
from app_services import initialize_database
from frontend import render_brand, render_global_styles, render_page_intro

st.set_page_config(
    page_title="Nutrify | Nutrition intelligence",
    page_icon=":material/nutrition:",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_global_styles()
render_brand()


def render_home():
    render_page_intro(
        "Home",
        "Your nutrition workspace",
        f"Welcome, {st.session_state.get('username', 'Nutrify user')}. "
        "Your account keeps your meal history private.",
        icon=":material/grid_view:",
    )

    destinations = [
        (
            dashboard_page,
            "View your health estimates, daily calories and macros, and generate a nutrition critique.",
        ),
        (
            meal_page,
            "Upload a meal photo and let AI estimate its nutrition.",
        ),
        (
            recipe_page,
            "Find recipe ideas based on your ingredients and dietary preferences.",
        ),
    ]

    columns = st.columns(3, vertical_alignment="top", border=True)
    for column, (page, description) in zip(columns, destinations):
        with column:
            st.subheader(page.title, icon=page.icon)
            st.caption(description)
            st.page_link(
                page,
                label=f"Open {page.title}",
                icon=":material/arrow_forward:",
                width="stretch",
            )


home_page = st.Page(render_home, title="Home", icon=":material/home:")
dashboard_page = st.Page(
    "views/dashboard.py",
    title="Dashboard",
    icon=":material/monitoring:",
    default=True,
)
meal_page = st.Page(
    "views/log_meal.py",
    title="Log a Meal",
    icon=":material/add_a_photo:",
)
recipe_page = st.Page(
    "views/recipe_ai.py",
    title="Recipe AI",
    icon=":material/menu_book:",
)


def render_authentication():
    render_page_intro(
        "Private by design",
        "A clearer view of your nutrition",
        "Sign in or create an account to keep your profile and meal history private.",
        icon=":material/health_and_safety:",
    )

    auth_panel, context_panel = st.columns([3, 2], vertical_alignment="top")
    with auth_panel:
        with st.container(border=True):
            login_tab, register_tab = st.tabs(["Log in", "Create account"])
            with login_tab:
                with st.form("login_form", border=False):
                    login_username = st.text_input("Username")
                    login_password = st.text_input(
                        "Password", type="password", max_chars=128
                    )
                    login_submitted = st.form_submit_button("Log in", type="primary")

            if login_submitted:
                try:
                    user = database.get_user_by_username(login_username.strip())
                except MySQLError as error:
                    st.error(f"Unable to log in because the database request failed: {error}")
                else:
                    if user and verify_password(login_password, user["password_hash"]):
                        st.session_state["user_id"] = user["id"]
                        st.session_state["username"] = user["username"]
                        st.rerun()
                    st.error("The username or password is incorrect.")

            with register_tab:
                with st.form("register_form", border=False):
                    username = st.text_input("Username", key="register_username")
                    password = st.text_input(
                        "Password (at least 10 characters)",
                        type="password",
                        key="register_password",
                        max_chars=128,
                    )
                    confirm_password = st.text_input(
                        "Confirm password",
                        type="password",
                        key="register_password_confirmation",
                        max_chars=128,
                    )
                    age = st.number_input("Age", min_value=18, max_value=120, value=18, step=1)
                    gender_identity = st.text_input(
                        "Gender identity",
                        placeholder="e.g., Woman, Man, Non-binary, or Prefer not to say",
                        max_chars=80,
                    )
                    sex_choice = st.selectbox(
                        "Sex input for BMR estimate (optional)",
                        ["Not provided", "Female", "Male"],
                    )
                    height_col, inches_col = st.columns(2)
                    with height_col:
                        height_ft = st.number_input(
                            "Height (feet)", min_value=3, max_value=8, value=5, step=1
                        )
                    with inches_col:
                        height_in = st.number_input(
                            "Height (additional inches)", min_value=0, max_value=11, value=5, step=1
                        )
                    weight_kg = st.number_input(
                        "Weight (kg)", min_value=25.0, max_value=350.0, value=70.0, step=0.1
                    )
                    activity_level = st.selectbox(
                        "Activity level", list(ACTIVITY_FACTORS.keys())
                    )
                    profession = st.text_input("Profession", max_chars=120)
                    openai_profile_consent = st.checkbox(
                        "I understand Nutrify sends my age, height, weight, activity level, "
                        "and optional BMR sex input to OpenAI to generate my estimates. "
                        "My username, password, gender identity, and profession are not sent."
                    )
                    register_submitted = st.form_submit_button(
                        "Create profile", type="primary"
                    )

            if register_submitted:
                if not openai_profile_consent:
                    st.error(
                        "Consent to OpenAI processing is required to create a profile "
                        "and generate its requested AI estimates."
                    )
                elif password != confirm_password:
                    st.error("The password and confirmation do not match.")
                else:
                    try:
                        clean_username = validate_profile(
                            username,
                            password,
                            int(age),
                            gender_identity,
                            int(height_ft),
                            int(height_in),
                            float(weight_kg),
                            activity_level,
                            profession,
                        )
                        user_id = database.create_user(
                            clean_username,
                            hash_password(password),
                            int(age),
                            gender_identity.strip(),
                            sex_choice.lower() if sex_choice != "Not provided" else None,
                            int(height_ft),
                            int(height_in),
                            float(weight_kg),
                            activity_level,
                            profession.strip(),
                            True,
                        )
                    except ValueError as error:
                        st.error(str(error))
                    except MySQLError as error:
                        st.error(f"Unable to create the account because the database request failed: {error}")
                    else:
                        st.session_state["user_id"] = user_id
                        st.session_state["username"] = clean_username
                        st.rerun()

    with context_panel:
        with st.container(border=True):
            st.subheader("One workspace", icon=":material/monitoring:")
            st.write(
                "Bring your meal history, image analysis, recipe discovery, and daily nutrition into one private view."
            )
            st.caption("Your sign-in keeps the account and meal history scoped to you.")


try:
    initialize_database()
except MySQLError as error:
    st.error(f"Nutrify could not initialize its MySQL database: {error}")
    st.stop()

user_id = st.session_state.get("user_id")
current_user = None
if user_id is not None:
    try:
        current_user = database.get_user_by_id(user_id)
    except MySQLError as error:
        st.error(f"Unable to load the signed-in profile: {error}")
        st.stop()
    if current_user is None:
        st.session_state.pop("user_id", None)
        st.session_state.pop("username", None)

if current_user is None:
    render_authentication()
    st.stop()

navigation = st.navigation(
    [home_page, dashboard_page, meal_page, recipe_page],
    position="top",
)
with st.sidebar:
    st.caption("SIGNED-IN PROFILE")
    st.write(current_user["username"])
    st.caption("Manage navigation from the top bar.")
    if st.button("Log out", width="stretch"):
        st.session_state.pop("user_id", None)
        st.session_state.pop("username", None)
        st.rerun()
navigation.run()
