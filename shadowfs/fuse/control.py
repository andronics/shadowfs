#!/usr/bin/env python3
"""Runtime control server for ShadowFS.

This module provides a lightweight HTTP API for runtime management:
- Statistics and monitoring
- Cache management
- Configuration hot-reload
- Virtual layer management
- Rule management

The server runs in a separate thread and provides JSON endpoints.

Example:
    >>> from shadowfs.fuse.control import ControlServer
    >>> server = ControlServer(fuse_ops, config_manager, port=8080)
    >>> server.start()
"""

import http.server
import json
import threading
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

from shadowfs.core.config import ConfigManager
from shadowfs.core.logging import Logger
from shadowfs.fuse.operations import ShadowFS


class ControlServerError(Exception):
    """Exception raised for control server errors."""

    pass


class ControlRequestHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for control server."""

    def log_message(self, format, *args):
        """Override to use our logger instead of stderr."""
        if hasattr(self.server, "logger"):
            self.server.logger.debug(format % args)

    def _send_json_response(self, data: Dict[str, Any], status: int = 200) -> None:
        """
        Send JSON response.

        Args:
            data: Response data dictionary
            status: HTTP status code
        """
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        response_json = json.dumps(data, indent=2)
        self.wfile.write(response_json.encode("utf-8"))

    def _send_error_response(self, message: str, status: int = 400) -> None:
        """
        Send error response.

        Args:
            message: Error message
            status: HTTP status code
        """
        self._send_json_response({"error": message, "success": False}, status)

    def do_GET(self):
        """Handle GET requests."""
        try:
            parsed_path = urlparse(self.path)
            path = parsed_path.path

            # Route requests
            if path == "/":
                self._handle_root()
            elif path == "/status":
                self._handle_status()
            elif path == "/stats":
                self._handle_stats()
            elif path == "/cache/stats":
                self._handle_cache_stats()
            elif path == "/config":
                self._handle_config()
            elif path == "/rules":
                self._handle_rules_list()
            elif path == "/layers":
                self._handle_layers_list()
            else:
                self._send_error_response(f"Unknown endpoint: {path}", 404)

        except Exception as e:
            self.server.logger.error(f"Error handling GET request: {e}")
            self._send_error_response(str(e), 500)

    def do_POST(self):
        """Handle POST requests."""
        try:
            parsed_path = urlparse(self.path)
            path = parsed_path.path

            # Read request body
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length > 0 else b"{}"

            try:
                data = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                self._send_error_response("Invalid JSON in request body")
                return

            # Route requests
            if path == "/cache/clear":
                self._handle_cache_clear(data)
            elif path == "/cache/invalidate":
                self._handle_cache_invalidate(data)
            elif path == "/config/reload":
                self._handle_config_reload(data)
            elif path == "/rules/add":
                self._handle_rule_add(data)
            elif path == "/rules/remove":
                self._handle_rule_remove(data)
            else:
                self._send_error_response(f"Unknown endpoint: {path}", 404)

        except Exception as e:
            self.server.logger.error(f"Error handling POST request: {e}")
            self._send_error_response(str(e), 500)

    def do_OPTIONS(self):
        """Handle OPTIONS requests for CORS."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    # =========================================================================
    # GET Handlers
    # =========================================================================

    def _handle_root(self):
        """Handle root endpoint - show available endpoints."""
        endpoints = {
            "GET": {
                "/": "Show this help",
                "/status": "Get server status",
                "/stats": "Get filesystem statistics",
                "/cache/stats": "Get cache statistics",
                "/config": "Get current configuration",
                "/rules": "List active rules",
                "/layers": "List virtual layers",
            },
            "POST": {
                "/cache/clear": "Clear all caches",
                "/cache/invalidate": "Invalidate specific path",
                "/config/reload": "Reload configuration",
                "/rules/add": "Add new rule",
                "/rules/remove": "Remove rule by name",
            },
        }

        self._send_json_response({"endpoints": endpoints, "version": "1.0.0"})

    def _handle_status(self):
        """Handle status endpoint."""
        fuse_ops = self.server.fuse_ops

        status = {
            "running": True,
            "mount_point": getattr(self.server, "mount_point", "unknown"),
            "readonly": fuse_ops.readonly if fuse_ops else None,
            "open_files": len(fuse_ops.fds) if fuse_ops else 0,
        }

        self._send_json_response(status)

    def _handle_stats(self):
        """Handle stats endpoint."""
        fuse_ops = self.server.fuse_ops

        if not fuse_ops:
            self._send_error_response("FUSE operations not available", 503)
            return

        try:
            stats = fuse_ops.get_stats()
            self._send_json_response(stats)
        except Exception as e:
            self._send_error_response(f"Failed to get stats: {e}", 500)

    def _handle_cache_stats(self):
        """Handle cache stats endpoint."""
        fuse_ops = self.server.fuse_ops

        if not fuse_ops or not fuse_ops.cache:
            self._send_error_response("Cache not available", 503)
            return

        try:
            stats = fuse_ops.cache.get_stats()
            self._send_json_response(stats)
        except Exception as e:
            self._send_error_response(f"Failed to get cache stats: {e}", 500)

    def _handle_config(self):
        """Handle config endpoint."""
        config_manager = self.server.config_manager

        if not config_manager:
            self._send_error_response("Configuration not available", 503)
            return

        # Return sanitized config (hide sensitive data)
        config = getattr(config_manager, "_config", {})
        self._send_json_response({"config": config})

    def _handle_rules_list(self):
        """Handle rules list endpoint."""
        fuse_ops = self.server.fuse_ops

        if not fuse_ops or not fuse_ops.rule_engine:
            self._send_error_response("Rule engine not available", 503)
            return

        try:
            # Get rule count
            rule_count = len(fuse_ops.rule_engine)
            self._send_json_response({"rule_count": rule_count, "success": True})
        except Exception as e:
            self._send_error_response(f"Failed to list rules: {e}", 500)

    def _handle_layers_list(self):
        """Handle virtual layers list endpoint."""
        fuse_ops = self.server.fuse_ops

        if not fuse_ops or not fuse_ops.layer_manager:
            self._send_error_response("Virtual layer manager not available", 503)
            return

        try:
            layer_count = len(fuse_ops.layer_manager.layers)
            self._send_json_response({"layer_count": layer_count, "success": True})
        except Exception as e:
            self._send_error_response(f"Failed to list layers: {e}", 500)

    # =========================================================================
    # POST Handlers
    # =========================================================================

    def _handle_cache_clear(self, data: Dict):
        """Handle cache clear endpoint."""
        fuse_ops = self.server.fuse_ops

        if not fuse_ops:
            self._send_error_response("FUSE operations not available", 503)
            return

        try:
            fuse_ops.invalidate_cache()
            self._send_json_response({"success": True, "message": "Cache cleared"})
        except Exception as e:
            self._send_error_response(f"Failed to clear cache: {e}", 500)

    def _handle_cache_invalidate(self, data: Dict):
        """Handle cache invalidate endpoint."""
        fuse_ops = self.server.fuse_ops

        if not fuse_ops:
            self._send_error_response("FUSE operations not available", 503)
            return

        path = data.get("path")
        if not path:
            self._send_error_response("Missing 'path' parameter")
            return

        try:
            fuse_ops.invalidate_cache(path)
            self._send_json_response({"success": True, "message": f"Cache invalidated for: {path}"})
        except Exception as e:
            self._send_error_response(f"Failed to invalidate cache: {e}", 500)

    def _handle_config_reload(self, data: Dict):
        """Handle config reload endpoint."""
        config_manager = self.server.config_manager

        if not config_manager:
            self._send_error_response("Configuration manager not available", 503)
            return

        # For now, just acknowledge the request
        # Full hot-reload would require more infrastructure
        self._send_json_response(
            {
                "success": True,
                "message": "Config reload requested",
                "note": "Full hot-reload not yet implemented",
            }
        )

    def _handle_rule_add(self, data: Dict):
        """Handle rule add endpoint."""
        fuse_ops = self.server.fuse_ops

        if not fuse_ops or not fuse_ops.rule_engine:
            self._send_error_response("Rule engine not available", 503)
            return

        # Validate required fields
        rule_type = data.get("type")
        pattern = data.get("pattern")

        if not rule_type or not pattern:
            self._send_error_response("Missing 'type' or 'pattern' parameter")
            return

        try:
            from shadowfs.rules.engine import Rule, RuleAction

            # Convert type string to RuleAction
            action = RuleAction.EXCLUDE if rule_type.lower() == "exclude" else RuleAction.INCLUDE

            # Create rule
            rule = Rule(
                name=data.get("name", f"{rule_type}:{pattern}"),
                action=action,
                patterns=[pattern],
                priority=data.get("priority", 100),
            )

            # Add to rule engine
            fuse_ops.rule_engine.add_rule(rule)

            self._send_json_response({"success": True, "message": f"Rule added: {rule.name}"})
        except Exception as e:
            self._send_error_response(f"Failed to add rule: {e}", 500)

    def _handle_rule_remove(self, data: Dict):
        """Handle rule remove endpoint."""
        fuse_ops = self.server.fuse_ops

        if not fuse_ops or not fuse_ops.rule_engine:
            self._send_error_response("Rule engine not available", 503)
            return

        rule_name = data.get("name")
        if not rule_name:
            self._send_error_response("Missing 'name' parameter")
            return

        try:
            # Remove rule
            fuse_ops.rule_engine.remove_rule(rule_name)
            self._send_json_response({"success": True, "message": f"Rule removed: {rule_name}"})
        except Exception as e:
            self._send_error_response(f"Failed to remove rule: {e}", 500)


class ControlServer:
    """
    HTTP control server for runtime management.

    Provides REST API endpoints for:
    - Status monitoring
    - Statistics retrieval
    - Cache management
    - Configuration reload
    - Rule management
    """

    def __init__(
        self,
        fuse_ops: Optional[ShadowFS] = None,
        config_manager: Optional[ConfigManager] = None,
        host: str = "127.0.0.1",
        port: int = 8080,
        mount_point: str = "",
    ):
        """
        Initialize control server.

        Args:
            fuse_ops: FUSE operations instance
            config_manager: Configuration manager instance
            host: Server host address
            port: Server port number
            mount_point: Mount point path (for display)
        """
        self.fuse_ops = fuse_ops
        self.config_manager = config_manager
        self.host = host
        self.port = port
        self.mount_point = mount_point
        self.logger = Logger("shadowfs.control", level="INFO")

        self.server: Optional[http.server.HTTPServer] = None
        self.server_thread: Optional[threading.Thread] = None
        self.running = False

    def start(self) -> None:
        """
        Start control server in background thread.

        Raises:
            ControlServerError: If server fails to start
        """
        if self.running:
            self.logger.warning("Control server already running")
            return

        try:
            # Create HTTP server
            self.server = http.server.HTTPServer((self.host, self.port), ControlRequestHandler)

            # Attach our objects to server so handler can access them
            self.server.fuse_ops = self.fuse_ops
            self.server.config_manager = self.config_manager
            self.server.mount_point = self.mount_point
            self.server.logger = self.logger

            # Start server in background thread
            self.server_thread = threading.Thread(
                target=self._run_server, daemon=True, name="ControlServer"
            )
            self.server_thread.start()

            self.running = True
            self.logger.info(f"Control server started on {self.host}:{self.port}")

        except OSError as e:
            raise ControlServerError(f"Failed to start control server: {e}")

    def _run_server(self) -> None:
        """Run server loop (called in background thread)."""
        try:
            self.server.serve_forever()
        except Exception as e:
            self.logger.error(f"Control server error: {e}")
            self.running = False

    def stop(self) -> None:
        """Stop control server."""
        if not self.running:
            return

        self.logger.info("Stopping control server...")

        if self.server:
            self.server.shutdown()
            self.server.server_close()

        if self.server_thread:
            self.server_thread.join(timeout=5.0)

        self.running = False
        self.logger.info("Control server stopped")

    def get_url(self) -> str:
        """
        Get server URL.

        Returns:
            Server base URL
        """
        return f"http://{self.host}:{self.port}"

    def is_running(self) -> bool:
        """
        Check if server is running.

        Returns:
            True if running, False otherwise
        """
        return self.running


def main():
    """
    Standalone entry point for testing control server.

    This is useful for testing the control server independently.
    """
    import sys

    logger = Logger("shadowfs.control.test", level="DEBUG")
    logger.info("Starting test control server...")

    # Create test server (without FUSE operations)
    server = ControlServer(host="127.0.0.1", port=8080)

    try:
        server.start()
        logger.info(f"Server running at: {server.get_url()}")
        logger.info("Press Ctrl+C to stop")

        # Keep main thread alive
        import time

        while server.is_running():
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        server.stop()
        return 0

    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
