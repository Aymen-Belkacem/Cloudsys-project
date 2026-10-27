# Creator: Abir Chebbi (abir.chebbi@hesge.ch)
# Edited by: Luca Di Cosola (luca.dicosola@hes-so.ch)

import boto3
import botocore
import os
from dotenv import load_dotenv

load_dotenv()

def create_bucket(s3_client, bucket_name, region):
    """ Create an S3 bucket """
    try:
        print(f"Creating bucket '{bucket_name}' in region '{region}'...")
        if region == "us-east-1":
            response = s3_client.create_bucket(Bucket=bucket_name)
        else:
            response = s3_client.create_bucket(Bucket=bucket_name, CreateBucketConfiguration={"LocationConstraint": region})
        print(response)
    except botocore.exceptions.ClientError as error:
        code = error.response['Error']['Code']
        if code == 'BucketAlreadyOwnedByYou':
            print(f"Bucket '{bucket_name}' already exists in your account, reusing it.")
        elif code in ('BucketAlreadyExists', 'IllegalLocationConstraintException'):
            ## S3 bucket names are unique across all AWS accounts worldwide
            raise SystemExit(f"\nThe bucket name '{bucket_name}' is already taken by someone else.\n")
        else:
            raise
    print()

def main(bucket_name, region):
    s3_client = boto3.client('s3', region_name=region)
    create_bucket(s3_client, bucket_name, region)

if __name__ == "__main__":
    main(os.getenv("BUCKET_NAME", "bdcs-g3-ingestion-s3"), os.getenv("REGION", "us-east-1"))
