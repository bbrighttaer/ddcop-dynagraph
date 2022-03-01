import os
import logging

LOGGING_LEVEL = logging.INFO


def get_logger(name, prefix=None):
    if prefix:
        prefix = prefix.strip() + ' '
    else:
        prefix = ''

    os.makedirs('logs/', exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(LOGGING_LEVEL)

    # create handlers
    c_handler = logging.StreamHandler()
    f_handler = logging.FileHandler(f'logs/{name}.log')
    c_handler.setLevel(logging.DEBUG)
    f_handler.setLevel(logging.ERROR)

    # create formatters
    c_format = logging.Formatter(f'[%(asctime)s] {prefix}%(name)s - %(levelname)s - %(message)s')
    f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # add formatters to handlers
    c_handler.setFormatter(c_format)
    f_handler.setFormatter(f_format)

    # add handlers to logger
    logger.addHandler(c_handler)
    logger.addHandler(f_handler)

    return logger
