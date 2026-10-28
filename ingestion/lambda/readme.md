# Step 1
Create role IAM with `create_iam.py` for the lambda to be able to access s3 bucket

# Step 2.0
Create the aws lambda with `create_lambda.py` if not existing

# Step 2.1
Update the `lambda_function.py` code if needed then update the aws lambda with `python manage_lambda.py update`

# Step 3
Create the s3 notification event with `configure_s3_event.py`

# Step 4
To delete lambda, execute `python manage_lambda.py delete`. it also delete the s3 event notifications.

# Create VPC S3 Gateway Endpoint
Because Lambdas needs to be in a VPC in order to access DocumentDB, we need to enable VPC's S3 Endpoint Gateway at url `https://us-east-1.console.aws.amazon.com/vpcconsole/home?region=us-east-1#Endpoints:` with service `com.amazonaws.us-east-1.s3` in `Gateway` mode