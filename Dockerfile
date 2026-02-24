FROM python:3.11-slim

# Evita geração de arquivos .pyc
ENV PYTHONDONTWRITEBYTECODE=1

# Evita buffering
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copia requirements primeiro (melhor prática para cache)
COPY requirements.txt .

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do projeto
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]