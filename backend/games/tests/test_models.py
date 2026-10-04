from django.contrib.auth import get_user_model
from django.db.models import ProtectedError
from django.test import TestCase
from django.utils import timezone

from games.models import Game, GamePlayer, Round, RoundAnswer
from questions.models import AnswerOption, Category, ChoiceQuestion, NumericQuestion

User = get_user_model()


class GameModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="host",
            email="host@example.com",
            password="password123",
        )

    def test_create_game_with_defaults(self):
        game = Game.objects.create(created_by=self.user)
        self.assertEqual(game.status, Game.WAITING)
        self.assertIsNotNone(game.created_at)
        self.assertIsNone(game.started_at)
        self.assertIsNone(game.finished_at)
        self.assertIn("waiting", str(game))

    def test_game_status_transitions(self):
        game = Game.objects.create(created_by=self.user)
        now = timezone.now()

        game.status = Game.IN_PROGRESS
        game.started_at = now
        game.save()
        self.assertEqual(game.status, Game.IN_PROGRESS)

        game.status = Game.FINISHED
        game.finished_at = now
        game.save()
        self.assertEqual(game.status, Game.FINISHED)

    def test_game_created_by_protect(self):
        Game.objects.create(created_by=self.user)
        with self.assertRaises(ProtectedError):
            self.user.delete()

    def test_deleting_game_cascades_to_players_and_rounds(self):
        game = Game.objects.create(created_by=self.user)
        player = GamePlayer.objects.create(game=game, user=self.user, player_order=1)

        category = Category.objects.create(name="Общи")
        numeric_q = NumericQuestion.objects.create(
            category=category,
            text="Колко е 10 + 10?",
            correct_answer=20,
        )
        round_obj = Round.objects.create(
            game=game,
            number=1,
            question_type=Round.NUMERIC,
            numeric_question=numeric_q,
        )

        game.delete()
        self.assertFalse(GamePlayer.objects.filter(id=player.id).exists())
        self.assertFalse(Round.objects.filter(id=round_obj.id).exists())


class GamePlayerModelTests(TestCase):
    def setUp(self):
        self.host = User.objects.create_user(username="host", email="host@example.com", password="pwd")
        self.player_user = User.objects.create_user(username="p1", email="p1@example.com", password="pwd")
        self.game = Game.objects.create(created_by=self.host)

    def test_create_player_defaults(self):
        player = GamePlayer.objects.create(
            game=self.game,
            user=self.player_user,
            player_order=1,
        )
        self.assertEqual(player.score, 0)
        self.assertTrue(player.is_active)
        self.assertIsNotNone(player.joined_at)
        self.assertIn("p1", str(player))

    def test_player_user_protect(self):
        GamePlayer.objects.create(game=self.game, user=self.player_user, player_order=1)
        with self.assertRaises(ProtectedError):
            self.player_user.delete()


class RoundModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="host", email="host@example.com", password="pwd")
        self.game = Game.objects.create(created_by=self.user)
        self.category = Category.objects.create(name="История")

        self.choice_q = ChoiceQuestion.objects.create(
            category=self.category,
            text="Коя година е основана България?",
        )
        self.opt1 = AnswerOption.objects.create(question=self.choice_q, text="681", is_correct=True)
        self.opt2 = AnswerOption.objects.create(question=self.choice_q, text="700", is_correct=False)
        self.opt3 = AnswerOption.objects.create(question=self.choice_q, text="800", is_correct=False)
        self.opt4 = AnswerOption.objects.create(question=self.choice_q, text="900", is_correct=False)

        self.numeric_q = NumericQuestion.objects.create(
            category=self.category,
            text="През коя година е основана България?",
            correct_answer=681,
        )

    def test_create_choice_round(self):
        round_obj = Round.objects.create(
            game=self.game,
            number=1,
            question_type=Round.CHOICE,
            choice_question=self.choice_q,
        )
        self.assertEqual(round_obj.status, Round.PENDING)
        self.assertEqual(round_obj.number, 1)
        self.assertEqual(round_obj.choice_question, self.choice_q)
        self.assertIn("Round 1", str(round_obj))

    def test_create_numeric_round(self):
        round_obj = Round.objects.create(
            game=self.game,
            number=2,
            question_type=Round.NUMERIC,
            numeric_question=self.numeric_q,
        )
        self.assertEqual(round_obj.question_type, Round.NUMERIC)
        self.assertEqual(round_obj.numeric_question, self.numeric_q)

    def test_round_status_transitions(self):
        round_obj = Round.objects.create(
            game=self.game,
            number=1,
            question_type=Round.CHOICE,
            choice_question=self.choice_q,
        )
        for next_status in [Round.OPEN, Round.CLOSED, Round.EVALUATED]:
            round_obj.status = next_status
            round_obj.save()
            self.assertEqual(round_obj.status, next_status)

    def test_round_protects_question_deletion(self):
        Round.objects.create(
            game=self.game,
            number=1,
            question_type=Round.CHOICE,
            choice_question=self.choice_q,
        )
        with self.assertRaises(ProtectedError):
            self.choice_q.delete()

        Round.objects.create(
            game=self.game,
            number=2,
            question_type=Round.NUMERIC,
            numeric_question=self.numeric_q,
        )
        with self.assertRaises(ProtectedError):
            self.numeric_q.delete()


class RoundAnswerModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="host", email="host@example.com", password="pwd")
        self.game = Game.objects.create(created_by=self.user)
        self.player = GamePlayer.objects.create(game=self.game, user=self.user, player_order=1)
        self.category = Category.objects.create(name="География")

        self.choice_q = ChoiceQuestion.objects.create(category=self.category, text="Столица на България?")
        self.opt1 = AnswerOption.objects.create(question=self.choice_q, text="София", is_correct=True)
        self.opt2 = AnswerOption.objects.create(question=self.choice_q, text="Варна", is_correct=False)
        self.opt3 = AnswerOption.objects.create(question=self.choice_q, text="Бургас", is_correct=False)
        self.opt4 = AnswerOption.objects.create(question=self.choice_q, text="Русе", is_correct=False)

        self.numeric_q = NumericQuestion.objects.create(
            category=self.category,
            text="Колко са континентите?",
            correct_answer=7,
        )

        self.choice_round = Round.objects.create(
            game=self.game,
            number=1,
            question_type=Round.CHOICE,
            choice_question=self.choice_q,
        )
        self.numeric_round = Round.objects.create(
            game=self.game,
            number=2,
            question_type=Round.NUMERIC,
            numeric_question=self.numeric_q,
        )

    def test_choice_answer_creation(self):
        answer = RoundAnswer.objects.create(
            round=self.choice_round,
            player=self.player,
            selected_option=self.opt1,
            is_correct=True,
            points_awarded=100,
            submitted_at=timezone.now(),
        )
        self.assertEqual(answer.points_awarded, 100)
        self.assertTrue(answer.is_correct)
        self.assertEqual(answer.selected_option, self.opt1)
        self.assertIn("host", str(answer))

    def test_numeric_answer_creation(self):
        answer = RoundAnswer.objects.create(
            round=self.numeric_round,
            player=self.player,
            numeric_value=7,
            is_correct=True,
            points_awarded=150,
        )
        self.assertEqual(answer.numeric_value, 7)
        self.assertEqual(answer.points_awarded, 150)

    def test_answer_option_protected_from_deletion(self):
        RoundAnswer.objects.create(
            round=self.choice_round,
            player=self.player,
            selected_option=self.opt1,
        )
        with self.assertRaises(ProtectedError):
            self.opt1.delete()

    def test_deleting_round_cascades_to_answers(self):
        answer = RoundAnswer.objects.create(
            round=self.choice_round,
            player=self.player,
            selected_option=self.opt1,
        )
        self.choice_round.delete()
        self.assertFalse(RoundAnswer.objects.filter(id=answer.id).exists())

    def test_deleting_player_cascades_to_answers(self):
        answer = RoundAnswer.objects.create(
            round=self.choice_round,
            player=self.player,
            selected_option=self.opt1,
        )
        self.player.delete()
        self.assertFalse(RoundAnswer.objects.filter(id=answer.id).exists())
