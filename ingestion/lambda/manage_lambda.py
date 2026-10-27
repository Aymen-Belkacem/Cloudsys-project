
import os
import io
import zipfile
import argparse
from pathlib import Path

import boto3
from dotenv import load_dotenv

load_dotenv()

REGION = os.environ["AWS_REGION"]
LAMBDA_NAME = os.environ["LAMBDA_NAME"]
BUCKET_NAME = os.environ["S3_BUCKET_NAME"]

lambda_client = boto3.client("lambda", region_name=REGION)


def create_deployment_package():
    buffer = io.BytesIO()
    source = Path(__file__).resolve().parent / "lambda_function.py"

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.write(source, arcname="lambda_function.py")

    return buffer.getvalue()


def update_lambda():
    package = create_deployment_package()

    response = lambda_client.update_function_code(FunctionName=LAMBDA_NAME, ZipFile=package, Publish=False)

    # Wait until the update is completed
    waiter = lambda_client.get_waiter("function_updated")
    waiter.wait(FunctionName=LAMBDA_NAME)

    print(f"Lambda updated: {response['FunctionArn']}")


def delete_lambda():
    s3 = boto3.client("s3", region_name=REGION)
    # Remove all S3 event notifications
    s3.put_bucket_notification_configuration(
        Bucket=BUCKET_NAME,
        NotificationConfiguration={}
    )
    lambda_client.delete_function(FunctionName=LAMBDA_NAME)
    print(f"Lambda deleted: {LAMBDA_NAME}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["update", "delete"])
    args = parser.parse_args()

    if args.action == "update":
        update_lambda()
    elif args.action == "delete":
        delete_lambda()
