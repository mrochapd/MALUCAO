#!/usr/bin/env bash
# Build usado pela hospedagem (Render): instala dependências, prepara arquivos e banco.
set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput
python manage.py setup_inicial
