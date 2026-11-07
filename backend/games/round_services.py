import random
from datetime import timedelta
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from questions.models import NumericQuestion
from .models import Game, GamePlayer, Round, RoundAnswer, RoundQuestion, RoundRanking


class RoundServiceError(Exception):
    """Base exception for all round service layer operations."""
    pass


# 1. Липсващ запис (NotFound)
class GameNotFoundError(RoundServiceError):
    """Raised when the specified game does not exist."""
    pass


class RoundNotFoundError(RoundServiceError):
    """Raised when the specified round does not exist."""
    pass


class PlayerNotFoundError(RoundServiceError):
    """Raised when the specified player does not exist."""
    pass


# 2. Недопустимо състояние (InvalidState)
class InvalidGameStateError(RoundServiceError):
    """Raised when game status does not permit the requested operation (must be 'active')."""
    pass


class InvalidRoundStateError(RoundServiceError):
    """Raised when round status does not permit the requested operation."""
    pass


class UnfinishedRoundExistsError(RoundServiceError):
    """Raised when attempting to create a round while another unfinished round exists."""
    pass


class PrematureEvaluationError(RoundServiceError):
    """Raised when evaluating a round before deadline while players have not all answered."""
    pass


class RoundAlreadyCompletedError(RoundServiceError):
    """Raised when attempting to modify, answer, or re-evaluate an already completed round."""
    pass


class InvalidAnswerValueError(RoundServiceError):
    """Raised when the submitted answer is not a valid integer (float, bool, None, etc.)."""
    pass


class PlayerNotEligibleError(RoundServiceError):
    """Raised when player does not belong to game or is not in the targeted question group."""
    pass


class DuplicateAnswerError(RoundServiceError):
    """Raised when player has already submitted an answer for the current question."""
    pass


class AnswerDeadlineExpiredError(RoundServiceError):
    """Raised when an answer is submitted at or after the question deadline."""
    pass


class NoQuestionsAvailableError(RoundServiceError):
    """Raised when question bank has no unused numeric questions left for this game."""
    pass


def _resolve_game(game_or_id):
    if isinstance(game_or_id, Game):
        return game_or_id
    try:
        return Game.objects.get(pk=int(game_or_id))
    except (Game.DoesNotExist, ValueError, TypeError):
        raise GameNotFoundError(f"Game '{game_or_id}' does not exist.")


def _resolve_round(round_or_id):
    if isinstance(round_or_id, Round):
        return round_or_id
    try:
        return Round.objects.select_related("game").get(pk=int(round_or_id))
    except (Round.DoesNotExist, ValueError, TypeError):
        raise RoundNotFoundError(f"Round '{round_or_id}' does not exist.")


def _resolve_player(player_or_id):
    if isinstance(player_or_id, GamePlayer):
        return player_or_id
    try:
        return GamePlayer.objects.select_related("game", "user").get(pk=int(player_or_id))
    except (GamePlayer.DoesNotExist, ValueError, TypeError):
        raise PlayerNotFoundError(f"Player '{player_or_id}' does not exist.")


def create_numeric_round(game_or_id, *, round_type=Round.CITY_CAPTURE, question=None, seed=None):
    """
    Creates a new numeric round in 'pending' status for an active game:
    - Validates game exists, is active, and has 3 players.
    - Validates no unfinished round exists in the game.
    - Next round number is max(existing) + 1 (or 1 for first round).
    - Selects a random unused numeric question (or explicit unused question).
    - Snapshots question text and correct answer into initial RoundQuestion (order 1).
    - Targets all 3 players for places [1, 2].
    - All performed atomically.
    """
    game = _resolve_game(game_or_id)

    with transaction.atomic():
        game = Game.objects.select_for_update().get(pk=game.pk)

        if game.status != Game.ACTIVE:
            raise InvalidGameStateError(
                f"Game #{game.id} is in status '{game.status}'. Rounds can only be created for active games."
            )

        if game.players.count() != 3:
            raise InvalidGameStateError(f"Game #{game.id} must have exactly 3 players to create a round.")

        # Check for unfinished rounds (pending, active, or open)
        unfinished = game.rounds.filter(status__in=[Round.PENDING, Round.ACTIVE, Round.OPEN]).exists()
        if unfinished:
            raise UnfinishedRoundExistsError(
                f"Game #{game.id} already has an unfinished round. Only one unfinished round is permitted at a time."
            )

        if game.territories.exists():
            free_count = game.territories.filter(owner__isnull=True).count()
            if free_count == 0:
                from .capture_services import NoFreeTerritoriesError
                raise NoFreeTerritoriesError("Cannot create city_capture round: all territories on the map have been captured.")

            from .models import TerritorySelectionRight
            pending_rights = TerritorySelectionRight.objects.filter(
                round__game=game,
                used_choices__lt=models.F("allocated_choices"),
            ).exists()
            if pending_rights:
                from .capture_services import PendingSelectionRightsError
                raise PendingSelectionRightsError("Cannot create new round while players have unexercised territory selection rights.")

            target_places_str = "1,2" if free_count >= 3 else "1"
        else:
            target_places_str = "1,2"

        # Find used question IDs in this game
        used_q_ids = set(RoundQuestion.objects.filter(round__game=game).values_list("question_id", flat=True))
        used_q_ids.update(
            Round.objects.filter(game=game, numeric_question__isnull=False).values_list("numeric_question_id", flat=True)
        )

        if question is not None:
            if not isinstance(question, NumericQuestion):
                raise InvalidAnswerValueError("Provided question must be an instance of NumericQuestion.")
            if question.id in used_q_ids:
                raise NoQuestionsAvailableError(
                    f"Question #{question.id} has already been used in Game #{game.id}."
                )
            chosen_question = question
        else:
            candidates = list(NumericQuestion.objects.exclude(id__in=used_q_ids).order_by("id"))
            if not candidates:
                raise NoQuestionsAvailableError(
                    f"No unused numeric questions available in the question bank for Game #{game.id}."
                )
            rng = random.Random(seed) if seed is not None else random
            chosen_question = rng.choice(candidates)

        max_num = game.rounds.aggregate(models.Max("number"))["number__max"] or 0
        round_number = max_num + 1

        round_obj = Round.objects.create(
            game=game,
            number=round_number,
            status=Round.PENDING,
            round_type=round_type,
            question_type=Round.NUMERIC,
            numeric_question=chosen_question,
        )

        initial_rq = RoundQuestion.objects.create(
            round=round_obj,
            question=chosen_question,
            question_text=chosen_question.text,
            correct_answer=chosen_question.correct_answer,
            order=1,
            status=RoundQuestion.PENDING,
            target_places=target_places_str,
        )
        initial_rq.target_players.set(game.players.all())

        return round_obj


def start_round(round_or_id, *, timestamp=None):
    """
    Starts a pending round and its initial question:
    - Sets round status to 'active' and records started_at.
    - Sets current RoundQuestion status to 'active', started_at, and deadline (started_at + 10s).
    - Operates atomically.
    """
    round_obj = _resolve_round(round_or_id)

    with transaction.atomic():
        round_obj = Round.objects.select_for_update().get(pk=round_obj.pk)

        if round_obj.game.status != Game.ACTIVE:
            raise InvalidGameStateError(
                f"Game #{round_obj.game_id} is in status '{round_obj.game.status}'. Cannot start round."
            )

        if round_obj.status == Round.COMPLETED:
            raise RoundAlreadyCompletedError(f"Round #{round_obj.id} is already completed.")

        if round_obj.status != Round.PENDING:
            raise InvalidRoundStateError(
                f"Round #{round_obj.id} is in status '{round_obj.status}'. Only pending rounds can be started."
            )

        current_time = timestamp if timestamp is not None else timezone.now()

        round_obj.status = Round.ACTIVE
        round_obj.started_at = current_time
        round_obj.save()

        current_q = round_obj.get_current_question()
        if not current_q:
            raise InvalidRoundStateError(f"Round #{round_obj.id} has no questions configured.")

        current_q.status = RoundQuestion.ACTIVE
        current_q.started_at = current_time
        current_q.deadline = current_time + timedelta(seconds=10)
        current_q.save()

        return round_obj


def submit_numeric_answer(round_or_id, player_or_id, value, *, timestamp=None):
    """
    Submits a numeric answer for the currently active question in the round:
    - Validates game is active and round is active.
    - Validates player belongs to the game and is targeted by current question.
    - Validates value is integer (rejects float, bool, None, non-integer strings).
    - Uses application trusted time before checking deadline.
    - Rejects if timestamp >= deadline.
    - Rejects duplicate answers for the same question.
    - Computes absolute difference and records RoundAnswer.
    """
    # Strict integer validation: bool is subclass of int, so reject bool
    if isinstance(value, bool):
        raise InvalidAnswerValueError("Answer value cannot be a boolean.")
    if isinstance(value, float):
        raise InvalidAnswerValueError("Answer value cannot be a float; exact integer required.")
    if value is None:
        raise InvalidAnswerValueError("Answer value cannot be None.")

    try:
        if isinstance(value, str):
            # Check for dots or commas to prevent silent float truncation
            if "." in value or "," in value:
                raise ValueError("String contains decimal delimiter.")
            int_value = int(value.strip())
        elif isinstance(value, int):
            int_value = value
        else:
            raise ValueError("Unsupported numeric type.")
    except (ValueError, TypeError):
        raise InvalidAnswerValueError(f"Answer value '{value}' is not a valid integer.")

    round_obj = _resolve_round(round_or_id)
    player = _resolve_player(player_or_id)

    # Application determines trusted moment before checking deadline
    trusted_time = timestamp if timestamp is not None else timezone.now()

    with transaction.atomic():
        round_obj = Round.objects.select_for_update().get(pk=round_obj.pk)

        if round_obj.game.status != Game.ACTIVE:
            raise InvalidGameStateError("Game is not active.")

        if round_obj.status == Round.COMPLETED:
            raise RoundAlreadyCompletedError("Cannot submit answer to a completed round.")

        if round_obj.status != Round.ACTIVE:
            raise InvalidRoundStateError(
                f"Round #{round_obj.id} is in status '{round_obj.status}'. Only active rounds accept answers."
            )

        current_q = round_obj.get_current_question()
        if not current_q or current_q.status != RoundQuestion.ACTIVE:
            raise InvalidRoundStateError("No active question currently accepting answers in this round.")

        if player.game_id != round_obj.game_id:
            raise PlayerNotEligibleError(
                f"Player #{player.id} belongs to Game #{player.game_id}, not Game #{round_obj.game_id}."
            )

        if not current_q.target_players.filter(pk=player.pk).exists():
            raise PlayerNotEligibleError(
                f"Player '{player.user.username}' is not eligible to answer Question #{current_q.order}."
            )

        # Deadline check: exactly at or after deadline is rejected
        if trusted_time >= current_q.deadline:
            raise AnswerDeadlineExpiredError(
                f"Answer submitted at {trusted_time.isoformat()} is at or after deadline {current_q.deadline.isoformat()}."
            )

        # Duplicate answer check
        if RoundAnswer.objects.filter(round_question=current_q, player=player).exists():
            raise DuplicateAnswerError(
                f"Player '{player.user.username}' has already submitted an answer for Question #{current_q.order}."
            )

        diff = abs(int_value - current_q.correct_answer)
        is_correct = (diff == 0)

        answer = RoundAnswer.objects.create(
            round=round_obj,
            round_question=current_q,
            player=player,
            numeric_value=int_value,
            difference=diff,
            is_correct=is_correct,
            submitted_at=trusted_time,
        )

        return answer


def _finalize_completed_round(round_obj, trusted_time, unresolved_reason=""):
    round_obj.status = Round.COMPLETED
    round_obj.completed_at = trusted_time
    winner_rank = round_obj.rankings.filter(place=1).first()
    round_obj.winner = winner_rank.player if winner_rank else None
    round_obj.unresolved_reason = unresolved_reason
    round_obj.save()

    if round_obj.winner:
        from .capture_services import WIN_REWARD
        from .models import TerritorySelectionRight
        round_obj.winner.score += WIN_REWARD
        round_obj.winner.save(update_fields=["score"])

        free_count = round_obj.game.territories.filter(owner__isnull=True).count()
        second_place = round_obj.rankings.filter(place=2).first()

        if free_count >= 3:
            TerritorySelectionRight.objects.create(
                round=round_obj,
                player=round_obj.winner,
                allocated_choices=2,
                used_choices=0,
                order=1,
            )
            if second_place:
                TerritorySelectionRight.objects.create(
                    round=round_obj,
                    player=second_place.player,
                    allocated_choices=1,
                    used_choices=0,
                    order=2,
                )
        elif free_count == 2:
            TerritorySelectionRight.objects.create(
                round=round_obj,
                player=round_obj.winner,
                allocated_choices=2,
                used_choices=0,
                order=1,
            )
        elif free_count == 1:
            TerritorySelectionRight.objects.create(
                round=round_obj,
                player=round_obj.winner,
                allocated_choices=1,
                used_choices=0,
                order=1,
            )

    return round_obj


def evaluate_round(round_or_id, *, timestamp=None, next_question=None, seed=None):
    """
    Evaluates the current question of an active round:
    - Precondition: All targeted players have answered, OR question deadline has passed.
    - If neither: PrematureEvaluationError.
    - Evaluates answers: smaller difference is better; for equal difference, earlier submitted_at is better.
    - Identifies full ties (identical difference and identical submitted_at).
    - If needed places are resolved: creates RoundRankings, sets winner, marks completed.
    - If ties or no answers:
        - If question count < 3: activates a new RoundQuestion for the tied group with a fresh 10s deadline.
        - If question count == 3: marks round completed, records unresolved_reason='question_limit_reached'.
        - If question bank exhausted: marks round completed, records unresolved_reason='bank_exhausted'.
    - All state transitions and question generation are atomic.
    """
    round_obj = _resolve_round(round_or_id)

    with transaction.atomic():
        round_obj = Round.objects.select_for_update().get(pk=round_obj.pk)

        if round_obj.game.status != Game.ACTIVE:
            raise InvalidGameStateError("Game is not active.")

        if round_obj.status == Round.COMPLETED:
            raise RoundAlreadyCompletedError(f"Round #{round_obj.id} has already been completed.")

        if round_obj.status != Round.ACTIVE:
            raise InvalidRoundStateError(
                f"Round #{round_obj.id} is in status '{round_obj.status}'. Only active rounds can be evaluated."
            )

        current_q = round_obj.get_current_question()
        if not current_q or current_q.status != RoundQuestion.ACTIVE:
            raise InvalidRoundStateError("No active question to evaluate in this round.")

        trusted_time = timestamp if timestamp is not None else timezone.now()

        target_players = list(current_q.target_players.all())
        target_player_ids = {p.id for p in target_players}

        answers = list(
            current_q.answers.filter(player_id__in=target_player_ids).select_related("player").order_by("submitted_at")
        )
        answered_player_ids = {a.player_id for a in answers}

        all_answered = target_player_ids.issubset(answered_player_ids)
        deadline_passed = (trusted_time >= current_q.deadline)

        if not all_answered and not deadline_passed:
            raise PrematureEvaluationError(
                f"Cannot evaluate Question #{current_q.order} before deadline ({current_q.deadline.isoformat()}) "
                f"when only {len(answered_player_ids)}/{len(target_player_ids)} players have answered."
            )

        target_places = [int(p) for p in current_q.target_places.split(",") if p.strip()]

        # Sort answers by difference ASC, submitted_at ASC
        answers.sort(key=lambda a: (a.difference, a.submitted_at))

        # Group answers into equivalence tiers (identical difference AND identical submitted_at)
        tiers = []
        for a in answers:
            if not tiers:
                tiers.append([a])
            else:
                last_a = tiers[-1][0]
                if a.difference == last_a.difference and a.submitted_at == last_a.submitted_at:
                    tiers[-1].append(a)
                else:
                    tiers.append([a])

        # Track places resolved during this evaluation
        unresolved_places = []
        tied_players = []

        if len(answers) == 0:
            # Case 1: No answers at all
            unresolved_places = list(target_places)
            tied_players = list(target_players)
        elif len(answers) == 1:
            # Case 2: Exactly 1 answer accepted
            # Winner takes highest target place; no fictive second place is created
            single_player = answers[0].player
            highest_place = target_places[0]
            RoundRanking.objects.create(
                round=round_obj,
                player=single_player,
                place=highest_place,
                resolved_at_question=current_q,
                difference=answers[0].difference,
                submitted_at=answers[0].submitted_at,
            )
            # Remaining target places are NOT awarded because no other answers exist
            unresolved_places = []
            tied_players = []
        else:
            # Case 3: 2 or more answers
            if target_places == [1, 2]:
                if len(tiers[0]) == 1:
                    # Place 1 resolved
                    first_ans = tiers[0][0]
                    RoundRanking.objects.create(
                        round=round_obj,
                        player=first_ans.player,
                        place=1,
                        resolved_at_question=current_q,
                        difference=first_ans.difference,
                        submitted_at=first_ans.submitted_at,
                    )
                    # Check Place 2
                    if len(tiers) > 1:
                        if len(tiers[1]) == 1:
                            # Place 2 resolved
                            second_ans = tiers[1][0]
                            RoundRanking.objects.create(
                                round=round_obj,
                                player=second_ans.player,
                                place=2,
                                resolved_at_question=current_q,
                                difference=second_ans.difference,
                                submitted_at=second_ans.submitted_at,
                            )
                        else:
                            # Place 2 tied
                            unresolved_places = [2]
                            tied_players = [a.player for a in tiers[1]]
                else:
                    # Place 1 and 2 tied across top tier
                    unresolved_places = [1, 2]
                    tied_players = [a.player for a in tiers[0]]
            elif target_places == [2]:
                if len(tiers[0]) == 1:
                    # Place 2 resolved
                    second_ans = tiers[0][0]
                    RoundRanking.objects.create(
                        round=round_obj,
                        player=second_ans.player,
                        place=2,
                        resolved_at_question=current_q,
                        difference=second_ans.difference,
                        submitted_at=second_ans.submitted_at,
                    )
                else:
                    unresolved_places = [2]
                    tied_players = [a.player for a in tiers[0]]
            elif target_places == [1]:
                if len(tiers[0]) == 1:
                    first_ans = tiers[0][0]
                    RoundRanking.objects.create(
                        round=round_obj,
                        player=first_ans.player,
                        place=1,
                        resolved_at_question=current_q,
                        difference=first_ans.difference,
                        submitted_at=first_ans.submitted_at,
                    )
                else:
                    unresolved_places = [1]
                    tied_players = [a.player for a in tiers[0]]

        # Current question is now completed
        current_q.status = RoundQuestion.COMPLETED
        current_q.completed_at = trusted_time
        current_q.save()

        # Check if tie-breaker is required
        if not unresolved_places:
            # Everything required is resolved!
            return _finalize_completed_round(round_obj, trusted_time)

        # Ties remain: check limits and question availability
        if current_q.order >= 3:
            # Reached max limit of 3 questions
            return _finalize_completed_round(round_obj, trusted_time, "question_limit_reached")

        # Need next question: find an unused question in this game
        used_q_ids = set(RoundQuestion.objects.filter(round__game=round_obj.game).values_list("question_id", flat=True))
        used_q_ids.update(
            Round.objects.filter(game=round_obj.game, numeric_question__isnull=False).values_list("numeric_question_id", flat=True)
        )

        chosen_next_q = None
        if next_question is not None:
            if not isinstance(next_question, NumericQuestion):
                raise InvalidAnswerValueError("Provided next_question must be an instance of NumericQuestion.")
            if next_question.id in used_q_ids:
                raise NoQuestionsAvailableError(f"Question #{next_question.id} already used in this game.")
            chosen_next_q = next_question
        else:
            candidates = list(NumericQuestion.objects.exclude(id__in=used_q_ids).order_by("id"))
            if candidates:
                rng = random.Random(seed) if seed is not None else random
                chosen_next_q = rng.choice(candidates)

        if not chosen_next_q:
            # Question bank is exhausted!
            return _finalize_completed_round(round_obj, trusted_time, "bank_exhausted")

        # Activate next question with fresh 10-second deadline
        next_order = current_q.order + 1
        next_rq = RoundQuestion.objects.create(
            round=round_obj,
            question=chosen_next_q,
            question_text=chosen_next_q.text,
            correct_answer=chosen_next_q.correct_answer,
            order=next_order,
            status=RoundQuestion.ACTIVE,
            target_places=",".join(str(p) for p in unresolved_places),
            started_at=trusted_time,
            deadline=trusted_time + timedelta(seconds=10),
        )
        next_rq.target_players.set(tied_players)

        return round_obj


def get_round_state(round_or_id, *, timestamp=None):
    """
    Serializes round state for client inspection and recovery after reload:
    - round metadata: id, number, status, round_type, winner, completed_at, unresolved_reason
    - current question: order, status, text, started_at, deadline, remaining_seconds, target_players
    - questions history: list of all questions, their text, answers, differences
    - rankings: recorded places and winners
    """
    round_obj = _resolve_round(round_or_id)
    current_time = timestamp if timestamp is not None else timezone.now()

    current_q = round_obj.get_current_question()
    current_q_data = None
    if current_q:
        remaining_seconds = 0.0
        if current_q.status == RoundQuestion.ACTIVE and current_q.deadline:
            remaining_seconds = max(0.0, (current_q.deadline - current_time).total_seconds())

        current_q_data = {
            "id": current_q.id,
            "order": current_q.order,
            "status": current_q.status,
            "question_text": current_q.question_text,
            "started_at": current_q.started_at.isoformat() if current_q.started_at else None,
            "deadline": current_q.deadline.isoformat() if current_q.deadline else None,
            "remaining_seconds": remaining_seconds,
            "target_places": [int(p) for p in current_q.target_places.split(",") if p.strip()],
            "target_players": [p.user.username for p in current_q.target_players.all()],
        }

    history = []
    for q in round_obj.round_questions.order_by("order"):
        q_answers = [
            {
                "player": a.player.user.username,
                "numeric_value": a.numeric_value,
                "difference": a.difference,
                "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
            }
            for a in q.answers.order_by("submitted_at")
        ]
        history.append({
            "order": q.order,
            "status": q.status,
            "question_text": q.question_text,
            "answers": q_answers,
        })

    rankings = [
        {
            "place": r.place,
            "player": r.player.user.username,
            "difference": r.difference,
            "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
        }
        for r in round_obj.rankings.order_by("place")
    ]

    return {
        "round_id": round_obj.id,
        "number": round_obj.number,
        "status": round_obj.status,
        "round_type": round_obj.round_type,
        "winner": round_obj.winner.user.username if round_obj.winner else None,
        "completed_at": round_obj.completed_at.isoformat() if round_obj.completed_at else None,
        "unresolved_reason": round_obj.unresolved_reason,
        "current_question": current_q_data,
        "questions_history": history,
        "rankings": rankings,
    }
