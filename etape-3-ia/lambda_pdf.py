import boto3
import os
import json
import tempfile
import traceback
from datetime import datetime, timezone
from bson import ObjectId
import markdown2
from weasyprint import HTML, CSS
import pymongo


class JSONEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle ObjectId and datetime."""
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def json_dumps(obj, **kwargs):
    """JSON dumps with custom encoder."""
    return json.dumps(obj, cls=JSONEncoder, **kwargs)

CSS_STYLES = CSS(string="""
    @page { size: A4; margin: 2cm; }
    body { font-family: "DejaVu Sans", sans-serif; font-size: 10pt; line-height: 1.45; color: #1a1a2e; }
    h1 { font-size: 18pt; color: #1a1a2e; border-bottom: 2px solid #FF9900; padding-bottom: 4px; margin-top: 0; }
    h2 { font-size: 14pt; color: #1a1a2e; margin-top: 18px; margin-bottom: 8px; border-left: 3px solid #FF9900; padding-left: 8px; }
    h3 { font-size: 11pt; color: #333; margin-top: 12px; margin-bottom: 6px; }
    h4 { font-size: 10pt; color: #444; margin-top: 10px; margin-bottom: 4px; }
    p { margin: 6px 0; }
    strong { font-weight: bold; color: #1a1a2e; }
    em { font-style: italic; }
    table { width: 100%; border-collapse: collapse; margin: 10px 0; font-size: 9pt; page-break-inside: avoid; }
    th, td { border: 1px solid #ddd; padding: 5px 7px; text-align: left; vertical-align: top; }
    th { background: #f5f5f5; font-weight: bold; color: #1a1a2e; }
    tr:nth-child(even) td { background: #fafafa; }
    code { background: #f0f0f0; padding: 1px 4px; font-family: "DejaVu Sans Mono", monospace; font-size: 9pt; border-radius: 3px; }
    pre { background: #f8f8f8; padding: 10px; overflow: auto; border: 1px solid #eee; border-radius: 4px; font-size: 8.5pt; }
    pre code { background: none; padding: 0; }
    blockquote { border-left: 3px solid #FF9900; padding-left: 12px; margin: 10px 0; color: #555; font-style: italic; }
    hr { border: none; border-top: 1px solid #eee; margin: 16px 0; }
    ul, ol { margin: 6px 0 6px 20px; }
    li { margin: 3px 0; }
    .header-info { background: #f8f9fa; border: 1px solid #eee; border-radius: 4px; padding: 10px; margin-bottom: 16px; font-size: 9.5pt; }
    .header-info strong { display: inline-block; width: 140px; color: #333; }
""")

FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")

def markdown_to_pdf(markdown_text, output_path):
    html_body = markdown2.markdown(
        markdown_text,
        extras=["tables", "fenced-code-blocks", "header-ids", "footnotes", "strike", "task_list"]
    )
    
    html_full = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @font-face {{
                font-family: "DejaVu Sans";
                src: url("file://{FONT_DIR}/DejaVuSans.ttf");
            }}
            @font-face {{
                font-family: "DejaVu Sans";
                src: url("file://{FONT_DIR}/DejaVuSans-Bold.ttf");
                font-weight: bold;
            }}
            @font-face {{
                font-family: "DejaVu Sans Mono";
                src: url("file://{FONT_DIR}/DejaVuSansMono.ttf");
            }}
        </style>
    </head>
    <body>
        {html_body}
    </body>
    </html>
    """
    
    HTML(string=html_full, base_url=FONT_DIR).write_pdf(output_path, stylesheets=[CSS_STYLES])

def lambda_handler(event, context):
    region = os.environ.get("AWS_REGION", "us-east-1")
    bucket_name = os.environ.get("S3_BUCKET_REPORTS", "reports-pdf")
    local_test = os.environ.get("LOCAL_TEST") == "true"
    
    anomaly = event.get("anomaly_data", {})
    explanation = event.get("ai_explanation", "No explanation provided.")
    anomaly_id = anomaly.get("anomaly_id", "unknown_id")
    
    file_name = f"report_{anomaly_id}.pdf"
    local_path = f"/tmp/{file_name}"
    error_key = f"report_{anomaly_id}.error"
    s3_key = file_name

    def write_error_to_s3(error_msg, traceback_str):
        """Write error details to S3 as .error file"""
        if not local_test:
            try:
                s3_client = boto3.client("s3", region_name=region)
                error_content = {
                    "anomaly_id": anomaly_id,
                    "error": error_msg,
                    "traceback": traceback_str,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                s3_client.put_object(
                    Bucket=bucket_name,
                    Key=error_key,
                    Body=json_dumps(error_content, ensure_ascii=False).encode('utf-8'),
                    ContentType='application/json'
                )
                print(f"Error file written to S3: {error_key}")
            except Exception as e:
                print(f"Failed to write error file to S3: {e}")

    def check_pdf_exists(s3_client, bucket, key):
        """Check if PDF already exists in S3 using HEAD request (fast, no download)."""
        try:
            s3_client.head_object(Bucket=bucket_name, Key=s3_key)
            return True
        except Exception as e:
            if hasattr(e, 'response') and e.response['Error']['Code'] == '404':
                return False
            raise

    try:
        anomaly = event.get("anomaly_data", {})
        explanation = event.get("ai_explanation", "No explanation provided.")
        anomaly_id = anomaly.get("anomaly_id", "unknown_id")
        
        file_name = f"report_{anomaly_id}.pdf"
        local_path = f"/tmp/{file_name}"
        error_key = f"report_{anomaly_id}.error"
        s3_key = file_name

        # Check if PDF already exists in S3 (deduplication) - DISABLED temporarily due to IAM propagation
        # s3_key = file_name
        # if not local_test:
        #     s3_client = boto3.client("s3", region_name=region)
        #     if check_pdf_exists(s3_client, bucket_name, s3_key):
        #         print(f"PDF already exists for {anomaly_id}, returning existing presigned URL")
        #         presigned_url = s3_client.generate_presigned_url(
        #             "get_object",
        #             Params={"Bucket": bucket_name, "Key": file_name},
        #             ExpiresIn=3600
        #         )
        #         return {
        #             "statusCode": 200,
        #             "presigned_url": presigned_url
        #         }

        markdown_to_pdf(explanation, local_path)
        print(f"PDF generated: {local_path}")

        presigned_url = ""
        if not local_test:
            s3_client = boto3.client("s3", region_name=region)
            s3_client.upload_file(local_path, bucket_name, file_name)
            print(f"PDF uploaded to S3: s3://{bucket_name}/{file_name}")

            presigned_url = s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket_name, "Key": file_name},
                ExpiresIn=3600
            )
        else:
            presigned_url = f"file://{local_path}"
            print(f"Local mode - PDF available here: {local_path}")

        # Insert metadata into DocumentDB
        metadata_doc = {
            "anomaly_id": anomaly_id,
            "s3_key": file_name,
            "bucket": bucket_name,
            "presigned_url": presigned_url,
            "status": "COMPLETED",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "anomaly_data": anomaly,
            "ai_explanation": explanation
        }

        # Insert into DocumentDB (non-blocking, best effort)
        if not local_test:
            try:
                # Use environment variables
                docdb_host = os.environ.get("DOCDB_HOST", "bdcs-g3-documentdb-cluster.cluster-c9ackrdwcwiz.us-east-1.docdb.amazonaws.com")
                docdb_username = os.environ.get("DOCDB_USERNAME")
                docdb_password = os.environ.get("DOCDB_PASSWORD")
                docdb_database = os.environ.get("DOCDB_DATABASE", "ingestion")
                docdb_collection = os.environ.get("DOCDB_COLLECTION", "reports_metadata")
                docdb_tls = os.environ.get("DOCDB_TLS", "true").lower() == "true"

                if not docdb_username or not docdb_password:
                    raise ValueError("DOCDB_USERNAME and DOCDB_PASSWORD environment variables are required")

                # Build MongoDB URI
                docdb_uri = f"mongodb://{docdb_username}:{docdb_password}@{docdb_host}:27017"

                # Certificate from Dockerfile
                ca_file = "/opt/python/global-bundle.pem"

                # DocumentDB connection options - try multiple strategies
                # Strategy 1: Standard DocumentDB options
                documentdb_options = {
                    "tls": docdb_tls,
                    "tlsCAFile": "/opt/python/global-bundle.pem",
                    "replicaSet": "rs0",
                    "readPreference": "secondaryPreferred",
                    "retryWrites": False,
                }

                # Try multiple connection strategies
                connection_strategies = [
                    # Strategy 1: Standard with replicaSet
                    {
                        "uri": docdb_uri,
                        "options": documentdb_options,
                        "name": "cluster_endpoint_with_replicaset"
                    },
                    # Strategy 2: Cluster endpoint without replicaSet
                    {
                        "uri": docdb_uri,
                        "options": {**documentdb_options, "replicaSet": None},
                        "name": "cluster_endpoint_no_replicaset"
                    },
                    # Strategy 3: Instance endpoint directly
                    {
                        "uri": f"mongodb://{docdb_username}:{docdb_password}@bdcs-g3-documentdb.c9ackrdwcwiz.us-east-1.docdb.amazonaws.com:27017",
                        "options": {**documentdb_options, "replicaSet": None, "directConnection": True},
                        "name": "instance_endpoint_direct"
                    },
                    # Strategy 4: Reader endpoint
                    {
                        "uri": f"mongodb://{docdb_username}:{docdb_password}@bdcs-g3-documentdb-cluster.cluster-ro-c9ackrdwcwiz.us-east-1.docdb.amazonaws.com:27017",
                        "options": {**documentdb_options, "replicaSet": None, "readPreference": "secondaryPreferred"},
                        "name": "reader_endpoint"
                    },
                ]

                client = None
                for strategy in connection_strategies:
                    try:
                        opts = strategy["options"].copy()
                        # Remove None values
                        opts = {k: v for k, v in opts.items() if v is not None}
                        print(f"Trying {strategy['name']}...")
                        client = pymongo.MongoClient(
                            strategy["uri"],
                            serverSelectionTimeoutMS=5000,
                            **(opts if docdb_tls else {})
                        )
                        # Test the connection
                        client.admin.command('ping')
                        print(f"Successfully connected using {strategy['name']}")
                        break
                    except Exception as e:
                        print(f"Failed {strategy['name']}: {e}")
                        if client:
                            client.close()
                        client = None
                        continue
                
                if client is None:
                    raise Exception("All connection strategies failed")

                db = client[os.environ.get("DOCDB_DATABASE", "ingestion")]
                db[os.environ.get("DOCDB_COLLECTION", "reports_metadata")].insert_one(metadata_doc)
                print(f"Metadata inserted into DocumentDB for {anomaly_id}")
            except Exception as e:
                print(f"Warning: Failed to insert metadata into DocumentDB: {e}")
                # Don't fail the Lambda if DocDB insert fails

        print("Metadata for DocumentDB:", json_dumps(metadata_doc, ensure_ascii=False))

        return {
            "statusCode": 200,
            "presigned_url": presigned_url
        }

    except Exception as e:
        error_msg = str(e)
        traceback_str = traceback.format_exc()
        print(f"Error processing PDF generation: {error_msg}")
        print(traceback_str)
        write_error_to_s3(error_msg, traceback_str)
        raise

if __name__ == "__main__":
    os.environ["LOCAL_TEST"] = "true"
    os.environ["AWS_REGION"] = "us-east-1"
    
    with open("mock_event.json", "r") as f:
        anomaly = json.load(f)
    
    explanation_file = "mock_explanation.txt"
    if os.path.exists(explanation_file):
        with open(explanation_file, "r") as f:
            explanation = f.read()
    else:
        explanation = "Test explanation - mock_explanation.txt file missing."
    
    test_event = {
        "anomaly_data": anomaly,
        "ai_explanation": explanation
    }
    lambda_handler(test_event, None)




if __name__ == "__main__":
    os.environ["LOCAL_TEST"] = "true"
    os.environ["AWS_REGION"] = "us-east-1"
    
    with open("mock_event.json", "r") as f:
        anomaly = json.load(f)
    
    explanation_file = "mock_explanation.txt"
    if os.path.exists(explanation_file):
        with open(explanation_file, "r") as f:
            explanation = f.read()
    else:
        explanation = "Test explanation - mock_explanation.txt file missing."
    
    test_event = {
        "anomaly_data": anomaly,
        "ai_explanation": explanation
    }
    lambda_handler(test_event, None)




if __name__ == "__main__":
    os.environ["LOCAL_TEST"] = "true"
    os.environ["AWS_REGION"] = "us-east-1"
    
    with open("mock_event.json", "r") as f:
        anomaly = json.load(f)
    
    explanation_file = "mock_explanation.txt"
    if os.path.exists(explanation_file):
        with open(explanation_file, "r") as f:
            explanation = f.read()
    else:
        explanation = "Test explanation - mock_explanation.txt file missing."
    
    test_event = {
        "anomaly_data": anomaly,
        "ai_explanation": explanation
    }
    lambda_handler(test_event, None)