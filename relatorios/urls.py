from django.urls import path, re_path

from . import views

app_name = "relatorios"
urlpatterns = [
    path("", views.relatorios, name="index"),
    re_path(r"^exportar/(?P<formato>xlsx|pdf)/$", views.exportar, name="exportar"),
]
