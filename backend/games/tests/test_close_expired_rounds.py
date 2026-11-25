import io
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from questions.models import Category, NumericQuestion
from games.models import Game, GamePlayer, Round, RoundQuestion
from games.services import (
    AnswerDeadlineExpiredError,
    create_numeric_round,
    evaluate_round,
    initialize_game,
    start_round,
    submit_numeric_answer,
)

User = get_user_model()


class CloseExpiredRoundsCommandTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Тестова Категория")
        self.q = NumericQuestion.objects.create(
            category=self.category,
            text="Коя година е основана България?",
            correct_answer=681,
        )

        self.host = User.objects.create_user(username="host_bg", email="h@example.com", password="pwd")
        self.u1 = User.objects.create_user(username="u1", email="u1@example.com", password="pwd")
        self.u2 = User.objects.create_user(username="u2", email="u2@example.com", password="pwd")
        self.u3 = User.objects.create_user(username="u3", email="u3@example.com", password="pwd")

        self.game = Game.objects.create(created_by=self.host, status=Game.WAITING)
        GamePlayer.objects.create(game=self.game, user=self.u1, player_order=1, color="red")
        GamePlayer.objects.create(game=self.game, user=self.u2, player_order=2, color="green")
        GamePlayer.objects.create(game=self.game, user=self.u3, player_order=3, color="blue")

        initialize_game(self.game, capital_triplet=("vidin", "varna", "blagoevgrad"))
        self.p1, self.p2, self.p3 = list(self.game.players.order_by("player_order"))

    def test_command_processes_expired_round(self):
        """Command finds active question whose deadline passed and evaluates it."""
        t0 = timezone.now() - timedelta(seconds=20)
        r = create_numeric_round(self.game, question=self.q)
        start_round(r, timestamp=t0)
        q1 = r.get_current_question()

        # Submit one answer 15 seconds ago (before deadline t0 + 10s)
        submit_numeric_answer(r, self.p1, 681, timestamp=t0 + timedelta(seconds=5))

        # At current time, deadline t0 + 10s is in the past
        self.assertTrue(timezone.now() > q1.deadline)
        self.assertEqual(q1.status, RoundQuestion.ACTIVE)

        out = io.StringIO()
        call_command("close_expired_rounds", stdout=out)
        output = out.getvalue()

        self.assertIn("Processed: 1, Skipped: 0", output)

        q1.refresh_from_db()
        r.refresh_from_db()
        self.assertEqual(q1.status, RoundQuestion.COMPLETED)
        self.assertEqual(r.status, Round.COMPLETED)
        self.assertEqual(r.winner, self.p1)

    def test_command_does_not_process_non_expired_round(self):
        """Active question whose deadline is in the future is not processed."""
        t0 = timezone.now()
        r = create_numeric_round(self.game, question=self.q)
        start_round(r, timestamp=t0)

        out = io.StringIO()
        call_command("close_expired_rounds", stdout=out)
        output = out.getvalue()

        self.assertIn("Processed: 0, Skipped: 0", output)

    def test_idempotence_and_concurrency_guard(self):
        """Calling evaluate_round or command repeatedly is safe and avoids double points."""
        t0 = timezone.now() - timedelta(seconds=20)
        r = create_numeric_round(self.game, question=self.q)
        start_round(r, timestamp=t0)
        submit_numeric_answer(r, self.p1, 681, timestamp=t0 + timedelta(seconds=2))

        # First evaluation succeeds
        res1 = evaluate_round(r, timestamp=timezone.now())
        self.assertIsNotNone(res1)
        self.p1.refresh_from_db()
        score_after_first = self.p1.score
        self.assertEqual(score_after_first, 200)

        # Second call to close_expired_rounds finds 0 active expired rounds and changes nothing
        out = io.StringIO()
        call_command("close_expired_rounds", stdout=out)
        self.assertIn("Processed: 0, Skipped: 0", out.getvalue())

        self.p1.refresh_from_db()
        # Score is NOT doubled!
        self.assertEqual(self.p1.score, 200)

    def test_submit_answer_after_deadline_rejected_even_if_status_active(self):
        """Answer received after deadline is rejected even if question is still active in DB."""
        t0 = timezone.now() - timedelta(seconds=20)
        r = create_numeric_round(self.game, question=self.q)
        start_round(r, timestamp=t0)
        q1 = r.get_current_question()

        # In DB, q1.status is still ACTIVE because close_expired_rounds has not run yet
        self.assertEqual(q1.status, RoundQuestion.ACTIVE)

        # Player tries to submit now (after deadline)
        with self.assertRaises(AnswerDeadlineExpiredError):
            submit_numeric_answer(r, self.p1, 681, timestamp=timezone.now())
