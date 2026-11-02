# Creator: Abir Chebbi (abir.chebbi@hesge.ch)
# Edited by: Luca Di Cosola (luca.dicosola@hes-so.ch)

import boto3
import os
from dotenv import load_dotenv

load_dotenv()

def delete_bucket(bucket_name, region):
    s3_resource = boto3.resource('s3', region_name=region)
    s3_client = boto3.client('s3', region_name=region)

    bucket = s3_resource.Bucket(bucket_name)

    print("Deleting all objects in Bucket\n")
    bucket.objects.all().delete()
    ## Also remove object versions if versioning is enabled
    try:
        bucket.object_versions.all().delete()
    except Exception:
        pass

    print("Deleting Bucket")
    response = s3_client.delete_bucket(Bucket=bucket_name)
    print(response)


def main(bucket_name, region):
    confirm = input(f"Permanently delete bucket '{bucket_name}' and everything in it? [y/N] ")
    if confirm.strip().lower() != 'y':
        print("Aborted.")
        return
    delete_bucket(bucket_name, region)


if __name__ == "__main__":
    main(os.getenv("BUCKET_NAME", "bdcs-g3-ingestion-s3"), os.getenv("REGION", "us-east-1"))
