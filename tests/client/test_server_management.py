"""Comprehensive unit tests for client server management functions.

Server lifecycle management is critical - handles startup, health checks, recovery.
"""

import json
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock
from urllib.error import URLError

import pytest

# Import client
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "skills" / "pyclide"))
from pyclide_client import (
    is_server_healthy,
    check_uvx_available,
    start_server_via_uvx,
    get_or_start_server
)


@pytest.mark.client
@pytest.mark.unit
class TestIsServerHealthy:
    """Test is_server_healthy() function."""

    def test_server_healthy_returns_true_on_200(self):
        """is_server_healthy() returns True when server returns 200."""
        server_info = {"port": 8000}

        with patch("pyclide_client.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__enter__.return_value = mock_response
            mock_urlopen.return_value = mock_response

            result = is_server_healthy(server_info)

            assert result is True
            # Verify correct URL was called
            called_url = mock_urlopen.call_args[0][0].full_url
            assert "http://127.0.0.1:8000/health" == called_url

    def test_server_unhealthy_on_non_200(self):
        """is_server_healthy() returns False on non-200 status."""
        server_info = {"port": 8000}

        with patch("pyclide_client.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 500  # Server error
            mock_response.__enter__.return_value = mock_response
            mock_urlopen.return_value = mock_response

            result = is_server_healthy(server_info)

            assert result is False

    def test_server_unhealthy_on_url_error(self):
        """is_server_healthy() returns False on URLError."""
        server_info = {"port": 8000}

        with patch("pyclide_client.urlopen", side_effect=URLError("Connection refused")):
            result = is_server_healthy(server_info)

            assert result is False

    def test_server_unhealthy_on_timeout(self):
        """is_server_healthy() returns False on timeout."""
        server_info = {"port": 8000}

        with patch("pyclide_client.urlopen", side_effect=TimeoutError("Timeout")):
            result = is_server_healthy(server_info)

            assert result is False

    def test_server_unhealthy_on_os_error(self):
        """is_server_healthy() returns False on OSError."""
        server_info = {"port": 8000}

        with patch("pyclide_client.urlopen", side_effect=OSError("Network error")):
            result = is_server_healthy(server_info)

            assert result is False

    def test_server_healthy_uses_timeout(self):
        """is_server_healthy() uses 1 second timeout."""
        server_info = {"port": 8000}

        with patch("pyclide_client.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__enter__.return_value = mock_response
            mock_urlopen.return_value = mock_response

            is_server_healthy(server_info)

            # Check timeout was passed
            assert mock_urlopen.call_args[1]["timeout"] == 1.0

    def test_server_healthy_uses_correct_host(self):
        """is_server_healthy() always uses 127.0.0.1."""
        server_info = {"port": 9999}

        with patch("pyclide_client.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__enter__.return_value = mock_response
            mock_urlopen.return_value = mock_response

            is_server_healthy(server_info)

            called_url = mock_urlopen.call_args[0][0].full_url
            assert called_url.startswith("http://127.0.0.1:")


@pytest.mark.client
@pytest.mark.unit
class TestCheckUvxAvailable:
    """Test check_uvx_available() function."""

    def test_uvx_available_when_command_succeeds(self):
        """check_uvx_available() returns True when uvx --version succeeds."""
        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = check_uvx_available()

            assert result is True
            # Verify correct command was run
            assert mock_run.call_args[0][0] == ["uvx", "--version"]

    def test_uvx_not_available_when_command_fails(self):
        """check_uvx_available() returns False when uvx --version fails."""
        mock_result = Mock()
        mock_result.returncode = 1

        with patch("subprocess.run", return_value=mock_result):
            result = check_uvx_available()

            assert result is False

    def test_uvx_not_available_on_file_not_found(self):
        """check_uvx_available() returns False when uvx is not installed."""
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            result = check_uvx_available()

            assert result is False

    def test_uvx_not_available_on_timeout(self):
        """check_uvx_available() returns False on timeout."""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("uvx", 2.0)):
            result = check_uvx_available()

            assert result is False

    def test_uvx_check_uses_timeout(self):
        """check_uvx_available() uses 2 second timeout."""
        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            check_uvx_available()

            assert mock_run.call_args[1]["timeout"] == 2.0

    def test_uvx_check_captures_output(self):
        """check_uvx_available() captures output."""
        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            check_uvx_available()

            assert mock_run.call_args[1]["capture_output"] is True


@pytest.mark.client
@pytest.mark.unit
class TestStartServerViaUvx:
    """Test start_server_via_uvx() function."""

    def test_start_server_exits_if_uvx_not_available(self, tmp_path):
        """start_server_via_uvx() exits if uvx is not available."""
        with patch("pyclide_client.check_uvx_available", return_value=False):
            with pytest.raises(SystemExit) as exc_info:
                start_server_via_uvx(str(tmp_path))

            assert exc_info.value.code == 1

    def test_start_server_allocates_port(self, tmp_path):
        """start_server_via_uvx() allocates a port."""
        with patch("pyclide_client.check_uvx_available", return_value=True):
            with patch("pyclide_client.allocate_port", return_value=8123) as mock_allocate:
                with patch("subprocess.Popen"):
                    with patch("pyclide_client.is_server_healthy", return_value=True):
                        with patch("pyclide_client.add_server"):
                            server_info = start_server_via_uvx(str(tmp_path))

                            mock_allocate.assert_called_once()
                            assert server_info["port"] == 8123

    def test_start_server_spawns_process_windows(self, tmp_path):
        """start_server_via_uvx() uses correct flags on Windows."""
        with patch("pyclide_client.check_uvx_available", return_value=True):
            with patch("pyclide_client.allocate_port", return_value=8000):
                with patch("sys.platform", "win32"):
                    with patch("subprocess.Popen") as mock_popen:
                        with patch("pyclide_client.is_server_healthy", return_value=True):
                            with patch("pyclide_client.add_server"):
                                start_server_via_uvx(str(tmp_path))

                                # Check Windows-specific flags
                                call_kwargs = mock_popen.call_args[1]
                                assert "creationflags" in call_kwargs
                                # Should have DETACHED_PROCESS flag
                                assert call_kwargs["creationflags"] & subprocess.DETACHED_PROCESS

    def test_start_server_spawns_process_unix(self, tmp_path):
        """start_server_via_uvx() uses start_new_session on Unix."""
        with patch("pyclide_client.check_uvx_available", return_value=True):
            with patch("pyclide_client.allocate_port", return_value=8000):
                with patch("sys.platform", "linux"):
                    with patch("subprocess.Popen") as mock_popen:
                        with patch("pyclide_client.is_server_healthy", return_value=True):
                            with patch("pyclide_client.add_server"):
                                start_server_via_uvx(str(tmp_path))

                                # Check Unix-specific option
                                call_kwargs = mock_popen.call_args[1]
                                assert call_kwargs.get("start_new_session") is True

    def test_start_server_waits_for_health(self, tmp_path):
        """start_server_via_uvx() waits for server to be healthy."""
        health_checks = [0]

        def mock_health(server_info):
            health_checks[0] += 1
            # Healthy on 3rd check
            return health_checks[0] >= 3

        with patch("pyclide_client.check_uvx_available", return_value=True):
            with patch("pyclide_client.allocate_port", return_value=8000):
                with patch("subprocess.Popen"):
                    with patch("pyclide_client.is_server_healthy", side_effect=mock_health):
                        with patch("pyclide_client.add_server"):
                            with patch("time.sleep"):  # Skip actual sleep
                                server_info = start_server_via_uvx(str(tmp_path))

                                # Should have checked multiple times
                                assert health_checks[0] >= 3

    def test_start_server_raises_if_never_healthy(self, tmp_path):
        """start_server_via_uvx() raises if server never becomes healthy."""
        with patch("pyclide_client.check_uvx_available", return_value=True):
            with patch("pyclide_client.allocate_port", return_value=8000):
                with patch("subprocess.Popen"):
                    with patch("pyclide_client.is_server_healthy", return_value=False):
                        with patch("time.sleep"):  # Skip actual sleep
                            with pytest.raises(RuntimeError, match="Server failed to start"):
                                start_server_via_uvx(str(tmp_path))

    def test_start_server_adds_to_registry_on_success(self, tmp_path):
        """start_server_via_uvx() adds server to registry after successful start."""
        with patch("pyclide_client.check_uvx_available", return_value=True):
            with patch("pyclide_client.allocate_port", return_value=8555):
                with patch("subprocess.Popen"):
                    with patch("pyclide_client.is_server_healthy", return_value=True):
                        with patch("pyclide_client.add_server") as mock_add:
                            server_info = start_server_via_uvx(str(tmp_path))

                            # Should add to registry
                            mock_add.assert_called_once()
                            call_args = mock_add.call_args[0]
                            assert call_args[1] == 8555

    def test_start_server_resolves_workspace_path(self, tmp_path):
        """start_server_via_uvx() resolves workspace to absolute path."""
        workspace = tmp_path / "project"
        workspace.mkdir()

        with patch("pyclide_client.check_uvx_available", return_value=True):
            with patch("pyclide_client.allocate_port", return_value=8000):
                with patch("subprocess.Popen"):
                    with patch("pyclide_client.is_server_healthy", return_value=True):
                        with patch("pyclide_client.add_server"):
                            server_info = start_server_via_uvx(str(workspace))

                            # Should be absolute path
                            assert Path(server_info["workspace_root"]).is_absolute()

    def test_start_server_includes_timestamp(self, tmp_path):
        """start_server_via_uvx() includes started_at timestamp."""
        with patch("pyclide_client.check_uvx_available", return_value=True):
            with patch("pyclide_client.allocate_port", return_value=8000):
                with patch("subprocess.Popen"):
                    with patch("pyclide_client.is_server_healthy", return_value=True):
                        with patch("pyclide_client.add_server"):
                            before = time.time()
                            server_info = start_server_via_uvx(str(tmp_path))
                            after = time.time()

                            assert "started_at" in server_info
                            assert before <= server_info["started_at"] <= after


@pytest.mark.client
@pytest.mark.unit
class TestGetOrStartServer:
    """Test get_or_start_server() function."""

    def test_get_or_start_returns_existing_healthy_server(self, tmp_path):
        """get_or_start_server() returns existing server if healthy."""
        existing_server = {"workspace_root": str(tmp_path), "port": 8000}

        with patch("pyclide_client.find_server", return_value=existing_server):
            with patch("pyclide_client.is_server_healthy", return_value=True):
                server_info = get_or_start_server(str(tmp_path))

                assert server_info == existing_server

    def test_get_or_start_starts_new_if_none_exists(self, tmp_path):
        """get_or_start_server() starts new server if none exists."""
        new_server = {"workspace_root": str(tmp_path), "port": 8111}

        with patch("pyclide_client.find_server", return_value=None):
            with patch("pyclide_client.start_server_via_uvx", return_value=new_server) as mock_start:
                server_info = get_or_start_server(str(tmp_path))

                mock_start.assert_called_once_with(str(tmp_path))
                assert server_info == new_server

    def test_get_or_start_removes_unhealthy_server(self, tmp_path):
        """get_or_start_server() removes unhealthy server from registry."""
        unhealthy_server = {"workspace_root": str(tmp_path), "port": 8000}
        new_server = {"workspace_root": str(tmp_path), "port": 8222}

        with patch("pyclide_client.find_server", return_value=unhealthy_server):
            with patch("pyclide_client.is_server_healthy", return_value=False):
                with patch("pyclide_client.remove_server") as mock_remove:
                    with patch("pyclide_client.start_server_via_uvx", return_value=new_server):
                        server_info = get_or_start_server(str(tmp_path))

                        # Should remove unhealthy server
                        mock_remove.assert_called_once_with(str(tmp_path))
                        # Should start new server
                        assert server_info == new_server

    def test_get_or_start_restarts_unhealthy_server(self, tmp_path):
        """get_or_start_server() restarts server if unhealthy."""
        unhealthy_server = {"workspace_root": str(tmp_path), "port": 8000}
        new_server = {"workspace_root": str(tmp_path), "port": 8333}

        with patch("pyclide_client.find_server", return_value=unhealthy_server):
            with patch("pyclide_client.is_server_healthy", return_value=False):
                with patch("pyclide_client.remove_server"):
                    with patch("pyclide_client.start_server_via_uvx", return_value=new_server) as mock_start:
                        server_info = get_or_start_server(str(tmp_path))

                        # Should start new server
                        mock_start.assert_called_once()
                        assert server_info["port"] == 8333

    def test_get_or_start_doesnt_remove_if_healthy(self, tmp_path):
        """get_or_start_server() doesn't remove server if it's healthy."""
        healthy_server = {"workspace_root": str(tmp_path), "port": 8000}

        with patch("pyclide_client.find_server", return_value=healthy_server):
            with patch("pyclide_client.is_server_healthy", return_value=True):
                with patch("pyclide_client.remove_server") as mock_remove:
                    get_or_start_server(str(tmp_path))

                    # Should NOT remove healthy server
                    mock_remove.assert_not_called()

    def test_get_or_start_doesnt_start_if_healthy(self, tmp_path):
        """get_or_start_server() doesn't start new server if existing is healthy."""
        healthy_server = {"workspace_root": str(tmp_path), "port": 8000}

        with patch("pyclide_client.find_server", return_value=healthy_server):
            with patch("pyclide_client.is_server_healthy", return_value=True):
                with patch("pyclide_client.start_server_via_uvx") as mock_start:
                    get_or_start_server(str(tmp_path))

                    # Should NOT start new server
                    mock_start.assert_not_called()
