
import os
import sys
import boto3
from dotenv import load_dotenv

load_dotenv()

REGION = os.environ["AWS_REGION"]
BUCKET_NAME = os.environ["S3_BUCKET_NAME"]
LAMBDA_NAME = os.environ["LAMBDA_NAME"]

EVENT_ID = f"ObjectCreated-{LAMBDA_NAME}"

s3 = boto3.client("s3", region_name=REGION)
lambda_client = boto3.client("lambda", region_name=REGION)

def configure_s3_event():
    # Get existing notifications
    config = s3.get_bucket_notification_configuration(Bucket=BUCKET_NAME)
    config.pop("ResponseMetadata", None)

    # Exit if event already exists
    for event in config.get("LambdaFunctionConfigurations", []):
        if event.get("Id") == EVENT_ID:
            print(f"Event '{EVENT_ID}' already exists!")
            sys.exit(0)

    # Get Lambda ARN
    response = lambda_client.get_function_configuration(FunctionName=LAMBDA_NAME)
    lambda_arn = response["FunctionArn"]

    # Allow S3 to invoke Lambda
    try:
        lambda_client.add_permission(
            FunctionName=LAMBDA_NAME,
            StatementId=f"AllowS3Invoke-{LAMBDA_NAME}",
            Action="lambda:InvokeFunction",
            Principal="s3.amazonaws.com",
            SourceArn=f"arn:aws:s3:::{BUCKET_NAME}",
            SourceAccount=lambda_arn.split(":")[4]
        )
    except lambda_client.exceptions.ResourceConflictException:
        pass

    # Create event
    event = {"Id": EVENT_ID, "LambdaFunctionArn": lambda_arn, "Events": ["s3:ObjectCreated:*"]}

    # Append without deleting existing notifications
    config.setdefault("LambdaFunctionConfigurations", []).append(event)

    s3.put_bucket_notification_configuration(Bucket=BUCKET_NAME, NotificationConfiguration=config)

    print(f"Event '{EVENT_ID}' created!")

if __name__ == "__main__":
    configure_s3_event()