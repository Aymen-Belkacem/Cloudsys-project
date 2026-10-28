import os
import io
import zipfile
import boto3
from dotenv import load_dotenv

load_dotenv()

REGION = os.environ["AWS_REGION"]
ROLE_NAME = os.environ["IAM_ROLE_NAME"]
BUCKET_NAME = os.environ["S3_BUCKET_NAME"]
LAMBDA_NAME = os.environ["LAMBDA_NAME"]
RUNTIME = os.environ["LAMBDA_RUNTIME"]
LAYERs_ARNs = os.environ["LAMBDA_LAYERS_ARNS"]

iam = boto3.client("iam")
lambda_client = boto3.client("lambda", region_name=REGION)

def get_role_arn():
    response = iam.get_role(RoleName=ROLE_NAME)
    return response["Role"]["Arn"]


def create_deployment_package():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.write("lambda_function.py", arcname="lambda_function.py")
        zip_file.write("global-bundle.pem", arcname="global-bundle.pem")
    return buffer.getvalue()


def create_lambda():
    role_arn = get_role_arn()
    package = create_deployment_package()

    response = lambda_client.create_function(
        FunctionName=LAMBDA_NAME,
        Runtime=RUNTIME,
        Role=role_arn,
        Handler="lambda_function.lambda_handler",
        Code={"ZipFile": package},
        Layers=[layer for layer in LAYERs_ARNs.split(",")],
        Environment={
            "Variables": {
                "S3_BUCKET_NAME": BUCKET_NAME,
                "DOCDB_HOST": os.environ["DOCDB_HOST"],
                "DOCDB_USERNAME": os.environ["DOCDB_USERNAME"],
                "DOCDB_PASSWORD": os.environ["DOCDB_PASSWORD"],
            }
        },
        # Security group for the lambda function
        VpcConfig={
            "SubnetIds": [subnet.strip() for subnet in os.environ["LAMBDA_SUBNET_IDS"].split(",")],
            "SecurityGroupIds": [os.environ["LAMBDA_SECURITY_GROUP_ID"]],
        },
        Timeout=30,
        MemorySize=256,
        Description="Read files from an S3 bucket and process them",
    )

    return response["FunctionArn"]


if __name__ == "__main__":
    arn = create_lambda()
    print(f"Lambda created: {arn}")