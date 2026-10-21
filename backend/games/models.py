from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


WAITING = "waiting"
ACTIVE = "active"
IN_PROGRESS = "in_progress"
FINISHED = "finished"
CANCELLED = "cancelled"

STATUS_CHOICES = [
    (WAITING, "Waiting"),
    (ACTIVE, "Active"),
    (IN_PROGRESS, "In Progress"),
    (FINISHED, "Finished"),
    (CANCELLED, "Cancelled"),
]

PENDING = "pending"
OPEN = "open"
CLOSED = "closed"
EVALUATED = "evaluated"

ROUND_STATUS_CHOICES = [
    (PENDING, "Pending"),
    (OPEN, "Open"),
    (CLOSED, "Closed"),
    (EVALUATED, "Evaluated"),
]

CHOICE = "choice"
NUMERIC = "numeric"

QUESTION_TYPE_CHOICES = [
    (CHOICE, "Choice"),
    (NUMERIC, "Numeric"),
]


class Game(models.Model):
    WAITING = WAITING
    ACTIVE = ACTIVE
    IN_PROGRESS = IN_PROGRESS
    FINISHED = FINISHED
    CANCELLED = CANCELLED
    STATUS_CHOICES = STATUS_CHOICES

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_games",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=WAITING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Game #{self.id} ({self.status})"

    def clean(self):
        super().clean()
        if self.status in (self.ACTIVE, self.IN_PROGRESS):
            if not self.pk:
                raise ValidationError("Cannot create a new game directly in active status.")
            if self.territories.count() != 15 or Capital.objects.filter(territory__game=self).count() != 3:
                raise ValidationError(
                    "Game cannot transition to active status without successful initialization of map territories and capitals."
                )

    def save(self, *args, **kwargs):
        if self.pk:
            orig = Game.objects.filter(pk=self.pk).values("status").first()
            if orig and orig["status"] == self.WAITING and self.status in (self.ACTIVE, self.IN_PROGRESS):
                if self.territories.count() != 15 or Capital.objects.filter(territory__game=self).count() != 3:
                    raise ValidationError(
                        "Cannot transition game from waiting to active without initialization."
                    )
        super().save(*args, **kwargs)

    def initialize(self, *, seed=None, capital_triplet=None):
        from .services import initialize_game
        result = initialize_game(self, seed=seed, capital_triplet=capital_triplet)
        self.refresh_from_db()
        return result


class GamePlayer(models.Model):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"

    COLOR_CHOICES = [
        (RED, "Red"),
        (GREEN, "Green"),
        (BLUE, "Blue"),
    ]

    game = models.ForeignKey(
        Game,
        on_delete=models.CASCADE,
        related_name="players",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="game_participations",
    )
    player_order = models.PositiveSmallIntegerField()
    score = models.IntegerField(default=0)
    color = models.CharField(
        max_length=20,
        choices=COLOR_CHOICES,
        blank=True,
        default="",
    )
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["player_order"]
        constraints = [
            models.UniqueConstraint(
                fields=["game", "user"],
                name="unique_game_player",
            ),
            models.UniqueConstraint(
                fields=["game", "player_order"],
                name="unique_game_player_order",
            ),
            models.UniqueConstraint(
                fields=["game", "color"],
                condition=models.Q(color__gt=""),
                name="unique_game_player_color",
            ),
        ]

    def __str__(self):
        return f"{self.user.username} in Game #{self.game_id} (order {self.player_order})"

    def clean(self):
        super().clean()
        if self.score < 0:
            raise ValidationError("Player score must be non-negative.")
        if self.color:
            allowed = [c[0] for c in self.COLOR_CHOICES]
            if self.color not in allowed:
                raise ValidationError(f"Invalid player color '{self.color}'. Allowed colors: {allowed}.")
        if self.game_id:
            if not self.pk and self.game.status != Game.WAITING:
                raise ValidationError("Cannot add players to a game that is not in waiting status.")
            if self.pk and self.game.status != Game.WAITING:
                orig = GamePlayer.objects.filter(pk=self.pk).values("game_id", "user_id", "player_order").first()
                if orig:
                    if orig["game_id"] != self.game_id:
                        raise ValidationError("Cannot move player to a different game.")
                    if orig["user_id"] != self.user_id:
                        raise ValidationError("Cannot change user of a player once the game has started.")
                    if orig["player_order"] != self.player_order:
                        raise ValidationError("Cannot change player order once the game has started.")

    def save(self, *args, **kwargs):
        if self.game_id:
            if not self.pk and self.game.status != Game.WAITING:
                raise ValidationError("Cannot add players to a game that is not in waiting status.")
            if self.pk and self.game.status != Game.WAITING:
                orig = GamePlayer.objects.filter(pk=self.pk).values("game_id", "user_id", "player_order").first()
                if orig:
                    if orig["game_id"] != self.game_id:
                        raise ValidationError("Cannot move player to a different game.")
                    if orig["user_id"] != self.user_id:
                        raise ValidationError("Cannot change user of a player once the game has started.")
                    if orig["player_order"] != self.player_order:
                        raise ValidationError("Cannot change player order once the game has started.")
        if self.score < 0:
            raise ValidationError("Player score must be non-negative.")
        if self.color:
            allowed = [c[0] for c in self.COLOR_CHOICES]
            if self.color not in allowed:
                raise ValidationError(f"Invalid player color '{self.color}'. Allowed colors: {allowed}.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.game_id and self.game.status != Game.WAITING:
            raise ValidationError("Cannot remove players from an active, finished, or cancelled game.")
        return super().delete(*args, **kwargs)


class Round(models.Model):
    PENDING = PENDING
    OPEN = OPEN
    CLOSED = CLOSED
    EVALUATED = EVALUATED
    ROUND_STATUS_CHOICES = ROUND_STATUS_CHOICES

    CHOICE = CHOICE
    NUMERIC = NUMERIC
    QUESTION_TYPE_CHOICES = QUESTION_TYPE_CHOICES

    game = models.ForeignKey(
        Game,
        on_delete=models.CASCADE,
        related_name="rounds",
    )
    number = models.PositiveIntegerField()
    status = models.CharField(
        max_length=20,
        choices=ROUND_STATUS_CHOICES,
        default=PENDING,
    )
    question_type = models.CharField(
        max_length=20,
        choices=QUESTION_TYPE_CHOICES,
    )
    choice_question = models.ForeignKey(
        "questions.ChoiceQuestion",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="rounds",
    )
    numeric_question = models.ForeignKey(
        "questions.NumericQuestion",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="rounds",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["number"]
        constraints = [
            models.UniqueConstraint(
                fields=["game", "number"],
                name="unique_game_round_number",
            ),
        ]

    def __str__(self):
        return f"Round {self.number} (Game #{self.game_id})"

    def clean(self):
        super().clean()
        if self.question_type == CHOICE:
            if not self.choice_question_id:
                raise ValidationError("Choice round must have a choice question.")
            if self.numeric_question_id:
                raise ValidationError("Choice round cannot have a numeric question.")
        elif self.question_type == NUMERIC:
            if not self.numeric_question_id:
                raise ValidationError("Numeric round must have a numeric question.")
            if self.choice_question_id:
                raise ValidationError("Numeric round cannot have a choice question.")


class RoundAnswer(models.Model):
    round = models.ForeignKey(
        Round,
        on_delete=models.CASCADE,
        related_name="answers",
    )
    player = models.ForeignKey(
        GamePlayer,
        on_delete=models.CASCADE,
        related_name="answers",
    )
    selected_option = models.ForeignKey(
        "questions.AnswerOption",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="answers",
    )
    numeric_value = models.IntegerField(null=True, blank=True)
    is_correct = models.BooleanField(null=True, blank=True)
    points_awarded = models.IntegerField(default=0)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["submitted_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["round", "player"],
                name="unique_round_player_answer",
            ),
        ]

    def __str__(self):
        return f"Answer by {self.player.user.username} for Round {self.round.number}"

    def clean(self):
        super().clean()
        if self.player_id and self.round_id and self.player.game_id != self.round.game_id:
            raise ValidationError("Player must belong to the same game as the round.")

        if self.selected_option_id and self.numeric_value is not None:
            raise ValidationError("Answer cannot have both a selected option and a numeric value.")

        if self.round_id:
            if self.round.question_type == CHOICE:
                if self.numeric_value is not None:
                    raise ValidationError("Numeric value cannot be submitted for a choice question round.")
                if self.selected_option_id and self.round.choice_question_id:
                    if self.selected_option.question_id != self.round.choice_question_id:
                        raise ValidationError("Selected option must belong to the round's choice question.")
            elif self.round.question_type == NUMERIC:
                if self.selected_option_id:
                    raise ValidationError("Selected option cannot be submitted for a numeric question round.")


class Territory(models.Model):
    game = models.ForeignKey(
        Game,
        on_delete=models.CASCADE,
        related_name="territories",
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)
    owner = models.ForeignKey(
        GamePlayer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="territories",
    )
    score = models.IntegerField(default=0)
    neighbors = models.ManyToManyField(
        "self",
        symmetrical=True,
        blank=True,
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["game", "name"],
                name="unique_game_territory_name",
            ),
            models.UniqueConstraint(
                fields=["game", "slug"],
                name="unique_game_territory_slug",
            ),
        ]

    def __str__(self):
        return f"{self.name} (Game #{self.game_id})"

    def clean(self):
        super().clean()
        if not self.name or not self.name.strip():
            raise ValidationError("Territory name cannot be empty.")
        if not self.slug or not self.slug.strip():
            raise ValidationError("Territory slug cannot be empty.")

        self.name = self.name.strip()
        self.slug = self.slug.strip().lower()

        if self.score < 0:
            raise ValidationError("Territory score must be non-negative.")

        if self.owner_id and self.game_id:
            if self.owner.game_id != self.game_id:
                raise ValidationError("Territory owner must belong to the same game.")

        if self.pk:
            for neighbor in self.neighbors.all():
                if neighbor.game_id != self.game_id:
                    raise ValidationError("Neighbors must belong to the same game.")


class Capital(models.Model):
    territory = models.OneToOneField(
        Territory,
        on_delete=models.CASCADE,
        related_name="capital",
    )
    player = models.OneToOneField(
        GamePlayer,
        on_delete=models.CASCADE,
        related_name="capital",
    )
    health = models.PositiveSmallIntegerField(default=3)

    class Meta:
        ordering = ["territory__name"]

    def __str__(self):
        return f"Capital of {self.player.user.username} at {self.territory.name} (HP: {self.health})"

    @property
    def game(self):
        return self.territory.game if self.territory_id else None

    def clean(self):
        super().clean()
        if self.health < 0 or self.health > 3:
            raise ValidationError("Capital health must be between 0 and 3.")

        if self.territory_id and self.player_id:
            if self.player.game_id != self.territory.game_id:
                raise ValidationError("Capital player and territory must belong to the same game.")
            if self.territory.owner_id != self.player_id:
                raise ValidationError("Capital territory owner must match the capital player.")


class WaitingPlayer(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="waiting_entry")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.username


