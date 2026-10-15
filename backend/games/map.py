from collections import deque
from django.core.exceptions import ValidationError

BULGARIA_MAP_TERRITORIES = [
    {"name": "Благоевград", "slug": "blagoevgrad"},
    {"name": "Бургас", "slug": "burgas"},
    {"name": "Варна", "slug": "varna"},
    {"name": "Велико Търново", "slug": "veliko-tarnovo"},
    {"name": "Видин", "slug": "vidin"},
    {"name": "Враца", "slug": "vratsa"},
    {"name": "Габрово", "slug": "gabrovo"},
    {"name": "Добрич", "slug": "dobrich"},
    {"name": "Плевен", "slug": "pleven"},
    {"name": "Пловдив", "slug": "plovdiv"},
    {"name": "Русе", "slug": "ruse"},
    {"name": "София", "slug": "sofia"},
    {"name": "Стара Загора", "slug": "stara-zagora"},
    {"name": "Хасково", "slug": "haskovo"},
    {"name": "Шумен", "slug": "shumen"},
]

BULGARIA_MAP_ADJACENCY = {
    "blagoevgrad": ["sofia", "plovdiv"],
    "sofia": ["blagoevgrad", "vidin", "vratsa", "pleven", "plovdiv"],
    "vidin": ["sofia", "vratsa"],
    "vratsa": ["vidin", "sofia", "pleven"],
    "pleven": ["vratsa", "sofia", "gabrovo", "veliko-tarnovo", "plovdiv"],
    "gabrovo": ["pleven", "veliko-tarnovo", "stara-zagora"],
    "veliko-tarnovo": ["pleven", "gabrovo", "ruse", "shumen", "burgas"],
    "ruse": ["veliko-tarnovo", "shumen", "dobrich"],
    "dobrich": ["ruse", "shumen", "varna"],
    "varna": ["dobrich", "shumen", "burgas"],
    "shumen": ["ruse", "dobrich", "varna", "veliko-tarnovo", "burgas"],
    "burgas": ["varna", "shumen", "veliko-tarnovo", "stara-zagora", "haskovo"],
    "stara-zagora": ["gabrovo", "burgas", "haskovo", "plovdiv"],
    "haskovo": ["stara-zagora", "burgas", "plovdiv"],
    "plovdiv": ["blagoevgrad", "sofia", "pleven", "stara-zagora", "haskovo"],
}

SAMPLE_CAPITAL_TRIPLET = ("vidin", "varna", "blagoevgrad")


def validate_map_definition(territories=BULGARIA_MAP_TERRITORIES, adjacency=BULGARIA_MAP_ADJACENCY):
    errors = []
    count = len(territories)

    if count < 9 or count > 21 or count % 3 != 0:
        errors.append(f"Territory count must be between 9 and 21 and a multiple of 3 (got {count}).")

    names = [t["name"].strip() for t in territories]
    slugs = [t["slug"].strip().lower() for t in territories]

    if any(not name for name in names):
        errors.append("Territory names cannot be empty.")
    if len(names) != len(set(names)):
        errors.append("Territory names must be unique.")

    if any(not slug for slug in slugs):
        errors.append("Territory slugs cannot be empty.")
    if len(slugs) != len(set(slugs)):
        errors.append("Territory slugs must be unique.")

    slug_set = set(slugs)

    if set(adjacency.keys()) != slug_set:
        errors.append("Adjacency keys must match territory slugs exactly.")

    for slug, neighbors in adjacency.items():
        if len(neighbors) != len(set(neighbors)):
            errors.append(f"{slug}: duplicate neighbors found.")
        if slug in neighbors:
            errors.append(f"{slug}: self-referencing neighbor.")
        if len(neighbors) < 2:
            errors.append(f"{slug}: must have at least 2 neighbors.")
        for neighbor in neighbors:
            if neighbor not in slug_set:
                errors.append(f"{slug} -> {neighbor}: target territory does not exist.")
            elif slug not in adjacency.get(neighbor, []):
                errors.append(f"{slug} -> {neighbor}: missing symmetric connection.")

    if slug_set and not errors:
        start = next(iter(slug_set))
        visited = set()
        queue = deque([start])
        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            for n in adjacency.get(current, []):
                if n not in visited:
                    queue.append(n)

        if visited != slug_set:
            errors.append("The map graph is not fully connected.")

    has_independent_triplet = False
    slug_list = list(slug_set)
    for i in range(len(slug_list)):
        for j in range(i + 1, len(slug_list)):
            for k in range(j + 1, len(slug_list)):
                a, b, c = slug_list[i], slug_list[j], slug_list[k]
                adj_a = set(adjacency.get(a, []))
                adj_b = set(adjacency.get(b, []))
                if b not in adj_a and c not in adj_a and c not in adj_b:
                    has_independent_triplet = True
                    break
            if has_independent_triplet:
                break
        if has_independent_triplet:
            break

    if not has_independent_triplet:
        errors.append("Map must have at least one triplet of territories with no edges between any of them.")

    if errors:
        raise ValidationError("; ".join(errors))

    return True


def validate_game_map(game):
    territories = game.territories.all()
    count = territories.count()

    if count == 0:
        raise ValidationError("Game map is empty (not initialized).")

    if count != len(BULGARIA_MAP_TERRITORIES):
        raise ValidationError(
            f"Game map has {count} territories, expected {len(BULGARIA_MAP_TERRITORIES)}."
        )

    expected_slugs = {t["slug"] for t in BULGARIA_MAP_TERRITORIES}
    expected_names = {t["slug"]: t["name"] for t in BULGARIA_MAP_TERRITORIES}

    by_slug = {}
    for territory in territories:
        if territory.slug not in expected_slugs:
            raise ValidationError(f"Unexpected territory slug: {territory.slug}")
        if territory.name != expected_names[territory.slug]:
            raise ValidationError(
                f"Territory name mismatch for {territory.slug}: expected {expected_names[territory.slug]}, got {territory.name}"
            )
        by_slug[territory.slug] = territory

    for slug, territory in by_slug.items():
        expected_neighbors = set(BULGARIA_MAP_ADJACENCY.get(slug, []))
        actual_neighbors = set(territory.neighbors.values_list("slug", flat=True))

        for neighbor in territory.neighbors.all():
            if neighbor.game_id != game.id:
                raise ValidationError("Territory neighbor belongs to a different game.")

        if actual_neighbors != expected_neighbors:
            raise ValidationError(
                f"Adjacency mismatch for {slug}: expected {expected_neighbors}, got {actual_neighbors}"
            )

    return True


def get_game_territories(game):
    return game.territories.all()


def get_player_territories(player):
    return player.territories.all()


def get_player_capital(player):
    return getattr(player, "capital", None)


def get_territory_capital(territory):
    return getattr(territory, "capital", None)
