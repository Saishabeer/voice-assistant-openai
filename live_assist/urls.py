from django.contrib import admin
from django.urls import path
from voice import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.index, name="index"),
    path("session/", views.realtime_session, name="realtime_session"),
    path("save-conversation/", views.save_conversation, name="save_conversation"),
]
