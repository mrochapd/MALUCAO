from django.contrib import admin

from .models import Atleta, Inscricao


class InscricaoInline(admin.TabularInline):
    model = Inscricao
    extra = 0
    fields = ["evento", "pacote", "modalidades"]


@admin.register(Atleta)
class AtletaAdmin(admin.ModelAdmin):
    list_display = ["nome", "cpf_mascarado", "email", "criado_em"]
    search_fields = ["nome", "cpf", "email"]
    inlines = [InscricaoInline]


@admin.register(Inscricao)
class InscricaoAdmin(admin.ModelAdmin):
    list_display = ["atleta", "evento", "pacote", "criado_em"]
    list_filter = ["evento", "pacote"]
    search_fields = ["atleta__nome", "atleta__cpf"]
    filter_horizontal = ["modalidades"]
