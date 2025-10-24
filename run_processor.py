#!/usr/bin/env python3
"""
Automatic Processor Runner
Finds the latest promo folder and processes it with Ren3 agent
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)-8s %(message)s'
)
logger = logging.getLogger(__name__)


def get_latest_promo_folder():
    """Get the most recent promo folder"""
    output_dir = Path('/app/output')
    
    promo_folders = list(output_dir.glob('promo_*'))
    
    if not promo_folders:
        logger.warning("No promo folders found")
        return None
    
    # Sort by modification time (most recent first)
    promo_folders.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    
    latest = promo_folders[0]
    logger.info(f"Found latest promo folder: {latest.name}")
    
    return latest


def check_if_already_processed(promo_folder):
    """Check if this folder has already been processed"""
    processed_dir = Path('/app/processed') / promo_folder.name
    
    if processed_dir.exists():
        # Check if final Excel exists
        excel_files = list(processed_dir.glob('final_analysis_*.xlsx'))
        if excel_files:
            logger.info(f"Folder already processed: {excel_files[0].name}")
            return True
    
    return False


def main():
    logger.info("=" * 60)
    logger.info("AUTOMATIC PROCESSOR RUNNER")
    logger.info("=" * 60)
    logger.info(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Get latest folder
    promo_folder = get_latest_promo_folder()
    
    if not promo_folder:
        logger.error("No promo folders to process")
        sys.exit(1)
    
    # Check if already processed
    if check_if_already_processed(promo_folder):
        logger.info("Folder already processed. Skipping.")
        sys.exit(0)
    
    # Import and run processor
    logger.info(f"Processing: {promo_folder.name}")
    
    try:
        from ren3_processor import Ren3Config, Ren3AgentProcessor
        
        config = Ren3Config()
        processor = Ren3AgentProcessor(config)
        
        result = processor.process_promo_folder(str(promo_folder))
        
        if result:
            logger.info("=" * 60)
            logger.info("PROCESSING COMPLETE!")
            logger.info(f"Final output: {result}")
            logger.info("=" * 60)
            sys.exit(0)
        else:
            logger.error("Processing failed")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()