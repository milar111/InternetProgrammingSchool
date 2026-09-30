from django.core.management import call_command
from django.test import TestCase

from questions.models import AnswerOption, Category, ChoiceQuestion, NumericQuestion


class FixtureLoadingTests(TestCase):
    fixtures = ["questions/question_bank.json"]

    def test_fixture_counts(self):
        self.assertEqual(Category.objects.count(), 6)
        self.assertEqual(ChoiceQuestion.objects.count(), 12)
        self.assertEqual(AnswerOption.objects.count(), 48)
        self.assertEqual(NumericQuestion.objects.count(), 12)

    def test_fixture_choice_questions_validity(self):
        for question in ChoiceQuestion.objects.all():
            # Validate model clean and full_clean
            question.full_clean()

            # Validate each choice question has exactly four answers
            self.assertEqual(
                question.options.count(),
                4,
                f"Question '{question.text}' does not have exactly 4 answer options.",
            )

            # Validate each choice question has exactly one correct answer
            self.assertEqual(
                question.options.filter(is_correct=True).count(),
                1,
                f"Question '{question.text}' does not have exactly 1 correct answer option.",
            )

            # Validate question text is not empty
            self.assertTrue(len(question.text.strip()) > 0)

            # Validate all options have non-empty text
            for option in question.options.all():
                self.assertTrue(len(option.text.strip()) > 0)
                option.full_clean()

    def test_fixture_numeric_questions_validity(self):
        for question in NumericQuestion.objects.all():
            question.full_clean()

            # Validate question text is not empty
            self.assertTrue(len(question.text.strip()) > 0)

            # Validate correct_answer is an integer
            self.assertIsInstance(question.correct_answer, int)

    def test_fixture_categories_validity(self):
        for category in Category.objects.all():
            category.full_clean()
            self.assertTrue(len(category.name.strip()) > 0)

    def test_loaddata_command_runs_successfully(self):
        # Clear database and test loaddata command explicitly
        AnswerOption.objects.all().delete()
        ChoiceQuestion.objects.all().delete()
        NumericQuestion.objects.all().delete()
        Category.objects.all().delete()

        call_command("loaddata", "questions/question_bank.json")

        self.assertEqual(Category.objects.count(), 6)
        self.assertEqual(ChoiceQuestion.objects.count(), 12)
        self.assertEqual(AnswerOption.objects.count(), 48)
        self.assertEqual(NumericQuestion.objects.count(), 12)
