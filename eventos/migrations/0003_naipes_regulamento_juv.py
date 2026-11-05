"""Aplica às modalidades já cadastradas os naipes definidos no regulamento da JUV."""
from django.db import migrations

NAIPES = {
    "Futsal": "masc_fem", "Fut7": "masculino", "Vôlei": "masc_fem", "Handebol": "masc_fem",
    "Basquete": "masc_fem", "Vôlei de Praia": "masc_fem", "Tênis de Mesa": "masc_fem",
    "Peteca": "masc_fem", "E-sports": "misto", "Truco": "masc_fem", "Sinuca": "dupla_mista",
    "Xadrez": "misto", "Atletismo": "masc_fem", "Beach Tênis": "dupla_mista",
    "Natação": "masc_fem", "Futevôlei": "dupla_mista",
}


def aplicar(apps, schema_editor):
    Modalidade = apps.get_model("eventos", "Modalidade")
    for nome, naipe in NAIPES.items():
        Modalidade.objects.filter(nome=nome).update(naipe=naipe)


class Migration(migrations.Migration):
    dependencies = [("eventos", "0002_modalidade_naipe")]
    operations = [migrations.RunPython(aplicar, migrations.RunPython.noop)]
