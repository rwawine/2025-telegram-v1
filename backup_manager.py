#!/usr/bin/env python3
"""Manual backup management script."""

import argparse
import sys
import asyncio
from pathlib import Path
from services.backup_service import BackupService


def create_backup(args):
    """Create a manual backup."""
    backup_service = BackupService(
        db_path=args.db_path,
        backup_dir=args.backup_dir,
        max_age_days=args.max_age_days,
        compress=args.compress
    )
    
    print("Creating manual backup...")
    success = backup_service.create_full_backup()
    
    if success:
        print("Backup created successfully!")
        return 0
    else:
        print("Backup failed!")
        return 1


def list_backups(args):
    """List existing backups."""
    backup_service = BackupService(
        db_path=args.db_path,
        backup_dir=args.backup_dir,
        max_age_days=args.max_age_days,
        compress=args.compress
    )
    
    info = backup_service.get_backup_info()
    
    if info.get("error"):
        print(f"Error: {info['error']}")
        return 1
    
    print(f"Backup Statistics:")
    print(f"   Total backups: {info['backup_count']}")
    print(f"   Total size: {info['total_size_mb']} MB")
    print(f"   Max age: {info.get('max_age_days', 2)} days")
    print(f"   Expired backups: {info.get('expired_count', 0)}")
    print(f"   Latest backup: {info['latest_backup'] or 'None'}")
    print(f"   Oldest backup: {info['oldest_backup'] or 'None'}")
    
    if info['backup_files']:
        print(f"\nBackup Files:")
        for backup in info['backup_files']:
            size_str = f"{backup['size'] / (1024*1024):.1f} MB" if backup['size'] > 1024*1024 else f"{backup['size'] / 1024:.1f} KB"
            expires_indicator = " (expires soon)" if backup.get('expires_soon') else ""
            print(f"   {backup['name']} - {size_str} - {backup['age_days']} days old{expires_indicator}")
    
    return 0


def cleanup_backups(args):
    """Cleanup old backups."""
    backup_service = BackupService(
        db_path=args.db_path,
        backup_dir=args.backup_dir,
        max_age_days=args.max_age_days,
        compress=args.compress
    )
    
    print("Cleaning up old backups...")
    backup_service.cleanup_old_backups()
    print("Cleanup completed!")
    return 0


async def test_service(args):
    """Test backup service functionality."""
    backup_service = BackupService(
        db_path=args.db_path,
        backup_dir=args.backup_dir,
        max_age_days=1,  # 1 day for testing
        backup_interval_hours=0.001,  # Very short interval for testing
        compress=args.compress
    )
    
    print("Testing backup service...")
    
    # Start service
    await backup_service.start()
    print("Service started")
    
    # Wait a bit
    await asyncio.sleep(2)
    
    # Check if backup was created
    info = backup_service.get_backup_info()
    print(f"Backups created: {info['backup_count']}")
    
    # Stop service
    await backup_service.stop()
    print("Service stopped")
    
    return 0


def main():
    parser = argparse.ArgumentParser(description="Backup Management Tool")
    parser.add_argument("--db-path", default="data/lottery_bot.sqlite", help="Database path")
    parser.add_argument("--backup-dir", default="backups", help="Backup directory")
    parser.add_argument("--max-age-days", type=int, default=2, help="Maximum age of backups in days")
    parser.add_argument("--compress", action="store_true", default=True, help="Compress backups")
    parser.add_argument("--no-compress", action="store_false", dest="compress", help="Don't compress backups")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Create backup command
    create_parser = subparsers.add_parser("create", help="Create a manual backup")
    create_parser.set_defaults(func=create_backup)
    
    # List backups command
    list_parser = subparsers.add_parser("list", help="List existing backups")
    list_parser.set_defaults(func=list_backups)
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser("cleanup", help="Cleanup old backups")
    cleanup_parser.set_defaults(func=cleanup_backups)
    
    # Test command
    test_parser = subparsers.add_parser("test", help="Test backup service")
    test_parser.set_defaults(func=test_service)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        if args.command == "test":
            return asyncio.run(args.func(args))
        else:
            return args.func(args)
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
