from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from questions.models import Category, NumericQuestion
from games.models import Game, GamePlayer, Round, RoundAnswer, RoundQuestion, RoundRanking
from games.services import (
    AnswerDeadlineExpiredError,
    DuplicateAnswerError,
    GameNotFoundError,
    InvalidAnswerValueError,
    InvalidGameStateError,
    InvalidRoundStateError,
    NoQuestionsAvailableError,
    PlayerNotEligibleError,
    PrematureEvaluationError,
    RoundAlreadyCompletedError,
    RoundNotFoundError,
    UnfinishedRoundExistsError,
    create_numeric_round,
    evaluate_round,
    get_round_state,
    initialize_game,
    start_round,
    submit_numeric_answer,
)

User = get_user_model()


class M6BaseTestCase(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Общи знания")
        self.questions = [
            NumericQuestion.objects.create(category=self.category, text=f"Колко е 10 * {i}?", correct_answer=10 * i)
            for i in range(1, 10)
        ]

        self.host = User.objects.create_user(username="host_user", email="host@example.com", password="pwd")
        self.users = [
            User.objects.create_user(username=f"player_{i}", email=f"p{i}@example.com", password="pwd")
            for i in range(1, 4)
        ]

        self.game = Game.objects.create(created_by=self.host, status=Game.WAITING)
        colors = ["red", "green", "blue"]
        self.players = [
            GamePlayer.objects.create(game=self.game, user=u, player_order=idx + 1, color=colors[idx])
            for idx, u in enumerate(self.users)
        ]

        # Initialize game so it transitions to ACTIVE with territories & capitals
        initialize_game(self.game)
        self.game.refresh_from_db()
        self.p1, self.p2, self.p3 = list(self.game.players.order_by("player_order"))


class RoundWorkflowTests(M6BaseTestCase):
    def test_workflow_create_start_complete_winner(self):
        t0 = timezone.now()

        # 1. Create round
        round1 = create_numeric_round(self.game)
        self.assertEqual(round1.number, 1)
        self.assertEqual(round1.status, Round.PENDING)
        self.assertEqual(round1.round_type, Round.CITY_CAPTURE)
        self.assertEqual(round1.question_type, Round.NUMERIC)
        self.assertIsNone(round1.winner)
        self.assertIsNone(round1.completed_at)
        self.assertEqual(self.game.get_current_round().id, round1.id)

        # Verify initial RoundQuestion snapshot
        q1 = round1.get_current_question()
        self.assertEqual(q1.order, 1)
        self.assertEqual(q1.status, RoundQuestion.PENDING)
        self.assertEqual(q1.target_places, "1,2")
        self.assertEqual(set(q1.target_players.all()), set(self.players))

        # 2. Start round
        start_round(round1, timestamp=t0)
        round1.refresh_from_db()
        q1.refresh_from_db()

        self.assertEqual(round1.status, Round.ACTIVE)
        self.assertEqual(round1.started_at, t0)
        self.assertEqual(q1.status, RoundQuestion.ACTIVE)
        self.assertEqual(q1.started_at, t0)
        self.assertEqual(q1.deadline, t0 + timedelta(seconds=10))

        # 3. Submit answers
        # Correct answer for q1.correct_answer
        correct = q1.correct_answer
        ans1 = submit_numeric_answer(round1, self.p1, correct, timestamp=t0 + timedelta(seconds=2))
        self.assertEqual(ans1.difference, 0)
        self.assertTrue(ans1.is_correct)

        ans2 = submit_numeric_answer(round1, self.p2, correct + 5, timestamp=t0 + timedelta(seconds=3))
        self.assertEqual(ans2.difference, 5)
        self.assertFalse(ans2.is_correct)

        ans3 = submit_numeric_answer(round1, self.p3, correct - 10, timestamp=t0 + timedelta(seconds=1))
        self.assertEqual(ans3.difference, 10)

        # 4. Evaluate round
        t_eval = t0 + timedelta(seconds=4)
        evaluate_round(round1, timestamp=t_eval)
        round1.refresh_from_db()

        self.assertEqual(round1.status, Round.COMPLETED)
        self.assertEqual(round1.winner, self.p1)
        self.assertEqual(round1.completed_at, t_eval)
        self.assertEqual(round1.unresolved_reason, "")

        # Check rankings: place 1 and place 2
        rankings = list(round1.get_rankings())
        self.assertEqual(len(rankings), 2)
        self.assertEqual(rankings[0].place, 1)
        self.assertEqual(rankings[0].player, self.p1)
        self.assertEqual(rankings[1].place, 2)
        self.assertEqual(rankings[1].player, self.p2)

        # 5. Create round 2
        round2 = create_numeric_round(self.game)
        self.assertEqual(round2.number, 2)
        self.assertEqual(self.game.get_current_round().id, round2.id)

    def test_cannot_create_round_if_game_not_active(self):
        other_game = Game.objects.create(created_by=self.host, status=Game.WAITING)
        with self.assertRaises(InvalidGameStateError):
            create_numeric_round(other_game)

    def test_cannot_create_second_round_if_first_unfinished(self):
        create_numeric_round(self.game)
        with self.assertRaises(UnfinishedRoundExistsError):
            create_numeric_round(self.game)


class RoundAnswersEvaluationTests(M6BaseTestCase):
    def test_proximity_before_speed(self):
        t0 = timezone.now()
        r = create_numeric_round(self.game)
        start_round(r, timestamp=t0)
        q = r.get_current_question()
        c = q.correct_answer

        # P1 is closer (diff 2) but submitted slower (at 6s)
        submit_numeric_answer(r, self.p1, c + 2, timestamp=t0 + timedelta(seconds=6))
        # P2 is further (diff 5) but submitted faster (at 1s)
        submit_numeric_answer(r, self.p2, c + 5, timestamp=t0 + timedelta(seconds=1))
        # P3 is even further (diff 20) at 2s
        submit_numeric_answer(r, self.p3, c - 20, timestamp=t0 + timedelta(seconds=2))

        evaluate_round(r, timestamp=t0 + timedelta(seconds=7))
        r.refresh_from_db()

        self.assertEqual(r.winner, self.p1)
        rankings = list(r.get_rankings())
        self.assertEqual(rankings[0].player, self.p1)
        self.assertEqual(rankings[1].player, self.p2)

    def test_equal_proximity_different_times(self):
        t0 = timezone.now()
        r = create_numeric_round(self.game)
        start_round(r, timestamp=t0)
        q = r.get_current_question()
        c = q.correct_answer

        # P1 has diff 5 from below (c - 5) at 3.5 seconds
        submit_numeric_answer(r, self.p1, c - 5, timestamp=t0 + timedelta(seconds=3, microseconds=500000))
        # P2 has diff 5 from above (c + 5) at 1.2 seconds (faster!)
        submit_numeric_answer(r, self.p2, c + 5, timestamp=t0 + timedelta(seconds=1, microseconds=200000))
        # P3 has diff 10 at 0.5 seconds
        submit_numeric_answer(r, self.p3, c + 10, timestamp=t0 + timedelta(seconds=0, microseconds=500000))

        evaluate_round(r, timestamp=t0 + timedelta(seconds=4))
        r.refresh_from_db()

        self.assertEqual(r.winner, self.p2)
        rankings = list(r.get_rankings())
        self.assertEqual(rankings[0].player, self.p2)
        self.assertEqual(rankings[1].player, self.p1)

    def test_single_answer_received(self):
        t0 = timezone.now()
        r = create_numeric_round(self.game)
        start_round(r, timestamp=t0)
        q = r.get_current_question()

        # Only P1 answers
        submit_numeric_answer(r, self.p1, q.correct_answer, timestamp=t0 + timedelta(seconds=2))

        # Evaluate after deadline (10s)
        evaluate_round(r, timestamp=t0 + timedelta(seconds=10, microseconds=100))
        r.refresh_from_db()

        self.assertEqual(r.status, Round.COMPLETED)
        self.assertEqual(r.winner, self.p1)
        # Exactly one place awarded; no fictive second place
        rankings = list(r.get_rankings())
        self.assertEqual(len(rankings), 1)
        self.assertEqual(rankings[0].place, 1)
        self.assertEqual(rankings[0].player, self.p1)


class RoundRejectionsAndValidationTests(M6BaseTestCase):
    def test_reject_foreign_player(self):
        t0 = timezone.now()
        r = create_numeric_round(self.game)
        start_round(r, timestamp=t0)

        # Another player in another game
        other_user = User.objects.create_user(username="stranger", email="stranger@test.com", password="pwd")
        other_game = Game.objects.create(created_by=other_user, status=Game.WAITING)
        other_player = GamePlayer.objects.create(game=other_game, user=other_user, player_order=1, color="red")

        with self.assertRaises(PlayerNotEligibleError):
            submit_numeric_answer(r, other_player, 42, timestamp=t0 + timedelta(seconds=1))

    def test_reject_duplicate_answer(self):
        t0 = timezone.now()
        r = create_numeric_round(self.game)
        start_round(r, timestamp=t0)

        submit_numeric_answer(r, self.p1, 50, timestamp=t0 + timedelta(seconds=1))
        with self.assertRaises(DuplicateAnswerError):
            submit_numeric_answer(r, self.p1, 55, timestamp=t0 + timedelta(seconds=2))

        # Ensure first answer is unchanged
        answers = RoundAnswer.objects.filter(round=r, player=self.p1)
        self.assertEqual(answers.count(), 1)
        self.assertEqual(answers.first().numeric_value, 50)

    def test_reject_answer_before_start(self):
        r = create_numeric_round(self.game)
        with self.assertRaises(InvalidRoundStateError):
            submit_numeric_answer(r, self.p1, 50)

    def test_reject_repeated_evaluation_after_completed(self):
        t0 = timezone.now()
        r = create_numeric_round(self.game)
        start_round(r, timestamp=t0)
        submit_numeric_answer(r, self.p1, 50, timestamp=t0 + timedelta(seconds=1))
        evaluate_round(r, timestamp=t0 + timedelta(seconds=11))

        with self.assertRaises(RoundAlreadyCompletedError):
            evaluate_round(r, timestamp=t0 + timedelta(seconds=12))

    def test_reject_non_integer_values(self):
        t0 = timezone.now()
        r = create_numeric_round(self.game)
        start_round(r, timestamp=t0)

        # Float
        with self.assertRaises(InvalidAnswerValueError):
            submit_numeric_answer(r, self.p1, 42.5, timestamp=t0 + timedelta(seconds=1))

        # Boolean
        with self.assertRaises(InvalidAnswerValueError):
            submit_numeric_answer(r, self.p1, True, timestamp=t0 + timedelta(seconds=1))

        # None
        with self.assertRaises(InvalidAnswerValueError):
            submit_numeric_answer(r, self.p1, None, timestamp=t0 + timedelta(seconds=1))

        # String with decimals
        with self.assertRaises(InvalidAnswerValueError):
            submit_numeric_answer(r, self.p1, "42.0", timestamp=t0 + timedelta(seconds=1))

        # String with non-numeric text
        with self.assertRaises(InvalidAnswerValueError):
            submit_numeric_answer(r, self.p1, "abc", timestamp=t0 + timedelta(seconds=1))

        # Invalid attempts do NOT use up player's right to answer
        submit_numeric_answer(r, self.p1, 42, timestamp=t0 + timedelta(seconds=2))
        self.assertEqual(RoundAnswer.objects.filter(round=r, player=self.p1).count(), 1)


class RoundDeadlineTests(M6BaseTestCase):
    def test_deadline_exact_boundaries(self):
        t0 = timezone.now()
        r = create_numeric_round(self.game)
        start_round(r, timestamp=t0)

        # 1. Before deadline (9.999s) -> Accepted
        t_valid = t0 + timedelta(seconds=9, microseconds=999000)
        ans = submit_numeric_answer(r, self.p1, 10, timestamp=t_valid)
        self.assertIsNotNone(ans)

        # 2. Exactly at deadline (10.000000s) -> Rejected
        t_exact = t0 + timedelta(seconds=10)
        with self.assertRaises(AnswerDeadlineExpiredError):
            submit_numeric_answer(r, self.p2, 10, timestamp=t_exact)

        # 3. After deadline (10.001s) -> Rejected
        t_after = t0 + timedelta(seconds=10, microseconds=1000)
        with self.assertRaises(AnswerDeadlineExpiredError):
            submit_numeric_answer(r, self.p3, 10, timestamp=t_after)

    def test_premature_evaluation_rejected(self):
        t0 = timezone.now()
        r = create_numeric_round(self.game)
        start_round(r, timestamp=t0)

        # Only 1 player answered, deadline is 10s away
        submit_numeric_answer(r, self.p1, 10, timestamp=t0 + timedelta(seconds=1))

        # Evaluation at 5s (before deadline, not all answered) -> Premature
        with self.assertRaises(PrematureEvaluationError):
            evaluate_round(r, timestamp=t0 + timedelta(seconds=5))


class RoundTieBreakingAndCompletionTests(M6BaseTestCase):
    def test_tie_triggers_second_question_for_tied_group(self):
        t0 = timezone.now()
        r = create_numeric_round(self.game)
        start_round(r, timestamp=t0)
        q1 = r.get_current_question()
        c1 = q1.correct_answer

        # P1 and P2 tie on proximity and exact timestamp
        t_ans = t0 + timedelta(seconds=2)
        submit_numeric_answer(r, self.p1, c1 + 5, timestamp=t_ans)
        submit_numeric_answer(r, self.p2, c1 - 5, timestamp=t_ans)
        # P3 answers worse
        submit_numeric_answer(r, self.p3, c1 + 20, timestamp=t_ans)

        # Evaluate Question 1
        evaluate_round(r, timestamp=t0 + timedelta(seconds=3))
        r.refresh_from_db()

        # Round is STILL active, Question 2 is created
        self.assertEqual(r.status, Round.ACTIVE)
        self.assertEqual(r.round_questions.count(), 2)

        q2 = r.get_current_question()
        self.assertEqual(q2.order, 2)
        self.assertEqual(q2.status, RoundQuestion.ACTIVE)
        self.assertEqual(set(q2.target_players.all()), {self.p1, self.p2})
        self.assertEqual(q2.target_places, "1,2")

        # P3 is NOT eligible to answer Question 2
        with self.assertRaises(PlayerNotEligibleError):
            submit_numeric_answer(r, self.p3, q2.correct_answer, timestamp=q2.started_at + timedelta(seconds=1))

        # P1 and P2 answer Question 2
        c2 = q2.correct_answer
        submit_numeric_answer(r, self.p1, c2, timestamp=q2.started_at + timedelta(seconds=1))
        submit_numeric_answer(r, self.p2, c2 + 3, timestamp=q2.started_at + timedelta(seconds=1))

        # Evaluate Question 2
        evaluate_round(r, timestamp=q2.started_at + timedelta(seconds=2))
        r.refresh_from_db()

        self.assertEqual(r.status, Round.COMPLETED)
        self.assertEqual(r.winner, self.p1)
        rankings = list(r.get_rankings())
        self.assertEqual(len(rankings), 2)
        self.assertEqual(rankings[0].player, self.p1)
        self.assertEqual(rankings[1].player, self.p2)

    def test_tie_for_second_place_preserves_first_place(self):
        t0 = timezone.now()
        r = create_numeric_round(self.game)
        start_round(r, timestamp=t0)
        q1 = r.get_current_question()
        c1 = q1.correct_answer

        # P1 has clear 1st place
        submit_numeric_answer(r, self.p1, c1, timestamp=t0 + timedelta(seconds=1))
        # P2 and P3 tie for 2nd place
        t_ans = t0 + timedelta(seconds=2)
        submit_numeric_answer(r, self.p2, c1 + 5, timestamp=t_ans)
        submit_numeric_answer(r, self.p3, c1 - 5, timestamp=t_ans)

        evaluate_round(r, timestamp=t0 + timedelta(seconds=3))
        r.refresh_from_db()

        # Place 1 is already recorded!
        rank1 = r.rankings.filter(place=1).first()
        self.assertIsNotNone(rank1)
        self.assertEqual(rank1.player, self.p1)

        # Question 2 is created for place 2 with target_players=[P2, P3]
        q2 = r.get_current_question()
        self.assertEqual(q2.order, 2)
        self.assertEqual(q2.target_places, "2")
        self.assertEqual(set(q2.target_players.all()), {self.p2, self.p3})

        # P1 cannot answer Q2
        with self.assertRaises(PlayerNotEligibleError):
            submit_numeric_answer(r, self.p1, q2.correct_answer, timestamp=q2.started_at + timedelta(seconds=1))

        # In Q2, only P2 answers
        submit_numeric_answer(r, self.p2, q2.correct_answer + 1, timestamp=q2.started_at + timedelta(seconds=2))
        evaluate_round(r, timestamp=q2.deadline + timedelta(seconds=1))
        r.refresh_from_db()

        self.assertEqual(r.status, Round.COMPLETED)
        self.assertEqual(r.winner, self.p1)
        rankings = list(r.get_rankings())
        self.assertEqual(rankings[0].player, self.p1)
        self.assertEqual(rankings[1].player, self.p2)

    def test_no_answers_triggers_new_question_for_same_group(self):
        t0 = timezone.now()
        r = create_numeric_round(self.game)
        start_round(r, timestamp=t0)

        # Nobody answers Question 1 before deadline
        evaluate_round(r, timestamp=t0 + timedelta(seconds=11))
        r.refresh_from_db()

        self.assertEqual(r.status, Round.ACTIVE)
        q2 = r.get_current_question()
        self.assertEqual(q2.order, 2)
        self.assertEqual(set(q2.target_players.all()), set(self.players))

    def test_question_limit_three_questions(self):
        t0 = timezone.now()
        r = create_numeric_round(self.game)
        start_round(r, timestamp=t0)

        # Q1: Nobody answers
        evaluate_round(r, timestamp=t0 + timedelta(seconds=11))
        r.refresh_from_db()
        q2 = r.get_current_question()
        self.assertEqual(q2.order, 2)

        # Q2: Nobody answers
        evaluate_round(r, timestamp=q2.deadline + timedelta(seconds=1))
        r.refresh_from_db()
        q3 = r.get_current_question()
        self.assertEqual(q3.order, 3)

        # Q3: Nobody answers -> Limit reached!
        evaluate_round(r, timestamp=q3.deadline + timedelta(seconds=1))
        r.refresh_from_db()

        self.assertEqual(r.status, Round.COMPLETED)
        self.assertIsNone(r.winner)
        self.assertIsNotNone(r.completed_at)
        self.assertEqual(r.unresolved_reason, "question_limit_reached")

    def test_victory_on_third_question(self):
        t0 = timezone.now()
        r = create_numeric_round(self.game)
        start_round(r, timestamp=t0)

        # Q1: Nobody answers
        evaluate_round(r, timestamp=t0 + timedelta(seconds=11))
        r.refresh_from_db()
        q2 = r.get_current_question()

        # Q2: Nobody answers
        evaluate_round(r, timestamp=q2.deadline + timedelta(seconds=1))
        r.refresh_from_db()
        q3 = r.get_current_question()
        self.assertEqual(q3.order, 3)

        # Q3: Decisive answers
        c3 = q3.correct_answer
        submit_numeric_answer(r, self.p1, c3, timestamp=q3.started_at + timedelta(seconds=1))
        submit_numeric_answer(r, self.p2, c3 + 1, timestamp=q3.started_at + timedelta(seconds=1))
        submit_numeric_answer(r, self.p3, c3 + 2, timestamp=q3.started_at + timedelta(seconds=1))

        evaluate_round(r, timestamp=q3.started_at + timedelta(seconds=2))
        r.refresh_from_db()

        self.assertEqual(r.status, Round.COMPLETED)
        self.assertEqual(r.winner, self.p1)
        self.assertEqual(r.unresolved_reason, "")

    def test_bank_exhausted_during_tiebreak(self):
        # Create game with only 1 question available in the bank
        NumericQuestion.objects.all().delete()
        single_q = NumericQuestion.objects.create(category=self.category, text="Only question?", correct_answer=10)

        game2 = Game.objects.create(created_by=self.host, status=Game.WAITING)
        colors = ["red", "green", "blue"]
        for idx, u in enumerate(self.users):
            GamePlayer.objects.create(game=game2, user=u, player_order=idx + 1, color=colors[idx])
        initialize_game(game2)
        game2.refresh_from_db()

        p_list = list(game2.players.order_by("player_order"))

        t0 = timezone.now()
        r = create_numeric_round(game2, question=single_q)
        start_round(r, timestamp=t0)

        # Tie on question 1
        t_ans = t0 + timedelta(seconds=1)
        submit_numeric_answer(r, p_list[0], 15, timestamp=t_ans)
        submit_numeric_answer(r, p_list[1], 15, timestamp=t_ans)

        # Evaluate: bank has no more questions!
        evaluate_round(r, timestamp=t0 + timedelta(seconds=11))
        r.refresh_from_db()

        self.assertEqual(r.status, Round.COMPLETED)
        self.assertIsNone(r.winner)
        self.assertEqual(r.unresolved_reason, "bank_exhausted")


class RoundDataPersistenceTests(M6BaseTestCase):
    def test_data_persistence_and_reloading(self):
        t0 = timezone.now()
        r = create_numeric_round(self.game)
        start_round(r, timestamp=t0)
        q = r.get_current_question()
        q_text = q.question_text
        deadline = q.deadline

        submit_numeric_answer(r, self.p1, q.correct_answer, timestamp=t0 + timedelta(seconds=2))
        evaluate_round(r, timestamp=t0 + timedelta(seconds=11))

        # Reload completely from DB
        fresh_round = Round.objects.get(pk=r.pk)
        fresh_q = fresh_round.get_current_question()

        self.assertEqual(fresh_q.question_text, q_text)
        self.assertEqual(fresh_q.deadline, deadline)
        self.assertEqual(fresh_round.winner, self.p1)
        self.assertEqual(fresh_round.rankings.count(), 1)

    def test_question_bank_modification_does_not_affect_round(self):
        t0 = timezone.now()
        r = create_numeric_round(self.game)
        q = r.get_current_question()
        original_db_q = q.question
        original_correct = q.correct_answer

        # Modify original question in the bank
        original_db_q.text = "Completely altered text!"
        original_db_q.correct_answer = 999999
        original_db_q.save()

        # Start round and submit based on snapshot
        start_round(r, timestamp=t0)
        q.refresh_from_db()

        self.assertEqual(q.correct_answer, original_correct)
        self.assertNotEqual(q.correct_answer, 999999)

        ans = submit_numeric_answer(r, self.p1, original_correct, timestamp=t0 + timedelta(seconds=1))
        self.assertEqual(ans.difference, 0)
        self.assertTrue(ans.is_correct)

    def test_get_round_state_contract(self):
        t0 = timezone.now()
        r = create_numeric_round(self.game)
        start_round(r, timestamp=t0)
        q = r.get_current_question()

        submit_numeric_answer(r, self.p1, q.correct_answer, timestamp=t0 + timedelta(seconds=2))

        # Check state while active
        state_active = get_round_state(r, timestamp=t0 + timedelta(seconds=4))
        self.assertEqual(state_active["status"], Round.ACTIVE)
        self.assertAlmostEqual(state_active["current_question"]["remaining_seconds"], 6.0, delta=0.1)
        self.assertEqual(state_active["current_question"]["order"], 1)

        # Complete and check state
        evaluate_round(r, timestamp=t0 + timedelta(seconds=11))
        state_completed = get_round_state(r)
        self.assertEqual(state_completed["status"], Round.COMPLETED)
        self.assertEqual(state_completed["winner"], self.p1.user.username)
        self.assertEqual(len(state_completed["rankings"]), 1)


class RoundModelValidationTests(M6BaseTestCase):
    def test_completed_without_winner_requires_reason(self):
        now = timezone.now()
        r = Round(
            game=self.game,
            number=99,
            status=Round.COMPLETED,
            completed_at=now,
            winner=None,
            unresolved_reason="",
            numeric_question=self.questions[0],
        )
        with self.assertRaises(ValidationError):
            r.clean()

        r.unresolved_reason = "question_limit_reached"
        r.clean()  # Passes

    def test_winner_cannot_be_set_when_pending(self):
        r = Round(
            game=self.game,
            number=99,
            status=Round.PENDING,
            winner=self.p1,
            numeric_question=self.questions[0],
        )
        with self.assertRaises(ValidationError):
            r.clean()

    def test_winner_must_belong_to_round_game(self):
        other_user = User.objects.create_user(username="other", email="other@test.com", password="pwd")
        other_game = Game.objects.create(created_by=other_user, status=Game.WAITING)
        other_player = GamePlayer.objects.create(game=other_game, user=other_user, player_order=1, color="red")

        r = Round(
            game=self.game,
            number=99,
            status=Round.COMPLETED,
            completed_at=timezone.now(),
            winner=other_player,
            numeric_question=self.questions[0],
        )
        with self.assertRaises(ValidationError):
            r.clean()


class RoundConcurrencyBonusTests(M6BaseTestCase):
    def test_simultaneous_answers_rejected_by_db_constraint(self):
        """
        Tests the bonus task: verifies that two simultaneous answers for the same question
        from the same player are strictly prevented at the database level by unique constraint.
        """
        t0 = timezone.now()
        r = create_numeric_round(self.game)
        start_round(r, timestamp=t0)
        q = r.get_current_question()

        # First answer succeeds
        RoundAnswer.objects.create(
            round=r,
            round_question=q,
            player=self.p1,
            numeric_value=10,
            submitted_at=t0 + timedelta(seconds=1),
        )

        # Second concurrent answer for the exact same question and player raises IntegrityError
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RoundAnswer.objects.create(
                    round=r,
                    round_question=q,
                    player=self.p1,
                    numeric_value=20,
                    submitted_at=t0 + timedelta(seconds=1),
                )
