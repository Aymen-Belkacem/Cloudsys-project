# Creator: [Votre Nom]
# Script pour la création des rôles IAM (Projet 3 - Anomalies)

import boto3
import botocore
import json
import argparse

# 1. Politique de confiance de base (Trust Policy) pour autoriser AWS Lambda à assumer le rôle
LAMBDA_TRUST_POLICY = json.dumps({
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "lambda.amazonaws.com"},
        "Action": "sts:AssumeRole"
    }]
})

def create_lambda_ai_role(iam_client):
    """ Création du rôle pour l'orchestrateur IA """
    # role_name = "Role_Lambda_AI"
    role_name = "bdcs-g3-lambda-ai-role"
    print(f"Création du rôle: {role_name}...")
    
    try:
        # Création du rôle
        response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=LAMBDA_TRUST_POLICY,
            Description="Role pour Lambda_AI (Bedrock et Invocation asynchrone)"
        )
        
        # Attachement de la politique de base pour les logs (CloudWatch)
        iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
        )
        
        # Ajout des permissions spécifiques en ligne (Bedrock + appel Lambda)
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
        print(f"Rôle '{role_name}' créé avec succès. ARN: {response['Role']['Arn']}\n")
        
    except botocore.exceptions.ClientError as error:
        if error.response['Error']['Code'] == 'EntityAlreadyExists':
            print(f"Le rôle '{role_name}' existe déjà.\n")
        else:
            raise

def create_lambda_pdf_role(iam_client, bucket_name):
    """ Création du rôle pour la génération PDF et sauvegarde S3/DocumentDB """
    # role_name = "Role_Lambda_PDF"
    role_name = "bdcs-g3-lambda-pdf-role"
    print(f"Création du rôle: {role_name}...")
    
    try:
        # Création du rôle
        response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=LAMBDA_TRUST_POLICY,
            Description="Role pour Lambda_PDF (Acces VPC DocumentDB et ecriture S3)"
        )
        
        # Attachement des politiques managées (Logs + Accès réseau/VPC pour DocumentDB)
        iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
        )
        iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
        )
        
        # Ajout de la permission spécifique en ligne (Écriture stricte dans le bucket S3)
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
        print(f"Rôle '{role_name}' créé avec succès. ARN: {response['Role']['Arn']}\n")
        
    except botocore.exceptions.ClientError as error:
        if error.response['Error']['Code'] == 'EntityAlreadyExists':
            print(f"Le rôle '{role_name}' existe déjà.\n")
        else:
            raise

def main(bucket_name):
    # Initialisation du client IAM
    iam_client = boto3.client('iam')
    
    create_lambda_ai_role(iam_client)
    create_lambda_pdf_role(iam_client, bucket_name)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Créer les rôles IAM pour le pipeline de détection d'anomalies")
    # Le nom du bucket est requis pour sécuriser l'accès S3 du rôle PDF
    parser.add_argument("--bucket_name", required=True, help="Le nom du bucket S3 (ex: reports-pdf)")
    args = parser.parse_args()
    
    main(args.bucket_name)