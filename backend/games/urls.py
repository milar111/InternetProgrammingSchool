from django.urls import path
from .views import JoinWaitingRoomView, LeaveWaitingRoomView

urlpatterns = [
    path('join/', JoinWaitingRoomView.as_view(), name='waiting-room-join'),
    path('leave/', LeaveWaitingRoomView.as_view(), name='waiting-room-leave'),
]
