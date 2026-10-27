# Comtrade Anomalies – Step 2: Streamlit application

Placeholder version: the app shows a *status report* (version, environment,
ECS task, component states) without connecting to any database.
Goal: validate the **Docker → Amazon ECR → Amazon ECS Express Mode** chain.

## Layout

```
comtrade-app/
├── app/
│   ├── app.py                 # Streamlit application (status report)
│   ├── requirements.txt
│   └── .streamlit/config.toml # port 8501, listens on 0.0.0.0
├── Dockerfile                 # image pushed to ECR
├── .dockerignore
├── docker-compose.yml         # local development only
└── infra/
    ├── config.env             # resource names, region, CPU/memory
    ├── deploy.sh              # creates / updates all AWS resources
    └── teardown.sh            # deletes the resources (stops billing)
```

All commands below run from the `comtrade-app/` directory.

## 1. Run locally

```bash
docker compose up --build
# then open http://localhost:8501
```

The code is mounted into the container: editing `app/app.py` reloads the page
without a rebuild.

## 2. Deploy to AWS (from WSL)

```bash
chmod +x infra/*.sh        # once
./infra/deploy.sh
```

The script creates, in order: the ECR repository, the image (build + push), the
IAM roles (execution + infrastructure), the CloudWatch log group, the ECS cluster
and the ECS Express Mode service. It waits for the service to be stable, then
prints the public URL (`https://<service>.ecs.<region>.on.aws`).

Re-run `./infra/deploy.sh` after a code change: it pushes a new image (unique
tag) and updates the service without downtime.

The region comes from `AWS_REGION`, else `aws configure`, else `us-east-1`.
To force one: `AWS_REGION=eu-west-3 ./infra/deploy.sh`.

## 3. Check

- The page shows "Platform: AWS ECS (Fargate)" and the "ECS task" block.
- The button in the "Interactive test" block increments the counter: WebSockets
  go through the ALB.
- Logs: `aws logs tail /ecs/comtrade-app --follow`

## 4. Delete everything

```bash
./infra/teardown.sh               # service + ALB, cluster, ECR, logs
./infra/teardown.sh --delete-iam  # same + IAM roles
```

> ⚠️ As long as the service exists, the ALB and the Fargate task are billed,
> even with no traffic. Run `teardown.sh` at the end of every work session.

## Prerequisites

- Recent AWS CLI v2 (must know `aws ecs create-express-gateway-service`)
- Docker Desktop with WSL integration enabled
- A default VPC in the region (otherwise set `SUBNETS` in `config.env`)

## Next steps

- DocumentDB connection: set `SUBNETS` / `SECURITY_GROUPS` (cluster VPC),
  pass the URI as a secret (Secrets Manager), add the CA certificate to the Dockerfile.
- Call to the AI Lambda (step 3): add a task role (`--task-role-arn`)
  with `lambda:InvokeFunction`.
