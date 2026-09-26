from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from apps.accounts.views import LoginView, LogoutView, MeView, RefreshView
from config.views import HealthView

urlpatterns = [
    path("api/v1/", include("apps.attendance.urls")),
    path("api/v1/", include("apps.staff.urls")),
    path("health/", HealthView.as_view(), name="health"),
    path("admin/", admin.site.urls),
    path("api/v1/auth/token/", LoginView.as_view(), name="token"),
    path("api/v1/auth/token/refresh/", RefreshView.as_view(), name="token-refresh"),
    path("api/v1/auth/logout/", LogoutView.as_view(), name="logout"),
    path("api/v1/auth/me/", MeView.as_view(), name="me"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
