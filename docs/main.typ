#set page(paper: "a4", margin: 2cm)
#set text(font: "New Computer Modern", size: 11pt)

#align(center, text(17pt)[*Project: Wheat Trade Anomaly Detection*])
#v(1em)

*Group:* G3 \
*Students:* Aymen Belkacem, Luca Di Cosola, Zekria Sormasor \
*Git URL:* TODO: to add \
*Link to a video:*  TODO: to add

= 1. Architecture

#figure(
  rect(width: 100%, height: 7cm, stroke: 1pt + black)[Insert architecture image here],
  caption: [Component workflow (S3, Lambda, App Runner, DocumentDB, Bedrock)]
)

== 1.1 Components

*Amazon S3:*
Object storage for raw import/export data files and generated reports.

*AWS Lambda:*
Serverless execution of ETL pipelines and anomaly calculations.

*Amazon DocumentDB:*
NoSQL database to persist analysis results and metadata.

*Amazon Bedrock:*
Automated anomaly report generation via Claude and Nova models.

= 2. Deployment

1. Data is stored on Amazon S3 buckets.
2. Compute processes are represented by a set of FaaS on AWS Lambda.
3. The Streamlit application is deployed on AWS App Runner as a managed service.
4. The database is deployed on Amazon DocumentDB.
5. Generative AI is served via the managed Amazon Bedrock API.

= 3. Tasks

#table(
  columns: (auto, 1fr, auto),
  inset: 8pt,
  align: horizon,
  [*Tasks*], [*Outcome*], [*Students involved*],
  [Design of the architecture], [Validated diagram], [Zekria, Luca, Aymen],
  [Deployment and implementation], [Active pipelines and App Runner], [Zekria, Luca, Aymen],
  [Comparative study of cloud services], [Final AWS services selection], [Zekria, Luca, Aymen],
  [Security, privacy, sovereignty], [IAM management and restrictions], [Zekria, Luca, Aymen]
)

= Data ingestion and processing

== Architecture and operation

The ingestion pipeline relies on three AWS services: Amazon S3 receives CSV files, AWS Lambda processes them, and Amazon DocumentDB stores the enriched data. The services are provisioned through Python scripts using Boto3, with configuration parameters defined in `.env` files.

Creating an object in the S3 bucket triggers the Lambda function through an `s3:ObjectCreated:*` notification. The function downloads the file identified in the event and loads it into a pandas DataFrame in memory. It calculates the unit price in USD per tonne for strictly positive quantities and identifies the exporter and importer. Export and import declarations are matched by month, exporter, importer, and HS4 product code to compare FOB and CIF prices. The percentage gap is calculated as `(CIF − FOB) / FOB × 100`. The `Anomaly` field is set to 1 when this gap exceeds 35%, 2 when it is negative, and 0 otherwise; it is null when the calculation is not possible.

The enriched rows are converted into documents and inserted through PyMongo using `insert_many` with unordered execution. Each document receives a deterministic SHA-256 identifier derived from the bucket, S3 key, file hash, and row index. Reprocessing the same content under the same key in the same bucket therefore does not create duplicate documents: duplicate-key errors are ignored, while other write errors are propagated.

The Lambda function is attached to the VPC providing access to DocumentDB. The database security group allows TCP connections on port 27017 from the Lambda security group. An S3 Gateway endpoint, associated with the relevant subnet route tables, enables file retrieval from this VPC. The DocumentDB connection uses TLS and the `global-bundle.pem` certificate bundle; cluster storage is encrypted. The IAM role grants permission to read the bucket, perform the network operations required by Lambda, and write logs to CloudWatch.

== Network configuration and dependencies

In this architecture, Lambda and DocumentDB use the same VPC, with separate security groups belonging to that VPC. The DocumentDB security group allows inbound TCP traffic on port 27017 from the Lambda security group, whose outbound rules must also allow this connection.

Attaching Lambda to a VPC does not automatically provide internet access, even when public subnets are selected. To allow the function to retrieve S3 objects without a NAT gateway, we configured an S3 Gateway endpoint and associated it with the route tables used by the Lambda subnets. This provides access to S3 through the AWS network.

The Python dependencies are supplied through Lambda layers. We used the existing AWS-provided AWS SDK for pandas layer and created a custom layer for PyMongo. Both layers are compatible with the selected Python runtime and are attached to the function through the ARNs configured in `LAMBDA_LAYERS_ARNS`.

== Deployment order

+ *Prepare the environment.* Configure local AWS credentials, install the dependencies listed in `requirements.txt`, and complete the `.env` files in each subdirectory. Prepare the VPC, subnets, DocumentDB subnet group, both security groups, and S3 endpoint. The pandas and PyMongo layers must be available and compatible with the selected runtime; their ARNs are provided in the configuration.
+ *Create the storage services.* Run `s3/create-s3.py`, followed by `documentdb/create_cluster.py`, which creates the cluster and its instance. Wait until they are available and copy the cluster endpoint into the Lambda configuration as `DOCDB_HOST`.
+ *Create the execution role.* Run `lambda/create_iam.py` to create the IAM role and assign the required permissions.
+ *Deploy the processing function.* From the `lambda` directory, run `create_lambda.py`. This script packages the code and certificate bundle, attaches the layers, configures the environment variables and network settings, and creates the function with 1,024 MB of memory and a 150-second timeout.
+ *Enable and test ingestion.* Once the Lambda function is active, run `lambda/configure_s3_event.py` to allow S3 to invoke it and add the event notification. Then, from the `s3` directory, run `put-data-s3.py` to upload the CSV files from the configured local directory. Check the CloudWatch logs and the stored documents. Subsequent code changes are deployed from the `lambda` directory using `python manage_lambda.py update`.


= Streamlit application

The main resource was originally designed as an AWS App Runner. Due to Amazon discontinuing App Runners, it is instead an Elastic Container Service (ECS) Express Mode resource. The deployment works by first building a docker image describing the application's server, and then by pushing the image to an Elastic Container Registry (ECR) repository.

The script `deploy.sh` in the `infra` folder describes both the deployment of the application and its architectural choices. It is necessary to have the aws program installed and properly configured on the shell executing the script. Here "properly configured" means having set up the correct credentials and region - The region must be the same across the whole architecture.

Many constants are configured in the `config.env` file in the `infra` folder. They include fallback values for the AWS region, container configurations, and the necessary information to connect to the other two main parts of the project, the data and the chatbot. One notable exception is the DocumentDB's password, which is instead stored in an Amazon Secret. The secret's name is written in `config.env` with the rest of the daabse's constants, which allows the script to transmit the actual password to the container as a secretive environment variable called "SECRET_ARN".