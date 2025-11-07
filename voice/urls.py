from django.urls import path
from django.contrib.auth import views as auth_views
from .views import (
    index,
    realtime_session,
    save_conversation,
    signup_view,
    conversations_json,
    conversation_detail_json,
    conversation_delete_json,
)

urlpatterns = [
    path("", index, name="index"),

    # Auth
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("signup/", signup_view, name="signup"),

    # Realtime session + save/import
    path("session/", realtime_session, name="session"),
    path("save-conversation/", save_conversation, name="save_conversation"),

    # History APIs
    path("conversations/", conversations_json, name="conversations_json"),
    path("conversations/<int:pk>/", conversation_detail_json, name="conversation_detail_json"),
    path("conversations/<int:pk>/delete/", conversation_delete_json, name="conversation_delete_json"),
]