from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from games.models import Game, GamePlayer, Round, RoundAnswer
from questions.models import AnswerOption, Category, ChoiceQuestion, NumericQuestion

User = get_user_model()


class GamePlayerConstraintTests(TestCase):
    def setUp(self):
        self.host = User.objects.create_user(username="host", email="host@example.com", password="pwd")
        self.user1 = User.objects.create_user(username="p1", email="p1@example.com", password="pwd")
        self.user2 = User.objects.create_user(username="p2", email="p2@example.com", password="pwd")
        self.game = Game.objects.create(created_by=self.host)

    def test_unique_game_player(self):
        GamePlayer.objects.create(game=self.game, user=self.user1, player_order=1)
        with self.assertRaises(IntegrityError):
            GamePlayer.objects.create(game=self.game, user=self.user1, player_order=2)

    def test_unique_player_order(self):
        GamePlayer.objects.create(game=self.game, user=self.user1, player_order=1)
        with self.assertRaises(IntegrityError):
            GamePlayer.objects.create(game=self.game, user=self.user2, player_order=1)

    def test_same_user_can_join_different_games(self):
        game2 = Game.objects.create(created_by=self.host)
        player_g1 = GamePlayer.objects.create(game=self.game, user=self.user1, player_order=1)
        player_g2 = GamePlayer.objects.create(game=game2, user=self.user1, player_order=1)
        self.assertNotEqual(player_g1.game, player_g2.game)


class RoundConstraintAndValidationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="host", email="host@example.com", password="pwd")
        self.game = Game.objects.create(created_by=self.user)
        self.category = Category.objects.create(name="История")

        self.choice_q = ChoiceQuestion.objects.create(category=self.category, text="Въпрос 1?")
        for i in range(4):
            AnswerOption.objects.create(question=self.choice_q, text=f"Отговор {i}", is_correct=(i == 0))

        self.numeric_q = NumericQuestion.objects.create(
            category=self.category,
            text="Числов въпрос?",
            correct_answer=42,
        )

    def test_unique_game_round_number(self):
        Round.objects.create(
            game=self.game,
            number=1,
            question_type=Round.CHOICE,
            choice_question=self.choice_q,
        )
        with self.assertRaises(IntegrityError):
            Round.objects.create(
                game=self.game,
                number=1,
                question_type=Round.NUMERIC,
                numeric_question=self.numeric_q,
            )

    def test_choice_round_requires_choice_question(self):
        round_obj = Round(
            game=self.game,
            number=1,
            question_type=Round.CHOICE,
            choice_question=None,
        )
        with self.assertRaises(ValidationError):
            round_obj.clean()

    def test_choice_round_rejects_numeric_question(self):
        round_obj = Round(
            game=self.game,
            number=1,
            question_type=Round.CHOICE,
            choice_question=self.choice_q,
            numeric_question=self.numeric_q,
        )
        with self.assertRaises(ValidationError):
            round_obj.clean()

    def test_numeric_round_requires_numeric_question(self):
        round_obj = Round(
            game=self.game,
            number=1,
            question_type=Round.NUMERIC,
            numeric_question=None,
        )
        with self.assertRaises(ValidationError):
            round_obj.clean()

    def test_numeric_round_rejects_choice_question(self):
        round_obj = Round(
            game=self.game,
            number=1,
            question_type=Round.NUMERIC,
            numeric_question=self.numeric_q,
            choice_question=self.choice_q,
        )
        with self.assertRaises(ValidationError):
            round_obj.clean()

    def test_valid_rounds_pass_clean(self):
        choice_r = Round(
            game=self.game,
            number=1,
            question_type=Round.CHOICE,
            choice_question=self.choice_q,
        )
        choice_r.clean()

        numeric_r = Round(
            game=self.game,
            number=2,
            question_type=Round.NUMERIC,
            numeric_question=self.numeric_q,
        )
        numeric_r.clean()


class RoundAnswerConstraintAndValidationTests(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username="u1", email="u1@example.com", password="pwd")
        self.user2 = User.objects.create_user(username="u2", email="u2@example.com", password="pwd")

        self.game1 = Game.objects.create(created_by=self.user1)
        self.game2 = Game.objects.create(created_by=self.user2)

        self.player_g1 = GamePlayer.objects.create(game=self.game1, user=self.user1, player_order=1)
        self.player_g2 = GamePlayer.objects.create(game=self.game2, user=self.user2, player_order=1)

        self.category = Category.objects.create(name="Общи")
        self.choice_q1 = ChoiceQuestion.objects.create(category=self.category, text="Въпрос 1?")
        self.opt1_q1 = AnswerOption.objects.create(question=self.choice_q1, text="А", is_correct=True)
        self.opt2_q1 = AnswerOption.objects.create(question=self.choice_q1, text="Б", is_correct=False)
        self.opt3_q1 = AnswerOption.objects.create(question=self.choice_q1, text="В", is_correct=False)
        self.opt4_q1 = AnswerOption.objects.create(question=self.choice_q1, text="Г", is_correct=False)

        self.choice_q2 = ChoiceQuestion.objects.create(category=self.category, text="Въпрос 2?")
        self.opt1_q2 = AnswerOption.objects.create(question=self.choice_q2, text="X", is_correct=True)
        self.opt2_q2 = AnswerOption.objects.create(question=self.choice_q2, text="Y", is_correct=False)
        self.opt3_q2 = AnswerOption.objects.create(question=self.choice_q2, text="Z", is_correct=False)
        self.opt4_q2 = AnswerOption.objects.create(question=self.choice_q2, text="W", is_correct=False)

        self.numeric_q = NumericQuestion.objects.create(
            category=self.category,
            text="Числов?",
            correct_answer=10,
        )

        self.round_choice = Round.objects.create(
            game=self.game1,
            number=1,
            question_type=Round.CHOICE,
            choice_question=self.choice_q1,
        )
        self.round_numeric = Round.objects.create(
            game=self.game1,
            number=2,
            question_type=Round.NUMERIC,
            numeric_question=self.numeric_q,
        )

    def test_unique_round_player_answer(self):
        RoundAnswer.objects.create(
            round=self.round_choice,
            player=self.player_g1,
            selected_option=self.opt1_q1,
        )
        with self.assertRaises(IntegrityError):
            RoundAnswer.objects.create(
                round=self.round_choice,
                player=self.player_g1,
                selected_option=self.opt2_q1,
            )

    def test_player_must_belong_to_round_game(self):
        answer = RoundAnswer(
            round=self.round_choice,
            player=self.player_g2,
            selected_option=self.opt1_q1,
        )
        with self.assertRaises(ValidationError):
            answer.clean()

    def test_answer_cannot_have_both_option_and_numeric_value(self):
        answer = RoundAnswer(
            round=self.round_choice,
            player=self.player_g1,
            selected_option=self.opt1_q1,
            numeric_value=42,
        )
        with self.assertRaises(ValidationError):
            answer.clean()

    def test_choice_round_rejects_numeric_value(self):
        answer = RoundAnswer(
            round=self.round_choice,
            player=self.player_g1,
            numeric_value=10,
        )
        with self.assertRaises(ValidationError):
            answer.clean()

    def test_choice_round_rejects_option_from_another_question(self):
        answer = RoundAnswer(
            round=self.round_choice,
            player=self.player_g1,
            selected_option=self.opt1_q2,
        )
        with self.assertRaises(ValidationError):
            answer.clean()

    def test_numeric_round_rejects_selected_option(self):
        answer = RoundAnswer(
            round=self.round_numeric,
            player=self.player_g1,
            selected_option=self.opt1_q1,
        )
        with self.assertRaises(ValidationError):
            answer.clean()

    def test_valid_answers_pass_clean(self):
        choice_ans = RoundAnswer(
            round=self.round_choice,
            player=self.player_g1,
            selected_option=self.opt1_q1,
        )
        choice_ans.clean()

        numeric_ans = RoundAnswer(
            round=self.round_numeric,
            player=self.player_g1,
            numeric_value=10,
        )
        numeric_ans.clean()
