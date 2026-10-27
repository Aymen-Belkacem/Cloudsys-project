# CloudSys project – Comtrade trade anomalies

AWS architecture that detects trade anomalies in **UN Comtrade** data
(FOB/CIF mismatches between reporters and partners), in 3 steps:

1. **Ingestion and computation** → results in Amazon DocumentDB (`trades_matrix`).
2. **Streamlit application** → [`comtrade-app/`](comtrade-app/README.md).
3. **AI analysis and PDF reports** (AWS Lambda + Bedrock, S3).

## Workspace layout

| Path | Content |
|------|---------|
| `comtrade-app/` | Step 2: the deployed Streamlit app (Docker, ECR, ECS Express Mode). See its [README](comtrade-app/README.md). |
| `Doc/` | Project documentation: architecture, description, presentation, project list. |
| `data/` | Sample bilateral trade data (`Bilateral_data.csv` / `.xlsx`) and its description. |
| `pyproject.toml`, `.python-version` | Local Python (uv) workspace settings, not part of the deployed app. |
