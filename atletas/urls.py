from django.urls import path

from . import views

app_name = "atletas"
urlpatterns = [
    path("", views.AtletaListView.as_view(), name="lista"),
    path("novo/", views.atleta_criar, name="novo"),
    path("verificar-cpf/", views.verificar_cpf, name="verificar_cpf"),
    path("possiveis-duplicados/", views.DuplicadosView.as_view(), name="duplicados"),
    path("<int:pk>/", views.AtletaDetailView.as_view(), name="detalhe"),
    path("<int:pk>/editar/", views.AtletaUpdateView.as_view(), name="editar"),
    path("<int:pk>/excluir/", views.AtletaDeleteView.as_view(), name="excluir"),
    path("<int:atleta_pk>/inscricoes/nova/", views.inscricao_form, name="inscricao_nova"),
    path("inscricoes/<int:pk>/editar/", views.inscricao_form, name="inscricao_editar"),
    path("inscricoes/<int:pk>/excluir/", views.InscricaoDeleteView.as_view(), name="inscricao_excluir"),
]
