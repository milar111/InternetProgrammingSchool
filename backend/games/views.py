from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .waiting_room import join_w_room, leave_w_room, form_game

class JoinWaitingRoomView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        if not join_w_room(request.user): return Response({"error": "already waiting or in game"}, status=400)
        newGame = form_game()
        resData = {"message": "joined waiting room"}
        if newGame: resData["game_id"] = newGame.id
        return Response(resData, status=200)

class LeaveWaitingRoomView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        leave_w_room(request.user)
        return Response({"message": "left waiting room"}, status=200)
