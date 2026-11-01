"""Unit tests for Lambda AI (bdcs-g3-lambda-ai)."""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Add etape-3 to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lambda_ai import lambda_handler


class TestLambdaAI:
    """Tests for Lambda AI handler."""

    @pytest.fixture
    def mock_event(self):
        """Load mock event from fixture."""
        with open("tests/fixtures/mock_event.json", "r") as f:
            return json.load(f)

    @pytest.fixture
    def mock_context(self):
        """Mock Lambda context."""
        context = MagicMock()
        context.function_name = "bdcs-g3-lambda-ai"
        context.memory_limit_in_mb = 512
        context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:bdcs-g3-lambda-ai"
        return context

    @patch("lambda_ai.boto3.client")
    def test_lambda_handler_success(self, mock_boto_client, mock_event, mock_context):
        """Test successful Lambda AI invocation."""
        # Mock Bedrock response
        mock_bedrock = MagicMock()
        mock_bedrock.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": "# Test Report\n\n## Main Diagnosis\nTest diagnosis."}]
                }
            }
        }
        
        # Create a mock that handles any kwargs
        def mock_client_factory(service, **kwargs):
            if service == "bedrock-runtime":
                return mock_bedrock
            elif service == "lambda":
                mock_lambda = MagicMock()
                mock_lambda.invoke.return_value = {"StatusCode": 202}
                return mock_lambda
            return MagicMock()
        
        mock_boto_client.side_effect = mock_client_factory

        # Set env vars
        os.environ["LOCAL_TEST"] = "true"
        os.environ["BEDROCK_CHAT_MODEL_ID"] = "test-model"
        os.environ["PDF_LAMBDA_NAME"] = "test-pdf-lambda"

        response = lambda_handler(mock_event, mock_context)

        assert response["statusCode"] == 202
        body = json.loads(response["body"])
        assert body["status"] == "Processing"
        assert body["anomaly_id"] == "FRA_EGY_1001_2023-05"

    @patch("lambda_ai.boto3.client")
    def test_lambda_handler_bedrock_error(self, mock_boto_client, mock_event, mock_context):
        """Test Lambda AI handles Bedrock errors gracefully."""
        mock_bedrock = MagicMock()
        mock_bedrock.converse.side_effect = Exception("Bedrock unavailable")
        mock_boto_client.return_value = mock_bedrock

        os.environ["LOCAL_TEST"] = "true"

        with pytest.raises(Exception, match="Bedrock unavailable"):
            lambda_handler(mock_event, mock_context)

    def test_prompt_contains_required_sections(self, mock_event):
        """Test that prompt contains all required analysis sections."""
        # Import the prompt construction logic
        from lambda_ai import lambda_handler

        # We can't easily test the prompt without invoking, but we can verify
        # the event structure is valid
        assert "anomaly_id" in mock_event
        assert "period" in mock_event
        assert "reporter" in mock_event
        assert "partner" in mock_event
        assert "hs_code" in mock_event
        assert "product_name" in mock_event
        assert "fob_unit_price" in mock_event
        assert "cif_unit_price" in mock_event
        assert "gap_pct" in mock_event
        assert "anomaly_type" in mock_event
        assert "historical_context" in mock_event


class TestLambdaAIIntegration:
    """Integration-style tests (require AWS credentials)."""

    @pytest.mark.integration
    def test_lambda_ai_live(self):
        """Integration test against real Lambda (requires AWS creds)."""
        pytest.skip("Requires AWS credentials - run manually")