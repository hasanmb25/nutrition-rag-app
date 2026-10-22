import os
import json
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from operator import itemgetter
from config import Config

# Constants for our Vector DB
CHROMA_DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_db")
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "recipes.json")

# -----step_1:initializes_openai_embedding_model---
# Strict LangChain v0.3+ syntax for OpenAI embeddings
embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
    api_key=Config.OPENAI_API_KEY
)

def build_or_load_vector_store():
    """
    Loads recipes from JSON, chunks them optimally, attaches metadata, 
    and initializes the Chroma vector store.
    """
    # -----step_2:loads_existing_chromadb_if_found_on_disk---
    # If the database already exists on disk, just load and return it
    if os.path.exists(CHROMA_DB_DIR) and os.listdir(CHROMA_DB_DIR):
        print(f"Loading existing ChromaDB from {CHROMA_DB_DIR}...")
        try:
            return Chroma(
                persist_directory=CHROMA_DB_DIR, 
                embedding_function=embeddings
            )
        except Exception as e:
            print(f"Error loading ChromaDB: {e}")
            print("HINT: If you changed embedding models, delete the 'chroma_db' folder and rerun.")
            return None

    # -----step_3:loads_parsed_json_recipes_for_ingestion---
    # Otherwise, we need to ingest the data for the first time
    print(f"No existing ChromaDB found. Ingesting data from {DATA_FILE}...")
    
    if not os.path.exists(DATA_FILE):
        raise FileNotFoundError(f"Missing {DATA_FILE}. Please run the scraper first.")

    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        recipes = json.load(f)

    documents = []
    
    for recipe in recipes:
        # -----step_4:combines_text_and_attaches_explicit_metadata---
        # Combine highly relevant text for the vector search
        content = f"Title: {recipe['title']}\nIngredients: {', '.join(recipe['ingredients'])}\nInstructions: {recipe['instructions']}"
        
        # Explicit metadata tracking for precise filtering later
        metadata = {
            "title": recipe["title"],
            "calories": float(recipe["macros"]["calories"]),
            "protein": float(recipe["macros"]["protein"]),
            "carbs": float(recipe["macros"]["carbs"]),
            "fat": float(recipe["macros"]["fat"]),
            "tags": ", ".join(recipe["tags"]) 
        }
        
        documents.append(Document(page_content=content, metadata=metadata))

    # -----step_5:splits_documents_into_manageable_chunks_with_overlap---
    # We use a larger chunk size to try and keep the whole recipe intact, 
    # but overlap helps if a very long recipe gets split.
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, 
        chunk_overlap=150,
        separators=["\n\n", "\n", ".", " "]
    )
    
    chunked_docs = text_splitter.split_documents(documents)
    print(f"Split {len(recipes)} recipes into {len(chunked_docs)} chunks.")

    try:
        # -----step_6:creates_and_saves_chromadb_vector_store---
        vector_store = Chroma.from_documents(
            documents=chunked_docs,
            embedding=embeddings,
            persist_directory=CHROMA_DB_DIR
        )
        print("✅ Successfully created and saved ChromaDB!")
        return vector_store
    except Exception as e:
        print(f"❌ Failed to create ChromaDB. Error: {e}")
        return None

# -----step_7:initializes_llms_for_generation_and_critique---
# Initialize our LLMs strictly using the v0.3+ ChatOpenAI
llm_mini = ChatOpenAI(model="gpt-4o-mini", api_key=Config.OPENAI_API_KEY, temperature=0.7)
llm_pro = ChatOpenAI(model="gpt-4o", api_key=Config.OPENAI_API_KEY, temperature=0.3)

def format_docs(docs):
    """Helper to format retrieved documents for the prompt."""
    return "\n\n".join(doc.page_content for doc in docs)

def get_recipe_recommendation_chain(vector_store):
    """
    Chain A: Pantry-to-Recipe using RAG.
    Takes user ingredients, dietary preferences, and retrieves relevant recipes.
    """
    # -----step_8:sets_up_vector_retriever_for_top_3_results---
    # k=3 retrieves the top 3 most relevant recipe chunks
    retriever = vector_store.as_retriever(search_type="similarity", search_kwargs={"k": 3})
    
    # Updated Prompt to include dynamic user controls
    prompt = PromptTemplate.from_template(
        "You are a helpful culinary AI. Based on the user's available ingredients, recommend a recipe and it's macros from the provided context. "
        "If they are missing a minor ingredient, suggest a smart substitution.\n\n"
        "Consider their specific preferences:\n"
        "- Cuisine Style: {cuisine}\n"
        "- Dietary Goal: {diet_goal}\n"
        "(Note: If a preference is set to 'Flexible', you have full independence to choose the best fit based purely on ingredients).\n\n"
        "Context (Available Recipes):\n{context}\n\n"
        "User's Available Ingredients/Request: {question}\n\n"
        "Recommendation:"
    )
    
    # -----step_9:builds_rag_chain_with_context_and_prompt---
    # Strictly modern LCEL syntax using itemgetter to route multiple variables
    rag_chain = (
        {
            "context": itemgetter("question") | retriever | format_docs, 
            "question": itemgetter("question"),
            "cuisine": itemgetter("cuisine"),
            "diet_goal": itemgetter("diet_goal")
        }
        | prompt
        | llm_mini
        | StrOutputParser()
    )
    
    return rag_chain

def get_clinical_critique_chain():
    """
    Chain B: Clinical Critique using gpt-4o.
    Takes the user's daily totals and outputs a health synthesis. No vector retrieval needed here.
    """
    # -----step_10:builds_critique_chain_without_vector_retrieval---
    prompt = PromptTemplate.from_template(
        "You are a strict but supportive clinical nutritionist AI. "
        "Analyze the user's daily macro intake against standard daily goals (e.g., 2000 calories, 150g protein, 250g carbs, 65g fat).\n\n"
        "User's Logged Totals Today:\n"
        "Calories: {calories} kcal\n"
        "Protein: {protein} g\n"
        "Carbs: {carbs} g\n"
        "Fat: {fat} g\n\n"
        "Provide a concise, professional evaluation of their intake. Highlight any deficiencies or excesses and offer brief, actionable advice."
    )
    
    critique_chain = (
        prompt
        | llm_pro
        | StrOutputParser()
    )
    return critique_chain

# Quick test execution block
if __name__ == "__main__":
    # -----step_11:executes_pipeline_and_tests_rag_chain_locally---
    db = build_or_load_vector_store()
    if db:
        print(f"Vector store ready. Total vectors: {db._collection.count()}")
        print("\n--- Testing RAG Chain with Preferences ---")
        chain = get_recipe_recommendation_chain(db)
        
        # Test our new parameters
        test_inputs = {
            "question": "I have chicken, spinach, turmeric, and rice.",
            "cuisine": "Bangladeshi",
            "diet_goal": "High Protein"
        }
        
        print(f"Query: {test_inputs['question']}")
        print(f"Cuisine: {test_inputs['cuisine']} | Goal: {test_inputs['diet_goal']}")
        print("Generating response...\n")
        
        response = chain.invoke(test_inputs)
        print(f"Response:\n{response}")