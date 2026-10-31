# Comtrade Anomaly Detection - Step 3: AI Generation & PDF Storage

## 🎯 Overview

This module implements **Step 3** of the Comtrade Anomaly Detection pipeline: **AI-powered anomaly analysis report generation and PDF storage**.

### Pipeline Context
```
Step 1: Data Ingestion & FOB/CIF Calculation (Luca)
    ↓ Anomaly detected → S3 trigger
Step 2: Streamlit UI (Aymen) ──→ User clicks "Analyze"
    ↓ Invoke
Step 3: AI Generation & PDF Storage (THIS MODULE)
    ├── Lambda AI: Bedrock LLM generates structured anomaly report
    ├── Lambda PDF: Weasyprint renders Markdown → PDF
    ├── S3: PDF storage (bdcs-g3-reports-pdf)
    └── DocumentDB: Metadata persistence (reports_metadata)
```

---

## 🏗️ Architecture & Technology Choices (30% of grade)

### Infrastructure & Compute

| Component | Technology | Justification |
|-----------|------------|---------------|
| **Lambda AI** | AWS Lambda (Python 3.11, Zip) | Serverless, auto-scaling, pay-per-invocation, low latency for LLM inference |
| **Lambda PDF** | AWS Lambda (Container Image, Python 3.11) | Weasyprint requires system libs (cairo, pango); Container provides OS-level deps |
| **DocumentDB** | Amazon DocumentDB (MongoDB-compatible) | Managed, MongoDB API compatible, TLS encryption, VPC-native |
| **S3** | Amazon S3 | Durable, scalable, presigned URLs for secure PDF download |
| **Bedrock** | Amazon Bedrock (Claude Haiku 4.5) | Managed LLM, no infrastructure, pay-per-token, enterprise-grade |

### Database & Storage

| Component | Choice | Justification |
|-----------|--------|---------------|
| **Metadata DB** | DocumentDB (MongoDB API) | JSON-native, flexible schema for anomaly metadata, TLS encryption, VPC-native |
| **Report Storage** | S3 | Cost-effective, durable, presigned URLs for secure time-limited access |
| **Certificate Management** | AWS TLS CA bundle | Downloaded at build time to `/opt/python/global-bundle.pem` |

### LLM & AI

| Aspect | Choice | Justification |
|--------|--------|---------------|
| **LLM Model** | Anthropic Claude Haiku 4.5 (Bedrock) | Fast, cost-effective, strong structured reasoning, multilingual |
| **Prompt Engineering** | Structured, mandatory analysis order | Ensures consistent, auditable analysis (Geopolitical → Logistics → Customs) |
| **Output Format** | Markdown → PDF (Weasyprint) | Professional rendering, tables, Unicode support |

### Infrastructure & Security

| Aspect | Choice | Justification |
|--------|--------|---------------|
| **Network** | VPC (vpc-07f1d9fb1fef102bf), private subnets us-east-1a/1b | DocumentDB requires VPC; Lambda in same VPC for private access |
| **Security Groups** | `bdcs-g3-lambda-sg` → `bdcs-g3-data-access` (port 27017) | Least-privilege: only Lambda SG can reach DocDB on 27017 |
| **IAM Roles** | Least-privilege per Lambda | `bdcs-g3-lambda-ai-role`: Bedrock + Lambda invoke; `bdcs-g3-lambda-pdf-role`: S3 + DocDB |
| **Secrets** | Env vars (DOCDB_PASSWORD) | Simple for MVP; can migrate to Secrets Manager |

### Naming Convention
All resources follow `bdcs-g3-*` prefix:
- `bdcs-g3-lambda-ai`, `bdcs-g3-lambda-pdf`, `bdcs-g3-pdf`, `bdcs-g3-reports-pdf`, `bdcs-g3-pymongo-layer`, `bdcs-g3-lambda-sg`

---

## 🔧 Pipeline Implementation (30%)

### Lambda AI (`bdcs-g3-lambda-ai`)
- **Runtime**: Python 3.11 (Zip)
- **Trigger**: Synchronous invocation from Streamlit UI
- **Process**:
  1. Receives anomaly event (anomaly_id, prices, gap%, context)
  2. Constructs structured prompt with mandatory analysis order
  3. Calls Bedrock (Claude Haiku 4.5) with maxTokens=3000, temperature=0.3
  4. Returns 202 with anomaly_id; async invokes Lambda PDF
- **Response**: `{"statusCode": 202, "body": {"status": "Processing", "anomaly_id": "..."}}`

### Lambda PDF (`bdcs-g3-lambda-pdf`)
- **Runtime**: Python 3.11 (Container Image, ECR)
- **Trigger**: Async invocation from Lambda AI
- **Process**:
  1. Receives `anomaly_data` + `ai_explanation` (Markdown)
  2. Converts Markdown → HTML → PDF (Weasyprint 52, custom CSS)
  3. Uploads PDF to S3 (`bdcs-g3-reports-pdf/report_{anomaly_id}.pdf`)
  5. Generates presigned URL (1h expiry)
  6. Inserts metadata into DocumentDB (`reports_metadata`)
  7. Returns presigned URL to caller (via async callback)
- **Error Handling**: On failure, writes `report_{anomaly_id}.error` to S3 with traceback

### DocumentDB Schema (`reports_metadata`)
```json
{
  "anomaly_id": "FRA_EGY_1001_2023-05",
  "s3_key": "report_FRA_EGY_1001_2023-05.pdf",
  "bucket": "bdcs-g3-reports-pdf",
  "presigned_url": "https://...",
  "status": "COMPLETED",
  "created_at": "2026-10-31T20:48:09.108Z",
  "anomaly_data": { ... },
  "ai_explanation": "# Anomaly Report...\n## 1. GEOPOLITICAL..."
}
```

---

## 📋 Requirements & Documentation (15%)

### Functional Requirements
| ID | Requirement | Status |
|----|-------------|--------|
| REQ-3.1 | Generate structured anomaly report via LLM | ✅ |
| REQ-3.2 | Convert Markdown → PDF with professional rendering | ✅ |
| REQ-3.3 | Store PDF in S3 with presigned URL access | ✅ |
| REQ-3.4 | Persist report metadata in DocumentDB | ✅ |
| REQ-3.5 | Error handling with S3 `.error` files | ✅ |
| REQ-3.6 | English report generation | ✅ |
| REQ-3.7 | Async processing (202 response) | ✅ |

### Non-Functional
| NFR | Target | Achieved |
|-----|--------|----------|
| Latency (Lambda AI) | < 30s | ~19s |
| Latency (Lambda PDF) | < 10s | ~6s |
| Availability | 99.9% | Serverless |
| Report Language | English | ✅ |
| PDF Quality | Professional (tables, Unicode) | ✅ Weasyprint 52 |

---

## 📊 Dashboard & AI Reports (15%)

### AI Report Structure (English)
1. **Main Diagnosis** - One sentence: primary cause + % gap explained
2. **Detailed Analysis** (Priority order):
   - 1. Geopolitical & Macroeconomic Context
   - 2. Exceptional Logistics Costs
   - 3. Customs Declaration Errors (ruled out)
3. **Confidence Level**: HIGH / MEDIUM / LOW
4. **Recommended Actions** for verification

### Report Features
- **Language**: English (professional trade terminology)
- **Format**: Markdown → PDF (tables, bold, italic, Unicode)
- **Tables**: Border-collapse, zebra striping, header styling
- **Length**: 2-3 A4 pages (~1500-2000 tokens)

---

## 🧪 Tests (10%)

### Test Structure
```
etape-3/
├── tests/
│   ├── __init__.py
│   ├── test_lambda_ai.py
│   ├── test_lambda_pdf.py
│   ├── test_docdb_integration.py
│   └── fixtures/
│       ├── mock_event.json
│       └── mock_explanation.md
├── test_requirements.txt
└── pytest.ini
```

---

## 📁 Project Structure

```
Cloudsys-project/
├── etape-3/
│   ├── lambda_ai.py           # Lambda AI (Zip)
│   ├── lambda_pdf.py          # Lambda PDF (Container)
│   ├── Dockerfile.lambda_pdf  # Container build
│   ├── requirements.txt       # boto3, markdown2, weasyprint==52.0, pymongo==4.8.0
│   ├── Dockerfile.lambda_pdf  # Container build
│   ├── fonts/                 # DejaVu Sans fonts
│   ├── mock_event.json        # Test event
│   ├── mock_explanation.md    # Sample LLM output
│   ├── build_zip.sh           # Build script
│   ├── lambda_pdf.zip         # Deployed container (cached)
│   └── tests/
│       ├── __init__.py
│       ├── test_lambda_ai.py
│       ├── test_lambda_pdf.py
│       ├── test_docdb_integration.py
│       └── fixtures/
├── comtrade-app/              # Step 2 (Aymen)
└── etape-1/                   # Step 1 (Luca)
```

---

## 🚀 Deployment

### Prerequisites
- AWS CLI configured (`aws configure`)
- Docker installed
- ECR repo: `bdcs-g3-lambda-pdf`
- DocumentDB cluster: `bdcs-g3-documentdb-cluster`

### Deploy Lambda PDF (Container)
```bash
cd etape-3
docker buildx build --platform linux/amd64 -f Dockerfile.lambda_pdf -t bdcs-g3-lambda-pdf .
docker tag bdcs-g3-lambda-pdf:latest 352909266144.dkr.ecr.us-east-1.amazonaws.com/bdcs-g3-lambda-pdf:latest
docker push 352909266144.dkr.ecr.us-east-1.amazonaws.com/bdcs-g3-lambda-pdf:latest
aws lambda update-function-code --function-name bdcs-g3-lambda-pdf --image-uri 352909266144.dkr.ecr.us-east-1.amazonaws.com/bdcs-g3-lambda-pdf:latest
```

### Deploy Lambda AI (Zip)
```bash
cd etape-3
mkdir -p package_ai && cp lambda_ai.py package_ai/
cd package_ai && zip -r ../lambda_ai.zip .
aws lambda update-function-code --function-name bdcs-g3-lambda-ai --zip-file fileb://lambda_ai.zip
```

### Environment Variables (Lambda PDF)
```bash
aws lambda update-function-configuration \
  --function-name bdcs-g3-lambda-pdf \
  --environment "Variables={
    S3_BUCKET_REPORTS=bdcs-g3-reports-pdf,
    DOCDB_HOST=bdcs-g3-documentdb-cluster.cluster-c9ackrdwcwiz.us-east-1.docdb.amazonaws.com,
    DOCDB_DATABASE=ingestion,
    DOCDB_COLLECTION=reports_metadata,
    DOCDB_USERNAME=clusteradmin,
    DOCDB_PASSWORD=myclusterpassword,
    DOCDB_TLS=true
  }"
```

### VPC Configuration
```bash
aws lambda update-function-configuration \
  --function-name bdcs-g3-lambda-pdf \
  --vpc-config "SubnetIds=subnet-082245938bf53dc2d,subnet-053910c8b65c20a77,SecurityGroupIds=sg-00b097d8044392d31"
```

---

## 🧪 Running Tests

```bash
cd etape-3
python -m venv .venv_test
source .venv_test/bin/activate
pip install -r test_requirements.txt
pytest tests/ -v
```

---

## 🔗 Integration Points

| From | To | Interface |
|------|-----|-----------|
| Streamlit UI (Aymen) | Lambda AI | `lambda_client.invoke(FunctionName='bdcs-g3-lambda-ai', InvocationType='RequestResponse')` |
| Lambda AI | Lambda PDF | Async `lambda:InvokeFunction` with payload `{anomaly_data, ai_explanation}` |
| Lambda PDF | S3 | `upload_file` + `generate_presigned_url` |
| Lambda PDF | DocumentDB | `pymongo` with TLS, `replicaSet=rs0`, `readPreference=secondaryPreferred` |

---

## 📝 API Contracts

### Lambda AI Input (from UI)
```json
{
  "anomaly_id": "FRA_EGY_1001_2023-05",
  "period": "2023-05",
  "reporter": "FRA",
  "partner": "EGY",
  "hs_code": "1001",
  "product_name": "Wheat",
  "fob_unit_price": 400.0,
  "cif_unit_price": 600.0,
  "gap_pct": 50.0,
  "anomaly_type": "Gap > 35%",
  "historical_context": "Historical average gap on this route: 12%."
}
```

### Lambda AI Output (async invoke to Lambda PDF)
```json
{
  "anomaly_data": { ... },  // Same as input
  "ai_explanation": "# Anomaly Report...\n## 1. GEOPOLITICAL..."
}
```

### Lambda PDF Output (DocDB `reports_metadata`)
```json
{
  "anomaly_id": "FRA_EGY_1001_2023-05",
  "s3_key": "report_FRA_EGY_1001_2023-05.pdf",
  "bucket": "bdcs-g3-reports-pdf",
  "presigned_url": "https://...",
  "status": "COMPLETED",
  "created_at": "2026-10-31T20:48:09.108Z",
  "anomaly_data": {...},
  "ai_explanation": "..."
}
```

---

## 🔐 Security

- **No secrets in code** - all via env vars
- **DocumentDB TLS** - mandatory, CA bundle from AWS trust store
- **VPC isolation** - Lambdas in private subnets, no internet access
- **Presigned URLs** - 1-hour expiry, no public S3 access
- **Least-privilege IAM** - per-function roles

---

## 📚 References

- [AWS Lambda Developer Guide](https://docs.aws.amazon.com/lambda/)
- [Amazon DocumentDB Developer Guide](https://docs.aws.amazon.com/documentdb/)
- [Amazon Bedrock User Guide](https://docs.aws.amazon.com/bedrock/)
- [Weasyprint Documentation](https://doc.courtbouillon.org/weasyprint/)
- [Project Architecture Diagram](../architecture.md)

---

*Last updated: 2026-10-31 | Team: Zekria (Step 3 - AI/PDF)*  
*Course: BDCS-G3 - Comtrade Anomaly Detection Pipeline*