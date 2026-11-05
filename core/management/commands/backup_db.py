"""
Backup do banco de dados.

* PostgreSQL: usa `pg_dump` (formato custom, compactado).
* SQLite: usa a API de backup online do SQLite (cópia consistente) + gzip.
* Sempre gera também um JSON (dumpdata) compactado, portátil entre bancos.

Mantém apenas os N backups mais recentes (BACKUP_RETENCAO). Agende com cron, ex.:
    0 3 * * *  cd /app && python manage.py backup_db
"""
import gzip
import os
import shutil
import sqlite3
import subprocess
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone


class Command(BaseCommand):
    help = "Gera backup do banco de dados e remove backups antigos."

    def add_arguments(self, parser):
        parser.add_argument("--destino", default=str(settings.BACKUP_DIR))
        parser.add_argument("--retencao", type=int, default=settings.BACKUP_RETENCAO)

    def handle(self, *args, **opts):
        destino = Path(opts["destino"])
        destino.mkdir(parents=True, exist_ok=True)
        carimbo = timezone.localtime().strftime("%Y%m%d-%H%M%S")
        gerados = []

        db = settings.DATABASES["default"]
        motor = connection.vendor
        if motor == "sqlite":
            arquivo = destino / f"malucao-{carimbo}.sqlite3"
            origem = sqlite3.connect(db["NAME"])
            copia = sqlite3.connect(arquivo)
            with copia:
                origem.backup(copia)
            origem.close()
            copia.close()
            gerados.append(self._gzip(arquivo))
        elif motor == "postgresql":
            arquivo = destino / f"malucao-{carimbo}.dump"
            ambiente = {"PGPASSWORD": str(db.get("PASSWORD") or "")}
            cmd = ["pg_dump", "-Fc", "-h", str(db.get("HOST") or "localhost"), "-p", str(db.get("PORT") or 5432),
                   "-U", str(db.get("USER")), "-f", str(arquivo), str(db["NAME"])]
            try:
                subprocess.run(cmd, check=True, env={**os.environ, **ambiente})
                gerados.append(arquivo)
            except (OSError, subprocess.CalledProcessError) as erro:
                self.stderr.write(self.style.WARNING(f"pg_dump indisponível ou falhou ({erro}); usando apenas JSON."))

        json_arquivo = destino / f"malucao-{carimbo}.json.gz"
        with gzip.open(json_arquivo, "wt", encoding="utf-8") as saida:
            call_command("dumpdata", "--natural-foreign", "--natural-primary", "--indent", "1",
                         "-e", "contenttypes", "-e", "auth.permission", "-e", "sessions", "-e", "axes",
                         stdout=saida)
        gerados.append(json_arquivo)

        if not gerados:
            raise CommandError("Nenhum backup gerado.")
        removidos = self._limpar(destino, opts["retencao"])
        for g in gerados:
            self.stdout.write(self.style.SUCCESS(f"Backup gerado: {g}"))
        if removidos:
            self.stdout.write(f"{removidos} backup(s) antigo(s) removido(s).")

    @staticmethod
    def _gzip(arquivo: Path) -> Path:
        destino = arquivo.with_suffix(arquivo.suffix + ".gz")
        with open(arquivo, "rb") as ent, gzip.open(destino, "wb") as sai:
            shutil.copyfileobj(ent, sai)
        arquivo.unlink()
        return destino

    @staticmethod
    def _limpar(destino: Path, retencao: int) -> int:
        carimbos = sorted({p.name.split(".")[0] for p in destino.glob("malucao-*")}, reverse=True)
        removidos = 0
        for antigo in carimbos[retencao:]:
            for p in destino.glob(f"{antigo}.*"):
                p.unlink()
                removidos += 1
        return removidos
