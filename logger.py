import logging, configparser
from systemd.journal import JournaldLogHandler

config = configparser.ConfigParser()
# config.read('wxconf.ini')
# log_level = config['bme280']['log_level']
def log(message, level="info"):
    # get an instance of the logger object this module will use
    logger = logging.getLogger(__name__)
    # instantiate the JournaldLogHandler to hook into systemd
    journald_handler = JournaldLogHandler()
    # set a formatter to include the level name
    journald_handler.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
    # add the journald handler to the current logger
    logger.addHandler(journald_handler)
    if level == "info":
        logger.info(message)
    elif level == "debug":
        logger.debug(message)
    elif level == "error":
        logger.error(message)
    elif level == "warn":
        logging.warn(message)
    elif level == "critical":
        logging.critical(message)