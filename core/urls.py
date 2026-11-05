from django.urls import path

from . import views

app_name = "core"
urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("auditoria/", views.AuditoriaListView.as_view(), name="auditoria"),
    path("usuarios/", views.UsuarioListView.as_view(), name="usuarios"),
    path("usuarios/novo/", views.UsuarioCreateView.as_view(), name="usuario_novo"),
    path("usuarios/<int:pk>/editar/", views.UsuarioUpdateView.as_view(), name="usuario_editar"),
    path("privacidade/", views.PrivacidadeView.as_view(), name="privacidade"),
    path("saude/", views.saude, name="saude"),
]
