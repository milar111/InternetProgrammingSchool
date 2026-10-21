import random
from django.db import transaction
from .models import Game, GamePlayer, WaitingPlayer

def checkEligible(user):
    return not GamePlayer.objects.filter(user=user, game__status__in=[Game.WAITING, Game.ACTIVE, Game.IN_PROGRESS]).exists()

def join_w_room(u):
    if not checkEligible(u) or WaitingPlayer.objects.filter(user=u).exists(): return False
    WaitingPlayer.objects.create(user=u)
    return True

def leave_w_room(u):
    return WaitingPlayer.objects.filter(user=u).delete()[0] > 0

def form_game():
    waitingUsers = [w.user for w in WaitingPlayer.objects.all() if checkEligible(w.user)]
    if len(waitingUsers) < 3: return None
    pickedUsers, teamColors = random.sample(waitingUsers, 3), ["red", "green", "blue"]
    with transaction.atomic():
        newGame = Game.objects.create(created_by=random.choice(pickedUsers), status=Game.WAITING)
        for idx, usr in enumerate(pickedUsers): GamePlayer.objects.create(game=newGame, user=usr, player_order=idx+1, color=teamColors[idx], score=0)
        WaitingPlayer.objects.filter(user__in=pickedUsers).delete()
    return newGame
