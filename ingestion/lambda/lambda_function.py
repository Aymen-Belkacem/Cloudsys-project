import boto3
import pandas as pd
from io import BytesIO
from urllib.parse import unquote_plus
import os
from pymongo import MongoClient

s3 = boto3.client("s3")

def connect_db():
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
        socketTimeoutMS=5000,
    )
    return client

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

    client = connect_db()
    result = client.admin.command("ping")
    print("Connexion DocumentDB réussie :", result)

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

    return {"statusCode": 200}
