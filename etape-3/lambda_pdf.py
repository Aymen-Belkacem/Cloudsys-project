import boto3
import os
import json
import tempfile
from datetime import datetime, timezone
import markdown2
from weasyprint import HTML, CSS

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
    explanation = event.get("ai_explanation", "Aucune explication fournie.")
    anomaly_id = anomaly.get("anomaly_id", "unknown_id")

    file_name = f"report_{anomaly_id}.pdf"
    local_path = f"/tmp/{file_name}"

    markdown_to_pdf(explanation, local_path)
    print(f"PDF genere : {local_path}")

    presigned_url = ""
    if not local_test:
        s3_client = boto3.client("s3", region_name=region)
        s3_client.upload_file(local_path, bucket_name, file_name)
        print(f"PDF uploade sur S3 : s3://{bucket_name}/{file_name}")

        presigned_url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket_name, "Key": file_name},
            ExpiresIn=3600
        )
    else:
        presigned_url = f"file://{local_path}"
        print(f"Mode local - PDF dispo ici : {local_path}")

    metadata_doc = {
        "anomaly_id": anomaly_id,
        "s3_key": file_name,
        "bucket": bucket_name,
        "presigned_url": presigned_url,
        "status": "COMPLETED",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    print("Metadonnees pour DocumentDB :", json.dumps(metadata_doc, ensure_ascii=False))

    return {
        "statusCode": 200,
        "presigned_url": presigned_url
    }

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
        explanation = "Explication de test - fichier mock_explanation.txt manquant."
    
    test_event = {
        "anomaly_data": anomaly,
        "ai_explanation": explanation
    }
    lambda_handler(test_event, None)