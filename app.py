import streamlit as st

st.set_page_config(
    page_title="Nutrify | AI Assistant",
    page_icon="🥗",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        h1 {
            font-size: 3.5rem !important;
            font-weight: 800 !important;
            color: #27ae60 !important;
            margin-bottom: 0rem !important;
        }

        h2 {
            font-size: 2.2rem !important;
            font-weight: 700 !important;
            padding-top: 1rem !important;
        }

        .subtitle {
            font-size: 1.3rem !important;
            color: #555555;
            margin-bottom: 2rem !important;
        }

        div[data-testid="stMetricValue"] {
            font-size: 3rem !important;
            color: #27ae60 !important;
            font-weight: 700 !important;
        }

        p, li {
            font-size: 1.15rem !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown("<h1>🥗 Nutrify</h1>", unsafe_allow_html=True)
st.markdown(
    '<p class="subtitle">Your Multimodal AI Nutrition Assistant. '
    "Track meals, generate recipes, and get health critiques.</p>",
    unsafe_allow_html=True,
)


def render_home():
    st.header("Welcome to Nutrify")
    st.write("Choose a page to get started.")

    destinations = [
        (
            dashboard_page,
            "View your daily calories and macros, and generate a nutrition critique.",
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

    columns = st.columns(3)
    for column, (page, description) in zip(columns, destinations):
        with column:
            with st.container(border=True):
                st.subheader(page.title)
                st.write(description)
                st.page_link(
                    page,
                    label=f"Open {page.title}",
                    icon=page.icon,
                    width="stretch",
                )


home_page = st.Page(render_home, title="Home", icon="🏠", default=True)
dashboard_page = st.Page(
    "views/dashboard.py",
    title="Dashboard",
    icon="📊",
)
meal_page = st.Page(
    "views/log_meal.py",
    title="Log a Meal",
    icon="📸",
)
recipe_page = st.Page(
    "views/recipe_ai.py",
    title="Recipe AI",
    icon="🍳",
)

navigation = st.navigation(
    [home_page, dashboard_page, meal_page, recipe_page],
    position="sidebar",
    expanded=True,
)
navigation.run()
