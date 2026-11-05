from django import forms
from django.db.models import Q
from django.utils import timezone

from core.cpf import formatar_cpf, somente_digitos, validar_cpf
from core.forms import BootstrapFormMixin
from eventos.models import Evento, Modalidade, Pacote

from .models import Atleta, Inscricao


class AtletaForm(BootstrapFormMixin, forms.ModelForm):
    cpf = forms.CharField(
        label="CPF", max_length=14,
        widget=forms.TextInput(attrs={"inputmode": "numeric", "placeholder": "000.000.000-00", "data-mascara": "cpf"}),
    )

    class Meta:
        model = Atleta
        fields = ["nome", "cpf", "email", "telefone", "consentimento_lgpd", "observacoes"]
        widgets = {
            "observacoes": forms.Textarea(attrs={"rows": 2}),
            "telefone": forms.TextInput(attrs={"inputmode": "tel", "placeholder": "(33) 90000-0000"}),
            "email": forms.EmailInput(attrs={"placeholder": "nome@exemplo.com"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.atleta_existente = None
        if self.instance.pk:
            self.initial["cpf"] = formatar_cpf(self.instance.cpf)

    def clean_cpf(self):
        cpf = somente_digitos(self.cleaned_data["cpf"])
        validar_cpf(cpf)
        duplicado = Atleta.objects.filter(cpf=cpf).exclude(pk=self.instance.pk).first()
        if duplicado:
            self.atleta_existente = duplicado
            raise forms.ValidationError(
                "Já existe um atleta cadastrado com este CPF (%(nome)s). Use o cadastro existente "
                "para adicionar uma nova inscrição.",
                params={"nome": duplicado.nome},
                code="cpf_duplicado",
            )
        return cpf

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def clean_nome(self):
        nome = " ".join(self.cleaned_data["nome"].split())
        if len(nome.split()) < 2:
            raise forms.ValidationError("Informe o nome completo (nome e sobrenome).")
        return nome

    def save(self, commit=True):
        atleta = super().save(commit=False)
        if atleta.consentimento_lgpd and not atleta.consentimento_em:
            atleta.consentimento_em = timezone.now()
        if not atleta.consentimento_lgpd:
            atleta.consentimento_em = None
        if commit:
            atleta.save()
        return atleta


class InscricaoForm(BootstrapFormMixin, forms.ModelForm):
    """
    Inscrição de um atleta em um evento. Só aceita pacotes e modalidades vinculados ao
    evento escolhido e respeita as regras do pacote (modalidades permitidas e limite).
    """

    class Meta:
        model = Inscricao
        fields = ["evento", "pacote", "modalidades", "observacoes"]
        widgets = {
            "modalidades": forms.CheckboxSelectMultiple,
            "observacoes": forms.Textarea(attrs={"rows": 2}),
        }
        labels = {"pacote": "Pacote adquirido", "modalidades": "Modalidades"}

    def __init__(self, *args, atleta=None, usuario=None, obrigatoria=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.atleta = atleta if atleta is not None else (self.instance.atleta if self.instance.pk else None)
        self.usuario = usuario
        self.obrigatoria = obrigatoria
        inst = self.instance if self.instance.pk else None

        self.fields["evento"].queryset = Evento.objects.order_by("-data_inicio", "nome")
        self.fields["evento"].empty_label = "Selecione o evento…"
        self.fields["pacote"].queryset = Pacote.objects.filter(
            Q(ativo=True) | Q(pk=inst.pacote_id if inst else None)
        ).select_related("evento")
        self.fields["pacote"].empty_label = "Selecione o pacote…"
        self.fields["modalidades"].queryset = Modalidade.objects.filter(
            Q(ativa=True) | Q(pk__in=inst.modalidades.values("pk") if inst else [])
        )
        self.fields["modalidades"].required = False
        if not obrigatoria:
            self.fields["evento"].required = False
            self.fields["pacote"].required = False
            self.fields["evento"].empty_label = "— Cadastrar sem inscrição por enquanto —"

    @property
    def preenchida(self) -> bool:
        return bool(self.cleaned_data.get("evento")) if hasattr(self, "cleaned_data") else False

    def clean(self):
        dados = super().clean()
        evento = dados.get("evento")
        pacote = dados.get("pacote")
        modalidades = dados.get("modalidades") or []

        if not evento:
            if not self.obrigatoria and not pacote and not modalidades:
                return dados
            if not self.errors.get("evento"):
                self.add_error("evento", "Selecione o evento.")
            return dados

        if not pacote and "pacote" not in self.errors:
            self.add_error("pacote", "Selecione o pacote adquirido.")
        if pacote and pacote.evento_id != evento.pk:
            self.add_error("pacote", "O pacote selecionado não pertence a este evento.")
            pacote = None

        mudou_evento = not self.instance.pk or self.instance.evento_id != evento.pk
        if mudou_evento and not evento.aceita_inscricoes:
            pode_forcar = self.usuario is not None and self.usuario.has_perm("atletas.inscrever_fora_do_periodo")
            if not pode_forcar:
                self.add_error("evento", f"Não é possível inscrever neste evento: {evento.motivo_inscricoes_fechadas}.")

        if self.atleta is not None and self.atleta.pk:
            existente = Inscricao.objects.filter(atleta=self.atleta, evento=evento).exclude(pk=self.instance.pk)
            if existente.exists():
                self.add_error("evento", "Este atleta já possui inscrição neste evento. Edite a inscrição existente.")

        if not modalidades:
            self.add_error("modalidades", "Marque ao menos uma modalidade.")
        for erro in Inscricao.validar_modalidades(evento, pacote, modalidades):
            self.add_error("modalidades", erro)
        return dados

    def save(self, commit=True):
        inscricao = super().save(commit=False)
        if self.atleta is not None:
            inscricao.atleta = self.atleta
        if commit:
            inscricao.save()
            self.save_m2m()
        return inscricao


class FiltroAtletasForm(BootstrapFormMixin, forms.Form):
    q = forms.CharField(label="Buscar", required=False,
                        widget=forms.TextInput(attrs={"placeholder": "Nome ou CPF", "type": "search"}))
    evento = forms.ModelChoiceField(Evento.objects.all(), required=False, empty_label="Todos os eventos")
    pacote = forms.ModelChoiceField(Pacote.objects.select_related("evento"), required=False,
                                    empty_label="Todos os pacotes")
    modalidade = forms.ModelChoiceField(Modalidade.objects.all(), required=False, empty_label="Todas as modalidades")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["pacote"].label_from_instance = lambda p: f"{p.nome} ({p.evento})"
