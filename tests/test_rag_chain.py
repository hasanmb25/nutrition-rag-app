import unittest
from unittest.mock import patch

from langchain_core.runnables import RunnableLambda

import rag_chain


class ClinicalCritiqueChainTests(unittest.TestCase):
    def test_critique_uses_profile_goal_and_calorie_target(self):
        captured_prompts = []
        fake_model = RunnableLambda(
            lambda prompt_value: (
                captured_prompts.append(prompt_value.to_messages()[0].content)
                or "Your logged macros could include more varied whole foods."
            )
        )
        inputs = {
            "calories": 1850,
            "protein": 90,
            "carbs": 210,
            "fat": 60,
            "daily_calorie_target": 2200,
            "goal": "Calorie deficit",
        }

        with patch.object(rag_chain, "llm_pro", fake_model):
            report = rag_chain.get_clinical_critique_chain().invoke(inputs)

        self.assertIn("Calorie deficit", report)
        self.assertIn("1850 kcal", report)
        self.assertIn("2200 kcal", report)
        self.assertIn("Your logged macros", report)
        self.assertNotIn("2200", captured_prompts[0])
        self.assertNotIn("1850", captured_prompts[0])
        self.assertNotIn("2000 calories", report)

    def test_zero_logged_calories_are_not_reported_as_no_food_or_deficiency(self):
        fake_model = RunnableLambda(lambda _: "Your intake is critically deficient.")
        inputs = {
            "calories": 0,
            "protein": 0,
            "carbs": 0,
            "fat": 0,
            "daily_calorie_target": 2200,
            "goal": "Calorie deficit",
        }

        with patch.object(rag_chain, "llm_pro", fake_model):
            report = rag_chain.get_clinical_critique_chain().invoke(inputs)

        self.assertIn("No meals are logged today (0 kcal logged)", report)
        self.assertIn("2200 kcal", report)
        self.assertNotIn("critically deficient", report)


if __name__ == "__main__":
    unittest.main()
