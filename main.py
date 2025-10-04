"""Application entry point."""

from __future__ import annotations

import asyncio
import logging

from core import setup_logger, ApplicationInitializer
from services import set_main_loop

# Setup logging
logger = setup_logger(
    name="app",
    level=logging.INFO,
    log_file="logs/app.log",
    colored=True
)


async def main() -> None:
    """Main application entry point."""
    # Set event loop for services
    loop = asyncio.get_running_loop()
    set_main_loop(loop)
    
    # Initialize and run application
    app = ApplicationInitializer()
    await app.initialize()
    await app.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Application failed: {e}", exc_info=True)
