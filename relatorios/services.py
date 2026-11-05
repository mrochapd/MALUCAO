"""
Geração dos relatórios. Cada relatório é uma tabela (colunas + linhas) que é
exibida na tela e exportada para Excel ou PDF a partir dos mesmos dados.
"""
from dataclasses import dataclass, field

from django.db.models import Count, Q
from django.utils import timezone

from atletas.models import Inscricao
from eventos.models import Evento, Modalidade, Pacote


def _data(d):
    return d.strftime("%d/%m/%Y") if d else "—"


def _moeda(v):
    if v is None:
        return "—"
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


@dataclass
class Relatorio:
    chave: str
    titulo: str
    colunas: list[str]
    linhas: list[list] = field(default_factory=list)
    agrupar_por: int | None = None  # índice da coluna usada para agrupar na tela
    rodape: list[str] = field(default_factory=list)
    contem_dados_pessoais: bool = True

    @property
    def grupos(self):
        """Linhas agrupadas pela coluna `agrupar_por` (para exibição)."""
        if self.agrupar_por is None:
            return [(None, self.linhas)]
        grupos, atual, linhas = [], object(), []
        for linha in self.linhas:
            if linha[self.agrupar_por] != atual:
                if linhas:
                    grupos.append((atual, linhas))
                atual, linhas = linha[self.agrupar_por], []
            linhas.append(linha)
        if linhas:
            grupos.append((atual, linhas))
        return grupos


    @property
    def colunas_tabela(self):
        return [c for i, c in enumerate(self.colunas) if i != self.agrupar_por]

    @property
    def grupos_tabela(self):
        """Grupos com cada linha como pares (coluna, valor), sem a coluna de agrupamento."""
        return [
            (grupo, [[(c, v) for i, (c, v) in enumerate(zip(self.colunas, linha)) if i != self.agrupar_por]
                     for linha in linhas])
            for grupo, linhas in self.grupos
        ]


TIPOS = [
    ("inscritos", "Lista geral de atletas inscritos"),
    ("por_modalidade", "Atletas por modalidade"),
    ("por_pacote", "Atletas por pacote"),
    ("qtd_modalidade", "Quantidade de inscritos por modalidade"),
    ("qtd_evento", "Quantidade de inscritos por evento"),
    ("qtd_pacote", "Quantidade de atletas por pacote"),
    ("relacao", "Relação completa de atletas (dados e modalidades)"),
]
TITULOS = dict(TIPOS)


SEXOS = {"M": "Masculino", "F": "Feminino"}


def _sexo(atleta):
    return SEXOS.get(atleta.sexo, "Não informado")


class Filtros:
    def __init__(self, evento: Evento | None = None, pacote: Pacote | None = None,
                 modalidade: Modalidade | None = None, sexo: str = ""):
        self.evento, self.pacote, self.modalidade = evento, pacote, modalidade
        self.sexo = sexo if sexo in SEXOS else ""

    def descricao(self) -> str:
        partes = []
        if self.evento:
            partes.append(f"Evento: {self.evento}")
        if self.pacote:
            partes.append(f"Pacote: {self.pacote}")
        if self.modalidade:
            partes.append(f"Modalidade: {self.modalidade}")
        if self.sexo:
            partes.append(f"Sexo: {SEXOS[self.sexo]}")
        return " · ".join(partes) or "Todos os eventos, pacotes e modalidades"

    def inscricoes(self):
        qs = Inscricao.objects.select_related("atleta", "evento", "pacote").prefetch_related("modalidades")
        if self.evento:
            qs = qs.filter(evento=self.evento)
        if self.pacote:
            qs = qs.filter(pacote=self.pacote)
        if self.modalidade:
            qs = qs.filter(modalidades=self.modalidade)
        if self.sexo:
            qs = qs.filter(atleta__sexo=self.sexo)
        return qs.distinct()

    def filtro_inscricao(self, prefixo="inscricoes__"):
        q = Q()
        if self.evento:
            q &= Q(**{f"{prefixo}evento": self.evento})
        if self.pacote:
            q &= Q(**{f"{prefixo}pacote": self.pacote})
        if self.sexo:
            q &= Q(**{f"{prefixo}atleta__sexo": self.sexo})
        return q


def gerar(chave: str, filtros: Filtros, mostrar_cpf_completo: bool = False) -> Relatorio:
    cpf = (lambda a: a.cpf_formatado) if mostrar_cpf_completo else (lambda a: a.cpf_mascarado)
    titulo = TITULOS.get(chave)
    if titulo is None:
        raise ValueError("Relatório desconhecido")

    def nomes_modalidades(inscricao):
        return ", ".join(inscricao.disputas())

    if chave == "inscritos":
        rel = Relatorio(chave, titulo, ["Atleta", "Sexo", "CPF", "E-mail", "Evento", "Pacote", "Modalidades",
                                        "Inscrito em"])
        for i in filtros.inscricoes().order_by("atleta__nome"):
            rel.linhas.append([i.atleta.nome, _sexo(i.atleta), cpf(i.atleta), i.atleta.email, str(i.evento),
                               i.pacote.nome, nomes_modalidades(i), _data(timezone.localtime(i.criado_em))])
        rel.rodape.append(f"Total de inscrições: {len(rel.linhas)}")

    elif chave == "por_modalidade":
        rel = Relatorio(chave, titulo, ["Disputa (modalidade e naipe)", "Atleta", "Sexo", "CPF", "E-mail", "Evento",
                                        "Pacote"], agrupar_por=0)
        linhas = []
        for i in filtros.inscricoes():
            for m in i.modalidades.all():
                if filtros.modalidade and m != filtros.modalidade:
                    continue
                linhas.append([m.nome_naipe(i.atleta.sexo), i.atleta.nome, _sexo(i.atleta), cpf(i.atleta),
                               i.atleta.email, str(i.evento), i.pacote.nome])
        rel.linhas = sorted(linhas, key=lambda l: (l[0], l[1]))
        rel.rodape.append(f"Total de participações: {len(rel.linhas)}")

    elif chave == "por_pacote":
        rel = Relatorio(chave, titulo, ["Pacote", "Atleta", "Sexo", "CPF", "E-mail", "Evento", "Modalidades"],
                        agrupar_por=0)
        for i in filtros.inscricoes().order_by("pacote__nome", "evento__nome", "atleta__nome"):
            rel.linhas.append([f"{i.pacote.nome} — {i.evento}", i.atleta.nome, _sexo(i.atleta), cpf(i.atleta),
                               i.atleta.email, str(i.evento), nomes_modalidades(i)])
        rel.rodape.append(f"Total de atletas: {len(rel.linhas)}")

    elif chave == "qtd_modalidade":
        rel = Relatorio(chave, titulo, ["Modalidade", "Tipo", "Naipe", "Masculino", "Feminino", "Total", "Observação"],
                        contem_dados_pessoais=False)
        filtro = filtros.filtro_inscricao()
        qs = Modalidade.objects.all()
        if filtros.evento:
            qs = qs.filter(eventos=filtros.evento)
        if filtros.modalidade:
            qs = qs.filter(pk=filtros.modalidade.pk)
        qs = qs.annotate(
            total=Count("inscricoes", filter=filtro, distinct=True),
            masc=Count("inscricoes", filter=filtro & Q(inscricoes__atleta__sexo="M"), distinct=True),
            fem=Count("inscricoes", filter=filtro & Q(inscricoes__atleta__sexo="F"), distinct=True),
        ).order_by("-total", "nome")
        for m in qs:
            obs = ""
            if m.naipe == Modalidade.Naipe.DUPLA_MISTA and m.total and (not m.masc or not m.fem):
                obs = "Atenção: dupla mista exige ao menos 1 homem e 1 mulher"
            elif not m.ativa:
                obs = "Modalidade inativa"
            rel.linhas.append([m.nome, m.get_tipo_display(), m.naipe_curto, m.masc, m.fem, m.total, obs])
        rel.rodape.append(
            f"Participações: {sum(l[5] for l in rel.linhas)} "
            f"(masculino: {sum(l[3] for l in rel.linhas)} · feminino: {sum(l[4] for l in rel.linhas)})"
        )

    elif chave == "qtd_evento":
        rel = Relatorio(chave, titulo, ["Evento", "Status", "Início", "Encerramento", "Local", "Masculino",
                                        "Feminino", "Inscritos"], contem_dados_pessoais=False)
        filtro = Q()
        if filtros.pacote:
            filtro &= Q(inscricoes__pacote=filtros.pacote)
        if filtros.modalidade:
            filtro &= Q(inscricoes__modalidades=filtros.modalidade)
        if filtros.sexo:
            filtro &= Q(inscricoes__atleta__sexo=filtros.sexo)
        qs = Evento.objects.all()
        if filtros.evento:
            qs = qs.filter(pk=filtros.evento.pk)
        qs = qs.annotate(
            total=Count("inscricoes", filter=filtro, distinct=True),
            masc=Count("inscricoes", filter=filtro & Q(inscricoes__atleta__sexo="M"), distinct=True),
            fem=Count("inscricoes", filter=filtro & Q(inscricoes__atleta__sexo="F"), distinct=True),
        )
        for e in qs:
            rel.linhas.append([str(e), e.get_status_display(), _data(e.data_inicio), _data(e.data_fim),
                               e.local or "—", e.masc, e.fem, e.total])
        rel.rodape.append(f"Total de inscrições: {sum(l[7] for l in rel.linhas)}")

    elif chave == "qtd_pacote":
        rel = Relatorio(chave, titulo, ["Pacote", "Evento", "Valor", "Status", "Atletas", "Receita estimada"],
                        contem_dados_pessoais=False)
        filtro = Q()
        if filtros.modalidade:
            filtro &= Q(inscricoes__modalidades=filtros.modalidade)
        if filtros.sexo:
            filtro &= Q(inscricoes__atleta__sexo=filtros.sexo)
        qs = Pacote.objects.select_related("evento")
        if filtros.evento:
            qs = qs.filter(evento=filtros.evento)
        if filtros.pacote:
            qs = qs.filter(pk=filtros.pacote.pk)
        qs = qs.annotate(total=Count("inscricoes", filter=filtro, distinct=True)).order_by("evento__nome", "valor")
        receita = 0
        for p in qs:
            receita += p.valor * p.total
            rel.linhas.append([p.nome, str(p.evento), _moeda(p.valor), "Ativo" if p.ativo else "Inativo", p.total,
                               _moeda(p.valor * p.total)])
        rel.rodape.append(f"Total de atletas: {sum(l[4] for l in rel.linhas)} · Receita estimada: {_moeda(receita)}")

    else:  # relacao
        rel = Relatorio(chave, titulo, ["Atleta", "Sexo", "CPF", "E-mail", "Telefone", "Evento", "Pacote", "Valor",
                                        "Disputas (modalidade e naipe)", "Consentimento LGPD"])
        ids_atletas = set()
        for i in filtros.inscricoes().order_by("atleta__nome", "evento__nome"):
            a = i.atleta
            ids_atletas.add(a.pk)
            rel.linhas.append([a.nome, _sexo(a), cpf(a), a.email, a.telefone or "—", str(i.evento), i.pacote.nome,
                               _moeda(i.pacote.valor), ", ".join(i.disputas()),
                               "Sim" if a.consentimento_lgpd else "Não"])
        rel.rodape.append(
            f"Atletas distintos: {len(ids_atletas)} · Inscrições: {len(rel.linhas)}"
        )
    return rel

