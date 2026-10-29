import boto3
import pandas as pd
from io import BytesIO
from urllib.parse import unquote_plus
import os
import hashlib
from pymongo import MongoClient
from pymongo.errors import BulkWriteError

s3 = boto3.client("s3")

DATABASE_NAME = os.getenv("DOCDB_DATABASE", "ingestion")
COLLECTION_NAME = os.getenv("DOCDB_COLLECTION", "products")

client = MongoClient(
    host=os.environ["DOCDB_HOST"],
    port=27017,
    username=os.environ["DOCDB_USERNAME"],
    password=os.environ["DOCDB_PASSWORD"],
    authSource="admin",
    tls=True,
    tlsCAFile="/var/task/global-bundle.pem",
    replicaSet="rs0",
    retryWrites=False,
    serverSelectionTimeoutMS=5000,
    connectTimeoutMS=5000,
    socketTimeoutMS=120_000, # 120 seconds
)

def write_db(identity_base, df):
    collection = client[DATABASE_NAME][COLLECTION_NAME]

    # Convert missing values
    df = df.astype(object).where(pd.notna(df), None)

    # Convert DataFrame to documents
    documents = df.to_dict(orient="records")

    # Generate deterministic IDs
    for index, document in enumerate(documents):
        identity = f"{identity_base}:{index}"
        document["_id"] = hashlib.sha256(identity.encode("utf-8")).hexdigest()

    try:
        result = collection.insert_many(documents, ordered=False)
        print(f"Inserted: {len(result.inserted_ids)}", flush=True)
    except BulkWriteError as exc:
        errors = exc.details.get("writeErrors", [])
        # Ignore duplicate _id errors caused by retries
        unexpected = [error for error in errors if error.get("code") != 11000]
        if unexpected or exc.details.get("writeConcernErrors"):
            raise
        print(f"Inserted: {exc.details.get('nInserted', 0)}", flush=True)
        print(f"Already existing: {len(errors)}", flush=True)


    
def proccess_csv(content: bytes) -> pd.DataFrame:
    df = pd.read_csv(BytesIO(content),thousands="'",decimal=".")
    return df

def add_columns(df: pd.DataFrame):
    # Les quantités sont en tonnes : prix en USD/t.
    # Une quantité nulle ou négative ne permet pas de calculer un prix.
    df["Unit_price"] = df["Value_USD"].div(
        df["Qty_t"].where(df["Qty_t"] > 0)
    )

    is_export = df["Flow"].eq("Export")
    is_import = df["Flow"].eq("Import")

    # Identifier le sens réel du commerce, quel que soit le déclarant.
    df["Exporter"] = df["Reporter"].where(is_export, df["Partner"])
    df["Importer"] = df["Partner"].where(is_export, df["Reporter"])

    keys = ["YearMonth", "Exporter", "Importer", "HS4"]

    # Prix déclarés de chaque côté.
    fob = (
        df.loc[is_export, keys + ["Unit_price"]]
        .rename(columns={"Unit_price": "FOB_USD_t"})
    )

    cif = (
        df.loc[is_import, keys + ["Unit_price"]]
        .rename(columns={"Unit_price": "CIF_USD_t"})
    )

    # Ajouter les deux prix à chaque ligne du DataFrame.
    df = df.merge(fob, on=keys, how="left", validate="many_to_one")
    df = df.merge(cif, on=keys, how="left", validate="many_to_one")

    # Calcul possible uniquement lorsque les deux prix sont disponibles,
    # avec FOB strictement positif.
    valid = (
        df["FOB_USD_t"].gt(0)
        & df["CIF_USD_t"].ge(0)
    )

    df["Gap_pct"] = (
        (df["CIF_USD_t"] - df["FOB_USD_t"])
        .div(df["FOB_USD_t"].where(valid))
        .mul(100)
    )

    df["Anomaly"] = pd.Series(0, index=df.index, dtype="Int64")

    df.loc[df["Gap_pct"] > 35, "Anomaly"] = 1
    df.loc[df["Gap_pct"] < 0, "Anomaly"] = 2
    df.loc[df["Gap_pct"].isna(), "Anomaly"] = pd.NA

    return df

def lambda_handler(event, context):

    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])

        # Download CSV from S3
        response = s3.get_object(Bucket=bucket, Key=key)

        with response["Body"] as body:
            content = body.read()

        # Load CSV into Pandas DataFrame
        df = proccess_csv(content)

        print("Received Data;")
        print(df.head().to_string(index=False))

        df = add_columns(df)
        print("Adding columns and calculating anomalies;")
        print(df.head().to_string(index=False))

        file_hash = hashlib.sha256(content).hexdigest()
        write_db(identity_base=f"{bucket}:{key}:{file_hash}", df=df)
        # do not ever close client otherwise on warmstart lambda will use the same client var which will be closed

    return {"statusCode": 200}
