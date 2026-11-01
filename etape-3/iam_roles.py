# Creator: [Your Name]
# Script for creating IAM roles (Project 3 - Anomalies)

import boto3
import botocore
import json
import argparse

# 1. Base trust policy (Trust Policy) to authorize AWS Lambda to assume the role
LAMBDA_TRUST_POLICY = json.dumps({
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "lambda.amazonaws.com"},
        "Action": "sts:AssumeRole"
    }]
})

def create_lambda_ai_role(iam_client):
    """ Creation of the role for the AI orchestrator """
    # role_name = "Role_Lambda_AI"
    role_name = "bdcs-g3-lambda-ai-role"
    print(f"Creating role: {role_name}...")
    
    try:
        # Creating the role
        response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=LAMBDA_TRUST_POLICY,
            Description="Role for Lambda_AI (Bedrock and Async Invocation)"
        )
        
        # Attaching base policy for logs (CloudWatch)
        iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
        )
        
        # Adding specific inline permissions (Bedrock + Lambda call)
        ai_inline_policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": [
                    "bedrock:InvokeModel",
                    "lambda:InvokeFunction"
                ],
                "Resource": "*"
            }]
        }
        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName="BedrockAndLambdaInvokePolicy",
            PolicyDocument=json.dumps(ai_inline_policy)
        )
        print(f"Role '{role_name}' created successfully. ARN: {response['Role']['Arn']}\n")
        
    except botocore.exceptions.ClientError as error:
        if error.response['Error']['Code'] == 'EntityAlreadyExists':
            print(f"Role '{role_name}' already exists.\n")
        else:
            raise

def create_lambda_pdf_role(iam_client, bucket_name):
    """ Creation of the role for PDF generation and S3/DocumentDB storage """
    # role_name = "Role_Lambda_PDF"
    role_name = "bdcs-g3-lambda-pdf-role"
    print(f"Creating role: {role_name}...")
    
    try:
        # Creating the role
        response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=LAMBDA_TRUST_POLICY,
            Description="Role for Lambda_PDF (VPC DocumentDB access and S3 write)"
        )
        
        # Attaching managed policies (Logs + VPC/Network access for DocumentDB)
        iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
        )
        iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
        )
        
        # Adding specific inline permission (Strict write to S3 bucket)
        pdf_inline_policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": "s3:PutObject",
                "Resource": f"arn:aws:s3:::{bucket_name}/*"
            }]
        }
        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName="S3WriteReportsPolicy",
            PolicyDocument=json.dumps(pdf_inline_policy)
        )
        print(f"Role '{role_name}' created successfully. ARN: {response['Role']['Arn']}\n")
        
    except botocore.exceptions.ClientError as error:
        if error.response['Error']['Code'] == 'EntityAlreadyExists':
            print(f"Role '{role_name}' already exists.\n")
        else:
            raise

def main(bucket_name):
    # Initialisation du client IAM
    iam_client = boto3.client('iam')
    
    create_lambda_ai_role(iam_client)
    create_lambda_pdf_role(iam_client, bucket_name)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create IAM roles for anomaly detection pipeline")
    # The bucket name is required to secure S3 access for the PDF role
    parser.add_argument("--bucket_name", required=True, help="S3 bucket name (ex: reports-pdf)")
    args = parser.parse_args()
    
    main(args.bucket_name)