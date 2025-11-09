"""Comprehensive unit tests for client port management functions.

Port management is critical for server lifecycle - ensures no port conflicts.
"""

import socket
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Import client
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "skills" / "pyclide"))
from pyclide_client import is_port_available, allocate_port


@pytest.mark.client
@pytest.mark.unit
class TestIsPortAvailable:
    """Test is_port_available() function."""

    def test_port_available_on_free_port(self):
        """is_port_available() returns True for free port."""
        # Find a likely free port (high number)
        test_port = 50000

        # Should be available
        result = is_port_available(test_port)

        assert result is True

    def test_port_not_available_when_in_use(self):
        """is_port_available() returns False when port is in use."""
        # Bind to a port to make it unavailable
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', 0))  # OS assigns a port
            _, port = s.getsockname()

            # While socket is open, port should be unavailable
            result = is_port_available(port)

            assert result is False

    def test_port_available_after_release(self):
        """is_port_available() returns True after port is released."""
        # Bind and release
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', 0))
            _, port = s.getsockname()
            # Socket closes when exiting with block

        # Now port should be available again
        result = is_port_available(port)

        assert result is True

    def test_port_available_with_low_port(self):
        """is_port_available() handles low port numbers."""
        # Port 1 is usually reserved and unavailable
        result = is_port_available(1)

        # Likely False due to permissions/reserved
        assert isinstance(result, bool)

    def test_port_available_with_high_port(self):
        """is_port_available() handles high port numbers."""
        # Port 65000 should typically be available
        result = is_port_available(65000)

        assert isinstance(result, bool)

    def test_port_available_edge_case_zero(self):
        """is_port_available() handles port 0 (special case)."""
        # Port 0 means "let OS choose"
        result = is_port_available(0)

        # Should be available (OS will assign)
        assert result is True

    def test_port_available_handles_os_error(self):
        """is_port_available() returns False on OSError."""
        with patch("socket.socket") as mock_socket:
            mock_instance = MagicMock()
            mock_instance.bind.side_effect = OSError("Permission denied")
            mock_socket.return_value.__enter__.return_value = mock_instance

            result = is_port_available(8000)

            assert result is False


@pytest.mark.client
@pytest.mark.unit
class TestAllocatePort:
    """Test allocate_port() function."""

    def test_allocate_port_returns_valid_port(self):
        """allocate_port() returns a port number in valid range."""
        port = allocate_port()

        assert 5000 <= port < 6000

    def test_allocate_port_returns_available_port(self):
        """allocate_port() returns an available port."""
        port = allocate_port()

        # Port should be available
        assert is_port_available(port)

    def test_allocate_port_different_on_multiple_calls(self):
        """allocate_port() can return different ports."""
        # Occupy first port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s1:
            port1 = allocate_port()
            s1.bind(('127.0.0.1', port1))

            # Allocate second port (should be different)
            port2 = allocate_port()

            assert port1 != port2

    def test_allocate_port_handles_all_ports_busy(self):
        """allocate_port() raises when all ports in range are busy."""
        # Mock is_port_available to always return False
        with patch("pyclide_client.is_port_available", return_value=False):
            with pytest.raises(RuntimeError, match="No available ports in range 5000-6000"):
                allocate_port()

    def test_allocate_port_retries_until_available(self):
        """allocate_port() retries until it finds available port."""
        call_count = [0]

        def mock_is_available(port):
            call_count[0] += 1
            # First 3 calls return False, then True
            return call_count[0] > 3

        with patch("pyclide_client.is_port_available", side_effect=mock_is_available):
            port = allocate_port()

            # Should have retried multiple times
            assert call_count[0] > 1
            assert isinstance(port, int)

    def test_allocate_port_start_range(self):
        """allocate_port() starts at 5000."""
        # Mock to accept first port tried
        with patch("pyclide_client.is_port_available") as mock_available:
            mock_available.return_value = True

            port = allocate_port()

            # First call should be with 5000
            assert mock_available.call_args_list[0][0][0] == 5000
            assert port == 5000

    def test_allocate_port_max_attempts(self):
        """allocate_port() tries up to 1000 ports."""
        attempts = [0]

        def count_attempts(port):
            attempts[0] += 1
            return False  # Always unavailable

        with patch("pyclide_client.is_port_available", side_effect=count_attempts):
            with pytest.raises(RuntimeError):
                allocate_port()

            # Should try 1000 times (5000-5999)
            assert attempts[0] == 1000

    def test_allocate_port_incremental_search(self):
        """allocate_port() searches incrementally from 5000."""
        checked_ports = []

        def track_checks(port):
            checked_ports.append(port)
            # Available on 4th port
            return len(checked_ports) >= 4

        with patch("pyclide_client.is_port_available", side_effect=track_checks):
            port = allocate_port()

            # Should have checked ports in order
            assert checked_ports == [5000, 5001, 5002, 5003]
            assert port == 5003


@pytest.mark.client
@pytest.mark.unit
class TestPortManagementIntegration:
    """Integration tests for port management functions."""

    def test_port_allocation_lifecycle(self):
        """Full lifecycle: allocate, use, release, reuse."""
        # Allocate port
        port = allocate_port()
        assert is_port_available(port)

        # Use port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', port))
            # Port is busy
            assert not is_port_available(port)

        # After release, port is available again
        assert is_port_available(port)

    def test_multiple_port_allocations_no_conflict(self, monkeypatch):
        """Multiple allocations don't conflict."""
        # Track allocated ports
        used_ports = set()

        def mock_load_registry():
            return {"servers": [{"port": p} for p in used_ports]}

        monkeypatch.setattr("pyclide_client.load_registry", mock_load_registry)

        port1 = allocate_port()
        used_ports.add(port1)

        port2 = allocate_port()
        used_ports.add(port2)

        port3 = allocate_port()
        used_ports.add(port3)

        # All should be different
        assert len({port1, port2, port3}) == 3

        # All should be available
        assert is_port_available(port1)
        assert is_port_available(port2)
        assert is_port_available(port3)
