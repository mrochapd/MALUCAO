from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Núcleo do sistema"

    def ready(self):
        from django.contrib.auth.models import Group, User
        from django.contrib.auth.signals import user_logged_in, user_login_failed

        from atletas.models import Atleta, Inscricao
        from eventos.models import Evento, Modalidade, Pacote

        from . import auditoria

        auditoria.conectar(Atleta, Inscricao, Evento, Modalidade, Pacote, User, Group)

        def _login(sender, request, user, **kwargs):
            auditoria.registrar("acesso", "Login", user.pk, user.get_username(), {"resultado": "sucesso"}, request)

        def _falha(sender, credentials, request=None, **kwargs):
            auditoria.registrar(
                "acesso", "Login", "", credentials.get("username", ""), {"resultado": "falha"}, request
            )

        user_logged_in.connect(_login, dispatch_uid="auditoria_login")
        user_login_failed.connect(_falha, dispatch_uid="auditoria_login_falha")
