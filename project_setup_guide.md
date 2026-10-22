# Nutrify: Multimodal AI Nutrition Assistant Setup Guide

Welcome to the Nutrify project! This guide will walk you through setting up the application on a fresh machine after cloning the repository.

## Prerequisites
Before you begin, ensure you have the following installed on your system:
* **Python 3.9+**
* **MySQL Server** (Running locally)
* **Git**

## Step 1: Clone the Repository
Clone the project to your local machine and navigate into the directory:
```bash
git clone https://github.com/yourusername/nutrition-rag-app.git
cd nutrition-rag-app
```

## Step 2: Set Up the Virtual Environment
It is highly recommended to use a virtual environment to manage dependencies.
```bash
# Create the virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

## Step 3: Install Dependencies
Install all required Python packages using the provided requirements file:
```bash
pip install -r requirements.txt
```

## Step 4: Environment Variables
Create a new file named `.env` in the root directory of the project. You must add your OpenAI API key and MySQL credentials:

```env
OPENAI_API_KEY="your_openai_api_key_here"
MYSQL_HOST="localhost"
MYSQL_USER="root"
MYSQL_PASSWORD="your_mysql_password"
MYSQL_DATABASE="nutrition_app"
```
*(Note: Never commit your `.env` file to version control!)*

## Step 5: Database Initialization
Initialize the MySQL database and create the required `daily_logs` table. Our helper script handles this automatically:
```bash
python database.py
```
You should see a success message confirming the database was created.

## Step 6: Build the Vector Database (ChromaDB)
The repository includes a curated `data/recipes.json` seed file. You need to convert this into a local ChromaDB vector database so the RAG (Retrieval-Augmented Generation) system can function:
```bash
python rag_chain.py
```
This script will chunk the recipes, embed them using OpenAI, and create a `chroma_db` folder in your project root.

## Step 7: Launch the Application
You are ready to go! Start the Streamlit frontend:
```bash
streamlit run app.py
```
Your browser will automatically open to `http://localhost:8501`, and you can start logging meals and generating recipes.