import json
from unittest.mock import MagicMock, patch

import pytest

from main import main, upload_log


class TestUploadLog:
    @patch("main.storage.Client")
    def test_upload_log_creates_correct_path(self, mock_client_cls):
        mock_blob = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_client_cls.return_value.bucket.return_value = mock_bucket

        log_data = {"job": "ml-batch", "status": "success"}
        path = upload_log("test-bucket", "ml-batch", log_data)

        assert path.startswith("logs/")
        assert "ml-batch_" in path
        assert path.endswith(".json")

    @patch("main.storage.Client")
    def test_upload_log_sends_json(self, mock_client_cls):
        mock_blob = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_client_cls.return_value.bucket.return_value = mock_bucket

        log_data = {"job": "ml-batch", "status": "success"}
        upload_log("test-bucket", "ml-batch", log_data)

        call_args = mock_blob.upload_from_string.call_args
        uploaded = json.loads(call_args[0][0])
        assert uploaded["job"] == "ml-batch"
        assert uploaded["status"] == "success"
        assert call_args[1]["content_type"] == "application/json"


class TestMain:
    @patch("main.upload_log")
    def test_main_with_bucket(self, mock_upload, monkeypatch, capsys):
        monkeypatch.setenv("GCS_BUCKET", "test-bucket")
        monkeypatch.setenv("JOB_NAME", "ml-batch")
        mock_upload.return_value = "logs/20260326/ml-batch_20260326_120000.json"

        main()

        output = capsys.readouterr().out
        assert "Hello from Cloud Run Job: ml-batch" in output
        assert "ログ書き出し完了" in output
        mock_upload.assert_called_once()

    def test_main_without_bucket(self, monkeypatch, capsys):
        monkeypatch.delenv("GCS_BUCKET", raising=False)

        main()

        output = capsys.readouterr().out
        assert "スキップ" in output

    @patch("main.upload_log")
    def test_main_default_job_name(self, mock_upload, monkeypatch):
        monkeypatch.setenv("GCS_BUCKET", "test-bucket")
        monkeypatch.delenv("JOB_NAME", raising=False)
        mock_upload.return_value = "logs/test.json"

        main()

        call_args = mock_upload.call_args
        assert call_args[0][1] == "ml-batch"  # default job name
