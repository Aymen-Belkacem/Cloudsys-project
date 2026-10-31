import boto3
import json
import os

def lambda_handler(event, context):
    region = os.environ.get("AWS_REGION", "us-east-1")
    model_id = os.environ.get("BEDROCK_CHAT_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
    pdf_lambda_name = os.environ.get("PDF_LAMBDA_NAME", "Lambda_PDF")

    bedrock = boto3.client("bedrock-runtime", region_name=region)
    lambda_client = boto3.client("lambda", region_name=region)

    prompt = f"""You are a senior expert in international agricultural commodity trading at DNEXT.
An anomaly has been detected on a bilateral trade flow:
- Product: {event.get('hs_code')} ({event.get('product_name')})
- Exporter: {event.get('reporter')} | Importer: {event.get('partner')}
- Period: {event.get('period')}
- FOB Unit Price (Export): {event.get('fob_unit_price')} USD/t
- CIF Unit Price (Import): {event.get('cif_unit_price')} USD/t
- Gap: {event.get('gap_pct')}% (Rule triggered: {event.get('anomaly_type')})
- Historical Context: {event.get('historical_context', 'N/A')}

Write a structured, professional report in English explaining this anomaly.

**CRITICAL INSTRUCTION - MANDATORY ANALYSIS ORDER:**
You MUST analyze causes in the following order, stopping as soon as a cause sufficiently explains the anomaly:

### 1. GEOPOLITICAL & MACROECONOMIC CONTEXT OF THE PERIOD (ANALYZE FIRST)
Explicitly identify ALL major events known during {event.get('period')} impacting:
- The product **{event.get('product_name')}** (HS code {event.get('hs_code')})
- The trade route **{event.get('reporter')} -> {event.get('partner')}**
- The production/transit regions concerned (Black Sea, Mediterranean, etc.)

Cite specifically: active conflicts, sanctions, blockades, international agreements (e.g., Black Sea Grain Initiative), port disruptions, embargoes. If a major event exists, **it is the primary cause** -- quantify its estimated impact on the gap (insurance premiums, rerouting, supply/demand tension).

### 2. EXCEPTIONAL LOGISTICS COSTS (FREQUENT CONSEQUENCE OF #1)
If #1 is insufficient: analyze maritime freight (Baltic indices), "war risk" insurance premiums, fuel surcharges, rerouting (e.g., Cape of Good Hope vs Suez/Black Sea), port bottlenecks. Provide concrete $/t ranges.

### 3. CUSTOMS DECLARATION ERRORS (LAST RESORT)
Only if #1 and #2 don't explain the gap: quantity/value errors, HS classification errors, intentional manipulation (under/over-invoicing). Explain why this is unlikely given the context.

---

**EXPECTED RESPONSE FORMAT:**
1. **Main Diagnosis** (1 sentence: cause #1 identified + % gap explained)
2. **Detailed Analysis** by priority (#1 -> #2 -> #3) with figures
3. **Confidence Level**: HIGH / MEDIUM / LOW
4. **Recommended Actions** for verification (e.g., cross-check with spot prices, freight indices, insurance premiums)

**LENGTH CONSTRAINT:**
The report must fit within 2-3 A4 pages maximum (approximately 1500-2000 tokens).
Be concise: short sentences, compact tables, no repetitions.
Prioritize information density: figures > adjectives.
"""

    print("Appel a Amazon Bedrock en cours...")
    response = bedrock.converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 3000, "temperature": 0.3}
    )
    explanation = response["output"]["message"]["content"][0]["text"]
    print("Explication generee avec succes !")

    payload_for_pdf = {
        "anomaly_data": event,
        "ai_explanation": explanation
    }

    payload_json = json.dumps(payload_for_pdf)
    payload_size_kb = len(payload_json.encode("utf-8")) / 1024
    print(f"Payload Lambda_PDF: {payload_size_kb:.1f} KB")

    if os.environ.get("LOCAL_TEST") != "true":
        lambda_client.invoke(
            FunctionName=pdf_lambda_name,
            InvocationType="Event",
            Payload=payload_json
        )
        print(f"Lambda {pdf_lambda_name} declenchee de maniere asynchrone.")
    else:
        print("\n--- MODE TEST LOCAL : Resultat du LLM ---")
        print(explanation)

    return {
        "statusCode": 202,
        "body": json.dumps({"status": "Processing", "anomaly_id": event.get("anomaly_id")})
    }

if __name__ == "__main__":
    os.environ["LOCAL_TEST"] = "true"
    with open("mock_event.json", "r") as f:
        mock_data = json.load(f)
    lambda_handler(mock_data, None)