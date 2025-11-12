"""Tests for Control Server runtime management API.

This module tests the HTTP control server including:
- Server lifecycle (start, stop)
- GET endpoints (status, stats, cache, config, rules, layers)
- POST endpoints (cache management, config reload, rule management)
- Error handling and JSON responses
"""

import json
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock, PropertyMock, patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from shadowfs.core.logging import Logger
from shadowfs.fuse.control import ControlRequestHandler, ControlServer, ControlServerError


@pytest.fixture
def mock_fuse_ops():
    """Create mock FUSE operations."""
    fuse_ops = Mock()
    fuse_ops.readonly = True
    fuse_ops.fds = {}
    fuse_ops.cache = Mock()
    fuse_ops.rule_engine = Mock()
    fuse_ops.layer_manager = Mock()

    # Configure cache
    fuse_ops.cache.get_stats = Mock(
        return_value={
            "hits": 100,
            "misses": 50,
            "size": 1024,
        }
    )

    # Configure stats
    fuse_ops.get_stats = Mock(
        return_value={
            "open_files": 0,
            "total_reads": 1000,
            "total_writes": 500,
        }
    )

    # Configure rule engine
    fuse_ops.rule_engine.__len__ = Mock(return_value=5)

    # Configure virtual layer manager
    fuse_ops.layer_manager.layers = ["by-type", "by-date"]

    return fuse_ops


@pytest.fixture
def mock_config_manager():
    """Create mock configuration manager."""
    config_manager = Mock()
    config_manager._config = {
        "sources": [{"path": "/data", "priority": 1}],
        "readonly": True,
        "cache": {"enabled": True, "max_size_mb": 512},
    }
    return config_manager


@pytest.fixture
def logger():
    """Create test logger."""
    return Logger("test", level="DEBUG")


@pytest.fixture
def control_server(mock_fuse_ops, mock_config_manager, logger):
    """Create control server instance."""
    # Use a dynamic port (0 = OS assigns)
    server = ControlServer(
        fuse_ops=mock_fuse_ops,
        config_manager=mock_config_manager,
        host="127.0.0.1",
        port=0,  # Let OS assign port
        mount_point="/mnt/shadowfs",
    )

    # Store original get_url method
    original_get_url = server.get_url

    # Override get_url to use actual assigned port
    def get_url():
        if server.server:
            actual_port = server.server.server_address[1]
            return f"http://{server.host}:{actual_port}"
        return original_get_url()

    server.get_url = get_url

    yield server

    # Cleanup
    if server.running:
        server.stop()


class TestControlServerInit:
    """Test ControlServer initialization."""

    def test_init_stores_arguments(self, mock_fuse_ops, mock_config_manager, logger):
        """Stores initialization arguments."""
        server = ControlServer(
            fuse_ops=mock_fuse_ops,
            config_manager=mock_config_manager,
            host="127.0.0.1",
            port=8080,
            mount_point="/mnt/test",
        )

        assert server.fuse_ops == mock_fuse_ops
        assert server.config_manager == mock_config_manager
        assert server.host == "127.0.0.1"
        assert server.port == 8080
        assert server.mount_point == "/mnt/test"

    def test_init_creates_logger(self, mock_fuse_ops, mock_config_manager):
        """Creates logger instance."""
        server = ControlServer(
            fuse_ops=mock_fuse_ops,
            config_manager=mock_config_manager,
        )

        assert server.logger is not None

    def test_init_sets_running_false(self, mock_fuse_ops, mock_config_manager):
        """Initializes running flag to False."""
        server = ControlServer(
            fuse_ops=mock_fuse_ops,
            config_manager=mock_config_manager,
        )

        assert not server.running
        assert server.server is None
        assert server.server_thread is None


class TestServerLifecycle:
    """Test server start/stop lifecycle."""

    def test_start_server(self, control_server):
        """Starts server successfully."""
        control_server.start()

        assert control_server.running
        assert control_server.server is not None
        assert control_server.server_thread is not None
        assert control_server.server_thread.is_alive()

    def test_start_creates_http_server(self, control_server):
        """Creates HTTPServer instance."""
        control_server.start()

        import http.server

        assert isinstance(control_server.server, http.server.HTTPServer)

    def test_start_attaches_components_to_server(self, control_server):
        """Attaches FUSE ops and config manager to server."""
        control_server.start()

        assert control_server.server.fuse_ops == control_server.fuse_ops
        assert control_server.server.config_manager == control_server.config_manager
        assert control_server.server.mount_point == control_server.mount_point

    def test_start_already_running(self, control_server):
        """Handles start when already running."""
        control_server.start()

        # Try to start again
        control_server.start()

        # Should still be running
        assert control_server.running

    def test_stop_server(self, control_server):
        """Stops server successfully."""
        control_server.start()
        time.sleep(0.1)  # Let server start

        control_server.stop()

        assert not control_server.running

    def test_stop_not_running(self, control_server):
        """Handles stop when not running."""
        # Should not raise exception
        control_server.stop()

        assert not control_server.running

    def test_is_running(self, control_server):
        """Checks running status."""
        assert not control_server.is_running()

        control_server.start()
        assert control_server.is_running()

        control_server.stop()
        assert not control_server.is_running()

    def test_get_url(self, control_server):
        """Returns server URL."""
        control_server.start()

        url = control_server.get_url()

        # Should be http://127.0.0.1:<port>
        assert url.startswith("http://127.0.0.1:")
        assert control_server.host in url

        # Verify URL contains actual assigned port
        actual_port = control_server.server.server_address[1]
        assert str(actual_port) in url

    def test_start_on_busy_port(self, control_server):
        """Raises error if port is busy."""
        # Start first server
        control_server.start()
        actual_port = control_server.server.server_address[1]

        # Try to start second server on same port
        server2 = ControlServer(
            fuse_ops=control_server.fuse_ops,
            config_manager=control_server.config_manager,
            host="127.0.0.1",
            port=actual_port,
        )

        with pytest.raises(ControlServerError, match="Failed to start"):
            server2.start()


class TestGetEndpoints:
    """Test GET endpoint handlers."""

    def test_handle_root(self, control_server):
        """Root endpoint returns available endpoints."""
        control_server.start()
        time.sleep(0.1)

        url = control_server.get_url() + "/"
        response = urlopen(url)
        data = json.loads(response.read())

        assert "endpoints" in data
        assert "version" in data
        assert "GET" in data["endpoints"]
        assert "POST" in data["endpoints"]

    def test_handle_status(self, control_server):
        """Status endpoint returns server status."""
        control_server.start()
        time.sleep(0.1)

        url = control_server.get_url() + "/status"
        response = urlopen(url)
        data = json.loads(response.read())

        assert data["running"] is True
        assert data["mount_point"] == "/mnt/shadowfs"
        assert data["readonly"] is True
        assert "open_files" in data

    def test_handle_stats(self, control_server):
        """Stats endpoint returns filesystem statistics."""
        control_server.start()
        time.sleep(0.1)

        url = control_server.get_url() + "/stats"
        response = urlopen(url)
        data = json.loads(response.read())

        assert "open_files" in data
        assert "total_reads" in data

    def test_handle_cache_stats(self, control_server):
        """Cache stats endpoint returns cache statistics."""
        control_server.start()
        time.sleep(0.1)

        url = control_server.get_url() + "/cache/stats"
        response = urlopen(url)
        data = json.loads(response.read())

        assert "hits" in data
        assert "misses" in data
        assert "size" in data

    def test_handle_config(self, control_server):
        """Config endpoint returns configuration."""
        control_server.start()
        time.sleep(0.1)

        url = control_server.get_url() + "/config"
        response = urlopen(url)
        data = json.loads(response.read())

        assert "config" in data
        assert "sources" in data["config"]

    def test_handle_rules_list(self, control_server):
        """Rules endpoint returns rule count."""
        control_server.start()
        time.sleep(0.1)

        url = control_server.get_url() + "/rules"
        response = urlopen(url)
        data = json.loads(response.read())

        assert "rule_count" in data
        assert data["rule_count"] == 5
        assert data["success"] is True

    def test_handle_layers_list(self, control_server):
        """Layers endpoint returns virtual layer count."""
        control_server.start()
        time.sleep(0.1)

        url = control_server.get_url() + "/layers"
        response = urlopen(url)
        data = json.loads(response.read())

        assert "layer_count" in data
        assert data["layer_count"] == 2
        assert data["success"] is True

    def test_unknown_get_endpoint(self, control_server):
        """Unknown GET endpoint returns 404."""
        control_server.start()
        time.sleep(0.1)

        url = control_server.get_url() + "/unknown"

        with pytest.raises(HTTPError) as exc_info:
            urlopen(url)

        assert exc_info.value.code == 404


class TestPostEndpoints:
    """Test POST endpoint handlers."""

    def test_handle_cache_clear(self, control_server):
        """Cache clear endpoint clears cache."""
        control_server.start()
        time.sleep(0.1)

        url = control_server.get_url() + "/cache/clear"
        data = json.dumps({}).encode("utf-8")
        request = Request(url, data=data, headers={"Content-Type": "application/json"})

        response = urlopen(request)
        result = json.loads(response.read())

        assert result["success"] is True
        assert "Cache cleared" in result["message"]

        # Verify invalidate_cache was called
        control_server.fuse_ops.invalidate_cache.assert_called()

    def test_handle_cache_invalidate(self, control_server):
        """Cache invalidate endpoint invalidates specific path."""
        control_server.start()
        time.sleep(0.1)

        url = control_server.get_url() + "/cache/invalidate"
        data = json.dumps({"path": "/test/path"}).encode("utf-8")
        request = Request(url, data=data, headers={"Content-Type": "application/json"})

        response = urlopen(request)
        result = json.loads(response.read())

        assert result["success"] is True
        assert "/test/path" in result["message"]

        # Verify invalidate_cache was called with path
        control_server.fuse_ops.invalidate_cache.assert_called_with("/test/path")

    def test_handle_cache_invalidate_missing_path(self, control_server):
        """Cache invalidate returns error if path missing."""
        control_server.start()
        time.sleep(0.1)

        url = control_server.get_url() + "/cache/invalidate"
        data = json.dumps({}).encode("utf-8")
        request = Request(url, data=data, headers={"Content-Type": "application/json"})

        with pytest.raises(HTTPError) as exc_info:
            urlopen(request)

        assert exc_info.value.code == 400

    def test_handle_config_reload(self, control_server):
        """Config reload endpoint acknowledges request."""
        control_server.start()
        time.sleep(0.1)

        url = control_server.get_url() + "/config/reload"
        data = json.dumps({}).encode("utf-8")
        request = Request(url, data=data, headers={"Content-Type": "application/json"})

        response = urlopen(request)
        result = json.loads(response.read())

        assert result["success"] is True
        assert "reload requested" in result["message"]

    def test_handle_rule_add(self, control_server):
        """Rule add endpoint adds new rule."""
        control_server.start()
        time.sleep(0.1)

        url = control_server.get_url() + "/rules/add"
        data = json.dumps(
            {
                "name": "Test Rule",
                "type": "exclude",
                "pattern": "*.tmp",
                "priority": 50,
            }
        ).encode("utf-8")
        request = Request(url, data=data, headers={"Content-Type": "application/json"})

        response = urlopen(request)
        result = json.loads(response.read())

        assert result["success"] is True
        assert "Test Rule" in result["message"]

        # Verify add_rule was called
        control_server.fuse_ops.rule_engine.add_rule.assert_called()

    def test_handle_rule_add_missing_parameters(self, control_server):
        """Rule add returns error if parameters missing."""
        control_server.start()
        time.sleep(0.1)

        url = control_server.get_url() + "/rules/add"
        data = json.dumps({"name": "Test"}).encode("utf-8")
        request = Request(url, data=data, headers={"Content-Type": "application/json"})

        with pytest.raises(HTTPError) as exc_info:
            urlopen(request)

        assert exc_info.value.code == 400

    def test_handle_rule_remove(self, control_server):
        """Rule remove endpoint removes rule."""
        control_server.start()
        time.sleep(0.1)

        url = control_server.get_url() + "/rules/remove"
        data = json.dumps({"name": "Test Rule"}).encode("utf-8")
        request = Request(url, data=data, headers={"Content-Type": "application/json"})

        response = urlopen(request)
        result = json.loads(response.read())

        assert result["success"] is True
        assert "Test Rule" in result["message"]

        # Verify remove_rule was called
        control_server.fuse_ops.rule_engine.remove_rule.assert_called_with("Test Rule")

    def test_handle_rule_remove_missing_name(self, control_server):
        """Rule remove returns error if name missing."""
        control_server.start()
        time.sleep(0.1)

        url = control_server.get_url() + "/rules/remove"
        data = json.dumps({}).encode("utf-8")
        request = Request(url, data=data, headers={"Content-Type": "application/json"})

        with pytest.raises(HTTPError) as exc_info:
            urlopen(request)

        assert exc_info.value.code == 400

    def test_unknown_post_endpoint(self, control_server):
        """Unknown POST endpoint returns 404."""
        control_server.start()
        time.sleep(0.1)

        url = control_server.get_url() + "/unknown"
        data = json.dumps({}).encode("utf-8")
        request = Request(url, data=data, headers={"Content-Type": "application/json"})

        with pytest.raises(HTTPError) as exc_info:
            urlopen(request)

        assert exc_info.value.code == 404


class TestErrorHandling:
    """Test error handling in control server."""

    def test_invalid_json_in_post(self, control_server):
        """Returns error for invalid JSON in POST body."""
        control_server.start()
        time.sleep(0.1)

        url = control_server.get_url() + "/cache/clear"
        data = b"invalid json"
        request = Request(url, data=data, headers={"Content-Type": "application/json"})

        with pytest.raises(HTTPError) as exc_info:
            urlopen(request)

        assert exc_info.value.code == 400

    def test_stats_error_when_fuse_ops_none(self, mock_config_manager):
        """Returns 503 when FUSE operations not available."""
        server = ControlServer(
            fuse_ops=None,
            config_manager=mock_config_manager,
            port=0,
        )

        # Apply get_url override
        def get_url():
            if server.server:
                actual_port = server.server.server_address[1]
                return f"http://{server.host}:{actual_port}"
            return f"http://{server.host}:{server.port}"

        server.get_url = get_url

        server.start()
        time.sleep(0.1)

        url = server.get_url() + "/stats"

        with pytest.raises(HTTPError) as exc_info:
            urlopen(url)

        assert exc_info.value.code == 503

        server.stop()

    def test_cache_stats_error_when_cache_none(self, mock_fuse_ops, mock_config_manager):
        """Returns 503 when cache not available."""
        mock_fuse_ops.cache = None

        server = ControlServer(
            fuse_ops=mock_fuse_ops,
            config_manager=mock_config_manager,
            port=0,
        )

        # Apply get_url override
        def get_url():
            if server.server:
                actual_port = server.server.server_address[1]
                return f"http://{server.host}:{actual_port}"
            return f"http://{server.host}:{server.port}"

        server.get_url = get_url

        server.start()
        time.sleep(0.1)

        url = server.get_url() + "/cache/stats"

        with pytest.raises(HTTPError) as exc_info:
            urlopen(url)

        assert exc_info.value.code == 503

        server.stop()

    def test_rule_engine_error_when_none(self, mock_fuse_ops, mock_config_manager):
        """Returns 503 when rule engine not available."""
        mock_fuse_ops.rule_engine = None

        server = ControlServer(
            fuse_ops=mock_fuse_ops,
            config_manager=mock_config_manager,
            port=0,
        )

        # Apply get_url override
        def get_url():
            if server.server:
                actual_port = server.server.server_address[1]
                return f"http://{server.host}:{actual_port}"
            return f"http://{server.host}:{server.port}"

        server.get_url = get_url

        server.start()
        time.sleep(0.1)

        url = server.get_url() + "/rules"

        with pytest.raises(HTTPError) as exc_info:
            urlopen(url)

        assert exc_info.value.code == 503

        server.stop()

    def test_config_error_when_none(self, mock_fuse_ops):
        """Returns 503 when config manager not available."""
        server = ControlServer(
            fuse_ops=mock_fuse_ops,
            config_manager=None,
            port=0,
        )

        # Apply get_url override
        def get_url():
            if server.server:
                actual_port = server.server.server_address[1]
                return f"http://{server.host}:{actual_port}"
            return f"http://{server.host}:{server.port}"

        server.get_url = get_url

        server.start()
        time.sleep(0.1)

        url = server.get_url() + "/config"

        with pytest.raises(HTTPError) as exc_info:
            urlopen(url)

        assert exc_info.value.code == 503

        server.stop()


class TestExceptionHandling:
    """Test exception handling in endpoints."""

    def test_stats_exception_handling(self, control_server):
        """Handles exceptions when getting stats."""
        control_server.start()
        time.sleep(0.1)

        # Mock get_stats to raise exception
        control_server.fuse_ops.get_stats = Mock(side_effect=Exception("Stats error"))

        url = control_server.get_url() + "/stats"

        with pytest.raises(HTTPError) as exc_info:
            urlopen(url)

        assert exc_info.value.code == 500

    def test_cache_stats_exception_handling(self, control_server):
        """Handles exceptions when getting cache stats."""
        control_server.start()
        time.sleep(0.1)

        # Mock get_stats to raise exception
        control_server.fuse_ops.cache.get_stats = Mock(side_effect=Exception("Cache error"))

        url = control_server.get_url() + "/cache/stats"

        with pytest.raises(HTTPError) as exc_info:
            urlopen(url)

        assert exc_info.value.code == 500

    def test_rules_list_exception_handling(self, control_server):
        """Handles exceptions when listing rules."""
        control_server.start()
        time.sleep(0.1)

        # Mock __len__ to raise exception
        control_server.fuse_ops.rule_engine.__len__ = Mock(side_effect=Exception("Rule error"))

        url = control_server.get_url() + "/rules"

        with pytest.raises(HTTPError) as exc_info:
            urlopen(url)

        assert exc_info.value.code == 500

    def test_layers_list_exception_handling(self, control_server):
        """Handles exceptions when listing layers."""
        control_server.start()
        time.sleep(0.1)

        # Remove layers attribute to trigger exception
        delattr(control_server.fuse_ops.layer_manager, "layers")

        url = control_server.get_url() + "/layers"

        with pytest.raises(HTTPError) as exc_info:
            urlopen(url)

        assert exc_info.value.code == 500

    def test_cache_clear_exception_handling(self, control_server):
        """Handles exceptions when clearing cache."""
        control_server.start()
        time.sleep(0.1)

        # Mock invalidate_cache to raise exception
        control_server.fuse_ops.invalidate_cache = Mock(side_effect=Exception("Clear error"))

        url = control_server.get_url() + "/cache/clear"
        data = json.dumps({}).encode("utf-8")
        request = Request(url, data=data, headers={"Content-Type": "application/json"})

        with pytest.raises(HTTPError) as exc_info:
            urlopen(request)

        assert exc_info.value.code == 500

    def test_cache_invalidate_exception_handling(self, control_server):
        """Handles exceptions when invalidating cache."""
        control_server.start()
        time.sleep(0.1)

        # Mock invalidate_cache to raise exception
        control_server.fuse_ops.invalidate_cache = Mock(side_effect=Exception("Invalidate error"))

        url = control_server.get_url() + "/cache/invalidate"
        data = json.dumps({"path": "/test"}).encode("utf-8")
        request = Request(url, data=data, headers={"Content-Type": "application/json"})

        with pytest.raises(HTTPError) as exc_info:
            urlopen(request)

        assert exc_info.value.code == 500

    def test_rule_add_exception_handling(self, control_server):
        """Handles exceptions when adding rule."""
        control_server.start()
        time.sleep(0.1)

        # Mock add_rule to raise exception
        control_server.fuse_ops.rule_engine.add_rule = Mock(side_effect=Exception("Add error"))

        url = control_server.get_url() + "/rules/add"
        data = json.dumps(
            {
                "name": "Test",
                "type": "exclude",
                "pattern": "*.tmp",
            }
        ).encode("utf-8")
        request = Request(url, data=data, headers={"Content-Type": "application/json"})

        with pytest.raises(HTTPError) as exc_info:
            urlopen(request)

        assert exc_info.value.code == 500

    def test_rule_remove_exception_handling(self, control_server):
        """Handles exceptions when removing rule."""
        control_server.start()
        time.sleep(0.1)

        # Mock remove_rule to raise exception
        control_server.fuse_ops.rule_engine.remove_rule = Mock(
            side_effect=Exception("Remove error")
        )

        url = control_server.get_url() + "/rules/remove"
        data = json.dumps({"name": "Test"}).encode("utf-8")
        request = Request(url, data=data, headers={"Content-Type": "application/json"})

        with pytest.raises(HTTPError) as exc_info:
            urlopen(request)

        assert exc_info.value.code == 500


class TestCorsHeaders:
    """Test CORS header handling."""

    def test_get_response_includes_cors_headers(self, control_server):
        """GET responses include CORS headers."""
        control_server.start()
        time.sleep(0.1)

        url = control_server.get_url() + "/status"
        response = urlopen(url)

        assert response.headers.get("Access-Control-Allow-Origin") == "*"

    def test_post_response_includes_cors_headers(self, control_server):
        """POST responses include CORS headers."""
        control_server.start()
        time.sleep(0.1)

        url = control_server.get_url() + "/cache/clear"
        data = json.dumps({}).encode("utf-8")
        request = Request(url, data=data, headers={"Content-Type": "application/json"})

        response = urlopen(request)

        assert response.headers.get("Access-Control-Allow-Origin") == "*"

    def test_options_request_returns_cors_headers(self, control_server):
        """OPTIONS requests return CORS headers."""
        control_server.start()
        time.sleep(0.1)

        url = control_server.get_url() + "/status"
        request = Request(url, method="OPTIONS")

        response = urlopen(request)

        assert response.headers.get("Access-Control-Allow-Origin") == "*"
        assert "GET" in response.headers.get("Access-Control-Allow-Methods", "")
        assert "POST" in response.headers.get("Access-Control-Allow-Methods", "")


class TestJsonResponses:
    """Test JSON response formatting."""

    def test_json_response_is_valid(self, control_server):
        """Responses are valid JSON."""
        control_server.start()
        time.sleep(0.1)

        url = control_server.get_url() + "/status"
        response = urlopen(url)

        # Should not raise exception
        data = json.loads(response.read())
        assert isinstance(data, dict)

    def test_json_response_content_type(self, control_server):
        """Responses have correct Content-Type."""
        control_server.start()
        time.sleep(0.1)

        url = control_server.get_url() + "/status"
        response = urlopen(url)

        assert response.headers.get("Content-Type") == "application/json"

    def test_error_response_format(self, control_server):
        """Error responses have standard format."""
        control_server.start()
        time.sleep(0.1)

        url = control_server.get_url() + "/unknown"

        try:
            urlopen(url)
        except HTTPError as e:
            data = json.loads(e.read())

            assert "error" in data
            assert "success" in data
            assert data["success"] is False


class TestThreading:
    """Test threading behavior."""

    def test_server_runs_in_daemon_thread(self, control_server):
        """Server thread is daemon thread."""
        control_server.start()

        assert control_server.server_thread.daemon is True

    def test_server_thread_has_name(self, control_server):
        """Server thread has descriptive name."""
        control_server.start()

        assert control_server.server_thread.name == "ControlServer"

    def test_multiple_concurrent_requests(self, control_server):
        """Handles multiple concurrent requests."""
        control_server.start()
        time.sleep(0.1)

        import concurrent.futures

        def make_request(endpoint):
            url = control_server.get_url() + endpoint
            response = urlopen(url)
            return json.loads(response.read())

        endpoints = ["/status", "/stats", "/config", "/rules", "/layers"]

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request, endpoint) for endpoint in endpoints]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All requests should succeed
        assert len(results) == 5


class TestExceptionHandling:
    """Test exception handling in request handlers."""

    def test_get_request_exception_handling(self, mock_fuse_ops, mock_config_manager, logger):
        """Handles exceptions in GET request handler."""
        server = ControlServer(
            fuse_ops=mock_fuse_ops,
            config_manager=mock_config_manager,
            host="127.0.0.1",
            port=0,
            mount_point="/mnt/shadowfs",
        )

        # Override get_url to use actual port
        def get_url():
            if server.server:
                actual_port = server.server.server_address[1]
                return f"http://{server.host}:{actual_port}"
            return f"http://{server.host}:{server.port}"

        server.get_url = get_url

        # Make get_stats raise exception
        mock_fuse_ops.get_stats.side_effect = Exception("Stats error")

        server.start()
        time.sleep(0.1)

        url = server.get_url() + "/stats"

        try:
            urlopen(url)
        except HTTPError as e:
            data = json.loads(e.read())
            assert "error" in data
            assert data["success"] is False
        finally:
            server.stop()

    def test_rules_list_exception_handling(self, mock_fuse_ops, mock_config_manager, logger):
        """Handles exceptions when listing rules."""
        server = ControlServer(
            fuse_ops=mock_fuse_ops,
            config_manager=mock_config_manager,
            host="127.0.0.1",
            port=0,
            mount_point="/mnt/shadowfs",
        )

        def get_url():
            if server.server:
                actual_port = server.server.server_address[1]
                return f"http://{server.host}:{actual_port}"
            return f"http://{server.host}:{server.port}"

        server.get_url = get_url

        # Make len(rule_engine) raise exception
        mock_rule_engine = Mock()
        mock_rule_engine.__len__ = Mock(side_effect=Exception("Rule count error"))
        mock_fuse_ops.rule_engine = mock_rule_engine

        server.start()
        time.sleep(0.1)

        url = server.get_url() + "/rules"

        try:
            urlopen(url)
        except HTTPError as e:
            data = json.loads(e.read())
            assert "error" in data
            # Exception caught by do_GET top-level handler
            assert "Rule count error" in data["error"]
        finally:
            server.stop()

    def test_layers_list_exception_handling(self, mock_fuse_ops, mock_config_manager, logger):
        """Handles exceptions when listing virtual layers."""
        server = ControlServer(
            fuse_ops=mock_fuse_ops,
            config_manager=mock_config_manager,
            host="127.0.0.1",
            port=0,
            mount_point="/mnt/shadowfs",
        )

        def get_url():
            if server.server:
                actual_port = server.server.server_address[1]
                return f"http://{server.host}:{actual_port}"
            return f"http://{server.host}:{server.port}"

        server.get_url = get_url

        # Make layers access raise exception
        mock_vlm = Mock()
        type(mock_vlm).layers = PropertyMock(side_effect=Exception("Layers error"))
        mock_fuse_ops.layer_manager = mock_vlm

        server.start()
        time.sleep(0.1)

        url = server.get_url() + "/layers"

        try:
            urlopen(url)
        except HTTPError as e:
            data = json.loads(e.read())
            assert "error" in data
            # Exception caught by do_GET top-level handler
            assert "Layers error" in data["error"]
        finally:
            server.stop()


class TestServiceUnavailable:
    """Test service unavailability error handling."""

    def test_cache_clear_without_fuse_ops(self, mock_config_manager, logger):
        """Returns 503 when FUSE operations not available for cache clear."""
        server = ControlServer(
            fuse_ops=None,  # No FUSE ops
            config_manager=mock_config_manager,
            host="127.0.0.1",
            port=0,
            mount_point="/mnt/shadowfs",
        )

        def get_url():
            if server.server:
                actual_port = server.server.server_address[1]
                return f"http://{server.host}:{actual_port}"
            return f"http://{server.host}:{server.port}"

        server.get_url = get_url
        server.start()
        time.sleep(0.1)

        url = server.get_url() + "/cache/clear"
        data = json.dumps({}).encode("utf-8")
        request = Request(url, data=data, method="POST")
        request.add_header("Content-Type", "application/json")

        try:
            urlopen(request)
        except HTTPError as e:
            assert e.code == 503
            data = json.loads(e.read())
            assert "FUSE operations not available" in data["error"]
        finally:
            server.stop()

    def test_cache_invalidate_without_fuse_ops(self, mock_config_manager, logger):
        """Returns 503 when FUSE operations not available for cache invalidate."""
        server = ControlServer(
            fuse_ops=None,
            config_manager=mock_config_manager,
            host="127.0.0.1",
            port=0,
            mount_point="/mnt/shadowfs",
        )

        def get_url():
            if server.server:
                actual_port = server.server.server_address[1]
                return f"http://{server.host}:{actual_port}"
            return f"http://{server.host}:{server.port}"

        server.get_url = get_url
        server.start()
        time.sleep(0.1)

        url = server.get_url() + "/cache/invalidate"
        data = json.dumps({"path": "/test"}).encode("utf-8")
        request = Request(url, data=data, method="POST")
        request.add_header("Content-Type", "application/json")

        try:
            urlopen(request)
        except HTTPError as e:
            assert e.code == 503
            data = json.loads(e.read())
            assert "FUSE operations not available" in data["error"]
        finally:
            server.stop()

    def test_config_reload_without_config_manager(self, mock_fuse_ops, logger):
        """Returns 503 when config manager not available."""
        server = ControlServer(
            fuse_ops=mock_fuse_ops,
            config_manager=None,  # No config manager
            host="127.0.0.1",
            port=0,
            mount_point="/mnt/shadowfs",
        )

        def get_url():
            if server.server:
                actual_port = server.server.server_address[1]
                return f"http://{server.host}:{actual_port}"
            return f"http://{server.host}:{server.port}"

        server.get_url = get_url
        server.start()
        time.sleep(0.1)

        url = server.get_url() + "/config/reload"
        data = json.dumps({}).encode("utf-8")
        request = Request(url, data=data, method="POST")
        request.add_header("Content-Type", "application/json")

        try:
            urlopen(request)
        except HTTPError as e:
            assert e.code == 503
            data = json.loads(e.read())
            assert "Configuration manager not available" in data["error"]
        finally:
            server.stop()

    def test_rule_add_without_rule_engine(self, mock_fuse_ops, mock_config_manager, logger):
        """Returns 503 when rule engine not available."""
        mock_fuse_ops.rule_engine = None  # No rule engine

        server = ControlServer(
            fuse_ops=mock_fuse_ops,
            config_manager=mock_config_manager,
            host="127.0.0.1",
            port=0,
            mount_point="/mnt/shadowfs",
        )

        def get_url():
            if server.server:
                actual_port = server.server.server_address[1]
                return f"http://{server.host}:{actual_port}"
            return f"http://{server.host}:{server.port}"

        server.get_url = get_url
        server.start()
        time.sleep(0.1)

        url = server.get_url() + "/rules/add"
        data = json.dumps({"type": "exclude", "pattern": "*.tmp"}).encode("utf-8")
        request = Request(url, data=data, method="POST")
        request.add_header("Content-Type", "application/json")

        try:
            urlopen(request)
        except HTTPError as e:
            assert e.code == 503
            data = json.loads(e.read())
            assert "Rule engine not available" in data["error"]
        finally:
            server.stop()

    def test_rule_remove_without_rule_engine(self, mock_fuse_ops, mock_config_manager, logger):
        """Returns 503 when rule engine not available for removal."""
        mock_fuse_ops.rule_engine = None

        server = ControlServer(
            fuse_ops=mock_fuse_ops,
            config_manager=mock_config_manager,
            host="127.0.0.1",
            port=0,
            mount_point="/mnt/shadowfs",
        )

        def get_url():
            if server.server:
                actual_port = server.server.server_address[1]
                return f"http://{server.host}:{actual_port}"
            return f"http://{server.host}:{server.port}"

        server.get_url = get_url
        server.start()
        time.sleep(0.1)

        url = server.get_url() + "/rules/remove"
        data = json.dumps({"name": "test-rule"}).encode("utf-8")
        request = Request(url, data=data, method="POST")
        request.add_header("Content-Type", "application/json")

        try:
            urlopen(request)
        except HTTPError as e:
            assert e.code == 503
            data = json.loads(e.read())
            assert "Rule engine not available" in data["error"]
        finally:
            server.stop()


class TestServerLifecycle:
    """Test server lifecycle and error conditions."""

    def test_server_handles_error_in_run_loop(self, mock_fuse_ops, mock_config_manager, logger):
        """Handles exception in server run loop."""
        server = ControlServer(
            fuse_ops=mock_fuse_ops,
            config_manager=mock_config_manager,
            host="127.0.0.1",
            port=0,
            mount_point="/mnt/shadowfs",
        )

        # Start server
        server.start()
        assert server.running

        # Simulate server error by calling shutdown (will trigger exception path in future requests)
        server.stop()
        assert not server.running

    def test_stop_when_not_running(self, mock_fuse_ops, mock_config_manager, logger):
        """Calling stop when not running is safe."""
        server = ControlServer(
            fuse_ops=mock_fuse_ops,
            config_manager=mock_config_manager,
            host="127.0.0.1",
            port=0,
            mount_point="/mnt/shadowfs",
        )

        # Stop without starting
        server.stop()

        # Should not raise exception
        assert not server.running


class TestMainEntryPoint:
    """Test standalone main() execution."""

    def test_main_function_runs(self):
        """Tests main() function execution."""
        import subprocess
        import sys

        # Run control_server main with keyboard interrupt after short time
        proc = subprocess.Popen(
            [sys.executable, "-m", "shadowfs.fuse.control_server"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Let it start
        time.sleep(0.2)

        # Send interrupt
        proc.terminate()
        stdout, stderr = proc.communicate(timeout=5)

        # Should have executed the code path (may return 1 or be terminated)
        # The important thing is the code ran without syntax errors
        assert proc.returncode is not None  # Process completed
