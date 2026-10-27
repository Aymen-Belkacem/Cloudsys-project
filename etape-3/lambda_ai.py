import boto3
import json
import os

def lambda_handler(event, context):
    region = os.environ.get("AWS_REGION", "us-east-1")
    model_id = os.environ.get("BEDROCK_CHAT_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
    pdf_lambda_name = os.environ.get("PDF_LAMBDA_NAME", "Lambda_PDF")

    bedrock = boto3.client("bedrock-runtime", region_name=region)
    lambda_client = boto3.client("lambda", region_name=region)

    prompt = f"""Tu es un expert senior en commerce international de matieres premieres agricoles chez DNEXT.
Une anomalie a ete detectee sur un flux commercial bilaterale :
- Produit : {event.get('hs_code')} ({event.get('product_name')})
- Exportateur : {event.get('reporter')} | Importateur : {event.get('partner')}
- Periode : {event.get('period')}
- Prix unitaire FOB (Export) : {event.get('fob_unit_price')} USD/t
- Prix unitaire CIF (Import) : {event.get('cif_unit_price')} USD/t
- Ecart (Gap) : {event.get('gap_pct')}% (Regle declenchee : {event.get('anomaly_type')})
- Contexte historique : {event.get('historical_context', 'N/A')}

Redige un rapport structure et professionnel en francais expliquant cette anomalie.

**INSTRUCTION CRITIQUE - ORDRE D'ANALYSE OBLIGATOIRE :**
Tu DOIS analyser les causes dans l'ordre suivant, en t'arretant des qu'une cause explique suffisamment l'anomalie :

### 1. CONTEXTE GEOPOLITIQUE ET MACROECONOMIQUE DE LA PERIODE (ANALYSER EN PREMIER)
Identifie explicitement TOUS les evenements majeurs connus a la periode {event.get('period')} impactant :
- Le produit **{event.get('product_name')}** (code HS {event.get('hs_code')})
- La route commerciale **{event.get('reporter')} -> {event.get('partner')}**
- Les regions de production/transit concernees (Mer Noire, Mediterranee, etc.)

Cite nommement : conflits actifs, sanctions, blocus, accords internationaux (ex: Initiative Cereales Mer Noire), perturbations portuaires, embargos. Si un evenement majeur existe, **c'est la cause principale** -- quantifie son impact estime sur le gap (primes assurance, reroutage, tension offre/demande).

### 2. COUTS LOGISTIQUES EXCEPTIONNELS (CONSEQUENCE FREQUENTE DU #1)
Si le #1 ne suffit pas : analyse fret maritime (indices Baltic), primes d'assurance "war risk", surcouts carburant, reroutage (ex: Cap Bonne-Esperance vs Suez/Mer Noire), goulets portuaires. Donne des fourchettes $/t concretes.

### 3. ERREURS DE DECLARATION DOUANIERE (DERNIER RECOURS)
Uniquement si #1 et #2 n'expliquent pas l'ecart : erreurs quantites, valeurs, classification HS, manipulation intentionnelle (sous/sur-facturation). Precise pourquoi c'est peu probable au vu du contexte.

---

**FORMAT DE REPONSE ATTENDU :**
1. **Diagnostic principal** (1 phrase : cause #1 identifiee + % gap explique)
2. **Analyse detaillee** par priorite (#1 -> #2 -> #3) avec chiffres
3. **Niveau de confiance** : ELEVE / MOYEN / FAIBLE
4. **Actions recommandees** pour verification (ex: croiser avec prix spot, indices fret, primes assurance)

**CONTRAINTE DE LONGUEUR :**
Le rapport doit tenir sur 2-3 pages A4 maximum (environ 1500-2000 tokens).
Sois concis : phrases courtes, tableaux compacts, pas de repetitions.
Privilegiez la densite d'information : chiffres > adjectifs.
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