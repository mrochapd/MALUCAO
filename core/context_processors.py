from django.conf import settings


def sistema(request):
    return {
        "SISTEMA_NOME": settings.SISTEMA_NOME,
        "SISTEMA_ORGANIZACAO": settings.SISTEMA_ORGANIZACAO,
    }
