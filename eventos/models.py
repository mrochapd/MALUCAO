from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Modalidade(models.Model):
    class Tipo(models.TextChoices):
        INDIVIDUAL = "individual", "Individual"
        DUPLA = "dupla", "Dupla"
        COLETIVA = "coletiva", "Coletiva"

    class Naipe(models.TextChoices):
        MASC_FEM = "masc_fem", "Masculino e feminino (disputas separadas)"
        MASCULINO = "masculino", "Somente masculino"
        FEMININO = "feminino", "Somente feminino"
        MISTO = "misto", "Misto (aberto a qualquer sexo)"
        DUPLA_MISTA = "dupla_mista", "Dupla/equipe mista (exige homens e mulheres)"

    nome = models.CharField("nome da modalidade", max_length=100, unique=True)
    descricao = models.TextField("descrição", blank=True)
    tipo = models.CharField("categoria / tipo", max_length=20, choices=Tipo.choices, default=Tipo.COLETIVA)
    naipe = models.CharField(
        "naipe", max_length=20, choices=Naipe.choices, default=Naipe.MASC_FEM,
        help_text="Define quem pode disputar: separado por sexo, exclusivo de um sexo, misto ou dupla mista.",
    )
    ativa = models.BooleanField("ativa", default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "modalidade"
        verbose_name_plural = "modalidades"

    def __str__(self):
        return self.nome

    def get_absolute_url(self):
        return reverse("eventos:modalidade_editar", args=[self.pk])

    NAIPE_CURTO = {
        "masc_fem": "Masc. e fem.",
        "masculino": "Só masculino",
        "feminino": "Só feminino",
        "misto": "Misto",
        "dupla_mista": "Dupla mista",
    }

    @property
    def naipe_curto(self) -> str:
        return self.NAIPE_CURTO.get(self.naipe, "")

    @property
    def separa_por_sexo(self) -> bool:
        """Modalidades com disputas separadas (ou exclusivas) por sexo."""
        return self.naipe in {self.Naipe.MASC_FEM, self.Naipe.MASCULINO, self.Naipe.FEMININO}

    def aceita_sexo(self, sexo: str) -> bool:
        """M/F. Retorna False quando a modalidade é exclusiva do outro sexo."""
        if self.naipe == self.Naipe.MASCULINO:
            return sexo == "M"
        if self.naipe == self.Naipe.FEMININO:
            return sexo == "F"
        return True

    def nome_naipe(self, sexo: str) -> str:
        """Nome da disputa em que o atleta compete, ex.: “Futsal Feminino”."""
        if self.separa_por_sexo and sexo in ("M", "F"):
            return f"{self.nome} {'Masculino' if sexo == 'M' else 'Feminino'}"
        if self.naipe == self.Naipe.DUPLA_MISTA:
            return f"{self.nome} (dupla mista)"
        if self.naipe == self.Naipe.MISTO:
            return f"{self.nome} (misto)"
        return self.nome


class EventoQuerySet(models.QuerySet):
    def futuros(self):
        hoje = timezone.localdate()
        return self.filter(models.Q(data_fim__gte=hoje) | models.Q(data_fim__isnull=True))

    def anteriores(self):
        return self.filter(data_fim__lt=timezone.localdate())


class Evento(models.Model):
    class Status(models.TextChoices):
        PLANEJAMENTO = "planejamento", "Planejamento"
        INSCRICOES_ABERTAS = "inscricoes_abertas", "Inscrições abertas"
        INSCRICOES_ENCERRADAS = "inscricoes_encerradas", "Inscrições encerradas"
        FINALIZADO = "finalizado", "Finalizado"

    nome = models.CharField("nome do evento", max_length=150)
    edicao = models.CharField(
        "edição", max_length=50, blank=True, help_text="Ex.: 2026, 12ª edição. Diferencia edições do mesmo evento."
    )
    descricao = models.TextField("descrição", blank=True)
    data_inicio = models.DateField("data de início", null=True, blank=True)
    data_fim = models.DateField("data de encerramento", null=True, blank=True)
    local = models.CharField("local de realização", max_length=200, blank=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.PLANEJAMENTO)
    inscricoes_inicio = models.DateTimeField(
        "abertura das inscrições", null=True, blank=True, help_text="Opcional. Em branco = sem restrição de data."
    )
    inscricoes_fim = models.DateTimeField(
        "encerramento das inscrições", null=True, blank=True, help_text="Opcional. Em branco = sem restrição de data."
    )
    modalidades = models.ManyToManyField(
        Modalidade, related_name="eventos", blank=True, verbose_name="modalidades disponíveis"
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = EventoQuerySet.as_manager()

    class Meta:
        ordering = ["-data_inicio", "-criado_em"]
        verbose_name = "evento"
        verbose_name_plural = "eventos"
        constraints = [
            models.UniqueConstraint(fields=["nome", "edicao"], name="evento_nome_edicao_unico"),
        ]

    def __str__(self):
        return f"{self.nome} — {self.edicao}" if self.edicao else self.nome

    def get_absolute_url(self):
        return reverse("eventos:evento_detalhe", args=[self.pk])

    def clean(self):
        erros = {}
        if self.data_inicio and self.data_fim and self.data_fim < self.data_inicio:
            erros["data_fim"] = "A data de encerramento não pode ser anterior à data de início."
        if self.inscricoes_inicio and self.inscricoes_fim and self.inscricoes_fim < self.inscricoes_inicio:
            erros["inscricoes_fim"] = "O encerramento das inscrições não pode ser anterior à abertura."
        if erros:
            raise ValidationError(erros)

    @property
    def periodo_inscricoes_vigente(self) -> bool:
        agora = timezone.now()
        if self.inscricoes_inicio and agora < self.inscricoes_inicio:
            return False
        if self.inscricoes_fim and agora > self.inscricoes_fim:
            return False
        return True

    @property
    def aceita_inscricoes(self) -> bool:
        return self.status == self.Status.INSCRICOES_ABERTAS and self.periodo_inscricoes_vigente

    @property
    def motivo_inscricoes_fechadas(self) -> str:
        if self.status != self.Status.INSCRICOES_ABERTAS:
            return f"o evento está com status “{self.get_status_display()}”"
        agora = timezone.now()
        if self.inscricoes_inicio and agora < self.inscricoes_inicio:
            return "o período de inscrições ainda não começou"
        if self.inscricoes_fim and agora > self.inscricoes_fim:
            return "o período de inscrições já terminou"
        return ""

    @property
    def status_cor(self) -> str:
        return {
            self.Status.PLANEJAMENTO: "secondary",
            self.Status.INSCRICOES_ABERTAS: "success",
            self.Status.INSCRICOES_ENCERRADAS: "warning",
            self.Status.FINALIZADO: "dark",
        }.get(self.status, "secondary")

    def modalidades_ativas(self):
        return self.modalidades.filter(ativa=True)

    def pacotes_ativos(self):
        return self.pacotes.filter(ativo=True)


class Pacote(models.Model):
    evento = models.ForeignKey(Evento, on_delete=models.PROTECT, related_name="pacotes", verbose_name="evento")
    nome = models.CharField("nome do pacote", max_length=100)
    descricao = models.TextField("descrição", blank=True)
    valor = models.DecimalField("valor (R$)", max_digits=10, decimal_places=2, default=0)
    beneficios = models.TextField(
        "benefícios e serviços incluídos", blank=True, help_text="Um benefício por linha."
    )
    max_modalidades = models.PositiveSmallIntegerField(
        "limite de modalidades por atleta",
        null=True,
        blank=True,
        help_text="Regra da organização. Em branco = sem limite.",
    )
    modalidades_permitidas = models.ManyToManyField(
        Modalidade,
        related_name="pacotes",
        blank=True,
        verbose_name="modalidades permitidas",
        help_text="Deixe todas desmarcadas para liberar todas as modalidades do evento.",
    )
    ativo = models.BooleanField("ativo", default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["evento", "valor", "nome"]
        verbose_name = "pacote"
        verbose_name_plural = "pacotes"
        constraints = [
            models.UniqueConstraint(fields=["evento", "nome"], name="pacote_nome_unico_por_evento"),
        ]

    def __str__(self):
        return self.nome

    def get_absolute_url(self):
        return reverse("eventos:pacote_editar", args=[self.pk])

    @property
    def lista_beneficios(self) -> list[str]:
        return [b.strip(" -•\t") for b in self.beneficios.splitlines() if b.strip(" -•\t")]

    def modalidades_disponiveis(self):
        """Modalidades que um atleta com este pacote pode escolher no evento."""
        qs = self.evento.modalidades_ativas()
        if self.pk and self.modalidades_permitidas.exists():
            qs = qs.filter(pk__in=self.modalidades_permitidas.values("pk"))
        return qs
