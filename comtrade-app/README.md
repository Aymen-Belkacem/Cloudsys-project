# Comtrade Anomalies – Step 2: Streamlit application

The app connects to Amazon DocumentDB and has two pages:

- **Trade anomalies**: pick an exporter, a product and a frequency (yearly,
  quarterly or monthly), then read the heatmap of its top 10 partner countries.
  White = consistent, red = flagged, grey = no mirror data. A red cell shows the
  FOB, CIF and gap. Its "Analyze anomaly" button is a stub for now.
- **Status report**: version, environment, ECS task, database connection,
  collections and a sample document. Useful for debugging.

## Layout

```
comtrade-app/
├── app/
│   ├── app.py                 # entry point, page navigation
│   ├── matrix_page.py         # heatmap page
│   ├── matrix.py              # mirror matching and anomaly rule (no Streamlit)
│   ├── countries.py           # country names, Comtrade aggregates
│   ├── status_page.py         # status report
│   ├── db.py                  # DocumentDB client and queries
│   ├── requirements.txt
│   └── .streamlit/config.toml # port 8501, listens on 0.0.0.0
├── Dockerfile                 # image pushed to ECR
├── .dockerignore
├── docker-compose.yml         # local development only (app + MongoDB)
├── local/seed.py              # loads data/Bilateral_data.csv into the local MongoDB
├── tests/                     # unit tests of the anomaly computation
├── pytest.ini
└── infra/
    ├── config.env             # resource names, region, CPU/memory, network, DocumentDB
    ├── deploy.sh              # creates / updates all AWS resources
    └── teardown.sh            # deletes the resources (stops billing)
```

All commands below run from the `comtrade-app/` directory.

## 1. Run locally

```bash
docker compose up --build
# then open http://localhost:8501
```

The code is mounted into the container: editing a file in `app/` reloads the
page without a rebuild.

A MongoDB container stands in for DocumentDB. The `seed` service loads
`data/Bilateral_data.csv` once, into a Docker volume. To reload it:

```bash
docker compose down -v
```

## Run the tests

```bash
uv run --no-project --with pandas --with pytest pytest
```

## 2. Deploy to AWS (from WSL)

```bash
chmod +x infra/*.sh        # once
./infra/deploy.sh
```

The first run asks for the DocumentDB password (hidden input) and stores it in
Secrets Manager. Never put it in `config.env`: this file is committed.

The script then creates, in order: the ECR repository, the image (build + push),
the IAM roles (execution + infrastructure), the CloudWatch log group, the app
security group and its rule on the DocumentDB security group, the ECS cluster and
the ECS Express Mode service. It waits for the service to be stable, then prints
the public URL (`https://<service>.ecs.<region>.on.aws`).

Re-run `./infra/deploy.sh` after a code change: it pushes a new image (unique
tag) and updates the service without downtime.

The region comes from `AWS_REGION`, else `aws configure`, else `us-east-1`.
To force one: `AWS_REGION=eu-west-3 ./infra/deploy.sh`.

## 3. Check

- The Status report page shows "Platform: AWS ECS (Fargate)" and the "ECS task" block.
- Its "Database" block shows "Connected", the collections and a sample document.
- The button in the "Interactive test" block increments the counter: WebSockets
  go through the ALB.
- Logs: `aws logs tail /ecs/bdcs-g3-streamlit --follow`

## 4. Delete everything

```bash
./infra/teardown.sh               # service, cluster, ECR, logs
./infra/teardown.sh --delete-iam  # same + IAM roles
./infra/teardown.sh --delete-db-access  # same + app security group, its rule, password secret
```

> WARNING!! As long as the service exists, the Fargate task is billed, even with no
> traffic. Run `teardown.sh` at the end of every work session.
>
> The ALB is managed by ECS and shared by every Express service on the same
> network: it stays in place as long as another service uses it. Do not delete it.

All resources are named `bdcs-g3-<name>` (see `NAME_PREFIX` in `infra/config.env`).

## Prerequisites

- Recent AWS CLI v2 (must know `aws ecs create-express-gateway-service`)
- Docker Desktop with WSL integration enabled
- The DocumentDB password

## Next steps

- Call to the AI Lambda (step 3) from the "Analyze anomaly" button: add a task
  role (`--task-role-arn`) with `lambda:InvokeFunction`.
