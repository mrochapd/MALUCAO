import io

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from openpyxl import load_workbook

from core.models import RegistroAlteracao
from relatorios.services import TIPOS


class RelatoriosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("setup_inicial", demo=15, verbosity=0)
        cls.admin = User.objects.create_superuser("adm", "a@x.com", "Senha-forte-123")

    def setUp(self):
        self.client.force_login(self.admin)

    def test_todos_os_relatorios_na_tela(self):
        for chave, _ in TIPOS:
            r = self.client.get("/relatorios/", {"tipo": chave, "evento": 1})
            self.assertEqual(r.status_code, 200, chave)

    def test_exportar_excel(self):
        r = self.client.get("/relatorios/exportar/xlsx/", {"tipo": "inscritos"})
        self.assertEqual(r.status_code, 200)
        wb = load_workbook(io.BytesIO(r.content))
        valores = [c.value for c in wb.active[6]]
        self.assertEqual(valores[0], "Atleta")
        self.assertEqual(wb.active.max_row >= 6 + 15, True)
        self.assertTrue(RegistroAlteracao.objects.filter(acao="exportacao").exists())

    def test_exportar_pdf(self):
        for chave, _ in TIPOS:
            r = self.client.get("/relatorios/exportar/pdf/", {"tipo": chave})
            self.assertEqual(r["Content-Type"], "application/pdf")
            self.assertTrue(r.content.startswith(b"%PDF"), chave)

    def test_quantidades_por_modalidade_batem(self):
        from atletas.models import Inscricao

        r = self.client.get("/relatorios/", {"tipo": "qtd_modalidade"})
        linhas = r.context["rel"].linhas
        esperado = sum(i.modalidades.count() for i in Inscricao.objects.all())
        self.assertEqual(sum(l[5] for l in linhas), esperado)
        self.assertEqual(sum(l[3] + l[4] for l in linhas), esperado)  # masculino + feminino = total

    def test_relatorio_por_modalidade_separa_naipes(self):
        from atletas.models import Atleta, Inscricao
        from eventos.models import Modalidade

        futsal = Modalidade.objects.get(nome="Futsal")
        insc = Inscricao.objects.first()
        for sexo, cpf in (("M", "52998224725"), ("F", "11144477735")):
            a = Atleta.objects.create(nome=f"Teste {sexo} Naipe", cpf=cpf, sexo=sexo, email=f"{sexo}@x.com")
            Inscricao.objects.create(atleta=a, evento=insc.evento, pacote=insc.pacote).modalidades.set([futsal])
        r = self.client.get("/relatorios/", {"tipo": "por_modalidade", "modalidade": futsal.pk})
        grupos = [g for g, _ in r.context["rel"].grupos]
        self.assertIn("Futsal Masculino", grupos)
        self.assertIn("Futsal Feminino", grupos)
        r = self.client.get("/relatorios/", {"tipo": "inscritos", "sexo": "F"})
        self.assertTrue(all(l[1] == "Feminino" for l in r.context["rel"].linhas))
