# Etape 3 — Lambda PDF Generator with S3 Deduplication

## 1. Overview

The `etape-3` directory contains the **Lambda PDF Generator** component of the CloudSys project. This AWS Lambda function:

- **Generates PDF reports** from AI explanations using WeasyPrint (HTML/CSS → PDF)
- **Uploads PDFs to S3** (`bdcs-g3-reports-pdf` bucket) with presigned URLs
- **Stores metadata in DocumentDB** (`reports_metadata` collection)
- **Verifies PDF existence via S3 HEAD request** (deduplication — temporarily disabled due to IAM propagation)
- **Handles errors gracefully** with `.error` files written to S3

**Pipeline**: `Lambda AI` → `Lambda PDF` → `S3` → `DocumentDB` → Streamlit app displays presigned URL

---

## 2. Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Lambda AI  │────▶│   Lambda PDF     │────▶│     S3          │
│   (async)   │     │   (Docker image) │     │  (reports-pdf)  │
└─────────────┘     └──────────────────┘     └─────┬───────────┘
                                                   │
                              ┌────────────────────┘
                              ▼
                    ┌─────────────────┐
                    │   DocumentDB    │
                    │reports_metadata │
                    └─────────────────┘
```

**Flow**:
1. Lambda AI generates an AI explanation for a trade anomaly
2. Lambda AI invokes Lambda PDF asynchronously with the anomaly data + explanation
3. Lambda PDF renders HTML/CSS → PDF via WeasyPrint
4. PDF uploaded to S3, presigned URL generated (expires in 1 hour)
5. Metadata (anomaly_id, s3_key, presigned_url, status, etc.) inserted into DocumentDB
6. Streamlit app polls S3 for the PDF and displays it to the user

---

## 3. File Structure

| Path | Description |
|------|-------------|
| `lambda_pdf.py` | **Main Lambda handler** — PDF generation, S3 upload, DocDB insert, deduplication check |
| `lambda_ai.py` | Lambda AI handler — anomaly analysis, generates English explanation |
| `Dockerfile.lambda_pdf` | Docker build for Lambda PDF (Python 3.11, WeasyPrint, PyMongo, fonts, certs) |
| `requirements.txt` | Production dependencies (pymongo, weasyprint, markdown2, boto3) |
| `test_requirements.txt` | Test dependencies (pytest, moto, etc.) |
| `pytest.ini` | Pytest configuration |
| `README.md` | This file |
| `iam_roles.py` | Utility script for IAM role/policy management |
| `mock_event.json` | Mock event for local testing |
| `mock_explanation.txt` | Mock AI explanation for local testing |
| `fonts/` | DejaVu Sans fonts (DejaVuSans.ttf, DejaVuSans-Bold.ttf, DejaVuSansMono.ttf) |
| `certs/` | DocumentDB TLS certificates (global-bundle.pem) |
| `tests/` | Test suite (18 passed, 3 skipped) |
| `tests/test_lambda_pdf.py` | Tests for PDF Lambda |
| `tests/test_lambda_ai.py` | Tests for AI Lambda |
| `tests/test_docdb_integration.py` | Tests for DocumentDB connection |
| `tests/fixtures/` | Test fixtures (mock_event.json, mock_explanation.md) |
| `build_zip.sh` | Legacy zip build script (deprecated, Docker used instead) |

---

## 4. Development Process

### Phase 1: Initial Implementation
- Created `lambda_pdf.py` with WeasyPrint-based PDF generation
- Set up Docker container based on `public.ecr.aws/lambda/python:3.11`
- Installed system dependencies (cairo, pango, gdk-pixbuf2, freetype, fontconfig, gcc, gcc-c++, make, libjpeg-devel, zlib-devel, freetype-devel)

### Phase 2: DocumentDB Integration
- Added PyMongo with **4 connection strategies** with fallback:
  1. Cluster endpoint with replicaSet
  2. Cluster endpoint without replicaSet
  3. Instance endpoint (directConnection)
  4. Reader endpoint (secondaryPreferred)
- Added TLS certificate download in Dockerfile (`global-bundle.pem` from AWS truststore)

### Phase 3: S3 Deduplication
- Added `check_pdf_exists()` function using S3 `head_object`
- Returns existing presigned URL if PDF already exists (avoids regeneration, saves cost and time)
- **Blocked**: IAM `s3:GetObject` permission propagation (waiting 1h+, temporarily disabled in code)

### Phase 4: Error Handling
- Added `.error` file generation in S3 for failed PDF generations
- Error files contain anomaly_id, error message, traceback, UTC timestamp

### Phase 5: JSON Serialization Fix
- Added custom `JSONEncoder` class to handle MongoDB `ObjectId` and Python `datetime` serialization

### Phase 6: Testing
- Created test suite with pytest
- Tests cover: PDF generation, S3 upload, DocDB connection, error handling, JSON serialization
- Result: 18 passed, 3 skipped

### Phase 7: Deployment
- Built Docker image on `linux/amd64` platform
- Pushed to ECR (`352909266144.dkr.ecr.us-east-1.amazonaws.com/bdcs-g3-lambda-pdf:latest`)
- Updated Lambda function code via `aws lambda update-function-code`

---

## 5. Features Implemented

### 5.1 PDF Generation
- HTML/CSS rendering via WeasyPrint
- DejaVu Sans font family (regular, bold, monospace) embedded in container
- A4 page size, 2cm margins
- Styled tables, headers, code blocks, blockquotes, horizontal rules
- Markdown-to-HTML conversion via markdown2 (tables, fenced-code-blocks, header-ids, footnotes, strike, task_list)

### 5.2 S3 Operations
- Upload PDF to `bdcs-g3-reports-pdf` bucket
- Generate presigned URLs (1-hour expiration via `generate_presigned_url`)
- **Deduplication**: Check existing PDF via `head_object` (disabled — see section 7)
- Write `.error` files on failure for debugging

### 5.3 DocumentDB
- Multi-strategy connection with automatic fallback loop
- Metadata insertion: anomaly_id, s3_key, bucket, presigned_url, status, created_at, anomaly_data, ai_explanation
- Non-blocking insert (warning logged on failure, doesn't fail Lambda execution)

### 5.4 Error Handling
- Try/except around entire `lambda_handler`
- `.error` file written to S3 on any failure
- Error details: anomaly_id, error message, full traceback, UTC timestamp

### 5.5 Local Testing
- `LOCAL_TEST=true` environment variable skips S3/DocumentDB calls
- Writes PDF to `/tmp/` instead of S3
- Mock event (`mock_event.json`) and explanation (`mock_explanation.txt`) files provided

---

## 6. Problems Encountered & Solutions

### 6.1 IAM Permission: `s3:GetObject` Not Propagated ⚠️ **CURRENTLY BLOCKED**
- **Problem**: `head_object` returns `403 Forbidden` because Lambda IAM role lacked `s3:GetObject`
- **Policy updated**: `S3WriteReportsPolicy` now includes `["s3:PutObject", "s3:GetObject"]` on `arn:aws:s3:::bdcs-g3-reports-pdf/*`
- **Status**: Policy verified correct via `aws iam get-role-policy`, but propagation to Lambda endpoints still pending (1h+ elapsed)
- **Solution**: Temporarily disabled deduplication in `lambda_pdf.py` (deduplication block commented out around lines 144-158)
- **Reactivation**: Uncomment the `check_pdf_exists` block once IAM propagation completes

### 6.2 DocumentDB Connection Issues
- **Problem**: Cluster endpoint sometimes unreachable, DNS resolution failures, TLS handshake errors
- **Solution**: 4 connection strategies with fallback loop, 5-second server selection timeout, multiple endpoint types (cluster, instance, reader)

### 6.3 Font Rendering in WeasyPrint
- **Problem**: `@font-face` src paths invalid in Lambda container (file:// URLs not resolved)
- **Solution**: Embedded DejaVu fonts in Docker image at `/var/task/fonts/`, referenced via `file:///var/task/fonts/`

### 6.4 JSON Serialization of ObjectId/datetime
- **Problem**: `json.dumps` fails on MongoDB `ObjectId` and Python `datetime` objects
- **Solution**: Custom `JSONEncoder` class with `default()` method handling both types, exposed via `json_dumps()` helper

### 6.5 Docker Build Cache
- **Problem**: Slow rebuilds due to uncached system packages (yum install)
- **Solution**: Docker layer caching for `yum install` and `pip install` steps — subsequent builds reuse cached layers

---

## 7. Current Status & Known Issues

### ✅ Working
- PDF generation with WeasyPrint
- S3 upload + presigned URL generation
- DocumentDB metadata insertion (multi-strategy connection)
- Error handling with `.error` files
- JSON serialization fix
- Local testing mode (`LOCAL_TEST=true`)
- Test suite: 18 passed, 3 skipped

### ⏳ Blocked / Pending
- **S3 Deduplication**: `head_object` returns 403 — waiting for IAM `s3:GetObject` propagation
  - **Fix**: Uncomment `check_pdf_exists` block in `lambda_pdf.py` (lines 144-158)
  - **Policy**: Already updated in IAM, waiting for AWS propagation (can take 15-60+ minutes)

### 🔄 Temporary Behavior (without deduplication)
- Every invocation generates a new PDF even if one already exists for the same anomaly_id
- No functional impact, just minor S3 storage duplication
- Presigned URL still returned correctly for the newly generated PDF

---

## 8. Deployment

### 8.1 Prerequisites
- AWS CLI configured with appropriate credentials
- Docker installed and running
- ECR repository `352909266144.dkr.ecr.us-east-1.amazonaws.com/bdcs-g3-lambda-pdf` exists

### 8.2 Build & Push Docker Image

```bash
cd etape-3

# Build Docker image for linux/amd64
docker buildx build --platform linux/amd64 -f Dockerfile.lambda_pdf \
  -t bdcs-g3-lambda-pdf . --output type=docker,dest=/tmp/lambda-image.tar

# Load into local Docker
docker load -i /tmp/lambda-image.tar

# Tag for ECR
docker tag bdcs-g3-lambda-pdf:latest \
  352909266144.dkr.ecr.us-east-1.amazonaws.com/bdcs-g3-lambda-pdf:latest

# Authenticate with ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS \
  --password-stdin 352909266144.dkr.ecr.us-east-1.amazonaws.com

# Push to ECR
docker push 352909266144.dkr.ecr.us-east-1.amazonaws.com/bdcs-g3-lambda-pdf:latest
```

### 8.3 Update Lambda Function

```bash
aws lambda update-function-code \
  --function-name bdcs-g3-lambda-pdf \
  --image-uri 352909266144.dkr.ecr.us-east-1.amazonaws.com/bdcs-g3-lambda-pdf:latest \
  --region us-east-1

# Wait for activation
aws lambda wait function-active-v2 --function-name bdcs-g3-lambda-pdf --region us-east-1
```

### 8.4 Environment Variables (Lambda)

| Variable | Value | Description |
|----------|-------|-------------|
| `AWS_REGION` | `us-east-1` | AWS region |
| `S3_BUCKET_REPORTS` | `bdcs-g3-reports-pdf` | S3 bucket for PDF storage |
| `DOCDB_HOST` | `bdcs-g3-documentdb-cluster.cluster-c9ackrdwcwiz.us-east-1.docdb.amazonaws.com` | DocumentDB cluster endpoint |
| `DOCDB_USERNAME` | `clusteradmin` | DocumentDB username |
| `DOCDB_PASSWORD` | `myclusterpassword` | DocumentDB password |
| `DOCDB_DATABASE` | `ingestion` | DocumentDB database name |
| `DOCDB_COLLECTION` | `reports_metadata` | DocumentDB collection name |
| `DOCDB_TLS` | `true` | Enable TLS for DocumentDB |
| `Timeout` | `60` | Lambda timeout in seconds |
| `MemorySize` | `1024` | Lambda memory in MB |

---

## 9. Maintenance Guide

### 9.1 Reactivate S3 Deduplication

When IAM `s3:GetObject` propagation completes, uncomment the deduplication block in `lambda_pdf.py` (around lines 144-158):

```python
# Check if PDF already exists in S3 (deduplication)
s3_key = file_name
if not local_test:
    s3_client = boto3.client("s3", region_name=region)
    if check_pdf_exists(s3_client, bucket_name, s3_key):
        print(f"PDF already exists for {anomaly_id}, returning existing presigned URL")
        presigned_url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket_name, "Key": file_name},
            ExpiresIn=3600
        )
        return {
            "statusCode": 200,
            "presigned_url": presigned_url
        }
```

### 9.2 Run Tests Locally

```bash
cd etape-3
pip install -r test_requirements.txt
pytest tests/ -v
```

### 9.3 Local Test (without AWS)

```bash
cd etape-3
LOCAL_TEST=true python lambda_pdf.py
```

This reads `mock_event.json` and `mock_explanation.txt`, generates a PDF in `/tmp/`, and skips S3/DocumentDB.

### 9.4 Check Lambda Logs

```bash
aws logs tail /aws/lambda/bdcs-g3-lambda-pdf --since 5m --region us-east-1
```

### 9.5 Verify IAM Policy

```bash
aws iam get-role-policy \
  --role-name bdcs-g3-lambda-pdf-role \
  --policy-name S3WriteReportsPolicy \
  --region us-east-1
```

Expected output should include both `s3:PutObject` and `s3:GetObject` in the Action list.

### 9.6 Verify S3 Bucket Contents

```bash
aws s3 ls s3://bdcs-g3-reports-pdf/ --region us-east-1
```

Look for `report_<anomaly_id>.pdf` files and any `report_<anomaly_id>.error` files.

---

## 10. Contributors

- **Sormasor** — Lambda PDF implementation, Docker containerization, S3/DocumentDB integration, deduplication logic, error handling, testing, deployment
- **Aymen** — Branch `1-bloc-application` (Streamlit frontend, async report invocation flow, S3 fetch/display)

---

## 11. License

Academic project — HES-SO TSM CloudSys.

---

*Last updated: November 1, 2026*