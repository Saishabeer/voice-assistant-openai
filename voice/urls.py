from django.urls import path
from .views import index, realtime_session, save_conversation

urlpatterns = [
    path("", index, name="index"),
    path("session/", realtime_session, name="session"),
    path("save-conversation/", save_conversation, name="save_conversation"),
    # Optional legacy API alias for saving conversations:
    path("api/conversations/save/", save_conversation, name="save_conversation_legacy"),
]