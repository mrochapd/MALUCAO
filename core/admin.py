from django.contrib import admin

from .models import RegistroAlteracao


@admin.register(RegistroAlteracao)
class RegistroAlteracaoAdmin(admin.ModelAdmin):
    list_display = ["momento", "usuario", "acao", "entidade", "objeto_repr", "ip"]
    list_filter = ["acao", "entidade"]
    search_fields = ["objeto_repr", "usuario__username"]
    readonly_fields = [f.name for f in RegistroAlteracao._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
