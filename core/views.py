from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.models import User
from django.db import connection
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, TemplateView, UpdateView

from atletas.models import Atleta, Inscricao
from eventos.models import Evento, Modalidade, Pacote

from .forms import UsuarioForm
from .models import RegistroAlteracao


class PermissaoMixin(LoginRequiredMixin, PermissionRequiredMixin):
    """Exige login e a permissão informada; usuário logado sem permissão recebe 403."""

    raise_exception = False

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            self.raise_exception = True
        return super().handle_no_permission()


class ExclusaoProtegidaMixin:
    """Trata ProtectedError em exclusões, exibindo uma mensagem amigável."""

    mensagem_protegido = "Este registro possui vínculos e não pode ser excluído."

    def form_valid(self, form):
        from django.db.models import ProtectedError

        try:
            resposta = super().form_valid(form)
        except ProtectedError:
            messages.error(self.request, self.mensagem_protegido)
            return redirect(self.request.META.get("HTTP_REFERER") or self.get_success_url())
        messages.success(self.request, "Registro excluído com sucesso.")
        return resposta


def _ranking(itens, total=None):
    """Adiciona a proporção (0–100) de cada item em relação ao maior valor, para as barras."""
    itens = list(itens)
    maior = max((i["total"] for i in itens), default=0) or 1
    for item in itens:
        item["pct"] = round(item["total"] * 100 / maior)
    return itens


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "core/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        evento_id = self.request.GET.get("evento") or ""
        eventos = Evento.objects.order_by("-data_inicio", "-criado_em")
        evento = eventos.filter(pk=evento_id).first() if evento_id.isdigit() else None

        inscricoes = Inscricao.objects.all()
        if evento:
            inscricoes = inscricoes.filter(evento=evento)

        por_evento = (
            Evento.objects.annotate(total=Count("inscricoes"))
            .order_by("-total", "nome")
            .values("pk", "nome", "edicao", "status", "total")
        )
        filtro_ins = Q(inscricoes__evento=evento) if evento else Q()
        por_pacote = (
            Pacote.objects.filter(evento=evento) if evento else Pacote.objects.all()
        ).annotate(total=Count("inscricoes")).order_by("-total", "nome").values(
            "pk", "nome", "evento__nome", "evento__edicao", "total"
        )
        por_modalidade = (
            Modalidade.objects.annotate(total=Count("inscricoes", filter=filtro_ins, distinct=True))
            .filter(total__gt=0)
            .order_by("-total", "nome")
            .values("pk", "nome", "total")
        )

        atletas_base = Atleta.objects.filter(inscricoes__evento=evento).distinct() if evento else Atleta.objects.all()
        ctx.update(
            atletas_masc=atletas_base.filter(sexo="M").count(),
            atletas_fem=atletas_base.filter(sexo="F").count(),
            atletas_sem_sexo=atletas_base.filter(sexo="").count(),
            eventos=eventos,
            evento_filtro=evento,
            total_atletas=Atleta.objects.filter(inscricoes__evento=evento).distinct().count()
            if evento else Atleta.objects.count(),
            total_inscricoes=inscricoes.count(),
            total_eventos=Evento.objects.count(),
            eventos_abertos=Evento.objects.filter(status=Evento.Status.INSCRICOES_ABERTAS),
            total_modalidades_ativas=(evento.modalidades_ativas() if evento else Modalidade.objects.filter(ativa=True)).count(),
            modalidades_disponiveis=(evento.modalidades_ativas() if evento else Modalidade.objects.filter(ativa=True)),
            por_evento=_ranking(por_evento),
            por_pacote=_ranking(por_pacote),
            por_modalidade=_ranking(por_modalidade),
            recentes=inscricoes.select_related("atleta", "evento", "pacote").prefetch_related("modalidades")[:8],
        )
        return ctx


class AuditoriaListView(PermissaoMixin, ListView):
    permission_required = "core.ver_auditoria"
    template_name = "core/auditoria.html"
    paginate_by = 30
    context_object_name = "registros"

    def get_queryset(self):
        qs = RegistroAlteracao.objects.select_related("usuario")
        p = self.request.GET
        if p.get("entidade"):
            qs = qs.filter(entidade=p["entidade"])
        if p.get("acao"):
            qs = qs.filter(acao=p["acao"])
        if p.get("q"):
            qs = qs.filter(Q(objeto_repr__icontains=p["q"]) | Q(usuario__username__icontains=p["q"]))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["entidades"] = RegistroAlteracao.objects.order_by("entidade").values_list("entidade", flat=True).distinct()
        ctx["acoes"] = RegistroAlteracao.Acao.choices
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["querystring"] = params.urlencode()
        return ctx


class UsuarioListView(PermissaoMixin, ListView):
    permission_required = "core.gerenciar_usuarios"
    template_name = "core/usuarios.html"
    context_object_name = "usuarios"

    def get_queryset(self):
        return User.objects.prefetch_related("groups").order_by("-is_active", "username")


class UsuarioFormMixin(PermissaoMixin):
    permission_required = "core.gerenciar_usuarios"
    model = User
    form_class = UsuarioForm
    template_name = "core/usuario_form.html"
    success_url = reverse_lazy("core:usuarios")


class UsuarioCreateView(UsuarioFormMixin, CreateView):
    def form_valid(self, form):
        messages.success(self.request, "Usuário criado com sucesso.")
        return super().form_valid(form)


class UsuarioUpdateView(UsuarioFormMixin, UpdateView):
    def form_valid(self, form):
        if form.instance == self.request.user and not form.cleaned_data.get("is_active"):
            form.add_error("is_active", "Você não pode desativar o seu próprio usuário.")
            return self.form_invalid(form)
        messages.success(self.request, "Usuário atualizado com sucesso.")
        return super().form_valid(form)


class PrivacidadeView(LoginRequiredMixin, TemplateView):
    template_name = "core/privacidade.html"


def saude(request):
    """Endpoint de verificação de saúde (para monitoramento / balanceador)."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return JsonResponse({"status": "ok"})
    except Exception:  # pragma: no cover
        return JsonResponse({"status": "erro"}, status=503)
