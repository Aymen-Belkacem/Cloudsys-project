#!/bin/bash
# Build script for Lambda_PDF zip deployment

set -e

cd "$(dirname "$0")"

echo "Building Lambda_PDF deployment package..."

# Clean previous build
rm -rf package lambda_pdf.zip

# Create package directory
mkdir -p package

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt -t package/ --quiet

# Copy source files
cp lambda_pdf.py package/
cp -r fonts package/

# Create zip
echo "Creating zip..."
cd package
zip -r ../lambda_pdf.zip . --quiet
cd ..

echo "Done! Deployment package: lambda_pdf.zip"
ls -lh lambda_pdf.zip

echo ""
echo "To deploy:"
echo "  aws lambda update-function-code --function-name Lambda_PDF --zip-file fileb://lambda_pdf.zip"