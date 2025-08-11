#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AISEG2 → MQTT Publisher - Continuous execution wrapper
Runs aiseg2_publish.py at specified intervals with robust error handling
"""

import os
import sys
import time
import signal
import logging
import traceback
from datetime import datetime

from dotenv import load_dotenv

# Import the main publish function
from aiseg2_publish import main as publish_main

# ----- .env -----
load_dotenv(dotenv_path=os.getenv("AISEG2_ENV_FILE", ".env"))

# ----- Settings -----
INTERVAL_SECONDS = int(os.getenv("INTERVAL_SECONDS", "300"))  # Default: 5 minutes
MAX_CONSECUTIVE_ERRORS = int(os.getenv("MAX_CONSECUTIVE_ERRORS", "10"))
ERROR_RETRY_DELAY = int(os.getenv("ERROR_RETRY_DELAY", "60"))  # Delay after error
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ----- Logging setup -----
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("aiseg2mqtt.main")

# ----- Global state -----
should_exit = False
consecutive_errors = 0

def signal_handler(signum, _frame):
    """Handle shutdown signals gracefully"""
    global should_exit
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    should_exit = True

def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown"""
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Handle SIGHUP to reload config (future enhancement)
    if hasattr(signal, 'SIGHUP'):
        signal.signal(signal.SIGHUP, signal_handler)

def run_publish_cycle() -> bool:
    """
    Run one publish cycle
    Returns: True if successful, False if error occurred
    """
    try:
        logger.info("Starting data collection and publish cycle")
        start_time = time.time()
        
        # Run the publish function
        publish_main()
        
        elapsed = time.time() - start_time
        logger.info(f"Publish cycle completed successfully in {elapsed:.1f}s")
        return True
        
    except KeyboardInterrupt:
        # Re-raise to handle in main loop
        raise
    except Exception as e:
        logger.error(f"Error during publish cycle: {type(e).__name__}: {e}")
        logger.debug(traceback.format_exc())
        return False

def calculate_next_run_time(last_run: float, interval: int) -> float:
    """Calculate the next run time to maintain consistent intervals"""
    next_run = last_run + interval
    now = time.time()
    
    # If we're already past the next run time, schedule immediately
    if next_run <= now:
        return now
    
    return next_run

def sleep_until(target_time: float) -> bool:
    """
    Sleep until target time, checking for exit signals
    Returns: True if sleep completed, False if interrupted
    """
    while time.time() < target_time:
        if should_exit:
            return False
        
        # Sleep in small chunks to respond quickly to signals
        sleep_time = min(1.0, target_time - time.time())
        if sleep_time > 0:
            time.sleep(sleep_time)
    
    return True

def main():
    """Main entry point for continuous execution"""
    global consecutive_errors
    
    logger.info(f"AISEG2 MQTT Publisher starting (interval: {INTERVAL_SECONDS}s)")
    logger.info(f"Press Ctrl+C to stop")
    
    setup_signal_handlers()
    
    # Run immediately on startup
    last_run_time = 0
    
    while not should_exit:
        try:
            # Run the publish cycle
            success = run_publish_cycle()
            
            if success:
                consecutive_errors = 0
                last_run_time = time.time()
                
                # Calculate next run time
                next_run = calculate_next_run_time(last_run_time, INTERVAL_SECONDS)
                wait_seconds = next_run - time.time()
                
                if wait_seconds > 0:
                    logger.info(f"Next run scheduled in {wait_seconds:.0f}s at {datetime.fromtimestamp(next_run).strftime('%H:%M:%S')}")
                    
                    # Sleep until next run
                    if not sleep_until(next_run):
                        break
            else:
                consecutive_errors += 1
                logger.warning(f"Consecutive errors: {consecutive_errors}/{MAX_CONSECUTIVE_ERRORS}")
                
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    logger.error(f"Maximum consecutive errors ({MAX_CONSECUTIVE_ERRORS}) reached, exiting")
                    sys.exit(1)
                
                # Wait before retry
                logger.info(f"Waiting {ERROR_RETRY_DELAY}s before retry...")
                if not sleep_until(time.time() + ERROR_RETRY_DELAY):
                    break
                    
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
            break
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}")
            logger.debug(traceback.format_exc())
            consecutive_errors += 1
            
            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                logger.error(f"Maximum consecutive errors ({MAX_CONSECUTIVE_ERRORS}) reached, exiting")
                sys.exit(1)
            
            # Wait before retry
            if not sleep_until(time.time() + ERROR_RETRY_DELAY):
                break
    
    logger.info("AISEG2 MQTT Publisher stopped")

if __name__ == "__main__":
    main()