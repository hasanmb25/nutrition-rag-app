import math
from typing import Literal

from langchain_core.exceptions import OutputParserException
from langchain_core.prompts import ChatPromptTemplate
from openai import OpenAIError
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, ValidationError

from account_security import ACTIVITY_FACTORS
from config import Config


class NutritionAssessmentError(ValueError):
    """Raised when the model returns an invalid or inconsistent assessment."""


class NutritionAssessment(BaseModel):
    bmi: float = Field(description="Body mass index in kg/m^2.")
    bmr_kcal: float | None = Field(
        description="Estimated basal metabolic rate in kcal/day, or null if sex input is absent."
    )
    target_weight_min_kg: float = Field(description="Lower BMI-reference weight in kg.")
    target_weight_max_kg: float = Field(description="Upper BMI-reference weight in kg.")
    goal: Literal["Calorie surplus", "Maintenance", "Calorie deficit"]
    daily_calorie_limit_kcal: int | None = Field(
        description="Estimated daily calorie target in kcal, or null if BMR is unavailable."
    )
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
        bmr = None

    if bmi < 18.5:
        goal = "Calorie surplus"
    elif bmi > 24.9:
        goal = "Calorie deficit"
    else:
        goal = "Maintenance"

    calorie_limit = None
    if bmr is not None:
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


def _check_number(field, actual, expected, tolerance):
    if expected is None:
        if actual is not None:
            raise NutritionAssessmentError(
                f"The model returned {field} without the required BMR input."
            )
        return
    if (
        actual is None
        or not math.isfinite(float(actual))
        or abs(float(actual) - expected) > tolerance
    ):
        raise NutritionAssessmentError(
            f"The model's {field} did not match the validated estimate."
        )


def _validate_assessment(assessment, expected):
    _check_number("BMI", assessment.bmi, expected["bmi"], 0.15)
    _check_number("BMR", assessment.bmr_kcal, expected["bmr_kcal"], 5)
    _check_number(
        "minimum target weight",
        assessment.target_weight_min_kg,
        expected["target_weight_min_kg"],
        0.2,
    )
    _check_number(
        "maximum target weight",
        assessment.target_weight_max_kg,
        expected["target_weight_max_kg"],
        0.2,
    )
    _check_number(
        "daily calorie limit",
        assessment.daily_calorie_limit_kcal,
        expected["daily_calorie_limit_kcal"],
        25,
    )
    if assessment.goal != expected["goal"]:
        raise NutritionAssessmentError(
            "The model's goal did not match the validated BMI-based goal."
        )
    if assessment.target_weight_min_kg > assessment.target_weight_max_kg:
        raise NutritionAssessmentError("The model returned an invalid target-weight range.")
    if not assessment.explanation.strip():
        raise NutritionAssessmentError("The model returned no explanation.")
    return assessment.model_dump()


def generate_assessment(profile):
    """Ask GPT for structured health estimates and verify all numeric values."""
    height_inches = profile["height_ft"] * 12 + profile["height_in"]
    model_inputs = {
        "age_years": profile["age"],
        "sex_for_bmr": profile.get("sex_for_bmr"),
        "height_inches": height_inches,
        "height_cm": height_inches * 2.54,
        "weight_kg": float(profile["weight_kg"]),
        "activity_level": profile["activity_level"],
    }
    prompt = """
You provide general wellness estimates, not medical advice or a diagnosis.
Calculate a structured profile assessment using the supplied values and these
fixed rules:
- BMI = weight in kg / height in meters squared.
- Use the Mifflin-St Jeor equation for BMR: for male input,
  10*weight_kg + 6.25*height_cm - 5*age_years + 5; for female input, use
  the same equation with -161 instead of +5.
- If sex_for_bmr is null, return null for both bmr_kcal and
  daily_calorie_limit_kcal. Do not infer it from gender identity.
- The reference target-weight range is the weight corresponding to BMI 18.5
  through 24.9 at the supplied height.
- Activity multipliers are sedentary 1.2, lightly active 1.375,
  moderately active 1.55, very active 1.725, and extra active 1.9.
- BMI below 18.5 maps to "Calorie surplus" and a target of estimated
  maintenance calories + 250. BMI from 18.5 through 24.9 maps to
  "Maintenance" and estimated maintenance calories. BMI above 24.9 maps to
  "Calorie deficit" and estimated maintenance calories - 300, not below BMR.
- Estimated maintenance calories equal BMR times the activity multiplier.
Return the requested fields accurately, with a short, cautious explanation.
Do not mention or infer identifying details.
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
    ).with_structured_output(NutritionAssessment)
    try:
        result = (prompt_template | model).invoke(
            {"profile": model_inputs},
            config={"run_name": "nutrition_profile_estimate"},
        )
        assessment = (
            result
            if isinstance(result, NutritionAssessment)
            else NutritionAssessment.model_validate(result)
        )
    except (OpenAIError, OutputParserException, ValidationError) as error:
        raise NutritionAssessmentError(
            "The nutrition estimate could not be generated or parsed. Please try again."
        ) from error

    return _validate_assessment(assessment, _expected_assessment(profile))
