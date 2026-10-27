
import boto3
import pandas as pd
from io import BytesIO
from urllib.parse import unquote_plus

s3 = boto3.client("s3")


def lambda_handler(event, context):
    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])

        # Download CSV from S3
        response = s3.get_object(
            Bucket=bucket,
            Key=key
        )

        with response["Body"] as body:
            content = body.read()

        # Load CSV into Pandas DataFrame
        df = pd.read_csv(BytesIO(content))

        print(f"File: {key}")
        print(f"Shape: {df.shape}")
        print(df.head().to_string(index=False))

    return {"statusCode": 200}
