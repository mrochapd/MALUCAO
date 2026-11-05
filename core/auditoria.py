"""
Registro automático de alterações importantes nos cadastros.

Os sinais do Django capturam criação, alteração e exclusão dos modelos auditados
(inclusive feitas pelo /admin), e o middleware informa o usuário e o IP.
Dados pessoais sensíveis (CPF) são gravados mascarados no log.
"""
import datetime
import decimal

from django.db.models.signals import m2m_changed, post_delete, post_save, pre_save

from .cpf import mascarar_cpf
from .middleware import requisicao_atual
from .rede import ip_cliente

CAMPOS_IGNORADOS = {"criado_em", "atualizado_em", "password", "last_login"}
CAMPOS_MASCARADOS = {"cpf": mascarar_cpf}


def _ip(request):
    return ip_cliente(request)


def _usuario(request):
    user = getattr(request, "user", None)
    return user if user is not None and user.is_authenticated else None


def _valor(instancia, campo):
    valor = getattr(instancia, campo.attname)
    if campo.name in CAMPOS_MASCARADOS:
        return CAMPOS_MASCARADOS[campo.name](valor)
    if campo.is_relation and valor is not None:
        relacionado = getattr(instancia, campo.name, None)
        return str(relacionado) if relacionado is not None else valor
    if campo.choices:
        return dict(campo.flatchoices).get(valor, valor)
    if isinstance(valor, (datetime.date, datetime.datetime, decimal.Decimal)):
        return str(valor)
    return valor


def _snapshot(instancia):
    return {
        campo.name: _valor(instancia, campo)
        for campo in instancia._meta.concrete_fields
        if campo.name not in CAMPOS_IGNORADOS and not campo.primary_key
    }


def registrar(acao, entidade, objeto_id="", objeto_repr="", alteracoes=None, request=None):
    from .models import RegistroAlteracao

    request = request or requisicao_atual()
    return RegistroAlteracao.objects.create(
        usuario=_usuario(request),
        acao=acao,
        entidade=entidade,
        objeto_id=str(objeto_id or ""),
        objeto_repr=str(objeto_repr)[:255],
        alteracoes=alteracoes or {},
        ip=_ip(request),
    )


def _entidade(sender):
    return str(sender._meta.verbose_name).capitalize()


def _pre_save(sender, instance, **kwargs):
    if instance.pk:
        anterior = sender._default_manager.filter(pk=instance.pk).first()
        instance._auditoria_anterior = _snapshot(anterior) if anterior else None
    else:
        instance._auditoria_anterior = None


def _post_save(sender, instance, created, **kwargs):
    atual = _snapshot(instance)
    if created:
        registrar("criacao", _entidade(sender), instance.pk, str(instance), {"novo": atual})
        return
    anterior = getattr(instance, "_auditoria_anterior", None) or {}
    diff = {
        campo: {"de": anterior.get(campo), "para": valor}
        for campo, valor in atual.items()
        if anterior.get(campo) != valor
    }
    if diff:
        registrar("alteracao", _entidade(sender), instance.pk, str(instance), diff)


def _post_delete(sender, instance, **kwargs):
    registrar("exclusao", _entidade(sender), instance.pk, str(instance), {"removido": _snapshot(instance)})


def _m2m_changed(sender, instance, action, model, pk_set, reverse, **kwargs):
    if reverse or action not in {"post_add", "post_remove", "post_clear"}:
        return
    nome_campo = next(
        (f.name for f in instance._meta.many_to_many if f.remote_field.through is sender), "relacionamento"
    )
    if action == "post_clear":
        detalhe = {"removidos": "todos"}
    else:
        nomes = sorted(str(o) for o in model._default_manager.filter(pk__in=pk_set or []))
        if not nomes:
            return
        detalhe = {"adicionados" if action == "post_add" else "removidos": nomes}
    registrar("alteracao", type(instance)._meta.verbose_name.capitalize(), instance.pk, str(instance),
              {nome_campo: detalhe})


def conectar(*modelos):
    for modelo in modelos:
        uid = f"auditoria_{modelo._meta.label_lower}"
        pre_save.connect(_pre_save, sender=modelo, dispatch_uid=uid + "_pre")
        post_save.connect(_post_save, sender=modelo, dispatch_uid=uid + "_post")
        post_delete.connect(_post_delete, sender=modelo, dispatch_uid=uid + "_del")
        for campo in modelo._meta.many_to_many:
            m2m_changed.connect(_m2m_changed, sender=campo.remote_field.through, dispatch_uid=f"{uid}_{campo.name}")


def login_sucesso(sender, request, user, **kwargs):
    registrar("acesso", "Login", user.pk, user.get_username(), {"resultado": "sucesso"}, request)


def login_falha(sender, credentials, request=None, **kwargs):
    registrar("acesso", "Login", "", credentials.get("username", ""), {"resultado": "falha"}, request)
