from django import forms
from django.contrib import admin
from .models import AnswerOption, Category, ChoiceQuestion, NumericQuestion


class AnswerOptionInlineFormSet(forms.models.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        total_options = 0
        correct_options = 0

        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get("DELETE", False):
                continue
            total_options += 1
            if form.cleaned_data.get("is_correct", False):
                correct_options += 1

        if total_options != 4:
            raise forms.ValidationError(
                f"Choice question must have exactly 4 answer options (currently {total_options})."
            )
        if correct_options != 1:
            raise forms.ValidationError(
                f"Choice question must have exactly 1 correct answer option (currently {correct_options})."
            )


class AnswerOptionInline(admin.TabularInline):
    model = AnswerOption
    formset = AnswerOptionInlineFormSet
    extra = 4
    min_num = 4
    max_num = 4


class ChoiceQuestionAdminForm(forms.ModelForm):
    class Meta:
        model = ChoiceQuestion
        fields = "__all__"

    def clean(self):
        self.instance._skip_option_validation = True
        return super().clean()


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(ChoiceQuestion)
class ChoiceQuestionAdmin(admin.ModelAdmin):
    form = ChoiceQuestionAdminForm
    list_display = ("text", "category")
    list_filter = ("category",)
    search_fields = ("text",)
    inlines = [AnswerOptionInline]


@admin.register(NumericQuestion)
class NumericQuestionAdmin(admin.ModelAdmin):
    list_display = ("text", "category", "correct_answer")
    list_filter = ("category",)
    search_fields = ("text",)
