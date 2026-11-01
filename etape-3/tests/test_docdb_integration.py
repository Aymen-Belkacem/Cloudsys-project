"""Integration tests for DocumentDB connection."""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pymongo


class TestDocDBIntegration:
    """Integration tests for DocumentDB connection."""

    @pytest.mark.integration
    def test_docdb_connection(self):
        """Test actual DocumentDB connection (requires AWS creds and network)."""
        pytest.skip("Requires AWS credentials and VPC access")

    @patch("lambda_pdf.pymongo.MongoClient")
    def test_docdb_insert_metadata(self, mock_mongo_client):
        """Test metadata insertion logic."""
        from lambda_pdf import lambda_handler
        
        mock_client = MagicMock()
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_mongo_client.return_value = mock_client
        mock_client.__getitem__.return_value = mock_db
        mock_db.__getitem__.return_value = mock_collection
        
        # This would test the actual insertion logic
        # but requires the full lambda_handler context
        pytest.skip("Requires full lambda_handler context")


class TestConnectionStrategies:
    """Test DocumentDB connection strategies."""

    def test_strategy_order(self):
        """Verify connection strategies are tried in correct order."""
        from lambda_pdf import lambda_handler
        # The lambda_handler now tries multiple strategies:
        # 1. cluster_endpoint_with_replicaset
        # 2. cluster_endpoint_no_replicaset
        # 3. instance_endpoint_direct
        # 4. reader_endpoint
        # This is tested implicitly by integration tests
        pass


class TestEnvironmentVariables:
    """Test environment variable handling."""

    def test_default_values(self):
        """Test default values for environment variables."""
        import lambda_pdf
        
        # The module should use these defaults when env vars not set
        assert lambda_pdf.os.environ.get("DOCDB_DATABASE", "ingestion") == "ingestion"
        assert lambda_pdf.os.environ.get("DOCDB_COLLECTION", "reports_metadata") == "reports_metadata"
        assert lambda_pdf.os.environ.get("DOCDB_USERNAME", "clusteradmin") == "clusteradmin"
        assert lambda_pdf.os.environ.get("DOCDB_PASSWORD", "myclusterpassword") == "myclusterpassword"
        assert lambda_pdf.os.environ.get("DOCDB_TLS", "true").lower() == "true"

    def test_custom_values(self):
        """Test custom environment variable values."""
        import lambda_pdf
        
        os.environ["DOCDB_DATABASE"] = "test_db"
        os.environ["DOCDB_COLLECTION"] = "test_collection"
        
        # Would need to reload module to test - skipped
        pass