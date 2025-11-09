"""Comprehensive unit tests for client HTTP communication.

send_request() is critical - handles all client-server HTTP communication with retry logic.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock
from urllib.error import URLError

import pytest

# Import client
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "skills" / "pyclide"))
from pyclide_client import send_request


@pytest.mark.client
@pytest.mark.unit
class TestSendRequest:
    """Test send_request() function."""

    def test_send_request_successful(self):
        """send_request() returns JSON response on success."""
        server_info = {"port": 8000, "workspace_root": "/workspace"}
        endpoint = "defs"
        data = {"file": "test.py", "line": 10, "col": 5}

        expected_response = {"locations": [{"file": "test.py", "line": 10, "column": 5}]}

        with patch("pyclide_client.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = json.dumps(expected_response).encode('utf-8')
            mock_response.__enter__.return_value = mock_response
            mock_urlopen.return_value = mock_response

            result = send_request(server_info, endpoint, data)

            assert result == expected_response

    def test_send_request_uses_correct_url(self):
        """send_request() constructs URL correctly."""
        server_info = {"port": 9999, "workspace_root": "/workspace"}
        endpoint = "refs"
        data = {}

        with patch("pyclide_client.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = b'{"result": "ok"}'
            mock_response.__enter__.return_value = mock_response
            mock_urlopen.return_value = mock_response

            send_request(server_info, endpoint, data)

            # Check URL
            called_request = mock_urlopen.call_args[0][0]
            assert called_request.full_url == "http://127.0.0.1:9999/refs"

    def test_send_request_sends_json_data(self):
        """send_request() sends data as JSON."""
        server_info = {"port": 8000, "workspace_root": "/workspace"}
        endpoint = "rename"
        data = {"file": "app.py", "line": 5, "col": 10, "new_name": "new_func"}

        with patch("pyclide_client.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = b'{"patches": {}}'
            mock_response.__enter__.return_value = mock_response
            mock_urlopen.return_value = mock_response

            send_request(server_info, endpoint, data)

            # Check request data
            called_request = mock_urlopen.call_args[0][0]
            assert called_request.data == json.dumps(data).encode('utf-8')

    def test_send_request_sets_content_type_header(self):
        """send_request() sets Content-Type header."""
        server_info = {"port": 8000, "workspace_root": "/workspace"}
        endpoint = "hover"
        data = {}

        with patch("pyclide_client.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = b'{}'
            mock_response.__enter__.return_value = mock_response
            mock_urlopen.return_value = mock_response

            send_request(server_info, endpoint, data)

            # Check headers
            called_request = mock_urlopen.call_args[0][0]
            assert called_request.headers.get('Content-type') == 'application/json'

    def test_send_request_uses_timeout(self):
        """send_request() uses 10 second timeout."""
        server_info = {"port": 8000, "workspace_root": "/workspace"}
        endpoint = "defs"
        data = {}

        with patch("pyclide_client.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = b'{"result": "ok"}'
            mock_response.__enter__.return_value = mock_response
            mock_urlopen.return_value = mock_response

            send_request(server_info, endpoint, data)

            # Check timeout
            assert mock_urlopen.call_args[1]["timeout"] == 10.0

    def test_send_request_retries_on_url_error(self):
        """send_request() retries once on URLError."""
        server_info = {"port": 8000, "workspace_root": "/workspace"}
        endpoint = "refs"
        data = {}

        # First call fails, second succeeds
        call_count = [0]

        def mock_urlopen_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise URLError("Connection refused")
            # Second call succeeds
            mock_response = MagicMock()
            mock_response.read.return_value = b'{"success": true}'
            mock_response.__enter__.return_value = mock_response
            return mock_response

        with patch("pyclide_client.urlopen", side_effect=mock_urlopen_side_effect):
            with patch("pyclide_client.remove_server") as mock_remove:
                with patch("pyclide_client.get_or_start_server") as mock_restart:
                    mock_restart.return_value = server_info

                    result = send_request(server_info, endpoint, data)

                    # Should have removed old server
                    mock_remove.assert_called_once_with("/workspace")
                    # Should have restarted server
                    mock_restart.assert_called_once_with("/workspace")
                    # Should succeed on retry
                    assert result == {"success": True}

    def test_send_request_removes_server_before_restart(self):
        """send_request() removes server from registry before restarting."""
        server_info = {"port": 8000, "workspace_root": "/workspace"}
        endpoint = "defs"
        data = {}

        def mock_urlopen_side_effect(*args, **kwargs):
            # Always fail to trigger retry
            raise URLError("Server down")

        with patch("pyclide_client.urlopen", side_effect=mock_urlopen_side_effect):
            with patch("pyclide_client.remove_server") as mock_remove:
                with patch("pyclide_client.get_or_start_server") as mock_restart:
                    # Make restart also fail to prevent infinite retry
                    mock_restart.side_effect = RuntimeError("Can't start")

                    with pytest.raises(RuntimeError):
                        send_request(server_info, endpoint, data)

                    # Should have called remove before get_or_start
                    mock_remove.assert_called_once()

    def test_send_request_exits_on_unexpected_error(self):
        """send_request() exits on non-URLError exceptions."""
        server_info = {"port": 8000, "workspace_root": "/workspace"}
        endpoint = "defs"
        data = {}

        with patch("pyclide_client.urlopen", side_effect=ValueError("Bad data")):
            with pytest.raises(SystemExit) as exc_info:
                send_request(server_info, endpoint, data)

            assert exc_info.value.code == 1

    def test_send_request_handles_json_decode_response(self):
        """send_request() decodes JSON response correctly."""
        server_info = {"port": 8000, "workspace_root": "/workspace"}
        endpoint = "occurrences"
        data = {}

        complex_response = {
            "locations": [
                {"file": "a.py", "line": 1, "column": 2},
                {"file": "b.py", "line": 10, "column": 20}
            ],
            "count": 2
        }

        with patch("pyclide_client.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = json.dumps(complex_response).encode('utf-8')
            mock_response.__enter__.return_value = mock_response
            mock_urlopen.return_value = mock_response

            result = send_request(server_info, endpoint, data)

            assert result == complex_response
            assert len(result["locations"]) == 2

    def test_send_request_handles_empty_response(self):
        """send_request() handles empty JSON response."""
        server_info = {"port": 8000, "workspace_root": "/workspace"}
        endpoint = "defs"
        data = {}

        with patch("pyclide_client.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = b'{}'
            mock_response.__enter__.return_value = mock_response
            mock_urlopen.return_value = mock_response

            result = send_request(server_info, endpoint, data)

            assert result == {}

    def test_send_request_handles_unicode_in_response(self):
        """send_request() handles Unicode in response."""
        server_info = {"port": 8000, "workspace_root": "/workspace"}
        endpoint = "hover"
        data = {}

        unicode_response = {"docstring": "Función con ñ y 中文"}

        with patch("pyclide_client.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = json.dumps(unicode_response).encode('utf-8')
            mock_response.__enter__.return_value = mock_response
            mock_urlopen.return_value = mock_response

            result = send_request(server_info, endpoint, data)

            assert result["docstring"] == "Función con ñ y 中文"

    def test_send_request_preserves_data_types(self):
        """send_request() preserves data types in request."""
        server_info = {"port": 8000, "workspace_root": "/workspace"}
        endpoint = "extract-var"
        data = {
            "file": "test.py",
            "start_line": 10,
            "end_line": 12,
            "start_col": 5,
            "end_col": 20,
            "var_name": "extracted"
        }

        with patch("pyclide_client.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = b'{"patches": {}}'
            mock_response.__enter__.return_value = mock_response
            mock_urlopen.return_value = mock_response

            send_request(server_info, endpoint, data)

            # Check sent data preserved types
            called_request = mock_urlopen.call_args[0][0]
            sent_data = json.loads(called_request.data.decode('utf-8'))
            assert isinstance(sent_data["start_line"], int)
            assert sent_data["start_line"] == 10


@pytest.mark.client
@pytest.mark.unit
class TestSendRequestEdgeCases:
    """Test send_request() edge cases."""

    def test_send_request_with_special_characters_in_endpoint(self):
        """send_request() handles special characters in endpoint."""
        server_info = {"port": 8000, "workspace_root": "/workspace"}
        endpoint = "extract-method"  # Has hyphen
        data = {}

        with patch("pyclide_client.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = b'{}'
            mock_response.__enter__.return_value = mock_response
            mock_urlopen.return_value = mock_response

            send_request(server_info, endpoint, data)

            called_url = mock_urlopen.call_args[0][0].full_url
            assert "extract-method" in called_url

    def test_send_request_with_empty_data(self):
        """send_request() handles empty data dict."""
        server_info = {"port": 8000, "workspace_root": "/workspace"}
        endpoint = "health"
        data = {}

        with patch("pyclide_client.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = b'{"status": "ok"}'
            mock_response.__enter__.return_value = mock_response
            mock_urlopen.return_value = mock_response

            result = send_request(server_info, endpoint, data)

            assert result == {"status": "ok"}

    def test_send_request_retry_uses_original_request(self):
        """send_request() retry uses the original request object."""
        server_info = {"port": 8000, "workspace_root": "/workspace"}
        endpoint = "rename"
        data = {"file": "test.py", "new_name": "foo"}

        call_count = [0]

        def mock_urlopen_side_effect(request, timeout):
            call_count[0] += 1
            if call_count[0] == 1:
                raise URLError("First attempt failed")
            # Check that the same request data is used
            sent_data = json.loads(request.data.decode('utf-8'))
            assert sent_data == data
            mock_response = MagicMock()
            mock_response.read.return_value = b'{"success": true}'
            mock_response.__enter__.return_value = mock_response
            return mock_response

        with patch("pyclide_client.urlopen", side_effect=mock_urlopen_side_effect):
            with patch("pyclide_client.remove_server"):
                with patch("pyclide_client.get_or_start_server", return_value=server_info):
                    result = send_request(server_info, endpoint, data)

                    assert result == {"success": True}
                    assert call_count[0] == 2  # Original + retry

    def test_send_request_failure_prints_to_stderr(self):
        """send_request() prints error messages to stderr."""
        server_info = {"port": 8000, "workspace_root": "/workspace"}
        endpoint = "defs"
        data = {}

        with patch("pyclide_client.urlopen", side_effect=ValueError("Test error")):
            with patch("sys.stderr") as mock_stderr:
                with pytest.raises(SystemExit):
                    send_request(server_info, endpoint, data)

                # Should have printed error
                assert mock_stderr.write.called or mock_stderr.flush.called
