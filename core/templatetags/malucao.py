from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def brl(valor):
    """Formata como moeda brasileira: R$ 1.234,56"""
    try:
        v = Decimal(valor)
    except (InvalidOperation, TypeError, ValueError):
        return valor
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


@register.simple_tag(takes_context=True)
def cpf(context, atleta):
    """CPF completo apenas para quem tem permissão; os demais veem o CPF mascarado (LGPD)."""
    user = context["request"].user
    if user.has_perm("atletas.ver_dados_pessoais"):
        return atleta.cpf_formatado
    return atleta.cpf_mascarado


@register.simple_tag(takes_context=True)
def menu_ativo(context, *prefixos):
    """Marca o item do menu. Prefixos iniciados com "!" são exclusões."""
    caminho = context["request"].path
    if any(caminho.startswith(p[1:]) for p in prefixos if p.startswith("!")):
        return ""
    for p in prefixos:
        if p.startswith("!"):
            continue
        if (p == "/" and caminho == "/") or (p != "/" and caminho.startswith(p)):
            return "active"
    return ""


@register.filter
def iniciais(usuario):
    nome = usuario.get_full_name() or usuario.get_username()
    partes = nome.split()
    return (partes[0][0] + (partes[-1][0] if len(partes) > 1 else "")).upper()


@register.filter
def get(dicionario, chave):
    return dicionario.get(chave) if hasattr(dicionario, "get") else None
