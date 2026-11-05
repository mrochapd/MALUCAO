from django.urls import path

from . import views

app_name = "eventos"
urlpatterns = [
    path("", views.EventoListView.as_view(), name="eventos"),
    path("novo/", views.EventoCreateView.as_view(), name="evento_novo"),
    path("<int:pk>/", views.EventoDetailView.as_view(), name="evento_detalhe"),
    path("<int:pk>/editar/", views.EventoUpdateView.as_view(), name="evento_editar"),
    path("<int:pk>/excluir/", views.EventoDeleteView.as_view(), name="evento_excluir"),
    path("<int:pk>/duplicar/", views.evento_duplicar, name="evento_duplicar"),
    path("<int:pk>/status/", views.evento_status, name="evento_status"),
    path("modalidades/", views.ModalidadeListView.as_view(), name="modalidades"),
    path("modalidades/nova/", views.ModalidadeCreateView.as_view(), name="modalidade_nova"),
    path("modalidades/<int:pk>/editar/", views.ModalidadeUpdateView.as_view(), name="modalidade_editar"),
    path("modalidades/<int:pk>/excluir/", views.ModalidadeDeleteView.as_view(), name="modalidade_excluir"),
    path("modalidades/<int:pk>/alternar/", views.modalidade_alternar, name="modalidade_alternar"),
    path("pacotes/", views.PacoteListView.as_view(), name="pacotes"),
    path("pacotes/novo/", views.PacoteCreateView.as_view(), name="pacote_novo"),
    path("pacotes/<int:pk>/editar/", views.PacoteUpdateView.as_view(), name="pacote_editar"),
    path("pacotes/<int:pk>/excluir/", views.PacoteDeleteView.as_view(), name="pacote_excluir"),
]
