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
ACTIVE = "active"
CLOSED = "closed"
EVALUATED = "evaluated"
COMPLETED = "completed"

ROUND_STATUS_CHOICES = [
    (PENDING, "Pending"),
    (OPEN, "Open"),
    (ACTIVE, "Active"),
    (CLOSED, "Closed"),
    (EVALUATED, "Evaluated"),
    (COMPLETED, "Completed"),
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

    def get_current_round(self):
        return self.rounds.order_by("-number").first()


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
    ACTIVE = ACTIVE
    CLOSED = CLOSED
    EVALUATED = EVALUATED
    COMPLETED = COMPLETED
    ROUND_STATUS_CHOICES = ROUND_STATUS_CHOICES

    CHOICE = CHOICE
    NUMERIC = NUMERIC
    QUESTION_TYPE_CHOICES = QUESTION_TYPE_CHOICES

    CITY_CAPTURE = "city_capture"
    ROUND_TYPE_CHOICES = [
        (CITY_CAPTURE, "City Capture"),
    ]

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
    round_type = models.CharField(
        max_length=50,
        choices=ROUND_TYPE_CHOICES,
        default=CITY_CAPTURE,
    )
    question_type = models.CharField(
        max_length=20,
        choices=QUESTION_TYPE_CHOICES,
        default=NUMERIC,
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
    winner = models.ForeignKey(
        GamePlayer,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="won_rounds",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    unresolved_reason = models.CharField(max_length=255, blank=True, default="")

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

        if self.winner_id and self.game_id:
            if self.winner.game_id != self.game_id:
                raise ValidationError("Round winner must belong to the same game.")

        if self.status in (PENDING, ACTIVE, OPEN):
            if self.winner_id is not None:
                raise ValidationError("Round winner cannot be assigned while round is pending or active.")
            if self.completed_at is not None:
                raise ValidationError("Round completed_at cannot be set while round is pending or active.")

        if self.status == COMPLETED:
            if not self.completed_at:
                raise ValidationError("Completed round must have completed_at timestamp.")
            if not self.winner_id and not self.unresolved_reason:
                raise ValidationError("Completed round without a winner must have an unresolved_reason.")

    def get_current_question(self):
        return self.round_questions.order_by("-order").first()

    def get_rankings(self):
        return self.rankings.order_by("place")


class RoundQuestion(models.Model):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (ACTIVE, "Active"),
        (COMPLETED, "Completed"),
    ]

    round = models.ForeignKey(
        Round,
        on_delete=models.CASCADE,
        related_name="round_questions",
    )
    question = models.ForeignKey(
        "questions.NumericQuestion",
        on_delete=models.PROTECT,
        related_name="round_questions",
    )
    question_text = models.TextField()
    correct_answer = models.IntegerField()
    order = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=PENDING,
    )
    target_players = models.ManyToManyField(
        GamePlayer,
        blank=True,
        related_name="targeted_questions",
    )
    target_places = models.CharField(max_length=50, default="1,2")
    started_at = models.DateTimeField(null=True, blank=True)
    deadline = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["round", "order"]
        constraints = [
            models.UniqueConstraint(
                fields=["round", "order"],
                name="unique_round_question_order",
            ),
        ]

    def __str__(self):
        return f"Round #{self.round.number} Question #{self.order} ({self.status})"

    def clean(self):
        super().clean()
        if self.order < 1 or self.order > 3:
            raise ValidationError("Question order must be between 1 and 3.")
        if self.status == self.ACTIVE:
            if not self.started_at or not self.deadline:
                raise ValidationError("Active question must have started_at and deadline.")


class RoundAnswer(models.Model):
    round = models.ForeignKey(
        Round,
        on_delete=models.CASCADE,
        related_name="answers",
    )
    round_question = models.ForeignKey(
        RoundQuestion,
        null=True,
        blank=True,
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
    difference = models.IntegerField(null=True, blank=True)
    is_correct = models.BooleanField(null=True, blank=True)
    points_awarded = models.IntegerField(default=0)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["submitted_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["round", "player"],
                condition=models.Q(round_question__isnull=True),
                name="unique_round_player_answer",
            ),
            models.UniqueConstraint(
                fields=["round_question", "player"],
                condition=models.Q(round_question__isnull=False),
                name="unique_question_player_answer",
            ),
        ]

    def __str__(self):
        return f"Answer by {self.player.user.username} for Round {self.round.number}"

    def clean(self):
        super().clean()
        if self.player_id and self.round_id and self.player.game_id != self.round.game_id:
            raise ValidationError("Player must belong to the same game as the round.")

        if self.round_question_id and self.round_id:
            if self.round_question.round_id != self.round_id:
                raise ValidationError("RoundQuestion must belong to the same round.")

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


class RoundRanking(models.Model):
    round = models.ForeignKey(
        Round,
        on_delete=models.CASCADE,
        related_name="rankings",
    )
    player = models.ForeignKey(
        GamePlayer,
        on_delete=models.CASCADE,
        related_name="round_rankings",
    )
    place = models.PositiveSmallIntegerField()
    resolved_at_question = models.ForeignKey(
        RoundQuestion,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resolved_rankings",
    )
    difference = models.IntegerField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["place"]
        constraints = [
            models.UniqueConstraint(
                fields=["round", "place"],
                name="unique_round_place",
            ),
            models.UniqueConstraint(
                fields=["round", "player"],
                name="unique_round_player_ranking",
            ),
        ]

    def __str__(self):
        return f"Place {self.place}: {self.player.user.username} (Round #{self.round.number})"

    def clean(self):
        super().clean()
        if self.place not in (1, 2):
            raise ValidationError("Ranking place must be 1 or 2.")
        if self.player_id and self.round_id and self.player.game_id != self.round.game_id:
            raise ValidationError("Ranking player must belong to the round's game.")


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


