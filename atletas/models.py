from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse

from core.cpf import formatar_cpf, mascarar_cpf, somente_digitos, validar_cpf
from eventos.models import Evento, Modalidade, Pacote


class Atleta(models.Model):
    class Sexo(models.TextChoices):
        MASCULINO = "M", "Masculino"
        FEMININO = "F", "Feminino"

    nome = models.CharField("nome completo", max_length=200)
    cpf = models.CharField(
        "CPF", max_length=11, unique=True, validators=[validar_cpf],
        error_messages={"unique": "Já existe um atleta cadastrado com este CPF."},
    )
    sexo = models.CharField(
        "sexo", max_length=1, choices=Sexo.choices, blank=True,
        help_text="Define em qual naipe (masculino/feminino) o atleta compete, conforme o regulamento.",
    )
    email = models.EmailField("e-mail")
    telefone = models.CharField("telefone / WhatsApp", max_length=20, blank=True)
    consentimento_lgpd = models.BooleanField(
        "consentimento LGPD",
        default=False,
        help_text="O atleta autorizou o tratamento dos seus dados pessoais para fins de organização do evento.",
    )
    consentimento_em = models.DateTimeField("data do consentimento", null=True, blank=True)
    observacoes = models.TextField("observações", blank=True)
    criado_em = models.DateTimeField("cadastrado em", auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "atleta"
        verbose_name_plural = "atletas"
        permissions = [
            ("ver_dados_pessoais", "Pode ver CPF completo e dados pessoais dos atletas"),
        ]
        indexes = [models.Index(fields=["nome"])]

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        self.cpf = somente_digitos(self.cpf)
        self.email = (self.email or "").strip().lower()
        self.nome = " ".join((self.nome or "").split())
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("atletas:detalhe", args=[self.pk])

    @property
    def cpf_formatado(self):
        return formatar_cpf(self.cpf)

    @property
    def cpf_mascarado(self):
        return mascarar_cpf(self.cpf)

    @property
    def sexo_curto(self):
        return self.sexo or "—"


class Inscricao(models.Model):
    """Vínculo de um atleta com um evento: pacote adquirido + modalidades escolhidas."""

    atleta = models.ForeignKey(Atleta, on_delete=models.CASCADE, related_name="inscricoes")
    evento = models.ForeignKey(Evento, on_delete=models.PROTECT, related_name="inscricoes")
    pacote = models.ForeignKey(Pacote, on_delete=models.PROTECT, related_name="inscricoes")
    modalidades = models.ManyToManyField(Modalidade, related_name="inscricoes", blank=True)
    observacoes = models.TextField("observações", blank=True)
    criado_em = models.DateTimeField("inscrito em", auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "inscrição"
        verbose_name_plural = "inscrições"
        constraints = [
            models.UniqueConstraint(fields=["atleta", "evento"], name="uma_inscricao_por_atleta_por_evento"),
        ]
        permissions = [
            ("inscrever_fora_do_periodo", "Pode inscrever atletas fora do período de inscrições"),
        ]

    def __str__(self):
        return f"{self.atleta} — {self.evento}"

    def get_absolute_url(self):
        return reverse("atletas:detalhe", args=[self.atleta_id])

    def disputas(self) -> list[str]:
        """Nome de cada disputa com o naipe do atleta, ex.: ["Futsal Masculino", "Xadrez (misto)"]."""
        return sorted(m.nome_naipe(self.atleta.sexo) for m in self.modalidades.all())

    def clean(self):
        if self.pacote_id and self.evento_id and self.pacote.evento_id != self.evento_id:
            raise ValidationError({"pacote": "O pacote selecionado não pertence a este evento."})

    @staticmethod
    def validar_modalidades(evento: Evento, pacote: Pacote | None, modalidades, sexo: str | None = None) -> list[str]:
        """Regras de negócio da escolha de modalidades. Retorna a lista de erros encontrados."""
        erros = []
        modalidades = list(modalidades)
        if sexo in ("M", "F"):
            incompativeis = [m.nome for m in modalidades if not m.aceita_sexo(sexo)]
            if incompativeis:
                rotulo = "masculino" if sexo == "M" else "feminino"
                erros.append(
                    f"Modalidade(s) não disputada(s) no naipe {rotulo}: {', '.join(incompativeis)} (ver regulamento)."
                )
        disponiveis = set(evento.modalidades_ativas().values_list("pk", flat=True))
        fora = [m.nome for m in modalidades if m.pk not in disponiveis]
        if fora:
            erros.append(f"Modalidade(s) não disponível(is) neste evento: {', '.join(fora)}.")
        if pacote:
            permitidas = set(pacote.modalidades_permitidas.values_list("pk", flat=True))
            if permitidas:
                nao_permitidas = [m.nome for m in modalidades if m.pk not in permitidas and m.pk in disponiveis]
                if nao_permitidas:
                    erros.append(
                        f"O pacote “{pacote.nome}” não inclui: {', '.join(nao_permitidas)}."
                    )
            if pacote.max_modalidades is not None and len(modalidades) > pacote.max_modalidades:
                erros.append(
                    f"O pacote “{pacote.nome}” permite no máximo {pacote.max_modalidades} modalidade(s); "
                    f"foram selecionadas {len(modalidades)}."
                )
        return erros
