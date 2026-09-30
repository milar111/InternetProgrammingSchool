from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.test import TestCase

from questions.models import AnswerOption, Category, ChoiceQuestion, NumericQuestion


class CategoryModelTests(TestCase):
    def test_create_category_with_valid_name(self):
        category = Category.objects.create(name="История")
        self.assertEqual(category.name, "История")
        self.assertEqual(str(category), "История")
        category.full_clean()

    def test_duplicate_category_name_raises_integrity_error(self):
        Category.objects.create(name="География")
        with self.assertRaises(IntegrityError):
            Category.objects.create(name="География")

    def test_duplicate_category_name_raises_validation_error(self):
        Category.objects.create(name="Наука")
        duplicate = Category(name="Наука")
        with self.assertRaises(ValidationError):
            duplicate.full_clean()

    def test_empty_category_name_raises_validation_error(self):
        category = Category(name="")
        with self.assertRaises(ValidationError):
            category.full_clean()

        whitespace_category = Category(name="   ")
        with self.assertRaises(ValidationError):
            whitespace_category.full_clean()

    def test_protected_category_cannot_be_deleted_with_choice_questions(self):
        category = Category.objects.create(name="История")
        question = ChoiceQuestion.objects.create(
            category=category,
            text="Коя година е създадена България?",
        )
        for i in range(4):
            AnswerOption.objects.create(
                question=question,
                text=f"Отговор {i + 1}",
                is_correct=(i == 0),
            )

        with self.assertRaises(ProtectedError):
            category.delete()

    def test_protected_category_cannot_be_deleted_with_numeric_questions(self):
        category = Category.objects.create(name="Математика")
        NumericQuestion.objects.create(
            category=category,
            text="Колко е 2 + 2?",
            correct_answer=4,
        )

        with self.assertRaises(ProtectedError):
            category.delete()

    def test_unprotected_category_can_be_deleted(self):
        category = Category.objects.create(name="Празни въпроси")
        cat_id = category.id
        category.delete()
        self.assertFalse(Category.objects.filter(id=cat_id).exists())


class ChoiceQuestionModelTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Общи знания")

    def test_create_valid_choice_question(self):
        question = ChoiceQuestion.objects.create(
            category=self.category,
            text="Коя е столицата на България?",
        )
        AnswerOption.objects.create(question=question, text="София", is_correct=True)
        AnswerOption.objects.create(question=question, text="Пловдив", is_correct=False)
        AnswerOption.objects.create(question=question, text="Варна", is_correct=False)
        AnswerOption.objects.create(question=question, text="Бургас", is_correct=False)

        question.full_clean()
        self.assertEqual(question.category, self.category)
        self.assertEqual(question.text, "Коя е столицата на България?")
        self.assertEqual(str(question), "Коя е столицата на България?")
        self.assertEqual(question.options.count(), 4)
        self.assertEqual(question.options.filter(is_correct=True).count(), 1)

    def test_invalid_choice_question_less_than_four_options(self):
        question = ChoiceQuestion.objects.create(
            category=self.category,
            text="Непълен въпрос с 3 отговора",
        )
        AnswerOption.objects.create(question=question, text="А", is_correct=True)
        AnswerOption.objects.create(question=question, text="Б", is_correct=False)
        AnswerOption.objects.create(question=question, text="В", is_correct=False)

        with self.assertRaises(ValidationError):
            question.clean()

        with self.assertRaises(ValidationError):
            question.full_clean()

    def test_invalid_choice_question_more_than_four_options(self):
        question = ChoiceQuestion.objects.create(
            category=self.category,
            text="Въпрос с 5 отговора",
        )
        AnswerOption.objects.create(question=question, text="А", is_correct=True)
        AnswerOption.objects.create(question=question, text="Б", is_correct=False)
        AnswerOption.objects.create(question=question, text="В", is_correct=False)
        AnswerOption.objects.create(question=question, text="Г", is_correct=False)
        AnswerOption.objects.create(question=question, text="Д", is_correct=False)

        with self.assertRaises(ValidationError):
            question.clean()

        with self.assertRaises(ValidationError):
            question.full_clean()

    def test_invalid_choice_question_no_correct_option(self):
        question = ChoiceQuestion.objects.create(
            category=self.category,
            text="Въпрос без верен отговор",
        )
        AnswerOption.objects.create(question=question, text="А", is_correct=False)
        AnswerOption.objects.create(question=question, text="Б", is_correct=False)
        AnswerOption.objects.create(question=question, text="В", is_correct=False)
        AnswerOption.objects.create(question=question, text="Г", is_correct=False)

        with self.assertRaises(ValidationError):
            question.clean()

        with self.assertRaises(ValidationError):
            question.full_clean()

    def test_invalid_choice_question_multiple_correct_options(self):
        question = ChoiceQuestion.objects.create(
            category=self.category,
            text="Въпрос с два верни отговора",
        )
        AnswerOption.objects.create(question=question, text="А", is_correct=True)
        AnswerOption.objects.create(question=question, text="Б", is_correct=True)
        AnswerOption.objects.create(question=question, text="В", is_correct=False)
        AnswerOption.objects.create(question=question, text="Г", is_correct=False)

        with self.assertRaises(ValidationError):
            question.clean()

        with self.assertRaises(ValidationError):
            question.full_clean()

    def test_delete_choice_question_cascades_to_answer_options(self):
        question = ChoiceQuestion.objects.create(
            category=self.category,
            text="Въпрос за изтриване",
        )
        opt1 = AnswerOption.objects.create(question=question, text="1", is_correct=True)
        opt2 = AnswerOption.objects.create(question=question, text="2", is_correct=False)
        opt3 = AnswerOption.objects.create(question=question, text="3", is_correct=False)
        opt4 = AnswerOption.objects.create(question=question, text="4", is_correct=False)

        question_id = question.id
        question.delete()

        self.assertFalse(ChoiceQuestion.objects.filter(id=question_id).exists())
        self.assertFalse(AnswerOption.objects.filter(id=opt1.id).exists())
        self.assertFalse(AnswerOption.objects.filter(id=opt2.id).exists())
        self.assertFalse(AnswerOption.objects.filter(id=opt3.id).exists())
        self.assertFalse(AnswerOption.objects.filter(id=opt4.id).exists())

    def test_related_names_and_properties(self):
        question = ChoiceQuestion.objects.create(
            category=self.category,
            text="Тест на релации",
        )
        for i in range(4):
            AnswerOption.objects.create(
                question=question,
                text=f"Опция {i}",
                is_correct=(i == 0),
            )

        self.assertIn(question, self.category.choicequestions.all())
        self.assertIn(question, self.category.choice_questions.all())
        self.assertEqual(question.options.count(), 4)
        self.assertEqual(question.answer_options.count(), 4)
        self.assertEqual(question.answeroption_set.count(), 4)


class NumericQuestionModelTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="История")

    def test_create_valid_numeric_question(self):
        question = NumericQuestion.objects.create(
            category=self.category,
            text="През коя година е създадена България?",
            correct_answer=681,
        )
        question.full_clean()
        self.assertEqual(question.category, self.category)
        self.assertEqual(question.text, "През коя година е създадена България?")
        self.assertEqual(question.correct_answer, 681)
        self.assertEqual(str(question), "През коя година е създадена България?")

    def test_numeric_question_requires_correct_answer(self):
        question = NumericQuestion(
            category=self.category,
            text="Липсващ отговор",
            correct_answer=None,
        )
        with self.assertRaises(ValidationError):
            question.full_clean()

    def test_related_names_and_properties(self):
        question = NumericQuestion.objects.create(
            category=self.category,
            text="Тест на релации за numeric",
            correct_answer=42,
        )
        self.assertIn(question, self.category.numericquestions.all())
        self.assertIn(question, self.category.numeric_questions.all())


class AnswerOptionModelTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Литература")
        self.question = ChoiceQuestion.objects.create(
            category=self.category,
            text="Примерен въпрос?",
        )

    def test_answer_option_defaults_and_str(self):
        option = AnswerOption.objects.create(
            question=self.question,
            text="Грешен отговор",
        )
        self.assertFalse(option.is_correct)
        self.assertEqual(str(option), "Грешен отговор (Incorrect)")

        correct_option = AnswerOption.objects.create(
            question=self.question,
            text="Верен отговор",
            is_correct=True,
        )
        self.assertTrue(correct_option.is_correct)
        self.assertEqual(str(correct_option), "Верен отговор (Correct)")
