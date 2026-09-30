# Quiz Game - Internet Programming Project

## Backend Setup & Instructions

### 1. Migrations
Apply database migrations:

```bash
python backend/manage.py migrate
```

### 2. Loading the Question Bank Fixture
Load the initial question bank (categories, choice questions with options, and numeric questions):

```bash
python backend/manage.py loaddata questions/question_bank.json
```

Or from the `backend/` directory:

```bash
python manage.py loaddata questions/question_bank.json
```

### 3. Verifying the Question Bank Data
To inspect the loaded bank via the Django shell:

```bash
python backend/manage.py shell
```

```python
from questions.models import Category, ChoiceQuestion, NumericQuestion

print("Categories:", Category.objects.count())
print("Choice questions:", ChoiceQuestion.objects.count())
print("Numeric questions:", NumericQuestion.objects.count())
```

Expected counts:
- 6 Categories
- 12 Choice Questions
- 12 Numeric Questions

### 4. Running Backend Tests
To run tests for the questions app:

```bash
python backend/manage.py test questions
```

To run all backend tests:

```bash
python backend/manage.py test accounts questions
```
