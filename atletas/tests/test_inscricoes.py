from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from atletas.models import Atleta
from eventos.models import Evento, Modalidade, Pacote

CPF = "529.982.247-25"


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("setup_inicial", verbosity=0)
        cls.juv = Evento.objects.get(nome__startswith="JUV")
        cls.juv.status = Evento.Status.INSCRICOES_ABERTAS
        cls.juv.save()
        cls.atleta_pac = Pacote.objects.get(evento=cls.juv, nome="Pacote Atleta")
        cls.futsal = Modalidade.objects.get(nome="Futsal")
        cls.xadrez = Modalidade.objects.get(nome="Xadrez")
        cls.outro = Evento.objects.create(nome="Copa Teste", edicao="2027", status=Evento.Status.INSCRICOES_ABERTAS)
        cls.outro.modalidades.set([cls.xadrez])
        cls.pacote_outro = Pacote.objects.create(evento=cls.outro, nome="Único", valor=10)
        cls.operador = User.objects.create_user("op", "op@x.com", "Senha-forte-123")
        cls.operador.groups.add(Group.objects.get(name="Operador de inscrições"))
        cls.consulta = User.objects.create_user("ver", "v@x.com", "Senha-forte-123")
        cls.consulta.groups.add(Group.objects.get(name="Consulta"))

    def dados(self, **extra):
        d = {"nome": "Maria da Silva", "cpf": CPF, "sexo": "F", "email": "Maria@Exemplo.com", "consentimento_lgpd": "on",
             "insc-evento": self.juv.pk, "insc-pacote": self.atleta_pac.pk, "insc-modalidades": [self.futsal.pk]}
        d.update(extra)
        return d


class CadastroAtletaTests(Base):
    def setUp(self):
        self.client.force_login(self.operador)

    def test_cadastra_atleta_com_inscricao(self):
        r = self.client.post(reverse("atletas:novo"), self.dados())
        atleta = Atleta.objects.get()
        self.assertRedirects(r, atleta.get_absolute_url())
        self.assertEqual(atleta.cpf, "52998224725")
        self.assertEqual(atleta.email, "maria@exemplo.com")
        self.assertIsNotNone(atleta.consentimento_em)
        insc = atleta.inscricoes.get()
        self.assertEqual(insc.evento, self.juv)
        self.assertEqual(list(insc.modalidades.all()), [self.futsal])

    def test_cpf_invalido(self):
        r = self.client.post(reverse("atletas:novo"), self.dados(cpf="123.456.789-00"))
        self.assertContains(r, "CPF inválido")
        self.assertFalse(Atleta.objects.exists())

    def test_cpf_duplicado_identificado(self):
        Atleta.objects.create(nome="Maria Existente", cpf=CPF, email="m@x.com")
        r = self.client.post(reverse("atletas:novo"), self.dados())
        self.assertContains(r, "Já existe um atleta cadastrado com este CPF")
        self.assertContains(r, "Adicionar inscrição")
        self.assertEqual(Atleta.objects.count(), 1)
        j = self.client.get(reverse("atletas:verificar_cpf"), {"cpf": CPF}).json()
        self.assertTrue(j["existe"])

    def test_pacote_de_outro_evento_rejeitado(self):
        r = self.client.post(reverse("atletas:novo"), self.dados(**{"insc-pacote": self.pacote_outro.pk}))
        self.assertContains(r, "não pertence a este evento")
        self.assertFalse(Atleta.objects.exists())

    def test_modalidade_nao_vinculada_ao_evento_rejeitada(self):
        self.juv.modalidades.remove(self.xadrez)
        r = self.client.post(reverse("atletas:novo"), self.dados(**{"insc-modalidades": [self.xadrez.pk]}))
        self.assertContains(r, "não disponível")
        self.assertFalse(Atleta.objects.exists())

    def test_modalidade_inativa_rejeitada(self):
        self.futsal.ativa = False
        self.futsal.save()
        r = self.client.post(reverse("atletas:novo"), self.dados())
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Atleta.objects.exists())

    def test_regras_do_pacote(self):
        self.atleta_pac.max_modalidades = 1
        self.atleta_pac.save()
        r = self.client.post(reverse("atletas:novo"), self.dados(**{"insc-modalidades": [self.futsal.pk, self.xadrez.pk]}))
        self.assertContains(r, "no máximo 1 modalidade")
        self.atleta_pac.max_modalidades = None
        self.atleta_pac.save()
        self.atleta_pac.modalidades_permitidas.set([self.xadrez])
        r = self.client.post(reverse("atletas:novo"), self.dados())
        self.assertContains(r, "não inclui")
        self.assertFalse(Atleta.objects.exists())

    def test_inscricoes_fechadas(self):
        self.juv.status = Evento.Status.PLANEJAMENTO
        self.juv.save()
        r = self.client.post(reverse("atletas:novo"), self.dados())
        self.assertContains(r, "Não é possível inscrever neste evento")
        # administrador (permissão especial) pode inscrever fora do período
        admin = User.objects.create_superuser("adm", "a@x.com", "Senha-forte-123")
        self.client.force_login(admin)
        r = self.client.post(reverse("atletas:novo"), self.dados())
        self.assertEqual(Atleta.objects.count(), 1)

    def test_cadastro_sem_inscricao(self):
        d = self.dados(**{"insc-evento": "", "insc-pacote": "", "insc-modalidades": []})
        self.client.post(reverse("atletas:novo"), d)
        self.assertEqual(Atleta.objects.get().inscricoes.count(), 0)

    def test_mesmo_atleta_em_varios_eventos_mas_uma_vez_por_evento(self):
        self.client.post(reverse("atletas:novo"), self.dados())
        atleta = Atleta.objects.get()
        url = reverse("atletas:inscricao_nova", args=[atleta.pk])
        r = self.client.post(url, {"evento": self.juv.pk, "pacote": self.atleta_pac.pk, "modalidades": [self.futsal.pk]})
        self.assertContains(r, "já possui inscrição neste evento")
        self.client.post(url, {"evento": self.outro.pk, "pacote": self.pacote_outro.pk, "modalidades": [self.xadrez.pk]})
        self.assertEqual(atleta.inscricoes.count(), 2)
        detalhe = self.client.get(atleta.get_absolute_url())
        self.assertContains(detalhe, "Copa Teste")

    def test_busca_por_nome_e_cpf(self):
        self.client.post(reverse("atletas:novo"), self.dados())
        self.assertContains(self.client.get(reverse("atletas:lista"), {"q": "maria"}), "Maria da Silva")
        self.assertContains(self.client.get(reverse("atletas:lista"), {"q": "529982"}), "Maria da Silva")
        self.assertNotContains(self.client.get(reverse("atletas:lista"), {"q": "zzz"}), "Maria da Silva")


class SexoNaipeTests(Base):
    """Regras de sexo/naipe do regulamento da JUV."""

    def setUp(self):
        self.client.force_login(self.operador)
        self.fut7 = Modalidade.objects.get(nome="Fut7")          # Futebol Society: só masculino
        self.sinuca = Modalidade.objects.get(nome="Sinuca")      # dupla mista

    def test_sexo_obrigatorio(self):
        r = self.client.post(reverse("atletas:novo"), self.dados(sexo=""))
        self.assertContains(r, "Informe o sexo do atleta")
        self.assertFalse(Atleta.objects.exists())

    def test_atleta_feminina_nao_entra_em_modalidade_so_masculina(self):
        r = self.client.post(reverse("atletas:novo"), self.dados(**{"insc-modalidades": [self.fut7.pk]}))
        self.assertContains(r, "não disputada(s) no naipe feminino")
        self.assertFalse(Atleta.objects.exists())

    def test_atleta_masculino_entra_em_modalidade_so_masculina(self):
        self.client.post(reverse("atletas:novo"), self.dados(sexo="M", **{"insc-modalidades": [self.fut7.pk]}))
        self.assertEqual(Atleta.objects.get().sexo, "M")

    def test_modalidades_mistas_aceitam_ambos_os_sexos(self):
        mods = [self.sinuca.pk, self.xadrez.pk, self.futsal.pk]
        self.client.post(reverse("atletas:novo"), self.dados(**{"insc-modalidades": mods}))
        insc = Atleta.objects.get().inscricoes.get()
        self.assertEqual(insc.disputas(), ["Futsal Feminino", "Sinuca (dupla mista)", "Xadrez (misto)"])

    def test_inscricao_de_atleta_sem_sexo_pede_atualizacao(self):
        atleta = Atleta.objects.create(nome="Sem Sexo Teste", cpf=CPF, email="s@x.com")
        r = self.client.post(reverse("atletas:inscricao_nova", args=[atleta.pk]),
                             {"evento": self.juv.pk, "pacote": self.atleta_pac.pk, "modalidades": [self.futsal.pk]})
        self.assertContains(r, "Informe o sexo do atleta no cadastro")
        self.assertFalse(atleta.inscricoes.exists())

    def test_filtro_por_sexo(self):
        Atleta.objects.create(nome="Ana Teste", cpf=CPF, sexo="F", email="a@x.com")
        r = self.client.get(reverse("atletas:lista"), {"sexo": "M"})
        self.assertNotContains(r, "Ana Teste")
        self.assertContains(self.client.get(reverse("atletas:lista"), {"sexo": "F"}), "Ana Teste")


class PermissoesTests(Base):
    def test_anonimo_vai_para_login(self):
        r = self.client.get(reverse("atletas:lista"))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("login"), r["Location"])

    def test_perfil_consulta_somente_leitura_e_cpf_mascarado(self):
        Atleta.objects.create(nome="Joao Lima", cpf=CPF, email="j@x.com")
        self.client.force_login(self.consulta)
        r = self.client.get(reverse("atletas:lista"))
        self.assertContains(r, "***.982.247-**")
        self.assertNotContains(r, "529.982.247-25")
        self.assertEqual(self.client.get(reverse("atletas:novo")).status_code, 403)
        self.assertEqual(self.client.get(reverse("eventos:evento_novo")).status_code, 403)
        self.assertEqual(self.client.get(reverse("core:auditoria")).status_code, 403)
        self.assertEqual(self.client.get(reverse("relatorios:exportar", args=["xlsx"])).status_code, 403)

    def test_operador_ve_cpf_completo(self):
        Atleta.objects.create(nome="Joao Lima", cpf=CPF, email="j@x.com")
        self.client.force_login(self.operador)
        self.assertContains(self.client.get(reverse("atletas:lista")), "529.982.247-25")
        self.assertEqual(self.client.get(reverse("core:usuarios")).status_code, 403)
