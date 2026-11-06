import sys
import logging
import importlib.resources
from datetime import datetime

# Module-level variable to track if logging has been configured
_logging_configured = False


def setup_logging(log_level=logging.DEBUG, console_level=logging.WARNING):
    """
    Configure centralized logging for the entire pyecog2 application.
    
    This function should be called once at application startup (in main.py).
    All other modules should simply use:
        import logging
        logger = logging.getLogger(__name__)
    
    The root logger is configured to write to 'pyecog.log' file, so all child
    loggers (modules using __name__) will automatically inherit this configuration.
    
    Args:
        log_level: The logging level for the file handler (default: DEBUG)
        console_level: The logging level for console output (default: WARNING)
    
    Returns:
        tuple: (log_filename, logger) - the log file path and the root logger
    """
    global _logging_configured
    
    if _logging_configured:
        return None, logging.getLogger('pyecog2')
    
    # Get log file path within the pyecog2 package
    log_fname = importlib.resources.files('pyecog2').parent / 'pyecog.log'
    print('Log filename:', log_fname)
    
    # Configure the root logger with file handler
    # Using force=True to ensure reconfiguration if needed (Python 3.8+)
    logging.basicConfig(
        filename=log_fname,
        filemode='w',
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Get the root pyecog2 logger
    logger = logging.getLogger('pyecog2')
    logger.setLevel(log_level)
    
    # Add console handler for warnings and above
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    logger.info(f'Session start: {datetime.now()}')
    
    _logging_configured = True
    
    return log_fname, logger


def get_logger(name):
    """
    Get a logger for a module.
    
    This is a convenience function that ensures consistent logger naming.
    Modules should use this at the top of the file:
        from pyecog2.logging_aux import get_logger
        logger = get_logger(__name__)
    
    Or simply use the standard approach:
        import logging
        logger = logging.getLogger(__name__)
    
    Both approaches work identically since setup_logging configures the root logger.
    
    Args:
        name: The module name (typically __name__)
    
    Returns:
        logging.Logger: A logger instance for the module
    """
    return logging.getLogger(name)


class LoggerWriter:
    def __init__(self, logfct):
        self.logfct = logfct
        self.buf = []

    def write(self, msg):
        if msg.endswith('\n'):
            self.buf.append(msg.rstrip('\n'))
            self.logfct(''.join(self.buf))
            self.buf = []
        else:
            self.buf.append(msg)

    def flush(self):
        pass
