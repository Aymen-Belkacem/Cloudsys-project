import os
import json
import boto3
from dotenv import load_dotenv

load_dotenv()

ROLE_NAME = os.environ["IAM_ROLE_NAME"]
BUCKET_NAME = os.environ["S3_BUCKET_NAME"]

iam = boto3.client("iam")

# Allow AWS Lambda to assume this role
trust_policy = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "lambda.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}

# Allow read-only access to a specific S3 bucket
s3_policy = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": ["s3:ListBucket"],
            "Resource": f"arn:aws:s3:::{BUCKET_NAME}"
        },
        {
            "Effect": "Allow",
            "Action": ["s3:GetObject"],
            "Resource": f"arn:aws:s3:::{BUCKET_NAME}/*"
        }
    ]
}


def create_iam_role():
    try:
        response = iam.create_role(RoleName=ROLE_NAME, AssumeRolePolicyDocument=json.dumps(trust_policy))
        role_arn = response["Role"]["Arn"]
    except iam.exceptions.EntityAlreadyExistsException:
        response = iam.get_role(RoleName=ROLE_NAME)
        role_arn = response["Role"]["Arn"]

    # Grant permissions to read S3 objects
    iam.put_role_policy(RoleName=ROLE_NAME, PolicyName="S3ReadOnly", PolicyDocument=json.dumps(s3_policy))

    # Grant permissions to write CloudWatch logs
    # iam.attach_role_policy(RoleName=ROLE_NAME, PolicyArn=("arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"))

    return role_arn


if __name__ == "__main__":
    arn = create_iam_role()
    print(f"IAM Role ARN: {arn}")