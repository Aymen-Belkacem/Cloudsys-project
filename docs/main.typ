#set page(paper: "a4", margin: 2cm)
#set text(font: "New Computer Modern", size: 11pt)
#set par(spacing: 0.8em)

#align(center, text(17pt)[*Project: Wheat Trade Anomaly Detection*])
#v(1em)

*Group:* G3 \
*Students:* Aymen Belkacem, Luca Di Cosola, Zekria Sormasor \
*Git URL:* https://github.com/Aymen-Belkacem/Cloudsys-project \
*Link to a video:*  TODO: to add

= 1. Architecture

#figure(
  image("archi_cloudsys.drawio.png", height: 20cm),
  caption: [Component workflow (S3, Lambda, ECS, DocumentDB, Bedrock)]
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

*Amazon Elastic Container Registry (ECR):*
Container Image registry for the dashboard container. ECS downloads the image at each deployment.

*Amazon Elastic Container Service (ECS) Express Mode: *
Container As A Service running the Streamlit dashboard. Managed by Fargate, not by us. Express Mode creates the load balancer, and scales automatically.

*Application Load Balancer (ALB):*
Public HTTPS entry point of the dashboard.

= 2. Deployment

1. Raw data is stored on Amazon S3 buckets.
2. Compute processes are represented by a set of FaaS on AWS Lambda.
3. The database is deployed on Amazon DocumentDB.
4. Generative AI is served via the managed Amazon Bedrock API.
5. Everything is connected through a VPC network and security groups.
6. The Streamlit dashboard runs as a single container on Amazon ECS Express Mode. AWS Fargate runs the container without any server to manage.
7. The container image is stored in an Amazon ECR repository.
8. An Application Load Balancer is automatically created by ECS Express Mode. It exposes the dashboard over HTTPS and performs a health check of the container.
9. A dedicated security group for the dashboard is allowed on the port 27017 of the DocumentDB.
10. An IAM role limits the dashboard, allowing it to only invoking the AI Lambda and reading the generated reports from S3
11. A Cloudwatch Logs group monitors the Streamlit dashboard.

= 3. Tasks

#table(
  columns: (auto, 1fr, auto),
  inset: 8pt,
  align: horizon,
  [*Tasks*], [*Outcome*], [*Students involved*],
  [Design of the architecture], [Validated diagram], [Zekria, Luca, Aymen],
  [Deployment and implementation], [Active pipelines], [Zekria, Luca, Aymen],
  [Comparative study of cloud services], [Final AWS services selection], [Zekria, Luca, Aymen],
  [Security, privacy, sovereignty], [IAM management and restrictions], [Zekria, Luca, Aymen],
  [Data Ingestion], [Bucket S3, VPC Network, Lambda Function, DocumentDB], [Luca],
  [IA], [Lambda AI, Lambda PDF, Bedrock, S3 reports, DocumentDB], [Zekria],
  [Streamlit Application], [ECR, ECS, ALB, Secrets, IAM, Cloudwatch], [Aymen]
)
