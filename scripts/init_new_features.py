#!/usr/bin/env python3
"""Initialize database tables for new features."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core import get_logger
from services import (
    ensure_registration_table,
    ensure_analytics_table,
)

logger = get_logger(__name__)


async def init_new_tables():
    """Initialize all new feature tables."""
    logger.info("Initializing new feature tables...")
    
    try:
        # Registration state management
        logger.info("Creating registration_states table...")
        await ensure_registration_table()
        
        # Analytics events
        logger.info("Creating analytics_events table...")
        await ensure_analytics_table()
        
        logger.info("✅ All new tables initialized successfully!")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize tables: {e}", exc_info=True)
        return False


async def main():
    """Main entry point."""
    success = await init_new_tables()
    
    if success:
        print("\n✅ New features initialized successfully!")
        print("\nNew capabilities added:")
        print("  1. ✅ Ticket status notifications")
        print("  2. ✅ Registration confirmation with auto-save")
        print("  3. ✅ Photo upload with retry mechanism")
        print("  4. ✅ Analytics event tracking")
        print("  5. ✅ User personalization")
        print("\nYou can now use these features in your bot!")
        return 0
    else:
        print("\n❌ Failed to initialize new features")
        print("Check logs for details")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

