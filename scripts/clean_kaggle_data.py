import pandas as pd
import ast
import json
import os

def clean_food_com_dataset(csv_path: str, output_path: str, max_recipes: int = 500):
    """
    Reads the raw Food.com Kaggle CSV, extracts vital nutritional data,
    cleans the formatting, and outputs a structured JSON for ChromaDB ingestion.
    """
    print(f"Loading raw dataset from {csv_path}...")
    
    try:
        # -----step_1:loads_specific_csv_columns_to_save_memory---
        # Load the CSV. We only need specific columns to save memory.
        usecols = ['name', 'ingredients', 'steps', 'nutrition', 'tags']
        df = pd.read_csv(csv_path, usecols=usecols)
    except FileNotFoundError:
        print(f"ERROR: Could not find {csv_path}. Please download it and place it in the data folder.")
        return

    # -----step_2:drops_rows_missing_essential_data---
    # Drop any rows with missing essential data
    df = df.dropna(subset=['name', 'ingredients', 'steps', 'nutrition'])
    
    # -----step_3:samples_data_to_limit_api_costs---
    # Shuffle and take a sample. 
    # PRO TIP: We limit to 500-1000 for local testing so we don't spend hours 
    # and dollars embedding 200,000 recipes via the OpenAI API on our first run.
    df = df.sample(n=max_recipes, random_state=42).reset_index(drop=True)
    
    processed_recipes = []
    
    print(f"Processing {max_recipes} recipes...")
    
    for index, row in df.iterrows():
        try:
            # -----step_4:parses_stringified_lists_into_python_objects---
            # Food.com 'nutrition' column is a string representing a list:
            # [calories (#), total fat (PDV), sugar (PDV), sodium (PDV), protein (PDV), saturated fat (PDV), carbohydrates (PDV)]
            # PDV = Percentage Daily Value, but calories is absolute.
            nutrition_list = ast.literal_eval(row['nutrition'])
            calories = float(nutrition_list[0])
            fat = float(nutrition_list[1])
            protein = float(nutrition_list[4])
            carbs = float(nutrition_list[6])
            
            # Ingredients and steps are also stringified lists
            ingredients_list = ast.literal_eval(row['ingredients'])
            steps_list = ast.literal_eval(row['steps'])
            tags_list = ast.literal_eval(row['tags'])[:5] # Keep it to 5 tags max
            
            # -----step_5:maps_extracted_data_to_strict_json_schema---
            # Map to our strict JSON schema
            recipe_doc = {
                "title": str(row['name']).title(),
                "ingredients": ingredients_list,
                "instructions": " ".join(steps_list).capitalize(),
                "macros": {
                    "calories": calories,
                    "protein": protein,
                    "carbs": carbs,
                    "fat": fat
                },
                "tags": tags_list
            }
            processed_recipes.append(recipe_doc)
            
        except (ValueError, SyntaxError, IndexError) as e:
            # Skip rows with malformed data strings
            continue

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # -----step_6:saves_processed_recipes_to_json_file---
    # Save to JSON
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(processed_recipes, f, indent=4)
        
    print(f"✅ Successfully cleaned and saved {len(processed_recipes)} recipes to {output_path}")

if __name__ == "__main__":
    # Define file paths dynamically based on this script's location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    RAW_CSV_PATH = os.path.join(script_dir, "../data/RAW_recipes.csv")
    OUTPUT_JSON_PATH = os.path.join(script_dir, "../data/recipes.json")
    
    # You can increase max_recipes later once the RAG pipeline is tested and working!
    clean_food_com_dataset(RAW_CSV_PATH, OUTPUT_JSON_PATH, max_recipes=500)