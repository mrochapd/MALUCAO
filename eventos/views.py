from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import permission_required
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from core.views import ExclusaoProtegidaMixin, PermissaoMixin

from .forms import DuplicarEventoForm, EventoForm, ModalidadeForm, PacoteForm
from .models import Evento, Modalidade, Pacote
from .services import duplicar_evento


class MensagemSucessoMixin:
    mensagem_sucesso = "Registro salvo com sucesso."

    def form_valid(self, form):
        resposta = super().form_valid(form)
        messages.success(self.request, self.mensagem_sucesso)
        return resposta


# ---------------------------------------------------------------- Modalidades
class ModalidadeListView(PermissaoMixin, ListView):
    permission_required = "eventos.view_modalidade"
    template_name = "eventos/modalidade_list.html"
    context_object_name = "modalidades"

    def get_queryset(self):
        qs = Modalidade.objects.annotate(
            n_eventos=Count("eventos", distinct=True),
            n_participantes=Count("inscricoes", distinct=True),
        )
        status = self.request.GET.get("status")
        if status == "ativas":
            qs = qs.filter(ativa=True)
        elif status == "inativas":
            qs = qs.filter(ativa=False)
        if self.request.GET.get("tipo"):
            qs = qs.filter(tipo=self.request.GET["tipo"])
        if self.request.GET.get("naipe"):
            qs = qs.filter(naipe=self.request.GET["naipe"])
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["tipos"] = Modalidade.Tipo.choices
        ctx["naipes"] = Modalidade.Naipe.choices
        return ctx


class ModalidadeCreateView(PermissaoMixin, MensagemSucessoMixin, CreateView):
    permission_required = "eventos.add_modalidade"
    model = Modalidade
    form_class = ModalidadeForm
    template_name = "eventos/form_simples.html"
    success_url = reverse_lazy("eventos:modalidades")
    mensagem_sucesso = "Modalidade cadastrada."
    extra_context = {"titulo": "Nova modalidade", "voltar": reverse_lazy("eventos:modalidades")}


class ModalidadeUpdateView(PermissaoMixin, MensagemSucessoMixin, UpdateView):
    permission_required = "eventos.change_modalidade"
    model = Modalidade
    form_class = ModalidadeForm
    template_name = "eventos/form_simples.html"
    success_url = reverse_lazy("eventos:modalidades")
    mensagem_sucesso = "Modalidade atualizada."
    extra_context = {"titulo": "Editar modalidade", "voltar": reverse_lazy("eventos:modalidades")}


class ModalidadeDeleteView(PermissaoMixin, ExclusaoProtegidaMixin, DeleteView):
    permission_required = "eventos.delete_modalidade"
    model = Modalidade
    template_name = "confirmar_exclusao.html"
    success_url = reverse_lazy("eventos:modalidades")


@require_POST
@permission_required("eventos.change_modalidade", raise_exception=True)
def modalidade_alternar(request, pk):
    modalidade = get_object_or_404(Modalidade, pk=pk)
    modalidade.ativa = not modalidade.ativa
    modalidade.save()
    messages.success(request, f"Modalidade “{modalidade}” {'ativada' if modalidade.ativa else 'desativada'}.")
    return redirect(request.POST.get("next") or "eventos:modalidades")


# -------------------------------------------------------------------- Eventos
class EventoListView(PermissaoMixin, ListView):
    permission_required = "eventos.view_evento"
    template_name = "eventos/evento_list.html"
    context_object_name = "eventos"

    def get_queryset(self):
        qs = Evento.objects.annotate(
            n_inscritos=Count("inscricoes", distinct=True),
            n_modalidades=Count("modalidades", distinct=True),
            n_pacotes=Count("pacotes", distinct=True),
        )
        periodo = self.request.GET.get("periodo")
        if periodo == "futuros":
            qs = qs.futuros()
        elif periodo == "anteriores":
            qs = qs.anteriores()
        if self.request.GET.get("status"):
            qs = qs.filter(status=self.request.GET["status"])
        if self.request.GET.get("q"):
            q = self.request.GET["q"]
            qs = qs.filter(Q(nome__icontains=q) | Q(edicao__icontains=q) | Q(local__icontains=q))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["status_choices"] = Evento.Status.choices
        return ctx


class EventoDetailView(PermissaoMixin, DetailView):
    permission_required = "eventos.view_evento"
    model = Evento
    template_name = "eventos/evento_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        evento = self.object
        ctx["pacotes"] = evento.pacotes.annotate(n_atletas=Count("inscricoes")).prefetch_related("modalidades_permitidas")
        ctx["modalidades"] = evento.modalidades.annotate(
            n_participantes=Count("inscricoes", filter=Q(inscricoes__evento=evento), distinct=True),
            n_masc=Count("inscricoes", filter=Q(inscricoes__evento=evento, inscricoes__atleta__sexo="M"), distinct=True),
            n_fem=Count("inscricoes", filter=Q(inscricoes__evento=evento, inscricoes__atleta__sexo="F"), distinct=True),
        )
        ctx["por_sexo"] = {
            "M": evento.inscricoes.filter(atleta__sexo="M").count(),
            "F": evento.inscricoes.filter(atleta__sexo="F").count(),
        }
        ctx["total_inscritos"] = evento.inscricoes.count()
        ctx["recentes"] = evento.inscricoes.select_related("atleta", "pacote")[:10]
        ctx["form_duplicar"] = DuplicarEventoForm(initial={"nome": evento.nome})
        return ctx


class EventoCreateView(PermissaoMixin, MensagemSucessoMixin, CreateView):
    permission_required = "eventos.add_evento"
    model = Evento
    form_class = EventoForm
    template_name = "eventos/evento_form.html"
    mensagem_sucesso = "Evento criado. Agora cadastre os pacotes de inscrição."


class EventoUpdateView(PermissaoMixin, MensagemSucessoMixin, UpdateView):
    permission_required = "eventos.change_evento"
    model = Evento
    form_class = EventoForm
    template_name = "eventos/evento_form.html"
    mensagem_sucesso = "Evento atualizado."


class EventoDeleteView(PermissaoMixin, ExclusaoProtegidaMixin, DeleteView):
    permission_required = "eventos.delete_evento"
    model = Evento
    template_name = "confirmar_exclusao.html"
    success_url = reverse_lazy("eventos:eventos")
    mensagem_protegido = (
        "Este evento possui pacotes ou inscrições vinculadas e não pode ser excluído. "
        "Altere o status para “Finalizado” para mantê-lo no histórico."
    )


@require_POST
@permission_required("eventos.add_evento", raise_exception=True)
def evento_duplicar(request, pk):
    origem = get_object_or_404(Evento, pk=pk)
    form = DuplicarEventoForm(request.POST)
    if form.is_valid():
        novo = duplicar_evento(origem, form.cleaned_data["nome"], form.cleaned_data["edicao"],
                               form.cleaned_data["copiar_pacotes"])
        messages.success(request, f"Nova edição “{novo}” criada a partir de “{origem}”. Revise datas e valores.")
        return redirect("eventos:evento_editar", pk=novo.pk)
    for erro in form.errors.values():
        messages.error(request, " ".join(erro))
    return redirect(origem)


@require_POST
@permission_required("eventos.change_evento", raise_exception=True)
def evento_status(request, pk):
    evento = get_object_or_404(Evento, pk=pk)
    novo = request.POST.get("status")
    if novo in Evento.Status.values:
        evento.status = novo
        evento.save()
        messages.success(request, f"Status do evento alterado para “{evento.get_status_display()}”.")
    return redirect(evento)


# -------------------------------------------------------------------- Pacotes
class PacoteListView(PermissaoMixin, ListView):
    permission_required = "eventos.view_pacote"
    template_name = "eventos/pacote_list.html"
    context_object_name = "pacotes"

    def get_queryset(self):
        qs = Pacote.objects.select_related("evento").annotate(n_atletas=Count("inscricoes"))
        if self.request.GET.get("evento"):
            qs = qs.filter(evento_id=self.request.GET["evento"])
        return qs.order_by("-evento__data_inicio", "evento__nome", "valor")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["eventos"] = Evento.objects.all()
        ctx["evento_filtro"] = self.request.GET.get("evento", "")
        return ctx


class PacoteFormMixin(PermissaoMixin, MensagemSucessoMixin):
    model = Pacote
    form_class = PacoteForm
    template_name = "eventos/pacote_form.html"

    def get_success_url(self):
        if self.request.GET.get("next") == "evento":
            return reverse("eventos:evento_detalhe", args=[self.object.evento_id])
        return reverse("eventos:pacotes")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["modalidades_por_evento"] = {
            str(e.pk): list(e.modalidades.values_list("pk", flat=True)) for e in Evento.objects.prefetch_related("modalidades")
        }
        return ctx


class PacoteCreateView(PacoteFormMixin, CreateView):
    permission_required = "eventos.add_pacote"
    mensagem_sucesso = "Pacote cadastrado."

    def get_initial(self):
        inicial = super().get_initial()
        if self.request.GET.get("evento"):
            inicial["evento"] = self.request.GET["evento"]
        return inicial


class PacoteUpdateView(PacoteFormMixin, UpdateView):
    permission_required = "eventos.change_pacote"
    mensagem_sucesso = "Pacote atualizado."


class PacoteDeleteView(PermissaoMixin, ExclusaoProtegidaMixin, DeleteView):
    permission_required = "eventos.delete_pacote"
    model = Pacote
    template_name = "confirmar_exclusao.html"
    success_url = reverse_lazy("eventos:pacotes")
    mensagem_protegido = "Há atletas inscritos com este pacote. Desative-o em vez de excluir."
