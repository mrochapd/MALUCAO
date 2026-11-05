from django import forms

from core.forms import BootstrapFormMixin
from eventos.models import Evento, Modalidade, Pacote

from .services import TIPOS


class FiltroRelatorioForm(BootstrapFormMixin, forms.Form):
    tipo = forms.ChoiceField(label="Relatório", choices=TIPOS, initial="inscritos")
    evento = forms.ModelChoiceField(Evento.objects.all(), required=False, empty_label="Todos os eventos")
    pacote = forms.ModelChoiceField(Pacote.objects.select_related("evento"), required=False,
                                    empty_label="Todos os pacotes")
    modalidade = forms.ModelChoiceField(Modalidade.objects.all(), required=False, empty_label="Todas as modalidades")
    sexo = forms.ChoiceField(label="Sexo", required=False,
                             choices=[("", "Ambos os sexos"), ("M", "Masculino"), ("F", "Feminino")])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["pacote"].label_from_instance = lambda p: f"{p.nome} — {p.evento}"
