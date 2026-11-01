import os
import boto3
from dotenv import load_dotenv

load_dotenv()

docdb = boto3.client("docdb", region_name=os.environ["AWS_REGION"])

CLUSTER_NAME = os.environ["DOCDB_CLUSTER_NAME"]
INSTANCE_NAME = os.environ["DOCDB_INSTANCE_NAME"]

try:
    instance = docdb.describe_db_instances(DBInstanceIdentifier=INSTANCE_NAME)["DBInstances"][0]
    if instance["DBInstanceStatus"] != "deleting":
        docdb.delete_db_instance(DBInstanceIdentifier=INSTANCE_NAME)
    docdb.get_waiter("db_instance_deleted").wait(DBInstanceIdentifier=INSTANCE_NAME, WaiterConfig={"Delay": 30, "MaxAttempts": 120})
    print("Instance deleted.")
except docdb.exceptions.DBInstanceNotFoundFault:
    print(f"The instance {INSTANCE_NAME} does not exist.")
except Exception as e:
    print("Failed to delete the instance db:",str(e))

try:
    cluster = docdb.describe_db_clusters(DBClusterIdentifier=CLUSTER_NAME)["DBClusters"][0]
    if cluster["Status"] != "deleting":
        if cluster.get("DeletionProtection"):
            docdb.modify_db_cluster(DBClusterIdentifier=CLUSTER_NAME, DeletionProtection=False, ApplyImmediately=True)
        docdb.delete_db_cluster(DBClusterIdentifier=CLUSTER_NAME, SkipFinalSnapshot=True)
    print("Cluster deleted.")
except docdb.exceptions.DBClusterNotFoundFault:
    print(f"The cluster {CLUSTER_NAME} does not exist.")
except Exception as e:
    print("Failed to delete the cluster db:",str(e))