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
To run tests for specific apps:

```bash
python backend/manage.py test questions
python backend/manage.py test games
```

To run all backend tests:

```bash
python backend/manage.py test accounts questions games
```

---

## M04 — Territories and Map Documentation

### 1. Карта и територии
Проектът използва дефиниция с **15 територии**, базирана на картата на България (кратно на 3: $15 = 3 \times 5$):

| Територия | Slug | Съседи |
|---|---|---|
| **Благоевград** | `blagoevgrad` | София, Пловдив |
| **Бургас** | `burgas` | Варна, Шумен, Велико Търново, Стара Загора, Хасково |
| **Варна** | `varna` | Добрич, Шумен, Бургас |
| **Велико Търново** | `veliko-tarnovo` | Плевен, Габрово, Русе, Шумен, Бургас |
| **Видин** | `vidin` | София, Враца |
| **Враца** | `vratsa` | Видин, София, Плевен |
| **Габрово** | `gabrovo` | Плевен, Велико Търново, Стара Загора |
| **Добрич** | `dobrich` | Русе, Шумен, Варна |
| **Плевен** | `pleven` | Враца, София, Габрово, Велико Търново, Пловдив |
| **Пловдив** | `plovdiv` | Благоевград, София, Плевен, Стара Загора, Хасково |
| **Русе** | `ruse` | Велико Търново, Шумен, Добрич |
| **София** | `sofia` | Благоевград, Видин, Враца, Плевен, Пловдив |
| **Стара Загора** | `stara-zagora` | Габрово, Бургас, Хасково, Пловдив |
| **Хасково** | `haskovo` | Стара Загора, Бургас, Пловдив |
| **Шумен** | `shumen` | Русе, Добрич, Варна, Велико Търново, Бургас |

#### Допустима независима тройка столици
Конкретната тройка територии, между които **няма нито едно ребро / съседство**:
- **Видин** (`vidin`)
- **Варна** (`varna`)
- **Благоевград** (`blagoevgrad`)

Никоя от тези три територии не граничи с останалите две, което гарантира равнопоставено и независимо начално разположение за 3-ма играчи.

### 2. Представяне и организация на данните
- **Статична дефиниция (`games/map.py`)**:
  - `BULGARIA_MAP_TERRITORIES`: списък от речници с `name` и `slug`.
  - `BULGARIA_MAP_ADJACENCY`: речник, съпоставящ всеки slug към списък от съседни slug-ове (ненасочен граф).
- **Игрово състояние (`Territory` модел)**:
  - Всяка игра получава собствени concrete записи `Territory`, свързани с конкретна игра чрез `ForeignKey(Game, on_delete=models.CASCADE)`.
  - Съседствата се пазят чрез симетрична M2M релация `neighbors = models.ManyToManyField("self", symmetrical=True, blank=True)`.
  - Еднакви имена и slug-ове са уникални в рамките на една игра (`UniqueConstraint`), но могат да се повтарят между различни игри.

### 3. Цялост, входни точки и правила
- **Разрешени входни точки за достъп и валидация (`games/map.py`)**:
  - `validate_map_definition()`: проверява проектния граф за брой (между 9 и 21, кратен на 3), свързаност, симетрия, липса на self-loops, поне 2 съседа на връх и наличие на независима тройка върхове.
  - `validate_game_map(game)`: валидира, че картата на конкретна игра съдържа всички 15 територии с точните имена, slug-ове и съседства, без чужди съседи от други игри.
  - `get_game_territories(game)`: връща QuerySet с всички територии на играта.
  - `get_player_territories(player)`: връща QuerySet с териториите, притежавани от играча.
  - `get_player_capital(player)`: връща обекта `Capital` на играча или `None` при липса на такъв (без да създава нов запис).
  - `get_territory_capital(territory)`: връща `Capital` на територията или `None`.
- **Нормализиране**:
  - Имената се почистват от излишни интервали в началото и края (`strip()`).
  - Slug-овете се привеждат автоматично към малки букви и се почистват (`strip().lower()`).
- **Поведение при изтриване**:
  - При изтриване на `Game`: каскадно се изтриват всички нейни `Territory` и `Capital` записи.
  - При изтриване на `Territory`: каскадно се изтрива асоциираният `Capital`.
  - При изтриване на `GamePlayer`: каскадно се изтрива асоциираният `Capital`, а собствеността на териториите му се нулира (`owner = models.SET_NULL`).
  - Играта на столицата се извежда през територията (`capital.game`), без независимо поле `game`.
- **Ограничения (DB и модели)**:
  - `UniqueConstraint` за `(game, name)` и `(game, slug)`.
  - `OneToOneField` за `Capital.territory` и `Capital.player` (най-много една столица на територия и на играч).
  - Валидация за неотрицателен score (`score >= 0`).
  - Валидация за здраве на столица между 0 и 3 (`0 <= health <= 3`).
  - Валидация в `clean()`, че собственикът на територията и столицата са от същата игра като територията.

### 4. Django Admin правила
- **Заключена структура**:
  - Забранено е добавянето на нови територии и столици през админа (`has_add_permission = False`).
  - Забранено е изтриването на територии и столици през админа (`has_delete_permission = False`).
  - Забранени са масови действия (`actions = None`).
  - Полетата `game`, `name`, `slug`, `owner` и `neighbors` в `TerritoryAdmin`, както и `player` и `territory` в `CapitalAdmin` са само за четене (`readonly_fields`).
- **Разрешена редакция на състояние**:
  - В `TerritoryAdmin` може да се редактира само `score` (с валидация `score >= 0`).
  - В `CapitalAdmin` може да се редактира само `health` (с валидация между 0 и 3).
- **Списъци и филтри**:
  - `TerritoryAdmin`: търсене по `name` и `slug`, филтри по `game` и `owner`, колона със съседите (`get_neighbors`).
  - `CapitalAdmin`: търсене по играч и територия, филтър по игра, колона за играта (`get_game`).
  - Прегледите и филтрите работят коректно дори когато няма инициализирани игри в базата.
