from django.urls import path

from knowledge_commons_profiles.pages import views

urlpatterns = [
    path(
        "registration/start/",
        views.site_page,
        {"slug": "registration-start"},
        name="registration_start",
    ),
]
