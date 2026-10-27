# CLAUDE.md – CloudSys project

Context handed over from claude.ai (TSM-CloudSys project). Read at the start of every session.

## The project

AWS architecture that detects trade anomalies in **UN Comtrade** data (FOB/CIF mismatches), in 3 steps:

1. **Ingestion and computation** → results in **Amazon DocumentDB** (`trades_matrix` collection). Built elsewhere, **not available yet**. Document schema **unknown**.
2. **Streamlit application** ← **`comtrade-app/`, the focus of this workspace**.
3. **AI analysis and PDF reports** (AWS Lambda + Bedrock, S3 storage). Not started.

Cognito (authentication): only if time allows.

**Philosophy:** first a simple architecture that works, then add complexity in small steps.

## Current state (end of October 2026)

- **Placeholder** Streamlit app, no database connection: it shows a status report (version, environment, uptime, ECS task metadata on AWS, architecture component states, all placeholders) and a counter button that checks WebSockets go through the load balancer.
- **Local deployment** (`docker compose`): works.
- **AWS deployment** (`infra/deploy.sh`): works.

Work so far focused on the DevOps chain: **Docker → Amazon ECR → Amazon ECS Express Mode**.

## Workspace layout

The git root is `Cloudsys-project/`. **Only `comtrade-app/` is deployed**; the other folders are context, not application code.

```
Cloudsys-project/
├── CLAUDE.md
├── README.md                  # project overview
├── comtrade-app/              # DEPLOYED APPLICATION (step 2), see below
├── Doc/                       # project docs: architecture.md, description.md,
│                              #   presentation, project list PDF (reference only)
├── data/                      # Bilateral_data.csv / .xlsx + description PDF
├── pyproject.toml             # local uv workspace settings, not deployed
└── .python-version
```

`data/Bilateral_data.csv` columns: `YearMonth, Reporter, Flow, Partner, HS4, Product, Value_USD, Qty_t` (ISO3 country codes, numbers use `'` as thousands separator, e.g. `22'998'882`). Planned source for the fake local MongoDB data.

### Deployed application

```
comtrade-app/
├── app/
│   ├── app.py                 # Streamlit application (status report)
│   ├── requirements.txt
│   └── .streamlit/config.toml # port 8501, listens on 0.0.0.0
├── Dockerfile                 # image pushed to ECR (healthcheck, non-root user, APP_VERSION build-arg)
├── .dockerignore
├── docker-compose.yml         # local development only
├── README.md
└── infra/
    ├── config.env             # resource names, region, CPU/memory, network
    ├── deploy.sh              # creates / updates all AWS resources (re-runnable)
    └── teardown.sh            # deletes the resources (stops billing)
```

## Commands

All run from `comtrade-app/`.

```bash
# Local: http://localhost:8501 (code mounted as a volume, hot reload)
docker compose up --build

# AWS (from WSL)
./infra/deploy.sh
./infra/teardown.sh               # service + ALB, cluster, ECR, logs
./infra/teardown.sh --delete-iam  # same + IAM roles

# Production logs
aws logs tail /ecs/comtrade-app --follow
```

## Technical choices and why

- **ECS Express Mode (Fargate + ALB) rather than App Runner**: Streamlit needs WebSockets, which App Runner does not support; App Runner is also closed to new customers since April 30, 2026. Express Mode also gives VPC access for DocumentDB and possible Cognito integration through the ALB.
- **Single task** (`MIN_TASKS=MAX_TASKS=1`): no need for sticky sessions.
- **Health check**: `/_stcore/health` (Streamlit's native endpoint), port 8501.
- **`linux/amd64` image**: X86_64 architecture of the Fargate service.
- **Unique image tag** on every deployment (short git hash + time, else a timestamp) to force ECS to roll out a new revision.
- **`deploy.sh` is idempotent**: each step checks whether the resource exists. Order: ECR → build/push → IAM roles (execution + infrastructure) → CloudWatch log group (7-day retention) → ECS cluster → Express service (created, then updated) → wait for stability → public URL.
- **`teardown.sh`** skips missing resources. Deleting the Express service also removes the ALB, target groups, security groups and autoscaling.
- **docker-compose is for local development only**, not production.

## AWS environment

- Region: **us-east-1**. Priority in `config.env`: `AWS_REGION` variable > `aws configure` region > file default (`us-east-1`).
- Credentials: those from `aws configure`, provided in an academic setting. No environment variables to set.
- Network: default VPC (`SUBNETS` and `SECURITY_GROUPS` empty in `config.env`). To be set later with the DocumentDB VPC.
- Scripts run from a **WSL** terminal, with Docker Desktop (WSL integration).

## Working rules

- **Language**: reply in French or English. Everything in the code is in **English**: comments, docstrings, variable/function names, log messages, Streamlit UI text, and READMEs. Keep comments ASCII-only.
- **Ask before running `deploy.sh` or `teardown.sh`**, or any AWS command that creates or deletes resources: they are real, billed resources. The ALB and the Fargate task cost money even with no traffic, so remember `teardown.sh` at the end of a session.
- Bash scripts: `set -euo pipefail`, checked with `shellcheck`.
- For any recent AWS CLI command (notably `aws ecs create-express-gateway-service`), check the syntax in the official documentation rather than from memory.
- Keep the READMEs up to date when usage or prerequisites change.

## Planned next steps

1. **DocumentDB connection** (once step 1 exists): set `SUBNETS` / `SECURITY_GROUPS` (cluster VPC, port 27017), pass the URI through Secrets Manager, add the CA certificate to the Dockerfile. Locally: MongoDB in docker-compose, seeded from `data/Bilateral_data.csv`, until the real `trades_matrix` schema is known.
2. **Real app**: anomaly heatmap and filters.
3. **Call to the AI Lambda (step 3)**: task role (`--task-role-arn`) with `lambda:InvokeFunction`. Start with a stub: the "Analyze anomaly" button shows a fake message.
4. **Cognito** through the ALB, if time allows.
