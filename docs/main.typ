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

1. Raw data is stored on Amazon S3 buckets.
2. Compute processes are represented by a set of FaaS on AWS Lambda.
3. The Streamlit application is deployed on AWS App Runner as a managed service.
4. The database is deployed on Amazon DocumentDB.
5. Generative AI is served via the managed Amazon Bedrock API.
6. Everything is connected through a VPC network with private subnets and security groups.

= 3. Tasks

#table(
  columns: (auto, 1fr, auto),
  inset: 8pt,
  align: horizon,
  [*Tasks*], [*Outcome*], [*Students involved*],
  [Design of the architecture], [Validated diagram], [Zekria, Luca, Aymen],
  [Deployment and implementation], [Active pipelines and App Runner], [Zekria, Luca, Aymen],
  [Comparative study of cloud services], [Final AWS services selection], [Zekria, Luca, Aymen],
  [Security, privacy, sovereignty], [IAM management and restrictions], [Zekria, Luca, Aymen],
  [Data Ingestion], [Bucket S3, VPC Network, Lambda Function, DocumentDB], [Luca],
  [IA], [???], [Zekria],
  [Streamlit Application], [???], [Aymen]
)

= Streamlit application

The main resource was originally designed as an AWS App Runner. Due to Amazon discontinuing App Runners, it is instead an Elastic Container Service (ECS) Express Mode resource. The deployment works by first building a docker image describing the application's server, and then by pushing the image to an Elastic Container Registry (ECR) repository.

The script `deploy.sh` in the `infra` folder describes both the deployment of the application and its architectural choices. It is necessary to have the aws program installed and properly configured on the shell executing the script. Here "properly configured" means having set up the correct credentials and region - The region must be the same across the whole architecture.

Many constants are configured in the `config.env` file in the `infra` folder. They include fallback values for the AWS region, container configurations, and the necessary information to connect to the other two main parts of the project, the data and the chatbot. One notable exception is the DocumentDB's password, which is instead stored in an Amazon Secret. The secret's name is written in `config.env` with the rest of the daabse's constants, which allows the script to transmit the actual password to the container as a secretive environment variable called "SECRET_ARN".