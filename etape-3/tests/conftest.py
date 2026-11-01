"""Pytest configuration and shared fixtures."""

import os
import sys
import pytest

# Add etape-3 to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="session")
def aws_credentials():
    """Mock AWS credentials for testing."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture(scope="function")
def mock_s3():
    """Mock S3 client."""
    with patch("boto3.client") as mock_client:
        mock_s3 = MagicMock()
        mock_client.return_value = mock_s3
        yield mock_s3


@pytest.fixture(scope="function")
def mock_lambda_client():
    """Mock Lambda client."""
    with patch("boto3.client") as mock_client:
        mock_lambda = MagicMock()
        mock_client.return_value = mock_lambda
        yield mock_lambda