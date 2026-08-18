import logging
import os

def setup_logger():
    if not os.path.exists('logs'):
        os.makedirs('logs')
    auth_logger = logging.getLogger('AuthServiceLogger')
    auth_logger.setLevel(logging.DEBUG)
    file_handler = logging.FileHandler('logs/auth_service.log')
    file_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s | %(levelname)-8s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(formatter)
    if not auth_logger.handlers:
        auth_logger.addHandler(file_handler)
    return auth_logger
