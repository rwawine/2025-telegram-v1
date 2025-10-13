"""Direct Flask server runner using environment variables."""

from __future__ import annotations

import os
from web import create_app
from config import load_config

if __name__ == "__main__":
    # Load configuration
    config = load_config()
    
    # Create Flask application
    app = create_app(config)
    
    # Get host and port from environment variables with defaults
    host = os.getenv("WEB_HOST", "0.0.0.0")
    port = int(os.getenv("WEB_PORT", "5000"))
    
    # Run Flask server
    app.run(host=host, port=port, debug=config.debug)
