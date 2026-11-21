import os
import json
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

logger = logging.getLogger("health_server")

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        payload = {
            "status": "healthy",
            "service": "slack-auto-reply-bot",
            "mode": "socket_mode"
        }
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def log_message(self, format, *args):
        # Silence routine access logs
        pass

def start_health_server(port: int = 8080):
    """Starts a non-blocking background HTTP server for cloud health checks."""
    try:
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True, name="health-http-server")
        thread.start()
        logger.info(f"🌐 Cloud HTTP health-check server running on port {port}")
    except Exception as e:
        logger.warning(f"Could not start HTTP health server on port {port}: {e}")
