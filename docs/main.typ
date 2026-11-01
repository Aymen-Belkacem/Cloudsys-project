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