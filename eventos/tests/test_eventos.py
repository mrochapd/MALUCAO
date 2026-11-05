from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from atletas.models import Atleta, Inscricao
from eventos.models import Evento, Modalidade, Pacote


class EventosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("setup_inicial", verbosity=0)
        cls.admin = User.objects.create_superuser("adm", "a@x.com", "Senha-forte-123")
        cls.juv = Evento.objects.get(nome__startswith="JUV")

    def setUp(self):
        self.client.force_login(self.admin)

    def test_dados_iniciais(self):
        self.assertEqual(Modalidade.objects.count(), 16)
        self.assertEqual(self.juv.modalidades.count(), 16)
        self.assertEqual(set(self.juv.pacotes.values_list("nome", flat=True)), {"Pacote Atleta", "Pacote Completo"})
        call_command("setup_inicial", verbosity=0)  # idempotente
        self.assertEqual(Evento.objects.count(), 1)

    def test_criar_evento_e_validar_datas(self):
        r = self.client.post(reverse("eventos:evento_novo"), {
            "nome": "Torneio", "edicao": "1", "status": "planejamento",
            "data_inicio": "2027-05-10", "data_fim": "2027-05-01",
        })
        self.assertContains(r, "não pode ser anterior")
        self.client.post(reverse("eventos:evento_novo"), {
            "nome": "Torneio", "edicao": "1", "status": "planejamento",
            "data_inicio": "2027-05-10", "data_fim": "2027-05-12", "modalidades": [Modalidade.objects.first().pk],
        })
        self.assertTrue(Evento.objects.filter(nome="Torneio").exists())

    def test_nova_edicao_nao_mistura_atletas(self):
        pac = self.juv.pacotes.first()
        a = Atleta.objects.create(nome="Ana Souza", cpf="52998224725", email="a@x.com")
        Inscricao.objects.create(atleta=a, evento=self.juv, pacote=pac)
        r = self.client.post(reverse("eventos:evento_duplicar", args=[self.juv.pk]),
                             {"nome": self.juv.nome, "edicao": "2027", "copiar_pacotes": "on"})
        nova = Evento.objects.get(edicao="2027")
        self.assertRedirects(r, reverse("eventos:evento_editar", args=[nova.pk]))
        self.assertEqual(nova.modalidades.count(), 16)
        self.assertEqual(nova.pacotes.count(), 2)
        self.assertEqual(nova.inscricoes.count(), 0)
        self.assertEqual(self.juv.inscricoes.count(), 1)

    def test_pacote_valida_modalidades_do_evento(self):
        outro = Evento.objects.create(nome="Outro", status="planejamento")
        r = self.client.post(reverse("eventos:pacote_novo"), {
            "evento": outro.pk, "nome": "X", "valor": "50", "ativo": "on",
            "modalidades_permitidas": [Modalidade.objects.first().pk],
        })
        self.assertContains(r, "não estão vinculadas ao evento")

    def test_exclusao_protegida(self):
        pac = self.juv.pacotes.first()
        a = Atleta.objects.create(nome="Ana Souza", cpf="52998224725", email="a@x.com")
        Inscricao.objects.create(atleta=a, evento=self.juv, pacote=pac)
        self.client.post(reverse("eventos:pacote_excluir", args=[pac.pk]))
        self.assertTrue(Pacote.objects.filter(pk=pac.pk).exists())

    def test_alternar_modalidade(self):
        m = Modalidade.objects.get(nome="Truco")
        self.client.post(reverse("eventos:modalidade_alternar", args=[m.pk]))
        m.refresh_from_db()
        self.assertFalse(m.ativa)

    def test_paginas_principais(self):
        for url in ["/", "/eventos/", f"/eventos/{self.juv.pk}/", "/eventos/modalidades/", "/eventos/pacotes/",
                    "/atletas/", "/atletas/novo/", "/auditoria/", "/usuarios/", "/privacidade/"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
