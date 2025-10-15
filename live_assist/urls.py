# Project URLConf: delegate to app routes and expose admin only.
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("voice.urls")),
]