FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    fastapi==0.115.5 \
    uvicorn[standard]==0.32.1 \
    psycopg[binary,pool]==3.2.3 \
    redis==5.2.0 \
    langchain==0.3.10 \
    langchain-openai==0.2.11 \
    pydantic==2.10.3 \
    pyyaml==6.0.2 \
    pandas==2.2.3 \
    numpy==2.1.3 \
    statsmodels==0.14.4 \
    scikit-learn==1.5.2

COPY . .

EXPOSE 8000
