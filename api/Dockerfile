# Imagem da API ORC (contexto = raiz deste repositório / pasta api/).

FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && mkdir -p /app/api /app/dados_usuario

COPY __init__.py auth.py config.py database.py deps.py main.py models.py schemas.py seed.py /app/api/
COPY routers /app/api/routers

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
