# Image de l'application Streamlit (etape 2), poussee sur Amazon ECR
# et executee par Amazon ECS Express Mode (Fargate, x86_64).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependances d'abord : cette couche reste en cache tant que requirements.txt ne change pas
COPY app/requirements.txt .
RUN pip install -r requirements.txt

# Code de l'application (et sa config .streamlit/)
COPY app/ .

# Ne pas tourner en root dans le conteneur
RUN useradd --create-home --uid 1000 appuser && chown -R appuser /app
USER appuser

# Version affichee dans le status report (passee par --build-arg dans deploy.sh)
ARG APP_VERSION=dev
ENV APP_VERSION=${APP_VERSION}

EXPOSE 8501

# Healthcheck Docker (local). Sur ECS, c'est l'ALB qui appelle le meme endpoint.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8501/_stcore/health', timeout=4).status == 200 else 1)"

CMD ["streamlit", "run", "app.py"]
