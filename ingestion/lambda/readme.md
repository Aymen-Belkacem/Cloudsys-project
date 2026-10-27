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