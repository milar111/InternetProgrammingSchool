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

## M05 — Инициализация на игра (Game Initialization)

### 1. Столици и алгоритъм за разпределяне
- **Търсене на допустими тройки (`find_all_independent_triplets`)**:
  - Алгоритъмът анализира графа на съседство (`BULGARIA_MAP_ADJACENCY`) и намира всички подмножества от точно 3 върха $\{a, b, c\}$, в които няма нито едно ребро между коя да е двойка ($b \notin \text{adj}(a)$, $c \notin \text{adj}(a)$, $c \notin \text{adj}(b)$).
  - За картата на България съществуват общо **165 независими тройки**, което гарантира огромно разнообразие и изключва възможността за безкрайно търсене или отказ при валидна карта ($O(1)$ намиране).
- **Случаен избор и съпоставяне с играчите**:
  - Изборът на тройка се извършва на случаен принцип чрез `random.choice(triplets)`.
  - За да не определя редът на постъпване на играчите (`player_order` или ID) коя територия получават, избраната тройка се разбърква случайно (`random.shuffle`) преди съпоставяне с тримата играчи.
  - Поддържа се незадължителен параметър `seed` за възпроизводимо тестване, както и възможност за подаване на изрична валидна тройка (`capital_triplet`).

### 2. Граница на операцията и атомарност
- **Обхват на операцията (`initialize_game`)**:
  - Всички промени се извършват в рамките на една обща транзакция (`@transaction.atomic`):
    1. Заключване на записа на играта и нейните участници (`select_for_update()`).
    2. Проверка на всички предусловия: статус `waiting`, точно 3 играчи с уникални потребители, валидни и уникални цветове (`red`, `green`, `blue`), неотрицателни точки, липса на съществуващи територии и столици.
    3. Случаен избор и съпоставяне на независима тройка столици.
    4. Създаване на точно 15 записа `Territory` със `score = 0`; 3-те столици получават `owner = player`, а останалите 12 остават с `owner = None`.
    5. Създаване на симетричните M2M ребра (`neighbors`) според проектната дефиниция от M04.
    6. Създаване на точно 3 записа `Capital` със начално здраве `health = 3`.
    7. Преход на статуса на играта: `status = Game.ACTIVE`, `started_at = timezone.now()`.
    8. Валидация на целостта на картата чрез `validate_game_map(game)`.
- **Поведение при грешка и Rollback**:
  - При възникване на грешка или изключение в която и да е стъпка, транзакцията се връща изцяло (`rollback`). В базата не остават частични територии, столици или междинни статуси. Играта запазва състоянието си отпреди опита (`waiting`), позволявайки повторен опит след отстраняване на причината.
  - Повторен опит върху вече активирана игра се отказва без преразпределяне, дублиране или промяна на състоянието (`InvalidGameStatusError`).

### 3. Конкурентност и запазване на състава
- **Предотвратяване на състезания (Race Conditions)**:
  - Използва се `Game.objects.select_for_update()` и `players.select_for_update()`.
  - При едновременни извиквания за една и съща игра първата транзакция заключва реда, инициализира играта и преминава в статус `active`. Втората транзакция изчаква ключа и при получаването му прочита новия статус `active`, което предизвиква документиран отказ (`InvalidGameStatusError`). В резултат се изпълнява точно една инициализация.
- **Имутабилност на участниците в активна игра**:
  - След преминаване на играта в `active`, съставът ѝ е строго заключен:
    - Забранено е добавянето на нови играчи (`GamePlayer.clean()` и `save()` хвърлят `ValidationError`).
    - Забранено е изтриването на съществуващи играчи (`GamePlayer.delete()` хвърля `ValidationError`).
    - Забранена е промяната на потребител или ред на играч (`GamePlayer.clean()` хвърля `ValidationError`).
    - В Django Admin възможностите за добавяне и триене на играчи през `GamePlayerAdmin` и `GamePlayerInline` са забранени за активни/завършени игри.

### 4. Интерфейс и адаптирани входни точки от M03
- **Начин за задействане**:
  - Чрез service функцията: `from games.services import initialize_game; initialize_game(game_or_id)`
  - Чрез моделния метод: `game.initialize()`
  - През Django Admin: действие `Initialize selected game(s)` в `GameAdmin`.
- **Резултат и диференциация на отказите**:
  - При успех: връща инициализирания `Game` обект в статус `active`.
  - При отказ: хвърля специализирано изключение, наследяващо `GameInitializationError`:
    - `GameNotFoundError`: несъществуваща игра или невалидно ID.
    - `InvalidGameStatusError`: играта не е в статус `waiting` (напр. вече е `active` или `finished`).
    - `InvalidPlayersError`: броят играчи е различен от 3, потребителите не са уникални, точките са отрицателни или цветовете липсват/не са допустими и уникални.
    - `ExistingGameStateError`: играта вече съдържа частично/напълно създадени територии или столици.
    - `InvalidMapDefinitionError`: проектната дефиниция на картата не отговаря на изискванията от M04.
    - `NoValidCapitalsError`: липса на допустима независима тройка в графа.
- **Адаптирани входни точки от M03**:
  - Преходът от `waiting` към `active` се извършва **единствено** през операцията за инициализация по M05.
  - В `Game.clean()` и `Game.save()` е блокиран директен ръчен преход от `waiting` към `active` без валидно инициализирани 15 територии и 3 столици.
  - В `GameAdmin` изборът на статус `active` от падащото меню е скрит за чакащи игри, премахвайки заобиколни пътища за стартиране.

### 5. База данни: Конфигурация и ограничения
- **SQLite (Development / Testing environment)**:
  - Проектът по подразбиране използва SQLite (`django.db.backends.sqlite3`).
  - SQLite поддържа транзакции и атомарност (`transaction.atomic`), осигурявайки пълен rollback при грешка.
  - *Ограничения*: SQLite използва заключване на ниво цяла база данни (database-level locking), а не заключване на отделни редове (row-level locking). Поради това `select_for_update()` се изпълнява като no-op от драйвера на SQLite, но конкурентните транзакции се сериализират от механизма за заключване на файловата база.
- **PostgreSQL (Production recommendation)**:
  - За multi-user production среда се препоръчва PostgreSQL (`django.db.backends.postgresql`).
  - PostgreSQL осигурява истинско заключване на ниво ред (`SELECT ... FOR UPDATE`), пълен MVCC конкурентен контрол и изолирано изпълнение на конкурентни инициализации за различни игри без взаимно блокиране.

