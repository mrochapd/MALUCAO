"""
Configuração inicial (idempotente — pode ser executada várias vezes):

* cria os perfis de acesso (Administrador, Operador de inscrições, Consulta);
* cadastra as 16 modalidades iniciais da JUV;
* cadastra o evento JUV – Jogos Universitários do Vale do Aço com os pacotes Atleta e Completo;
* opcionalmente cria um superusuário a partir das variáveis DJANGO_SUPERUSER_*;
* com --demo, gera atletas fictícios para demonstração.
"""
import os
import random

from django.contrib.auth.models import Group, Permission, User
from django.core.management.base import BaseCommand
from django.db import transaction

from atletas.models import Atleta, Inscricao
from core.cpf import gerar_cpf_valido
from eventos.models import Evento, Modalidade, Pacote

# (nome, tipo, naipe) — naipes conforme o regulamento da JUV
MODALIDADES = [
    ("Futsal", "coletiva", "masc_fem"), ("Fut7", "coletiva", "masculino"), ("Vôlei", "coletiva", "masc_fem"),
    ("Handebol", "coletiva", "masc_fem"), ("Basquete", "coletiva", "masc_fem"),
    ("Vôlei de Praia", "dupla", "masc_fem"), ("Tênis de Mesa", "individual", "masc_fem"),
    ("Peteca", "dupla", "masc_fem"), ("E-sports", "coletiva", "misto"), ("Truco", "dupla", "masc_fem"),
    ("Sinuca", "dupla", "dupla_mista"), ("Xadrez", "individual", "misto"),
    ("Atletismo", "individual", "masc_fem"), ("Beach Tênis", "dupla", "dupla_mista"),
    ("Natação", "individual", "masc_fem"), ("Futevôlei", "dupla", "dupla_mista"),
]

APPS = ["atletas", "eventos"]

PERFIS = {
    "Administrador": None,  # todas as permissões dos módulos + auditoria, relatórios e usuários
    "Operador de inscrições": [
        "atletas.view_atleta", "atletas.add_atleta", "atletas.change_atleta", "atletas.ver_dados_pessoais",
        "atletas.view_inscricao", "atletas.add_inscricao", "atletas.change_inscricao", "atletas.delete_inscricao",
        "eventos.view_evento", "eventos.view_modalidade", "eventos.view_pacote",
        "core.ver_relatorios", "core.exportar_relatorios",
    ],
    "Consulta": [
        "atletas.view_atleta", "atletas.view_inscricao",
        "eventos.view_evento", "eventos.view_modalidade", "eventos.view_pacote",
        "core.ver_relatorios",
    ],
}

NOMES_F = ["Ana", "Carla", "Eduarda", "Gabriela", "Isabela", "Larissa", "Natália", "Paula", "Sabrina", "Vitória"]
NOMES_M = ["Bruno", "Diego", "Felipe", "Henrique", "João", "Marcos", "Otávio", "Rafael", "Thiago", "Lucas"]
SOBRENOMES = ["Silva", "Souza", "Oliveira", "Pereira", "Costa", "Rodrigues", "Almeida", "Lima", "Gomes",
              "Ribeiro", "Martins", "Carvalho", "Rocha", "Ferreira", "Barbosa"]


def _perm(codigo):
    app, codename = codigo.split(".")
    return Permission.objects.get(content_type__app_label=app, codename=codename)


class Command(BaseCommand):
    help = "Cria perfis de acesso, modalidades, o evento JUV e seus pacotes iniciais."

    def add_arguments(self, parser):
        parser.add_argument("--demo", type=int, default=0, metavar="N", help="Gera N atletas fictícios.")

    @transaction.atomic
    def handle(self, *args, **opts):
        if opts["verbosity"] == 0:
            self.stdout.write = lambda *a, **k: None
        self._perfis()
        modalidades = self._modalidades()
        evento = self._juv(modalidades)
        self._superusuario()
        if opts["demo"]:
            self._demo(evento, opts["demo"])
        self.stdout.write(self.style.SUCCESS("Configuração inicial concluída."))

    def _perfis(self):
        for nome, codigos in PERFIS.items():
            grupo, _ = Group.objects.get_or_create(name=nome)
            if codigos is None:
                perms = list(Permission.objects.filter(content_type__app_label__in=APPS))
                perms += [_perm(c) for c in ("core.ver_auditoria", "core.ver_relatorios",
                                             "core.exportar_relatorios", "core.gerenciar_usuarios")]
            else:
                perms = [_perm(c) for c in codigos]
            grupo.permissions.set(perms)
            self.stdout.write(f"  Perfil “{nome}”: {len(perms)} permissões")

    def _modalidades(self):
        objs = []
        for nome, tipo, naipe in MODALIDADES:
            m, criada = Modalidade.objects.get_or_create(nome=nome, defaults={"tipo": tipo, "naipe": naipe})
            objs.append(m)
        self.stdout.write(f"  {len(objs)} modalidades iniciais disponíveis")
        return objs

    def _juv(self, modalidades):
        evento, criado = Evento.objects.get_or_create(
            nome="JUV – Jogos Universitários do Vale do Aço",
            edicao=os.environ.get("JUV_EDICAO", "2026"),
            defaults={
                "descricao": "Jogos Universitários do Vale do Aço.",
                "local": "Vale do Aço — MG",
                "status": Evento.Status.PLANEJAMENTO,
            },
        )
        if criado:
            evento.modalidades.set(modalidades)
        Pacote.objects.get_or_create(
            evento=evento, nome="Pacote Atleta",
            defaults={
                "descricao": "Pacote destinado aos participantes das modalidades esportivas.",
                "beneficios": "Inscrição nas modalidades esportivas conforme as regras da organização",
            },
        )
        Pacote.objects.get_or_create(
            evento=evento, nome="Pacote Completo",
            defaults={
                "descricao": "Pacote com os benefícios adicionais definidos pela organização.",
                "beneficios": "Inscrição nas modalidades esportivas conforme as regras da organização\n"
                              "Benefícios adicionais definidos pela organização",
            },
        )
        self.stdout.write(f"  Evento “{evento}” {'criado' if criado else 'já existente'} com pacotes Atleta e Completo")
        return evento

    def _superusuario(self):
        usuario = os.environ.get("DJANGO_SUPERUSER_USERNAME")
        senha = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
        if usuario and senha and not User.objects.filter(username=usuario).exists():
            User.objects.create_superuser(usuario, os.environ.get("DJANGO_SUPERUSER_EMAIL", ""), senha)
            self.stdout.write(f"  Superusuário “{usuario}” criado")

    def _demo(self, evento, quantidade):
        rnd = random.Random(42)
        if evento.status == Evento.Status.PLANEJAMENTO:
            evento.status = Evento.Status.INSCRICOES_ABERTAS
            evento.save()
        pacotes = list(evento.pacotes.all())
        modalidades = list(evento.modalidades.all())
        criados = 0
        for i in range(quantidade):
            cpf = gerar_cpf_valido(f"{rnd.randint(100_000_000, 999_999_999)}")
            if Atleta.objects.filter(cpf=cpf).exists():
                continue
            sexo = rnd.choice("MF")
            primeiro = rnd.choice(NOMES_M if sexo == "M" else NOMES_F)
            nome = f"{primeiro} {rnd.choice(SOBRENOMES)} {rnd.choice(SOBRENOMES)}"
            atleta = Atleta.objects.create(
                nome=nome, cpf=cpf, sexo=sexo, email=f"{primeiro.lower()}.{i}@exemplo.com", consentimento_lgpd=True,
            )
            insc = Inscricao.objects.create(atleta=atleta, evento=evento, pacote=rnd.choice(pacotes))
            possiveis = [m for m in modalidades if m.aceita_sexo(sexo)]
            insc.modalidades.set(rnd.sample(possiveis, rnd.randint(1, 3)))
            criados += 1
        self.stdout.write(f"  {criados} atletas de demonstração criados")
