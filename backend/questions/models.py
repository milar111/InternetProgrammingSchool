from django.core.exceptions import ValidationError
from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=255, unique=True)

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if not self.name or not self.name.strip():
            raise ValidationError("Category name cannot be empty.")

    @property
    def choice_questions(self):
        return self.choicequestions

    @property
    def numeric_questions(self):
        return self.numericquestions


class BaseQuestion(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="%(class)ss",
    )
    text = models.TextField()

    class Meta:
        abstract = True

    def __str__(self):
        return self.text


class ChoiceQuestion(BaseQuestion):
    class Meta:
        verbose_name = "Choice Question"
        verbose_name_plural = "Choice Questions"

    def clean(self):
        super().clean()
        if getattr(self, "_skip_option_validation", False):
            return

        if self.pk:
            count = self.options.count()
            correct_count = self.options.filter(is_correct=True).count()
        else:
            count = 0
            correct_count = 0

        if count != 4:
            raise ValidationError(
                f"Choice question must have exactly 4 answer options (currently {count})."
            )
        if correct_count != 1:
            raise ValidationError(
                f"Choice question must have exactly 1 correct answer option (currently {correct_count})."
            )

    @property
    def answer_options(self):
        return self.options

    @property
    def answeroption_set(self):
        return self.options


class NumericQuestion(BaseQuestion):
    correct_answer = models.IntegerField()

    class Meta:
        verbose_name = "Numeric Question"
        verbose_name_plural = "Numeric Questions"

    def clean(self):
        super().clean()
        if self.correct_answer is None:
            raise ValidationError("Numeric question must have a correct answer.")


class AnswerOption(models.Model):
    question = models.ForeignKey(
        ChoiceQuestion,
        on_delete=models.CASCADE,
        related_name="options",
    )
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Answer Option"
        verbose_name_plural = "Answer Options"

    def __str__(self):
        return f"{self.text} ({'Correct' if self.is_correct else 'Incorrect'})"
