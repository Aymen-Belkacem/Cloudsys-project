# Data ingestion and processing

## Architecture and operation

The ingestion pipeline relies on three AWS services: Amazon S3 receives CSV files, AWS Lambda processes them, and Amazon DocumentDB stores the enriched data. The services are provisioned through Python scripts using Boto3, with configuration parameters defined in `.env` files.

Creating an object in the S3 bucket triggers the Lambda function through an `s3:ObjectCreated:*` notification. The function downloads the file identified in the event and loads it into a pandas DataFrame in memory. It calculates the unit price in USD per tonne for strictly positive quantities and identifies the exporter and importer. Export and import declarations are matched by month, exporter, importer, and HS4 product code to compare FOB and CIF prices. The percentage gap is calculated as `(CIF − FOB) / FOB × 100`. The `Anomaly` field is set to 1 when this gap exceeds 35%, 2 when it is negative, and 0 otherwise; it is null when the calculation is not possible.

The enriched rows are converted into documents and inserted through PyMongo using `insert_many` with unordered execution. Each document receives a deterministic SHA-256 identifier derived from the bucket, S3 key, file hash, and row index. Reprocessing the same content under the same key in the same bucket therefore does not create duplicate documents: duplicate-key errors are ignored, while other write errors are propagated.

The Lambda function is attached to the VPC providing access to DocumentDB. The database security group allows TCP connections on port 27017 from the Lambda security group. An S3 Gateway endpoint, associated with the relevant subnet route tables, enables file retrieval from this VPC. The DocumentDB connection uses TLS and the `global-bundle.pem` certificate bundle; cluster storage is encrypted. The IAM role grants permission to read the bucket, perform the network operations required by Lambda, and write logs to CloudWatch.

## Service selection

**AWS Lambda** fits the event-driven ingestion workflow: each S3 upload triggers processing without requiring a continuously running application server. Its Python runtime supports the existing pandas transformation code, while AWS manages the execution infrastructure.

**Amazon DocumentDB** provides managed document storage for the enriched records. Each processed row can be stored directly as a document containing the original attributes, calculated prices, and anomaly flag. Its flexible document model allows additional fields to be introduced as processing evolves, and its MongoDB-compatible API supports the PyMongo operations used in this project. This choice prioritizes document storage and Python integration; it does not imply that a relational database would be unsuitable for the original tabular data.

## Network configuration and dependencies

In this architecture, Lambda and DocumentDB use the same VPC, with separate security groups belonging to that VPC. The DocumentDB security group allows inbound TCP traffic on port 27017 from the Lambda security group, whose outbound rules must also allow this connection.

Attaching Lambda to a VPC does not automatically provide internet access, even when public subnets are selected. To allow the function to retrieve S3 objects without a NAT gateway, we configured an S3 Gateway endpoint and associated it with the route tables used by the Lambda subnets. This provides access to S3 through the AWS network.

The Python dependencies are supplied through Lambda layers. We used the existing AWS-provided AWS SDK for pandas layer and created a custom layer for PyMongo. Both layers are compatible with the selected Python runtime and are attached to the function through the ARNs configured in `LAMBDA_LAYERS_ARNS`.

## Deployment order

1. **Prepare the environment.** Configure local AWS credentials, install the dependencies listed in `requirements.txt`, and complete the `.env` files in each subdirectory. Prepare the VPC, subnets, DocumentDB subnet group, both security groups, and S3 endpoint. The pandas and PyMongo layers must be available and compatible with the selected runtime; their ARNs are provided in the configuration.
2. **Create the storage services.** Run `s3/create-s3.py`, followed by `documentdb/create_cluster.py`, which creates the cluster and its instance. Wait until they are available and copy the cluster endpoint into the Lambda configuration as `DOCDB_HOST`.
3. **Create the execution role.** Run `lambda/create_iam.py` to create the IAM role and assign the required permissions.
4. **Deploy the processing function.** From the `lambda` directory, run `create_lambda.py`. This script packages the code and certificate bundle, attaches the layers, configures the environment variables and network settings, and creates the function with 1,024 MB of memory and a 150-second timeout.
5. **Enable and test ingestion.** Once the Lambda function is active, run `lambda/configure_s3_event.py` to allow S3 to invoke it and add the event notification. Then, from the `s3` directory, run `put-data-s3.py` to upload the CSV files from the configured local directory. Check the CloudWatch logs and the stored documents. Subsequent code changes are deployed from the `lambda` directory using `python manage_lambda.py update`.
