"""Regras compartilhadas entre os módulos de eventos e de inscrição."""
from django.db import transaction

from .models import Evento, Pacote


def opcoes_por_evento(incluir_ids_pacote=(), incluir_ids_modalidade=()):
    """
    Estrutura (serializável em JSON) com os pacotes e modalidades disponíveis em cada
    evento. Usada pelo formulário de inscrição para exibir somente as opções vinculadas
    ao evento escolhido.
    """
    dados = {}
    eventos = Evento.objects.prefetch_related("modalidades", "pacotes__modalidades_permitidas")
    for evento in eventos:
        modalidades = [
            {"id": m.pk, "nome": m.nome, "tipo": m.get_tipo_display(), "naipe": m.naipe, "naipe_txt": m.naipe_curto}
            for m in evento.modalidades.all()
            if m.ativa or m.pk in incluir_ids_modalidade
        ]
        pacotes = [
            {
                "id": p.pk,
                "nome": p.nome,
                "valor": f"{p.valor:.2f}".replace(".", ","),
                "max": p.max_modalidades,
                "permitidas": [m.pk for m in p.modalidades_permitidas.all()],
                "beneficios": p.lista_beneficios,
            }
            for p in evento.pacotes.all()
            if p.ativo or p.pk in incluir_ids_pacote
        ]
        dados[str(evento.pk)] = {
            "nome": str(evento),
            "aceita": evento.aceita_inscricoes,
            "motivo": evento.motivo_inscricoes_fechadas,
            "modalidades": sorted(modalidades, key=lambda m: m["nome"]),
            "pacotes": pacotes,
        }
    return dados


@transaction.atomic
def duplicar_evento(origem: Evento, nome: str, edicao: str, copiar_pacotes: bool = True) -> Evento:
    """Cria uma nova edição de um evento com as mesmas modalidades (e pacotes), sem atletas."""
    novo = Evento.objects.create(
        nome=nome,
        edicao=edicao,
        descricao=origem.descricao,
        local=origem.local,
        status=Evento.Status.PLANEJAMENTO,
    )
    novo.modalidades.set(origem.modalidades.all())
    if copiar_pacotes:
        for pacote in origem.pacotes.all():
            copia = Pacote.objects.create(
                evento=novo,
                nome=pacote.nome,
                descricao=pacote.descricao,
                valor=pacote.valor,
                beneficios=pacote.beneficios,
                max_modalidades=pacote.max_modalidades,
                ativo=pacote.ativo,
            )
            copia.modalidades_permitidas.set(pacote.modalidades_permitidas.all())
    return novo
