# Streamlit application image (step 2), pushed to Amazon ECR
# and run by Amazon ECS Express Mode (Fargate, x86_64).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies first: this layer stays cached as long as requirements.txt does not change
COPY app/requirements.txt .
RUN pip install -r requirements.txt

# Application code (and its .streamlit/ config)
COPY app/ .

# CA bundle required by the TLS connection to DocumentDB
ADD --chmod=644 https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem /etc/ssl/certs/docdb-global-bundle.pem

# Do not run as root inside the container
RUN useradd --create-home --uid 1000 appuser && chown -R appuser /app
USER appuser

# Version shown in the status report (passed with --build-arg by deploy.sh)
ARG APP_VERSION=dev
ENV APP_VERSION=${APP_VERSION}

EXPOSE 8501

# Docker healthcheck (local). On ECS, the ALB calls the same endpoint.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8501/_stcore/health', timeout=4).status == 200 else 1)"

CMD ["streamlit", "run", "app.py"]
