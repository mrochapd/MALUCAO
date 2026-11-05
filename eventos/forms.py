from django import forms
from django.db.models import Q

from core.forms import BootstrapFormMixin

from .models import Evento, Modalidade, Pacote


class ModalidadeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Modalidade
        fields = ["nome", "tipo", "naipe", "descricao", "ativa"]
        widgets = {"descricao": forms.Textarea(attrs={"rows": 3})}


def _modalidades_queryset(instancia_m2m=None):
    """Modalidades ativas + as já vinculadas ao registro (mesmo que tenham sido desativadas)."""
    filtro = Q(ativa=True)
    if instancia_m2m is not None:
        filtro |= Q(pk__in=instancia_m2m.values("pk"))
    return Modalidade.objects.filter(filtro).order_by("nome")


class EventoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Evento
        fields = [
            "nome", "edicao", "descricao", "data_inicio", "data_fim", "local", "status",
            "inscricoes_inicio", "inscricoes_fim", "modalidades",
        ]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 3}),
            "data_inicio": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "data_fim": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "inscricoes_inicio": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "inscricoes_fim": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "modalidades": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["modalidades"].queryset = _modalidades_queryset(
            self.instance.modalidades if self.instance.pk else None
        )


class PacoteForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Pacote
        fields = [
            "evento", "nome", "descricao", "valor", "beneficios", "max_modalidades",
            "modalidades_permitidas", "ativo",
        ]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 2}),
            "beneficios": forms.Textarea(attrs={"rows": 5, "placeholder": "Ex.:\nCamiseta oficial\nKit atleta\nAcesso às festas"}),
            "valor": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "modalidades_permitidas": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["modalidades_permitidas"].queryset = _modalidades_queryset(
            self.instance.modalidades_permitidas if self.instance.pk else None
        )
        self.fields["evento"].queryset = Evento.objects.order_by("-data_inicio", "nome")

    def clean_valor(self):
        valor = self.cleaned_data["valor"]
        if valor is not None and valor < 0:
            raise forms.ValidationError("O valor não pode ser negativo.")
        return valor

    def clean(self):
        dados = super().clean()
        evento, permitidas = dados.get("evento"), dados.get("modalidades_permitidas")
        if evento and permitidas:
            do_evento = set(evento.modalidades.values_list("pk", flat=True))
            fora = [m.nome for m in permitidas if m.pk not in do_evento]
            if fora:
                self.add_error(
                    "modalidades_permitidas",
                    f"Estas modalidades não estão vinculadas ao evento {evento}: {', '.join(fora)}.",
                )
        return dados


class DuplicarEventoForm(BootstrapFormMixin, forms.Form):
    nome = forms.CharField(label="Nome do evento", max_length=150)
    edicao = forms.CharField(label="Nova edição", max_length=50, help_text="Ex.: 2027")
    copiar_pacotes = forms.BooleanField(label="Copiar pacotes (nome, valor, benefícios e regras)", required=False, initial=True)

    def clean(self):
        dados = super().clean()
        if Evento.objects.filter(nome=dados.get("nome"), edicao=dados.get("edicao")).exists():
            raise forms.ValidationError("Já existe um evento com este nome e edição.")
        return dados
