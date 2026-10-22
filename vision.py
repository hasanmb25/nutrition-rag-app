import base64
import os
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from config import Config

# 1. Define our strict output schema using Pydantic
# This forces the LLM to return exactly the data structure we need for our MySQL database.
class FoodItem(BaseModel):
    food_name: str = Field(description="Name of the specific food item")
    weight_g: float = Field(description="Estimated weight in grams")
    calories: float = Field(description="Estimated total calories")
    protein: float = Field(description="Estimated protein in grams")
    carbs: float = Field(description="Estimated carbohydrates in grams")
    fat: float = Field(description="Estimated fat in grams")

class MealAnalysis(BaseModel):
    items: list[FoodItem] = Field(description="List of all distinct food items identified in the image")

# 2. Initialize the LLM with structured output capabilities
# We use gpt-4o-mini as it is extremely fast and cost-effective for vision tasks.
llm = ChatOpenAI(model="gpt-4o-mini", api_key=Config.OPENAI_API_KEY, temperature=0.0)
structured_vision_llm = llm.with_structured_output(MealAnalysis)

def encode_image(image_path: str) -> str:
    """Helper function to encode a local image into base64 for the OpenAI API."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def analyze_meal_image(image_path: str) -> MealAnalysis:
    """
    Takes an image path, encodes it, and sends it to the vision model 
    to extract structured nutritional data.
    """
    try:
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found at path: {image_path}")

        base64_image = encode_image(image_path)

        # LangChain v0.3+ syntax for passing images to chat models
        message = HumanMessage(
            content=[
                {
                    "type": "text", 
                    "text": (
                        "You are a clinical nutritionist AI. Analyze this image of a meal. "
                        "Identify each distinct food item, estimate its portion size in grams, "
                        "and provide a highly accurate estimation of calories, protein, carbs, and fat. "
                        "If it is a receipt, parse the grocery items and estimate macros per standard serving."
                    )
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                },
            ]
        )

        print("Analyzing image... This may take a few seconds.")
        # Invoke the chain. The output will automatically be a parsed MealAnalysis Pydantic object.
        result = structured_vision_llm.invoke([message])
        return result

    except Exception as e:
        print(f"❌ Error during image analysis: {e}")
        return None

# Quick test execution block
if __name__ == "__main__":
    # To test this, you will need a sample image in your project folder.
    # Let's assume you place a file named "sample_plate.jpg" in the root directory.
    test_image_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_plate.jpg")
    
    if os.path.exists(test_image_path):
        print(f"Testing vision parser with {test_image_path}...")
        analysis = analyze_meal_image(test_image_path)
        
        if analysis:
            print("\n✅ Successfully Parsed Meal:")
            for item in analysis.items:
                print(f"- {item.food_name} ({item.weight_g}g): {item.calories} kcal "
                      f"| P: {item.protein}g | C: {item.carbs}g | F: {item.fat}g")
    else:
        print(f"⚠️ Skipping test: No image found at {test_image_path}.")
        print("To test, place an image named 'sample_plate.jpg' in the root directory and run this script again.")