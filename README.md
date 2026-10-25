# Nutrify

Nutrify is a Streamlit nutrition assistant for logging meals from photos,
tracking daily macros, and finding recipes based on available ingredients.

## Project structure

```text
.
|-- app.py                  # Home page and Streamlit navigation
|-- app_services.py         # Shared database and vector-store setup
|-- views/                  # Dashboard, meal logging, and recipe pages
|-- data/recipes.json       # Recipe data used to build the vector database
|-- database.py             # MySQL setup and meal logging
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
the database and meal-log table when you open the Dashboard or Log a Meal page.

The local Chroma vector database is created from `data/recipes.json` the first
time you generate a recipe. This requires your OpenAI API key.

## Run the app

```bash
streamlit run app.py
```

Open the local URL printed in your terminal. Use the sidebar to move between
the Dashboard, Log a Meal, and Recipe AI pages.