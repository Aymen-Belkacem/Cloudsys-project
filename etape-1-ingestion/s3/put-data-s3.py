# Creator: Abir Chebbi (abir.chebbi@hesge.ch)
# Edited by: Luca Di Cosola (luca.dicosola@hes-so.ch)

import boto3
import os
from dotenv import load_dotenv

load_dotenv()

# Function to write data to S3
def write_data(s3_client, directory, bucket):
    if not os.path.isdir(directory):
        raise SystemExit(f"Local path '{directory}' does not exist.")
    count = 0
    for filename in os.listdir(directory):
        if filename.endswith(".csv"):  # Check if the file is a CSV
            file_path = os.path.join(directory, filename)
            with open(file_path, 'rb') as file:
                print(f"Uploading {filename} to bucket {bucket}...")
                s3_client.put_object(Body=file, Bucket=bucket, Key=filename)
                print(f"{filename} uploaded successfully.")
                count += 1
    if count == 0:
        raise SystemExit(f"No CSV files found in '{directory}'. Nothing was uploaded.")
    print(f"\nUploaded {count} CSV file(s).")


def main(bucket_name, local_dir, region):
    s3_client = boto3.client('s3', region_name=region)
    write_data(s3_client, local_dir, bucket_name)


if __name__ == "__main__":
    main(
        os.getenv("BUCKET_NAME", "bdcs-g3-ingestion-s3"),
        os.getenv("LOCAL_FILES", "../../data/"),
        os.getenv("REGION", "us-east-1")
    )
