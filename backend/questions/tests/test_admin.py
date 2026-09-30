from django.contrib.admin.sites import site
from django.forms.models import inlineformset_factory
from django.test import TestCase

from questions.admin import (
    AnswerOptionInline,
    AnswerOptionInlineFormSet,
    CategoryAdmin,
    ChoiceQuestionAdmin,
    NumericQuestionAdmin,
)
from questions.models import AnswerOption, Category, ChoiceQuestion, NumericQuestion


class AdminSiteConfigurationTests(TestCase):
    def test_models_are_registered(self):
        self.assertIn(Category, site._registry)
        self.assertIsInstance(site._registry[Category], CategoryAdmin)

        self.assertIn(ChoiceQuestion, site._registry)
        self.assertIsInstance(site._registry[ChoiceQuestion], ChoiceQuestionAdmin)

        self.assertIn(NumericQuestion, site._registry)
        self.assertIsInstance(site._registry[NumericQuestion], NumericQuestionAdmin)

    def test_category_admin_options(self):
        admin_obj = site._registry[Category]
        self.assertEqual(admin_obj.list_display, ("name",))
        self.assertEqual(admin_obj.search_fields, ("name",))

    def test_choice_question_admin_options(self):
        admin_obj = site._registry[ChoiceQuestion]
        self.assertEqual(admin_obj.list_display, ("text", "category"))
        self.assertEqual(admin_obj.list_filter, ("category",))
        self.assertEqual(admin_obj.search_fields, ("text",))
        self.assertEqual(len(admin_obj.inlines), 1)
        self.assertEqual(admin_obj.inlines[0], AnswerOptionInline)

    def test_numeric_question_admin_options(self):
        admin_obj = site._registry[NumericQuestion]
        self.assertEqual(admin_obj.list_display, ("text", "category", "correct_answer"))
        self.assertEqual(admin_obj.list_filter, ("category",))
        self.assertEqual(admin_obj.search_fields, ("text",))

    def test_answer_option_inline_formset_validation(self):
        category = Category.objects.create(name="История")
        question = ChoiceQuestion.objects.create(
            category=category,
            text="Примерен въпрос?",
        )

        OptionFormSet = inlineformset_factory(
            ChoiceQuestion,
            AnswerOption,
            formset=AnswerOptionInlineFormSet,
            fields=("text", "is_correct"),
            extra=4,
        )

        # Valid formset: exactly 4 options, 1 correct
        valid_data = {
            "options-TOTAL_FORMS": "4",
            "options-INITIAL_FORMS": "0",
            "options-MIN_NUM_FORMS": "4",
            "options-MAX_NUM_FORMS": "4",
            "options-0-text": "Опция 1",
            "options-0-is_correct": "True",
            "options-1-text": "Опция 2",
            "options-1-is_correct": "False",
            "options-2-text": "Опция 3",
            "options-2-is_correct": "False",
            "options-3-text": "Опция 4",
            "options-3-is_correct": "False",
        }
        formset = OptionFormSet(data=valid_data, instance=question)
        self.assertTrue(formset.is_valid(), formset.errors)

        # Invalid formset: 0 correct options
        no_correct_data = {
            "options-TOTAL_FORMS": "4",
            "options-INITIAL_FORMS": "0",
            "options-MIN_NUM_FORMS": "4",
            "options-MAX_NUM_FORMS": "4",
            "options-0-text": "Опция 1",
            "options-0-is_correct": "False",
            "options-1-text": "Опция 2",
            "options-1-is_correct": "False",
            "options-2-text": "Опция 3",
            "options-2-is_correct": "False",
            "options-3-text": "Опция 4",
            "options-3-is_correct": "False",
        }
        invalid_formset = OptionFormSet(data=no_correct_data, instance=question)
        self.assertFalse(invalid_formset.is_valid())

        # Invalid formset: 2 correct options
        two_correct_data = {
            "options-TOTAL_FORMS": "4",
            "options-INITIAL_FORMS": "0",
            "options-MIN_NUM_FORMS": "4",
            "options-MAX_NUM_FORMS": "4",
            "options-0-text": "Опция 1",
            "options-0-is_correct": "True",
            "options-1-text": "Опция 2",
            "options-1-is_correct": "True",
            "options-2-text": "Опция 3",
            "options-2-is_correct": "False",
            "options-3-text": "Опция 4",
            "options-3-is_correct": "False",
        }
        invalid_formset_2 = OptionFormSet(data=two_correct_data, instance=question)
        self.assertFalse(invalid_formset_2.is_valid())
