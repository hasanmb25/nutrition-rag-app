from langchain_core.exceptions import OutputParserException
from langchain_core.prompts import ChatPromptTemplate
from openai import OpenAIError
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, ValidationError

from account_security import ACTIVITY_FACTORS
from config import Config


class NutritionAssessmentError(ValueError):
    """Raised when the model cannot produce a profile explanation."""


class NutritionExplanation(BaseModel):
    explanation: str = Field(description="A short, cautious, non-clinical explanation.")


def _expected_assessment(profile):
    height_inches = profile["height_ft"] * 12 + profile["height_in"]
    height_cm = height_inches * 2.54
    height_m = height_cm / 100
    weight_kg = float(profile["weight_kg"])
    bmi = weight_kg / (height_m * height_m)
    target_weight_min = 18.5 * height_m * height_m
    target_weight_max = 24.9 * height_m * height_m

    sex_for_bmr = profile.get("sex_for_bmr")
    if sex_for_bmr == "male":
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * profile["age"] + 5
    elif sex_for_bmr == "female":
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * profile["age"] - 161
    else:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * profile["age"] - 78

    if bmi < 18.5:
        goal = "Calorie surplus"
    elif bmi > 24.9:
        goal = "Calorie deficit"
    else:
        goal = "Maintenance"

    maintenance = bmr * ACTIVITY_FACTORS[profile["activity_level"]]
    if goal == "Calorie surplus":
        calorie_limit = round(maintenance + 250)
    elif goal == "Calorie deficit":
        calorie_limit = round(max(bmr, maintenance - 300))
    else:
        calorie_limit = round(maintenance)

    return {
        "bmi": bmi,
        "bmr_kcal": bmr,
        "target_weight_min_kg": target_weight_min,
        "target_weight_max_kg": target_weight_max,
        "goal": goal,
        "daily_calorie_limit_kcal": calorie_limit,
    }


def assessment_with_explanation(profile, explanation):
    """Combine locally calculated numeric estimates with explanatory text."""
    if not explanation or not explanation.strip():
        raise NutritionAssessmentError("The nutrition estimate explanation was empty.")
    return {**_expected_assessment(profile), "explanation": explanation.strip()}


def normalize_assessment(profile, saved_assessment):
    """Refresh saved numeric values from the current profile and local formulas."""
    explanation = saved_assessment.get("explanation", "")
    return assessment_with_explanation(profile, explanation)


def generate_assessment(profile):
    """Calculate numeric estimates locally and ask GPT for a concise explanation."""
    height_inches = profile["height_ft"] * 12 + profile["height_in"]
    estimates = _expected_assessment(profile)
    model_inputs = {
        "age_years": profile["age"],
        "sex_for_bmr": profile.get("sex_for_bmr"),
        "height_inches": height_inches,
        "height_cm": height_inches * 2.54,
        "weight_kg": float(profile["weight_kg"]),
        "activity_level": profile["activity_level"],
        **estimates,
    }
    prompt = """
You provide general wellness information, not medical advice or a diagnosis.
Write a brief, supportive explanation of the already-calculated estimates
provided by the user. Do not recalculate or change any number, and do not
infer identifying details. If the BMR method uses an average because no
optional sex input was provided, clearly call it a rough midpoint estimate.
Mention that the BMI-based goal and calorie target are approximate.
"""
    prompt_template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                prompt,
            ),
            ("human", "{profile}"),
        ]
    )
    model = ChatOpenAI(
        model="gpt-4o-mini",
        api_key=Config.OPENAI_API_KEY,
        temperature=0,
    ).with_structured_output(NutritionExplanation)
    try:
        result = (prompt_template | model).invoke(
            {"profile": model_inputs},
            config={"run_name": "nutrition_profile_estimate"},
        )
        explanation = (
            result.explanation
            if isinstance(result, NutritionExplanation)
            else NutritionExplanation.model_validate(result).explanation
        )
    except (OpenAIError, OutputParserException, ValidationError) as error:
        raise NutritionAssessmentError(
            "The AI explanation could not be generated or parsed."
        ) from error

    return assessment_with_explanation(profile, explanation)
