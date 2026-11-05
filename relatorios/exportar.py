"""Exportação dos relatórios para Excel (.xlsx) e PDF."""
import io

from django.conf import settings
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image, LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle

from .services import Relatorio

VERMELHO = "E30613"
PRETO = "111111"
AVISO_LGPD = (
    "Documento com dados pessoais protegidos pela LGPD (Lei 13.709/2018). "
    "Uso restrito à organização do evento — não compartilhe."
)


def para_excel(rel: Relatorio, filtros_txt: str, usuario: str) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = rel.titulo[:31]
    ncol = len(rel.colunas)

    ws.append([rel.titulo])
    ws["A1"].font = Font(bold=True, size=14, color=PRETO)
    ws.append([f"{settings.SISTEMA_ORGANIZACAO}"])
    ws.append([f"Filtros: {filtros_txt}"])
    ws.append([f"Gerado em {timezone.localtime():%d/%m/%Y %H:%M} por {usuario}"])
    for linha in range(2, 5):
        ws.cell(linha, 1).font = Font(italic=True, size=9, color="555555")
    ws.append([])

    ws.append(rel.colunas)
    cab = ws.max_row
    for col in range(1, ncol + 1):
        c = ws.cell(cab, col)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=VERMELHO)
        c.alignment = Alignment(vertical="center")
    for linha in rel.linhas:
        ws.append(linha)
    ultima = ws.max_row
    if rel.linhas:
        ws.auto_filter.ref = f"A{cab}:{get_column_letter(ncol)}{ultima}"
    ws.freeze_panes = ws.cell(cab + 1, 1)

    ws.append([])
    for texto in rel.rodape:
        ws.append([texto])
        ws.cell(ws.max_row, 1).font = Font(bold=True)
    if rel.contem_dados_pessoais:
        ws.append([AVISO_LGPD])
        ws.cell(ws.max_row, 1).font = Font(italic=True, size=8, color="888888")

    for col in range(1, ncol + 1):
        valores = [str(ws.cell(r, col).value or "") for r in range(cab, ultima + 1)]
        ws.column_dimensions[get_column_letter(col)].width = min(max(len(v) for v in valores) + 3, 60)

    saida = io.BytesIO()
    wb.save(saida)
    return saida.getvalue()


def para_pdf(rel: Relatorio, filtros_txt: str, usuario: str) -> bytes:
    saida = io.BytesIO()
    pagina = landscape(A4)
    doc = SimpleDocTemplate(
        saida, pagesize=pagina, leftMargin=12 * mm, rightMargin=12 * mm, topMargin=12 * mm, bottomMargin=14 * mm,
        title=rel.titulo, author=settings.SISTEMA_ORGANIZACAO,
    )
    estilo_titulo = ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=15, leading=18)
    estilo_sub = ParagraphStyle("s", fontName="Helvetica", fontSize=8.5, textColor=colors.HexColor("#555555"), leading=11)
    estilo_celula = ParagraphStyle("c", fontName="Helvetica", fontSize=7.5, leading=9.2)
    estilo_cab = ParagraphStyle("h", parent=estilo_celula, fontName="Helvetica-Bold", textColor=colors.white)
    estilo_rodape = ParagraphStyle("r", fontName="Helvetica-Bold", fontSize=9, leading=12)

    logo = settings.BASE_DIR / "static" / "img" / "logo-wordmark.png"
    elementos = []
    if logo.exists():
        img = Image(str(logo), width=48 * mm, height=48 * mm * 384 / 900)
        img.hAlign = "LEFT"
        elementos.append(img)
        elementos.append(Spacer(1, 3 * mm))
    elementos += [
        Paragraph(rel.titulo, estilo_titulo),
        Paragraph(f"Filtros: {filtros_txt}", estilo_sub),
        Paragraph(f"Gerado em {timezone.localtime():%d/%m/%Y %H:%M} por {usuario}", estilo_sub),
        Spacer(1, 4 * mm),
    ]

    dados = [[Paragraph(str(c), estilo_cab) for c in rel.colunas]]
    for linha in rel.linhas:
        dados.append([Paragraph(str(v).replace("&", "&amp;").replace("<", "&lt;"), estilo_celula) for v in linha])
    if len(dados) == 1:
        dados.append([Paragraph("Nenhum registro encontrado para os filtros informados.", estilo_celula)]
                     + [""] * (len(rel.colunas) - 1))

    largura_util = pagina[0] - doc.leftMargin - doc.rightMargin
    pesos = []
    for i, col in enumerate(rel.colunas):
        maior = max([len(str(col))] + [len(str(l[i])) for l in rel.linhas[:200]])
        pesos.append(min(max(maior, 6), 45))
    larguras = [largura_util * p / sum(pesos) for p in pesos]

    tabela = LongTable(dados, colWidths=larguras, repeatRows=1)
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#" + VERMELHO)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F4F4")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#DDDDDD")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elementos.append(tabela)
    elementos.append(Spacer(1, 4 * mm))
    for texto in rel.rodape:
        elementos.append(Paragraph(texto, estilo_rodape))

    def rodape(canvas, documento):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#777777"))
        texto = f"{settings.SISTEMA_ORGANIZACAO} — página {documento.page}"
        canvas.drawString(documento.leftMargin, 8 * mm, texto)
        if rel.contem_dados_pessoais:
            canvas.drawRightString(pagina[0] - documento.rightMargin, 8 * mm, AVISO_LGPD)
        canvas.restoreState()

    doc.build(elementos, onFirstPage=rodape, onLaterPages=rodape)
    return saida.getvalue()
