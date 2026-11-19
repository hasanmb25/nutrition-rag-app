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
|-- nutrition_estimates.py  # AI profile explanation and numeric estimates
|-- rag_chain.py            # Recipe search and nutrition critique chains
|-- vision.py               # Meal image analysis
|-- ai_models.py            # Builds the AI clients for the active provider
|-- config.py               # Environment variables, provider and model names
|-- requirements.txt        # Python dependencies
`-- .streamlit/config.toml   # Streamlit theme
```

## Setup

Requirements: Python 3.10+, a running MySQL server, and one AI key: an OpenAI
API key, a free Google Gemini API key (https://aistudio.google.com/apikey), or a
Hugging Face token with the "Inference Providers" permission.

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

Create a `.env` file in the project root (see `.env.example`):

```text
AI_PROVIDER=openai          # or: gemini, huggingface, ollama
OPENAI_API_KEY=your_openai_api_key
GOOGLE_API_KEY=your_google_api_key
HF_TOKEN=your_huggingface_token
MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password
MYSQL_DATABASE=nutrition_app
```

## Choosing the AI provider and models

Every AI feature (meal photo analysis, recipe recommendations, the dashboard
report and the profile explanation) uses one provider, set by `AI_PROVIDER` in
`.env`. Only the key for that provider is required. Restart Streamlit after
changing it.

Model names are all in `config.py`, in `Config.MODELS`. To swap a model, edit
its name there and restart the app. Hugging Face models must be served by an
Inference Provider; if one fails, pick another model from
https://huggingface.co/models?inference_provider=all. Vision needs a model that
accepts images.

### Running on free local models (Ollama)

`AI_PROVIDER=ollama` runs every AI feature on your own GPU at no cost. The
default models (`gemma3:12b` for everything, `nomic-embed-text` for recipe
search) fit on a 12 GB card such as an RTX 3060.

1. Install Ollama from https://ollama.com/download and start it.
2. Download the models:

   ```bash
   ollama pull gemma3:12b
   ollama pull nomic-embed-text
   ```

3. In `.env`:

   ```env
   AI_PROVIDER=ollama
   OLLAMA_BASE_URL=http://localhost:11434   # optional, this is the default
   FALLBACK_PROVIDER=gemini                 # used if Ollama is unavailable
   GOOGLE_API_KEY=your_google_key           # needed for the fallback
   ```

When the app starts it checks that Ollama is reachable and that every model in
`Config.MODELS["ollama"]` is downloaded. If not, it switches to
`FALLBACK_PROVIDER` and the sidebar shows which provider is active and why. The
check runs once per start, so restart Streamlit after starting Ollama. The first
recipe request builds `chroma_db_ollama_nomic_embed_text/` locally.

**Using the main PC's GPU from another computer.** A low-end PC on the same
network can use the main PC's Ollama instead of installing models:

1. On the main PC, set the Windows environment variable `OLLAMA_HOST=0.0.0.0`,
   then quit and restart Ollama.
2. Allow inbound TCP port 11434 in Windows Defender Firewall (private networks
   only).
3. On the other PC, set `OLLAMA_BASE_URL=http://<main-PC-LAN-IP>:11434` in `.env`
   (find the IP with `ipconfig`).

Ollama has no password, so only expose it on a trusted home network. If the
main PC is off, the other PC falls back to Gemini automatically.

**Online deployment.** Free hosts (Streamlit Community Cloud, Hugging Face
Spaces) cannot run local models: set `AI_PROVIDER=gemini` there, using the host's
secrets/environment settings instead of `.env`. The committed
`chroma_db_gemini_*` folder means the deployed app doesn't re-embed the recipes.

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
time you generate a recipe, using the active provider's embedding model. Each
embedding model gets its own folder (`chroma_db/` for the default OpenAI model,
`chroma_db_gemini_<model>/` for Gemini, `chroma_db_hf_<model>/` for Hugging Face,
`chroma_db_ollama_<model>/` for Ollama).

The dashboard's synthesized daily report compares logged calories with the
signed-in user's estimated daily calorie target and BMI-based suggested goal,
instead of applying the same generic calorie benchmark to every account.

## Presentation demo account

From the project root, run:

```bash
python -m scripts.seed_presentation_demo
```

The script creates a fictional `nutrifyuser` profile and prompts
for a password and confirmation before creating it. It also asks for explicit
consent before saving the profile with OpenAI processing enabled. Keep the
password you choose; it is not stored in the repository or printed by the
script. If this demo account already exists, the script preserves its profile
and password.

The seeder adds synthetic meals for today and the previous six days. Re-running
it replaces only its marked meal rows for the demo account, so today's dashboard
totals and recent-history charts remain populated without duplicating data.
It does not modify user ID 1 or any other account. Sign in to the app with
`nutrifyuser` and the password you set. An OpenAI API key is needed
for AI-generated profile explanations and the synthesized nutrition report;
the dashboard can still show formula-based estimates if the AI explanation is
unavailable.

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