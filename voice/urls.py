# URL configuration for the voice app (kept minimal and clear).
from django.urls import path
from .views import index, realtime_session, save_conversation

urlpatterns = [
    path("", index, name="index"),
    path("session/", realtime_session, name="realtime_session"),
    path("save-conversation/", save_conversation, name="save_conversation"),
]