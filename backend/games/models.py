from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


WAITING = "waiting"
IN_PROGRESS = "in_progress"
FINISHED = "finished"
CANCELLED = "cancelled"

STATUS_CHOICES = [
    (WAITING, "Waiting"),
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


class GamePlayer(models.Model):
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
        ]

    def __str__(self):
        return f"{self.user.username} in Game #{self.game_id} (order {self.player_order})"


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
