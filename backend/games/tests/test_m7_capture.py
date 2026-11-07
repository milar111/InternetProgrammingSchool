from datetime import timedelta
from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TestCase
from django.utils import timezone

from questions.models import Category, NumericQuestion
from games.models import Game, GamePlayer, Round, RoundAnswer, Territory, TerritoryCapture, TerritorySelectionRight
from games.services import (
    CAPTURE_REWARD,
    TERRITORY_SCORE_INCREMENT,
    WIN_REWARD,
    NoFreeTerritoriesError,
    NoSelectionRightsError,
    OutOfTurnSelectionError,
    PendingSelectionRightsError,
    PlayerNotEligibleError,
    TerritoryAlreadyOwnedError,
    TerritoryNotAdjacentError,
    choose_territory,
    create_numeric_round,
    evaluate_round,
    get_eligible_territories,
    get_selection_status,
    initialize_game,
    start_round,
    submit_numeric_answer,
)

User = get_user_model()


class M7BaseTestCase(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Тест Категория")
        self.questions = [
            NumericQuestion.objects.create(category=self.category, text=f"Въпрос {i}?", correct_answer=10 * i)
            for i in range(1, 20)
        ]

        self.host = User.objects.create_user(username="host_m7", email="host@example.com", password="pwd")
        self.users = [
            User.objects.create_user(username=f"student_{i}", email=f"s{i}@example.com", password="pwd")
            for i in range(1, 4)
        ]

        self.game = Game.objects.create(created_by=self.host, status=Game.WAITING)
        colors = ["red", "green", "blue"]
        for idx, u in enumerate(self.users):
            GamePlayer.objects.create(game=self.game, user=u, player_order=idx + 1, color=colors[idx])

        # Use fixed triplet for deterministic map setup: vidin (P1), varna (P2), blagoevgrad (P3)
        initialize_game(self.game, capital_triplet=("vidin", "varna", "blagoevgrad"))
        self.game.refresh_from_db()
        self.p1, self.p2, self.p3 = list(self.game.players.order_by("player_order"))

    def play_round_with_results(self, winner=None, runner_up=None):
        """Helper to run a round and complete it with given winner and runner-up."""
        t0 = timezone.now()
        r = create_numeric_round(self.game)
        start_round(r, timestamp=t0)
        q = r.get_current_question()
        c = q.correct_answer

        p_first = winner or self.p1
        p_second = runner_up or self.p2
        # p_third is whoever is left
        p_third = [p for p in (self.p1, self.p2, self.p3) if p not in (p_first, p_second)][0]

        submit_numeric_answer(r, p_first, c, timestamp=t0 + timedelta(seconds=1))
        submit_numeric_answer(r, p_second, c + 5, timestamp=t0 + timedelta(seconds=2))
        submit_numeric_answer(r, p_third, c + 20, timestamp=t0 + timedelta(seconds=3))

        evaluate_round(r, timestamp=t0 + timedelta(seconds=4))
        r.refresh_from_db()
        return r


class TerritoryDistributionTests(M7BaseTestCase):
    def test_distribution_2_plus_1_in_correct_order(self):
        # 12 free territories initially
        r = self.play_round_with_results(winner=self.p1, runner_up=self.p2)

        rights = list(r.selection_rights.order_by("order"))
        self.assertEqual(len(rights), 2)
        self.assertEqual(rights[0].player, self.p1)
        self.assertEqual(rights[0].allocated_choices, 2)
        self.assertEqual(rights[1].player, self.p2)
        self.assertEqual(rights[1].allocated_choices, 1)

        # P1's capital is vidin. Free neighbors of vidin: vratsa, sofia
        eligible_p1 = get_eligible_territories(self.game, self.p1)
        self.assertIn("vratsa", eligible_p1.values_list("slug", flat=True))

        # P1 makes Choice 1
        vratsa = Territory.objects.get(game=self.game, slug="vratsa")
        cap1 = choose_territory(self.game, self.p1, vratsa)
        self.assertEqual(cap1.choice_number, 1)
        self.assertEqual(vratsa.owner, self.p1)

        # Status: P1 has 1 remaining choice
        status = get_selection_status(self.game)
        self.assertEqual(status["current_player"], self.p1.user.username)
        self.assertEqual(status["remaining_choices"], 1)

        # P1 makes Choice 2 (e.g. sofia)
        sofia = Territory.objects.get(game=self.game, slug="sofia")
        cap2 = choose_territory(self.game, self.p1, sofia)
        self.assertEqual(cap2.choice_number, 2)
        self.assertEqual(sofia.owner, self.p1)

        # Now P1 is finished, turn switches to P2
        status = get_selection_status(self.game)
        self.assertEqual(status["current_player"], self.p2.user.username)
        self.assertEqual(status["remaining_choices"], 1)

        # P2's capital is varna. Free neighbors of varna: dobrich, shumen, burgas
        dobrich = Territory.objects.get(game=self.game, slug="dobrich")
        cap3 = choose_territory(self.game, self.p2, dobrich)
        self.assertEqual(cap3.choice_number, 1)
        self.assertEqual(dobrich.owner, self.p2)

        # All rights are now used
        status = get_selection_status(self.game)
        self.assertIsNone(status["current_player"])
        self.assertEqual(status["remaining_choices"], 0)

    def test_distribution_last_two_territories(self):
        # Assign 10 territories so only 2 remain free
        free = list(self.game.territories.filter(owner__isnull=True))
        for t in free[:-2]:
            t.owner = self.p3
            t.save()

        self.assertEqual(self.game.territories.filter(owner__isnull=True).count(), 2)

        # Round with 2 free territories
        r = self.play_round_with_results(winner=self.p1, runner_up=self.p2)

        # P1 gets 2 choices, P2 gets 0 choices
        rights = list(r.selection_rights.order_by("order"))
        self.assertEqual(len(rights), 1)
        self.assertEqual(rights[0].player, self.p1)
        self.assertEqual(rights[0].allocated_choices, 2)

    def test_distribution_last_one_territory(self):
        # Assign 11 territories so only 1 remains free
        free = list(self.game.territories.filter(owner__isnull=True))
        for t in free[:-1]:
            t.owner = self.p3
            t.save()

        self.assertEqual(self.game.territories.filter(owner__isnull=True).count(), 1)

        # Round with 1 free territory
        r = self.play_round_with_results(winner=self.p1, runner_up=self.p2)

        # P1 gets 1 choice, P2 gets 0 choices
        rights = list(r.selection_rights.order_by("order"))
        self.assertEqual(len(rights), 1)
        self.assertEqual(rights[0].player, self.p1)
        self.assertEqual(rights[0].allocated_choices, 1)


class TerritoryAdjacencyTests(M7BaseTestCase):
    def test_valid_adjacent_neighbor(self):
        self.play_round_with_results(winner=self.p1, runner_up=self.p2)

        # P1 capital is vidin; vratsa is direct neighbor
        vratsa = Territory.objects.get(game=self.game, slug="vratsa")
        capture = choose_territory(self.game, self.p1, vratsa)
        self.assertEqual(capture.territory, vratsa)
        self.assertEqual(vratsa.owner, self.p1)

    def test_invalid_non_adjacent_target_rejected(self):
        self.play_round_with_results(winner=self.p1, runner_up=self.p2)

        # burgas is on the opposite coast and NOT adjacent to vidin
        burgas = Territory.objects.get(game=self.game, slug="burgas")
        with self.assertRaises(TerritoryNotAdjacentError):
            choose_territory(self.game, self.p1, burgas)

    def test_adjacency_exception_when_no_free_neighbors(self):
        # Surround P1's capital (vidin neighbors: sofia, vratsa)
        sofia = Territory.objects.get(game=self.game, slug="sofia")
        vratsa = Territory.objects.get(game=self.game, slug="vratsa")
        sofia.owner = self.p2
        sofia.save()
        vratsa.owner = self.p3
        vratsa.save()

        # Now P1 has NO free adjacent neighbors
        eligible = get_eligible_territories(self.game, self.p1)
        all_free = self.game.territories.filter(owner__isnull=True)
        self.assertEqual(eligible.count(), all_free.count())

        self.play_round_with_results(winner=self.p1, runner_up=self.p2)

        # P1 can now pick any free territory (e.g. burgas)
        burgas = Territory.objects.get(game=self.game, slug="burgas")
        capture = choose_territory(self.game, self.p1, burgas)
        self.assertEqual(capture.territory, burgas)
        self.assertEqual(burgas.owner, self.p1)

    def test_adjacency_changes_after_first_choice(self):
        self.play_round_with_results(winner=self.p1, runner_up=self.p2)

        # P1 picks vratsa (adjacent to vidin)
        vratsa = Territory.objects.get(game=self.game, slug="vratsa")
        choose_territory(self.game, self.p1, vratsa)

        # pleven is adjacent to vratsa (but NOT to vidin!)
        pleven = Territory.objects.get(game=self.game, slug="pleven")
        eligible_now = get_eligible_territories(self.game, self.p1)
        self.assertIn("pleven", eligible_now.values_list("slug", flat=True))

        # P1 can now pick pleven as 2nd choice
        capture2 = choose_territory(self.game, self.p1, pleven)
        self.assertEqual(capture2.territory, pleven)
        self.assertEqual(pleven.owner, self.p1)


class SelectionRightsValidationTests(M7BaseTestCase):
    def test_foreign_player_cannot_choose(self):
        self.play_round_with_results(winner=self.p1, runner_up=self.p2)

        other_user = User.objects.create_user(username="outsider", email="out@test.com", password="pwd")
        other_game = Game.objects.create(created_by=other_user, status=Game.WAITING)
        other_player = GamePlayer.objects.create(game=other_game, user=other_user, player_order=1, color="red")

        vratsa = Territory.objects.get(game=self.game, slug="vratsa")
        with self.assertRaises(PlayerNotEligibleError):
            choose_territory(self.game, other_player, vratsa)

    def test_third_place_has_no_rights(self):
        self.play_round_with_results(winner=self.p1, runner_up=self.p2)
        vratsa = Territory.objects.get(game=self.game, slug="vratsa")

        with self.assertRaises(NoSelectionRightsError):
            choose_territory(self.game, self.p3, vratsa)

    def test_out_of_turn_selection_rejected(self):
        self.play_round_with_results(winner=self.p1, runner_up=self.p2)

        # P2 attempts to choose before P1 has made their choices
        dobrich = Territory.objects.get(game=self.game, slug="dobrich")
        with self.assertRaises(OutOfTurnSelectionError):
            choose_territory(self.game, self.p2, dobrich)

    def test_exceeding_allocated_choices_rejected(self):
        self.play_round_with_results(winner=self.p1, runner_up=self.p2)

        vratsa = Territory.objects.get(game=self.game, slug="vratsa")
        sofia = Territory.objects.get(game=self.game, slug="sofia")
        choose_territory(self.game, self.p1, vratsa)
        choose_territory(self.game, self.p1, sofia)

        # P1 tries 3rd choice
        pleven = Territory.objects.get(game=self.game, slug="pleven")
        with self.assertRaises(NoSelectionRightsError):
            choose_territory(self.game, self.p1, pleven)


class ScoringRulesTests(M7BaseTestCase):
    def test_victory_reward_and_capture_points(self):
        self.p1.score = 0
        self.p1.save()
        self.p2.score = 0
        self.p2.save()

        # Play round -> P1 wins (+200)
        self.play_round_with_results(winner=self.p1, runner_up=self.p2)
        self.p1.refresh_from_db()
        self.p2.refresh_from_db()

        self.assertEqual(self.p1.score, WIN_REWARD)
        self.assertEqual(self.p2.score, 0)

        # P1 captures vratsa (initial score 0 -> 100)
        vratsa = Territory.objects.get(game=self.game, slug="vratsa")
        self.assertEqual(vratsa.score, 0)

        cap1 = choose_territory(self.game, self.p1, vratsa)
        vratsa.refresh_from_db()
        self.p1.refresh_from_db()

        self.assertEqual(cap1.points_awarded, CAPTURE_REWARD)
        self.assertEqual(cap1.territory_score_before, 0)
        self.assertEqual(cap1.territory_score_after, TERRITORY_SCORE_INCREMENT)
        self.assertEqual(vratsa.score, TERRITORY_SCORE_INCREMENT)
        self.assertEqual(self.p1.score, WIN_REWARD + CAPTURE_REWARD)

        # P1 captures sofia
        sofia = Territory.objects.get(game=self.game, slug="sofia")
        choose_territory(self.game, self.p1, sofia)
        self.p1.refresh_from_db()
        self.assertEqual(self.p1.score, WIN_REWARD + 2 * CAPTURE_REWARD)

        # P2 captures dobrich (+100 for P2)
        dobrich = Territory.objects.get(game=self.game, slug="dobrich")
        choose_territory(self.game, self.p2, dobrich)
        self.p2.refresh_from_db()
        self.assertEqual(self.p2.score, CAPTURE_REWARD)

    def test_no_double_counting(self):
        r = self.play_round_with_results(winner=self.p1, runner_up=self.p2)
        self.p1.refresh_from_db()
        initial_score = self.p1.score

        # Calling evaluate again raises error and does NOT add points
        from games.services import RoundAlreadyCompletedError
        with self.assertRaises(RoundAlreadyCompletedError):
            evaluate_round(r)

        self.p1.refresh_from_db()
        self.assertEqual(self.p1.score, initial_score)


class ConquestPhaseLifecycleTests(M7BaseTestCase):
    def test_next_round_blocked_while_rights_pending(self):
        self.play_round_with_results(winner=self.p1, runner_up=self.p2)

        # Rights are still pending -> Cannot create next round!
        with self.assertRaises(PendingSelectionRightsError):
            create_numeric_round(self.game)

        # Exercise all rights
        vratsa = Territory.objects.get(game=self.game, slug="vratsa")
        sofia = Territory.objects.get(game=self.game, slug="sofia")
        dobrich = Territory.objects.get(game=self.game, slug="dobrich")
        choose_territory(self.game, self.p1, vratsa)
        choose_territory(self.game, self.p1, sofia)
        choose_territory(self.game, self.p2, dobrich)

        # Now creating next round succeeds!
        round2 = create_numeric_round(self.game)
        self.assertEqual(round2.number, 2)

    def test_phase_ends_when_full_map_captured(self):
        # Capture all remaining 12 territories
        free = list(self.game.territories.filter(owner__isnull=True))
        for t in free:
            t.owner = self.p1
            t.save()

        self.assertEqual(self.game.territories.filter(owner__isnull=True).count(), 0)
        status = get_selection_status(self.game)
        self.assertTrue(status["phase_completed"])

        with self.assertRaises(NoFreeTerritoriesError):
            create_numeric_round(self.game)


class AtomicityAndUnresolvedResultsTests(M7BaseTestCase):
    def test_atomicity_failure_leaves_no_partial_state(self):
        self.play_round_with_results(winner=self.p1, runner_up=self.p2)
        self.p1.refresh_from_db()
        burgas = Territory.objects.get(game=self.game, slug="burgas")

        p1_score_before = self.p1.score
        grant = TerritorySelectionRight.objects.get(round__game=self.game, player=self.p1)
        used_before = grant.used_choices

        with self.assertRaises(TerritoryNotAdjacentError):
            choose_territory(self.game, self.p1, burgas)

        # Verify nothing changed
        burgas.refresh_from_db()
        self.assertIsNone(burgas.owner)
        self.assertEqual(burgas.score, 0)

        self.p1.refresh_from_db()
        self.assertEqual(self.p1.score, p1_score_before)

        grant.refresh_from_db()
        self.assertEqual(grant.used_choices, used_before)

    def test_unresolved_second_place_preserves_first_place_rights(self):
        t0 = timezone.now()
        r = create_numeric_round(self.game)
        start_round(r, timestamp=t0)
        q1 = r.get_current_question()
        c = q1.correct_answer

        # P1 is clear winner; P2 and P3 tie for 2nd
        t_ans = t0 + timedelta(seconds=1)
        submit_numeric_answer(r, self.p1, c, timestamp=t_ans)
        submit_numeric_answer(r, self.p2, c + 5, timestamp=t_ans)
        submit_numeric_answer(r, self.p3, c - 5, timestamp=t_ans)

        # Q1 evaluated -> Q2 created for P2 and P3
        evaluate_round(r, timestamp=t0 + timedelta(seconds=2))
        r.refresh_from_db()
        q2 = r.get_current_question()

        # Q2: Nobody answers
        evaluate_round(r, timestamp=q2.deadline + timedelta(seconds=1))
        r.refresh_from_db()
        q3 = r.get_current_question()

        # Q3: Nobody answers -> 2nd place reaches question limit!
        evaluate_round(r, timestamp=q3.deadline + timedelta(seconds=1))
        r.refresh_from_db()

        self.assertEqual(r.status, Round.COMPLETED)
        self.assertEqual(r.winner, self.p1)
        self.assertEqual(r.unresolved_reason, "question_limit_reached")

        # P1 gets their 2 choices; no choices for 2nd place
        rights = list(r.selection_rights.order_by("order"))
        self.assertEqual(len(rights), 1)
        self.assertEqual(rights[0].player, self.p1)
        self.assertEqual(rights[0].allocated_choices, 2)


class ConcurrencyBonusTests(M7BaseTestCase):
    def test_concurrent_choice_for_same_territory(self):
        self.play_round_with_results(winner=self.p1, runner_up=self.p2)
        vratsa = Territory.objects.get(game=self.game, slug="vratsa")

        # First capture succeeds
        cap1 = choose_territory(self.game, self.p1, vratsa)
        self.assertIsNotNone(cap1)

        # Second attempt for same territory fails
        with self.assertRaises(TerritoryAlreadyOwnedError):
            choose_territory(self.game, self.p1, vratsa)

    def test_concurrent_attempts_for_last_selection_right(self):
        # 1 free territory left
        free = list(self.game.territories.filter(owner__isnull=True))
        for t in free[:-1]:
            t.owner = self.p3
            t.save()

        self.play_round_with_results(winner=self.p1, runner_up=self.p2)

        last_free = self.game.territories.filter(owner__isnull=True).first()
        choose_territory(self.game, self.p1, last_free)

        # Second attempt when choices exhausted
        with self.assertRaises(NoSelectionRightsError):
            choose_territory(self.game, self.p1, last_free)
