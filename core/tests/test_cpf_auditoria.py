from django.contrib.auth.models import User
from django.test import TestCase

from atletas.models import Atleta
from core.cpf import cpf_valido, formatar_cpf, gerar_cpf_valido, mascarar_cpf
from core.models import RegistroAlteracao


class CPFTests(TestCase):
    def test_validacao(self):
        self.assertTrue(cpf_valido("529.982.247-25"))
        self.assertTrue(cpf_valido("52998224725"))
        self.assertFalse(cpf_valido("529.982.247-24"))
        self.assertFalse(cpf_valido("111.111.111-11"))
        self.assertFalse(cpf_valido("123"))
        self.assertTrue(cpf_valido(gerar_cpf_valido("123456789")))

    def test_formatacao_e_mascara(self):
        self.assertEqual(formatar_cpf("52998224725"), "529.982.247-25")
        self.assertEqual(mascarar_cpf("52998224725"), "***.982.247-**")


class AuditoriaTests(TestCase):
    def test_registra_criacao_alteracao_exclusao_com_cpf_mascarado(self):
        a = Atleta.objects.create(nome="Ana Souza", cpf="52998224725", email="ana@x.com")
        a.email = "ana2@x.com"
        a.save()
        pk = a.pk
        a.delete()
        logs = RegistroAlteracao.objects.filter(entidade="Atleta", objeto_id=str(pk)).order_by("momento", "pk")
        self.assertEqual([l.acao for l in logs], ["criacao", "alteracao", "exclusao"])
        self.assertEqual(logs[1].alteracoes["email"], {"de": "ana@x.com", "para": "ana2@x.com"})
        self.assertEqual(logs[0].alteracoes["novo"]["cpf"], "***.982.247-**")
        self.assertNotIn("52998224725", str([l.alteracoes for l in logs]))

    def test_registra_usuario_da_requisicao(self):
        u = User.objects.create_superuser("chefe", "c@x.com", "Senha-forte-123")
        self.client.force_login(u)
        self.client.post("/eventos/modalidades/nova/", {"nome": "Queimada", "tipo": "coletiva", "naipe": "misto", "ativa": "on"})
        log = RegistroAlteracao.objects.get(entidade="Modalidade", acao="criacao", objeto_repr="Queimada")
        self.assertEqual(log.usuario, u)
