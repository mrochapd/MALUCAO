from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.text import slugify

from core.auditoria import registrar

from .exportar import para_excel, para_pdf
from .forms import FiltroRelatorioForm
from .services import Filtros, gerar


def _gerar(request):
    form = FiltroRelatorioForm(request.GET or None)
    if form.is_bound and form.is_valid():
        dados = form.cleaned_data
    else:
        form = FiltroRelatorioForm(initial={"tipo": "inscritos"})
        dados = {"tipo": "inscritos"}
    filtros = Filtros(dados.get("evento"), dados.get("pacote"), dados.get("modalidade"), dados.get("sexo", ""))
    rel = gerar(dados["tipo"], filtros, request.user.has_perm("atletas.ver_dados_pessoais"))
    return form, filtros, rel


@login_required
def relatorios(request):
    if not request.user.has_perm("core.ver_relatorios"):
        return render(request, "403.html", status=403)
    form, filtros, rel = _gerar(request)
    return render(request, "relatorios/relatorios.html", {
        "form": form, "rel": rel, "filtros_txt": filtros.descricao(),
        "querystring": request.GET.urlencode(),
    })


@login_required
def exportar(request, formato):
    if not request.user.has_perm("core.exportar_relatorios"):
        return render(request, "403.html", status=403)
    form, filtros, rel = _gerar(request)
    usuario = request.user.get_full_name() or request.user.get_username()
    nome = f"{slugify(rel.titulo)}-{timezone.localtime():%Y%m%d-%H%M}"
    if formato == "xlsx":
        conteudo = para_excel(rel, filtros.descricao(), usuario)
        tipo = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        conteudo = para_pdf(rel, filtros.descricao(), usuario)
        tipo = "application/pdf"
    registrar("exportacao", "Relatório", rel.chave, rel.titulo,
              {"formato": formato.upper(), "filtros": filtros.descricao(), "linhas": len(rel.linhas)}, request)
    resposta = HttpResponse(conteudo, content_type=tipo)
    resposta["Content-Disposition"] = f'attachment; filename="{nome}.{formato}"'
    return resposta
