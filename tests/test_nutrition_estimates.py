import unittest
from unittest.mock import patch

from langchain_core.runnables import RunnableLambda

from nutrition_estimates import (
    NutritionAssessment,
    NutritionAssessmentError,
    _expected_assessment,
    _validate_assessment,
    generate_assessment,
)


PROFILE = {
    "age": 30,
    "gender_identity": "Woman",
    "sex_for_bmr": "male",
    "height_ft": 5,
    "height_in": 8,
    "weight_kg": 70.0,
    "activity_level": "Moderately active",
    "profession": "Student",
}


def assessment_from_expected(expected):
    return NutritionAssessment(
        **{
            **expected,
            "bmi": round(expected["bmi"], 1),
            "bmr_kcal": round(expected["bmr_kcal"]),
            "target_weight_min_kg": round(expected["target_weight_min_kg"], 1),
            "target_weight_max_kg": round(expected["target_weight_max_kg"], 1),
            "explanation": "These are general estimates, not medical advice.",
        }
    )


class NutritionEstimatesTests(unittest.TestCase):
    def test_expected_calculations_use_profile_height_weight_and_activity(self):
        expected = _expected_assessment(PROFILE)

        self.assertAlmostEqual(expected["bmi"], 23.46, places=2)
        self.assertAlmostEqual(expected["bmr_kcal"], 1634.5, places=1)
        self.assertEqual(expected["goal"], "Maintenance")
        self.assertEqual(expected["daily_calorie_limit_kcal"], 2533)
        self.assertAlmostEqual(expected["target_weight_min_kg"], 55.19, places=2)
        self.assertAlmostEqual(expected["target_weight_max_kg"], 74.28, places=2)

    def test_missing_bmr_sex_withholds_bmr_and_calorie_target(self):
        profile = {**PROFILE, "sex_for_bmr": None}

        expected = _expected_assessment(profile)

        self.assertIsNone(expected["bmr_kcal"])
        self.assertIsNone(expected["daily_calorie_limit_kcal"])

    def test_model_values_are_rejected_when_inconsistent(self):
        expected = _expected_assessment(PROFILE)
        response = assessment_from_expected(expected).model_copy(
            update={"bmi": 35.0}
        )

        with self.assertRaisesRegex(NutritionAssessmentError, "BMI"):
            _validate_assessment(response, expected)

    def test_gpt_model_is_used_with_only_required_profile_inputs(self):
        expected = _expected_assessment(PROFILE)
        response = assessment_from_expected(expected)
        captured_messages = []
        model_output = RunnableLambda(
            lambda prompt_value: (
                captured_messages.extend(prompt_value.to_messages()) or response
            )
        )
        model = patch(
            "nutrition_estimates.ChatOpenAI",
            return_value=type(
                "MockChatModel",
                (),
                {
                    "with_structured_output": lambda self, schema: model_output
                },
            )(),
        )

        with model as mock_chat:
            result = generate_assessment(PROFILE)

        self.assertEqual(result["goal"], "Maintenance")
        mock_chat.assert_called_once()
        self.assertEqual(
            mock_chat.call_args.kwargs["model"],
            "gpt-4o-mini",
        )
        prompt_text = "\n".join(message.content for message in captured_messages)
        self.assertIn("age_years", prompt_text)
        self.assertNotIn("gender_identity", prompt_text)
        self.assertNotIn("profession", prompt_text)
        self.assertNotIn("username", prompt_text)


if __name__ == "__main__":
    unittest.main()
