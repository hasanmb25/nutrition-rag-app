# Nutrify

Nutrify is a Streamlit nutrition assistant for logging meals from photos,
tracking daily macros, and finding recipes based on available ingredients.
Accounts keep each user's profile and meal history separate.

## Project structure

```text
.
|-- app.py                  # Home page and Streamlit navigation
|-- app_services.py         # Shared database and vector-store setup
|-- views/                  # Dashboard, meal logging, and recipe pages
|-- data/recipes.json       # Recipe data used to build the vector database
|-- database.py             # MySQL setup and meal logging
|-- account_security.py     # Profile validation and password hashing
|-- nutrition_estimates.py  # GPT profile estimates and numeric validation
|-- rag_chain.py            # Recipe search and nutrition critique chains
|-- vision.py               # Meal image analysis
|-- config.py               # Environment variable loading
|-- requirements.txt        # Python dependencies
`-- .streamlit/config.toml   # Streamlit theme
```

## Setup

Requirements: Python 3.10+, a running MySQL server, and an OpenAI API key.

Create and activate a virtual environment:

```bash
python -m venv venv
# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# macOS/Linux:
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```text
OPENAI_API_KEY=your_openai_api_key
MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password
MYSQL_DATABASE=nutrition_app
```

The `.env` file contains secrets and should not be committed. The app creates
the database and account/profile tables on startup. Existing `daily_logs` rows
are preserved and assigned to the first account that is created; subsequent
meal rows belong to the currently signed-in account. Dashboard totals are
filtered to the current date, while the underlying rows and recent daily
history remain available to that account.

Create an account with a unique username and password, then enter age, gender
identity, height, weight, activity level, and profession. Profile
recommendations require an age of at least 18. A separate, optional sex input
is used only for the sex-specific BMR estimate. If it is not provided, Nutrify
shows a clearly labeled midpoint of the male/female Mifflin-St Jeor estimates
instead of inferring sex from gender identity.

Nutrify calculates BMI, BMR, target-weight range, goal, and daily calorie
target using local formulas, then uses `gpt-4o-mini` with `OPENAI_API_KEY` to
explain those values. This keeps numerical results consistent and available
even if the model's calculation differs or the AI explanation is temporarily
unavailable. Users must consent during account creation. The model receives
age, height, weight, activity level, and the optional BMR sex input; it does
not receive usernames, passwords, gender identity, or profession. The results
are informational estimates, not medical advice or a diagnosis.

The local Chroma vector database is created from `data/recipes.json` the first
time you generate a recipe. This requires your OpenAI API key.

The dashboard's synthesized daily report compares logged calories with the
signed-in user's estimated daily calorie target and BMI-based suggested goal,
instead of applying the same generic calorie benchmark to every account.

## Run the app

```bash
streamlit run app.py
```

Open the local URL printed in your terminal. Use the sidebar to move between
the Dashboard, Log a Meal, and Recipe AI pages.

Run the focused account, data-isolation, and estimate tests with:

```bash
python -m unittest discover -s tests -v
```