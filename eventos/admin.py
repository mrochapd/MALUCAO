from django.contrib import admin

from .models import Evento, Modalidade, Pacote


@admin.register(Modalidade)
class ModalidadeAdmin(admin.ModelAdmin):
    list_display = ["nome", "tipo", "ativa"]
    list_filter = ["tipo", "ativa"]
    search_fields = ["nome"]


class PacoteInline(admin.TabularInline):
    model = Pacote
    extra = 0
    fields = ["nome", "valor", "max_modalidades", "ativo"]


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ["nome", "edicao", "data_inicio", "data_fim", "status"]
    list_filter = ["status"]
    search_fields = ["nome", "edicao", "local"]
    filter_horizontal = ["modalidades"]
    inlines = [PacoteInline]


@admin.register(Pacote)
class PacoteAdmin(admin.ModelAdmin):
    list_display = ["nome", "evento", "valor", "ativo"]
    list_filter = ["evento", "ativo"]
    filter_horizontal = ["modalidades_permitidas"]
