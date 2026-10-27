import os
import boto3
from dotenv import load_dotenv

load_dotenv()

docdb = boto3.client("docdb", region_name=os.environ["AWS_REGION"])

response = docdb.create_db_cluster(
    DBClusterIdentifier=os.environ["DOCDB_CLUSTER_NAME"],
    Engine="docdb",
    MasterUsername=os.environ["DOCDB_MASTER_USERNAME"],
    MasterUserPassword=os.environ["DOCDB_MASTER_PASSWORD"],
    DBSubnetGroupName=os.environ["DOCDB_SUBNET_GROUP_NAME"],
    VpcSecurityGroupIds=[os.environ["DOCDB_SECURITY_GROUP_ID"]],
    StorageEncrypted=True,
)

print(response["DBCluster"]["DBClusterArn"])