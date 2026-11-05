"""Identificação do IP real do cliente quando o sistema roda atrás de um proxy (Render, Nginx...)."""
from django.conf import settings


def ip_cliente(request) -> str | None:
    """
    Com TRUSTED_PROXY_COUNT = N, usa o N-ésimo endereço da direita no X-Forwarded-For
    (o que foi anexado pelo proxy confiável — não pode ser forjado pelo cliente).
    Sem proxy configurado, usa REMOTE_ADDR.
    """
    if request is None:
        return None
    n = getattr(settings, "TRUSTED_PROXY_COUNT", 0)
    if n > 0:
        cadeia = [ip.strip() for ip in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if ip.strip()]
        if len(cadeia) >= n:
            return cadeia[-n]
    return request.META.get("REMOTE_ADDR")
