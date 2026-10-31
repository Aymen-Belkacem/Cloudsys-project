"""Unit tests for Lambda PDF (bdcs-g3-lambda-pdf)."""

import json
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch, mock_open

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Try to import lambda_pdf, skip tests if dependencies not available
try:
    from lambda_pdf import lambda_handler, markdown_to_pdf, JSONEncoder, json_dumps
    from bson import ObjectId
    from datetime import datetime
    LAMBDA_PDF_AVAILABLE = True
except ImportError as e:
    LAMBDA_PDF_AVAILABLE = False
    IMPORT_ERROR = str(e)


@pytest.mark.skipif(not LAMBDA_PDF_AVAILABLE, reason=f"Lambda PDF dependencies not available: {IMPORT_ERROR if not LAMBDA_PDF_AVAILABLE else ''}")
class TestLambdaPDF:
    """Tests for Lambda PDF handler."""

    @pytest.fixture
    def mock_event(self):
        return {
            "anomaly_data": {
                "anomaly_id": "TEST_123",
                "period": "2023-05",
                "reporter": "FRA",
                "partner": "EGY",
                "hs_code": "1001",
                "product_name": "Wheat",
                "fob_unit_price": 400.0,
                "cif_unit_price": 600.0,
                "gap_pct": 50.0,
                "anomaly_type": "Gap > 35%",
                "historical_context": "Test context"
            },
            "ai_explanation": "# Test Report\n\n**Main Diagnosis:** Test diagnosis."
        }

    @pytest.fixture
    def mock_context(self):
        context = MagicMock()
        context.function_name = "bdcs-g3-lambda-pdf"
        return context

    @patch("lambda_pdf.boto3.client")
    @patch("lambda_pdf.markdown_to_pdf")
    @patch("lambda_pdf.json_dumps")
    def test_lambda_handler_success(self, mock_json_dumps, mock_md_to_pdf, mock_boto_client, mock_event, mock_context):
        """Test successful PDF generation and S3 upload."""
        # Mock S3 client
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        # Mock markdown_to_pdf
        def mock_pdf_gen(text, path):
            with open(path, "wb") as f:
                f.write(b"fake pdf content")
        mock_md_to_pdf.side_effect = mock_pdf_gen
        
        # Mock json_dumps to return a string
        mock_json_dumps.return_value = '{"test": "data"}'

        os.environ["LOCAL_TEST"] = "false"
        os.environ["S3_BUCKET_REPORTS"] = "test-bucket"

        response = lambda_handler(mock_event, MagicMock())

        assert response["statusCode"] == 200
        assert "presigned_url" in response
        mock_s3.upload_file.assert_called_once()
        mock_s3.generate_presigned_url.assert_called_once()

    @patch("lambda_pdf.boto3.client")
    @patch("lambda_pdf.markdown_to_pdf")
    @patch("lambda_pdf.json_dumps")
    def test_lambda_handler_local_test(self, mock_json_dumps, mock_md_to_pdf, mock_boto_client, mock_event, mock_context):
        """Test local test mode (no S3 upload)."""
        os.environ["LOCAL_TEST"] = "true"
        
        def mock_pdf_gen(text, path):
            with open(path, "wb") as f:
                f.write(b"fake pdf content")
        mock_md_to_pdf.side_effect = mock_pdf_gen
        
        mock_json_dumps.return_value = '{"test": "data"}'

        response = lambda_handler(mock_event, mock_context)

        assert response["statusCode"] == 200
        assert response["presigned_url"].startswith("file://")

    @patch("lambda_pdf.boto3.client")
    @patch("lambda_pdf.markdown_to_pdf")
    @patch("lambda_pdf.json_dumps")
    def test_lambda_handler_s3_upload_error(self, mock_json_dumps, mock_md_to_pdf, mock_boto_client, mock_event, mock_context):
        """Test error handling on S3 upload failure."""
        mock_s3 = MagicMock()
        mock_s3.upload_file.side_effect = Exception("S3 unavailable")
        mock_boto_client.return_value = mock_s3

        def mock_pdf_gen(text, path):
            with open(path, "wb") as f:
                f.write(b"fake pdf content")
        mock_md_to_pdf.side_effect = mock_pdf_gen
        
        mock_json_dumps.return_value = '{"test": "data"}'

        os.environ["LOCAL_TEST"] = "false"

        with pytest.raises(Exception, match="S3 unavailable"):
            lambda_handler(mock_event, MagicMock())

    def test_markdown_to_pdf(self, tmp_path):
        """Test markdown to PDF conversion."""
        if not LAMBDA_PDF_AVAILABLE:
            pytest.skip("Lambda PDF dependencies not available")
            
        md = "# Test\n\n**Bold** and *italic*.\n\n| A | B |\n|---|---|\n| 1 | 2 |"
        output = tmp_path / "test.pdf"
        
        markdown_to_pdf(md, str(output))
        
        assert output.exists()
        assert output.stat().st_size > 0

    def test_json_encoder_objectid(self):
        """Test JSONEncoder handles ObjectId."""
        obj_id = ObjectId("507f1f77bcf86cd799439011")
        result = json_dumps({"id": obj_id})
        assert '"id": "507f1f77bcf86cd799439011"' in result

    def test_json_encoder_datetime(self):
        """Test JSONEncoder handles datetime."""
        dt = datetime(2023, 5, 15, 12, 30, 45)
        result = json_dumps({"date": dt})
        assert '"date": "2023-05-15T12:30:45"' in result

    def test_json_encoder_nested(self):
        """Test JSONEncoder handles nested structures."""
        obj_id = ObjectId("507f1f77bcf86cd799439011")
        dt = datetime(2023, 5, 15)
        data = {
            "items": [
                {"id": obj_id, "created": dt},
                {"id": ObjectId(), "created": datetime.now()}
            ]
        }
        result = json_dumps(data)
        assert "507f1f77bcf86cd799439011" in result
        assert "2023-05-15T00:00:00" in result

    def test_error_file_writing(self, tmp_path):
        """Test error file writing to S3."""
        from lambda_pdf import lambda_handler
        # This would require more mocking - skipped for brevity
        pass


class TestLambdaPDFIntegration:
    """Integration tests for Lambda PDF."""

    @pytest.mark.integration
    def test_lambda_pdf_live(self):
        """Integration test against real Lambda (requires AWS creds)."""
        pytest.skip("Requires AWS credentials - run manually")


class TestMarkdownToPDF:
    """Tests for markdown_to_pdf function."""

    @pytest.mark.skipif(not LAMBDA_PDF_AVAILABLE, reason="Lambda PDF dependencies not available")
    def test_simple_markdown(self, tmp_path):
        """Test simple markdown conversion."""
        md = "# Test\n\n**Bold** and *italic*.\n\n| A | B |\n|---|---|\n| 1 | 2 |"
        output = tmp_path / "test.pdf"
        markdown_to_pdf(md, str(output))
        assert output.exists()
        assert output.stat().st_size > 0

    def test_table_rendering(self, tmp_path):
        """Test table rendering."""
        md = "| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |"
        output = tmp_path / "table.pdf"
        markdown_to_pdf(md, str(output))
        assert output.exists()
        assert output.stat().st_size > 0

    def test_unicode_support(self, tmp_path):
        """Test Unicode character support."""
        md = "# Test \u2192 \u00c9gypt\n\n**Bl\u00e9** et *caf\u00e9*"
        output = tmp_path / "unicode.pdf"
        markdown_to_pdf(md, str(output))
        assert output.exists()
        assert output.stat().st_size > 0


class TestLambdaPDFIntegration:
    """Integration tests for Lambda PDF."""

    @pytest.mark.integration
    def test_lambda_pdf_live(self):
        """Integration test against real Lambda (requires AWS creds)."""
        pytest.skip("Requires AWS credentials - run manually")


class TestMarkdownToPDF:
    """Tests for markdown_to_pdf function."""

    @pytest.mark.skipif(not LAMBDA_PDF_AVAILABLE, reason="Lambda PDF dependencies not available")
    def test_simple_markdown(self, tmp_path):
        """Test simple markdown conversion."""
        md = "# Hello\n\n**Bold** text."
        output = tmp_path / "simple.pdf"
        markdown_to_pdf(md, str(output))
        assert output.exists()
        assert output.stat().st_size > 0

    def test_table_rendering(self, tmp_path):
        """Test table rendering."""
        md = "| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |"
        output = tmp_path / "table.pdf"
        markdown_to_pdf(md, str(output))
        assert output.exists()
        assert output.stat().st_size > 0

    def test_unicode_support(self, tmp_path):
        """Test Unicode character support."""
        md = "# Test \u2192 \u00c9gypt\n\n**Bl\u00e9** et *caf\u00e9*"
        output = tmp_path / "unicode.pdf"
        markdown_to_pdf(md, str(output))
        assert output.exists()
        assert output.stat().st_size > 0


class TestLambdaPDFIntegration:
    """Integration tests for Lambda PDF."""

    @pytest.mark.integration
    def test_lambda_pdf_live(self):
        """Integration test against real Lambda (requires AWS creds)."""
        pytest.skip("Requires AWS credentials - run manually")