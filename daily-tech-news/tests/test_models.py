import unittest

from models import CATEGORIES, categorize_article, normalize_title_key


class CategorizeArticleTests(unittest.TestCase):
    def test_categorizes_each_category(self) -> None:
        examples = {
            "Agentic AI": "New agentic AI tools help teams",
            "Quantum Computing": "Researchers improve a quantum computer",
            "Cybersecurity": "Ransomware attack affects a company",
            "Cloud": "Cloud computing services add a new feature",
            "AI": "Generative AI changes image editing",
            "Developer Tools": "A new code editor is released",
            "Programming": "Python programming language update",
            "Startups": "Startup announces a Series A funding round",
            "Technology Companies": "Nvidia announces a new product",
            "Other Technology": "A new smartphone display technology",
        }

        for expected_category, title in examples.items():
            with self.subTest(category=expected_category):
                self.assertEqual(categorize_article(title), expected_category)

    def test_agentic_ai_takes_priority_over_general_ai(self) -> None:
        article = "Agentic AI uses artificial intelligence to complete tasks"

        self.assertEqual(categorize_article(article), "Agentic AI")

    def test_short_keywords_do_not_match_inside_other_words(self) -> None:
        self.assertEqual(
            categorize_article("Metadata systems draw new interest"),
            "Other Technology",
        )

    def test_description_is_included_in_categorization(self) -> None:
        self.assertEqual(
            categorize_article("New research published", "The work uses quantum computing."),
            "Quantum Computing",
        )

    def test_categories_are_available_for_api_validation(self) -> None:
        self.assertEqual(CATEGORIES[-1], "Other Technology")
        self.assertEqual(len(CATEGORIES), 10)

    def test_title_key_ignores_case_and_punctuation(self) -> None:
        self.assertEqual(
            normalize_title_key("  New AI: Tools! "),
            "new ai tools",
        )


if __name__ == "__main__":
    unittest.main()
