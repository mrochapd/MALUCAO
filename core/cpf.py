"""Utilitários de CPF: normalização, validação (dígitos verificadores) e formatação."""
import re

from django.core.exceptions import ValidationError


def somente_digitos(valor: str | None) -> str:
    return re.sub(r"\D", "", valor or "")


def cpf_valido(valor: str | None) -> bool:
    cpf = somente_digitos(valor)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for tamanho in (9, 10):
        soma = sum(int(cpf[i]) * (tamanho + 1 - i) for i in range(tamanho))
        digito = (soma * 10) % 11
        if digito == 10:
            digito = 0
        if digito != int(cpf[tamanho]):
            return False
    return True


def validar_cpf(valor: str) -> None:
    if not cpf_valido(valor):
        raise ValidationError("CPF inválido. Confira os 11 dígitos.", code="cpf_invalido")


def formatar_cpf(valor: str | None) -> str:
    cpf = somente_digitos(valor)
    if len(cpf) != 11:
        return valor or ""
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"


def mascarar_cpf(valor: str | None) -> str:
    """Exibe apenas os dígitos centrais (padrão recomendado para LGPD): ***.456.789-**"""
    cpf = somente_digitos(valor)
    if len(cpf) != 11:
        return "***"
    return f"***.{cpf[3:6]}.{cpf[6:9]}-**"


def gerar_cpf_valido(base9: str) -> str:
    """Gera um CPF válido a partir de 9 dígitos (usado em testes e dados de demonstração)."""
    digitos = [int(d) for d in base9]
    for tamanho in (9, 10):
        soma = sum(digitos[i] * (tamanho + 1 - i) for i in range(tamanho))
        d = (soma * 10) % 11
        digitos.append(0 if d == 10 else d)
    return "".join(map(str, digitos))
