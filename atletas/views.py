from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.db.models.functions import Lower
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import DeleteView, DetailView, ListView, UpdateView

from core.cpf import cpf_valido, somente_digitos
from core.views import PermissaoMixin
from eventos.services import opcoes_por_evento

from .forms import AtletaForm, FiltroAtletasForm, InscricaoForm
from .models import Atleta, Inscricao


def filtrar_atletas(qs, dados):
    """Aplica busca por nome/CPF e filtros por evento, pacote e modalidade."""
    termo = (dados.get("q") or "").strip()
    if termo:
        digitos = somente_digitos(termo)
        filtro = Q(nome__icontains=termo) | Q(email__icontains=termo)
        if len(digitos) >= 3:
            filtro |= Q(cpf__contains=digitos)
        qs = qs.filter(filtro)
    if dados.get("evento"):
        qs = qs.filter(inscricoes__evento=dados["evento"])
    if dados.get("pacote"):
        qs = qs.filter(inscricoes__pacote=dados["pacote"])
    if dados.get("modalidade"):
        filtro_mod = Q(inscricoes__modalidades=dados["modalidade"])
        if dados.get("evento"):
            filtro_mod &= Q(inscricoes__evento=dados["evento"])
        qs = qs.filter(filtro_mod)
    if dados.get("sexo"):
        qs = qs.filter(sexo=dados["sexo"])
    return qs.distinct()


class AtletaListView(PermissaoMixin, ListView):
    permission_required = "atletas.view_atleta"
    template_name = "atletas/atleta_list.html"
    context_object_name = "atletas"
    paginate_by = 25

    def get_queryset(self):
        self.filtro = FiltroAtletasForm(self.request.GET or None)
        dados = self.filtro.cleaned_data if self.filtro.is_valid() else {}
        qs = Atleta.objects.prefetch_related(
            Prefetch("inscricoes", queryset=Inscricao.objects.select_related("evento", "pacote").prefetch_related("modalidades"))
        )
        return filtrar_atletas(qs, dados).order_by("nome")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx.update(filtro=self.filtro, querystring=params.urlencode(), total=self.get_queryset().count())
        return ctx


def _contexto_inscricao(form_inscricao, instancia=None):
    pacotes = [instancia.pacote_id] if instancia else []
    modalidades = list(instancia.modalidades.values_list("pk", flat=True)) if instancia else []
    selecionadas = form_inscricao["modalidades"].value() or []
    return {
        "opcoes_eventos": opcoes_por_evento(pacotes, modalidades),
        "modalidades_selecionadas": [str(v) for v in selecionadas],
        "pacote_selecionado": str(form_inscricao["pacote"].value() or ""),
    }


@login_required
def atleta_criar(request):
    """Cadastro do atleta já com a primeira inscrição (evento → pacote → modalidades)."""
    if not request.user.has_perm("atletas.add_atleta"):
        return render(request, "403.html", status=403)
    form = AtletaForm(request.POST or None)
    form_inscricao = InscricaoForm(request.POST or None, usuario=request.user, obrigatoria=False, prefix="insc")
    if request.method == "POST":
        atleta_ok = form.is_valid()
        # o sexo informado no próprio cadastro define os naipes permitidos na inscrição
        form_inscricao.sexo = form.cleaned_data.get("sexo") if atleta_ok else request.POST.get("sexo", "")
        inscricao_ok = form_inscricao.is_valid()
        if atleta_ok and inscricao_ok:
            with transaction.atomic():
                atleta = form.save()
                if form_inscricao.preenchida:
                    form_inscricao.atleta = atleta
                    form_inscricao.save()
            msg = "Atleta cadastrado"
            if form_inscricao.preenchida:
                msg += f" e inscrito em {form_inscricao.cleaned_data['evento']}"
            messages.success(request, msg + ".")
            if "salvar_novo" in request.POST:
                return redirect("atletas:novo")
            return redirect(atleta)
    ctx = {"form": form, "form_inscricao": form_inscricao, "atleta_existente": form.atleta_existente}
    ctx.update(_contexto_inscricao(form_inscricao))
    return render(request, "atletas/atleta_form.html", ctx)


class AtletaUpdateView(PermissaoMixin, UpdateView):
    permission_required = "atletas.change_atleta"
    model = Atleta
    form_class = AtletaForm
    template_name = "atletas/atleta_form.html"

    def form_valid(self, form):
        messages.success(self.request, "Dados do atleta atualizados.")
        return super().form_valid(form)

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form, atleta_existente=form.atleta_existente))


class AtletaDetailView(PermissaoMixin, DetailView):
    permission_required = "atletas.view_atleta"
    model = Atleta
    template_name = "atletas/atleta_detail.html"

    def get_context_data(self, **kwargs):
        from core.models import RegistroAlteracao

        ctx = super().get_context_data(**kwargs)
        ctx["inscricoes"] = self.object.inscricoes.select_related("evento", "pacote").prefetch_related("modalidades")
        if self.request.user.has_perm("core.ver_auditoria"):
            ids_insc = [str(i.pk) for i in ctx["inscricoes"]]
            ctx["historico"] = RegistroAlteracao.objects.filter(
                Q(entidade="Atleta", objeto_id=str(self.object.pk)) | Q(entidade="Inscrição", objeto_id__in=ids_insc)
            ).select_related("usuario")[:30]
        return ctx


class AtletaDeleteView(PermissaoMixin, DeleteView):
    permission_required = "atletas.delete_atleta"
    model = Atleta
    template_name = "confirmar_exclusao.html"
    success_url = reverse_lazy("atletas:lista")
    extra_context = {
        "aviso": "Todas as inscrições do atleta também serão excluídas. Esta ação atende ao direito de "
                 "eliminação de dados pessoais (LGPD) e não pode ser desfeita."
    }

    def form_valid(self, form):
        messages.success(self.request, "Atleta e suas inscrições foram excluídos.")
        return super().form_valid(form)


# ------------------------------------------------------------------ Inscrições
@login_required
def inscricao_form(request, atleta_pk=None, pk=None):
    if pk:
        inscricao = get_object_or_404(Inscricao.objects.select_related("atleta"), pk=pk)
        atleta = inscricao.atleta
        permissao = "atletas.change_inscricao"
    else:
        inscricao = None
        atleta = get_object_or_404(Atleta, pk=atleta_pk)
        permissao = "atletas.add_inscricao"
    if not request.user.has_perm(permissao):
        return render(request, "403.html", status=403)

    form = InscricaoForm(request.POST or None, instance=inscricao, atleta=atleta, usuario=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Inscrição salva com sucesso.")
        return redirect(atleta)
    ctx = {"form_inscricao": form, "atleta": atleta, "inscricao": inscricao, "sexo_atleta": atleta.sexo}
    ctx.update(_contexto_inscricao(form, inscricao))
    return render(request, "atletas/inscricao_form.html", ctx)


class InscricaoDeleteView(PermissaoMixin, DeleteView):
    permission_required = "atletas.delete_inscricao"
    model = Inscricao
    template_name = "confirmar_exclusao.html"

    def get_success_url(self):
        return reverse("atletas:detalhe", args=[self.object.atleta_id])

    def form_valid(self, form):
        messages.success(self.request, "Inscrição excluída.")
        return super().form_valid(form)


# ---------------------------------------------------------------- Duplicidade
@login_required
def verificar_cpf(request):
    """Consulta em tempo real usada no formulário para avisar sobre CPF já cadastrado."""
    cpf = somente_digitos(request.GET.get("cpf"))
    resposta = {"valido": cpf_valido(cpf), "existe": False}
    excluir = request.GET.get("excluir")
    if resposta["valido"]:
        qs = Atleta.objects.filter(cpf=cpf)
        if excluir and excluir.isdigit():
            qs = qs.exclude(pk=excluir)
        atleta = qs.first()
        if atleta:
            resposta.update(
                existe=True, nome=atleta.nome, url=atleta.get_absolute_url(),
                url_inscricao=reverse("atletas:inscricao_nova", args=[atleta.pk]),
            )
    return JsonResponse(resposta)


class DuplicadosView(PermissaoMixin, ListView):
    """
    O CPF é único no banco, então não há dois cadastros com o mesmo CPF. Esta tela aponta
    *possíveis* duplicidades: mesmo nome ou mesmo e-mail com CPFs diferentes (erro de digitação).
    """

    permission_required = "atletas.view_atleta"
    template_name = "atletas/duplicados.html"
    context_object_name = "grupos"

    def get_queryset(self):
        grupos = []
        nomes = (
            Atleta.objects.annotate(n=Lower("nome")).values("n").annotate(total=Count("id")).filter(total__gt=1)
        )
        for item in nomes:
            grupos.append(("Mesmo nome", item["n"], Atleta.objects.annotate(n=Lower("nome")).filter(n=item["n"])))
        emails = Atleta.objects.values("email").annotate(total=Count("id")).filter(total__gt=1)
        for item in emails:
            grupos.append(("Mesmo e-mail", item["email"], Atleta.objects.filter(email=item["email"])))
        return grupos
