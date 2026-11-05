from django.conf import settings
from django.db import models


class RegistroAlteracao(models.Model):
    """Trilha de auditoria: quem alterou o quê, quando e de onde."""

    class Acao(models.TextChoices):
        CRIACAO = "criacao", "Criação"
        ALTERACAO = "alteracao", "Alteração"
        EXCLUSAO = "exclusao", "Exclusão"
        EXPORTACAO = "exportacao", "Exportação"
        ACESSO = "acesso", "Acesso"

    momento = models.DateTimeField("data/hora", auto_now_add=True, db_index=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    acao = models.CharField("ação", max_length=20, choices=Acao.choices)
    entidade = models.CharField("cadastro", max_length=50, db_index=True)
    objeto_id = models.CharField(max_length=50, blank=True, db_index=True)
    objeto_repr = models.CharField("registro", max_length=255, blank=True)
    alteracoes = models.JSONField("alterações", default=dict, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-momento"]
        verbose_name = "registro de alteração"
        verbose_name_plural = "registros de alterações"
        permissions = [
            ("ver_auditoria", "Pode consultar o registro de alterações"),
            ("ver_relatorios", "Pode consultar relatórios"),
            ("exportar_relatorios", "Pode exportar relatórios (Excel/PDF)"),
            ("gerenciar_usuarios", "Pode gerenciar usuários do sistema"),
        ]

    def __str__(self):
        return f"{self.get_acao_display()} — {self.entidade} — {self.objeto_repr}"

    @property
    def acao_cor(self):
        return {
            "criacao": "success", "alteracao": "primary", "exclusao": "danger",
            "exportacao": "info", "acesso": "secondary",
        }.get(self.acao, "secondary")
