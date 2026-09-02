import logging
import os
import sys

def setup_logger():
    if not os.path.exists('logs'):
        os.makedirs('logs')
        
    auth_logger = logging.getLogger('AuthServiceLogger')
    auth_logger.setLevel(logging.DEBUG)
    
    # File handler (save disk logs)
    file_handler = logging.FileHandler('logs/auth_service.log')
    file_handler.setLevel(logging.INFO)
    
    # Console handler (so Kubernetes can see the logs)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    formatter = logging.Formatter('%(asctime)s | %(levelname)-8s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    if not auth_logger.handlers:
        auth_logger.addHandler(file_handler)
        auth_logger.addHandler(console_handler)
        
    return auth_logger