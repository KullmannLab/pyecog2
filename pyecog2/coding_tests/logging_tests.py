
import os
import importlib.resources
from pyecog2.coding_tests.logging_tests_submodule import test_function
import logging

log_fname = str(importlib.resources.files('pyecog2') /'pyecog.log')

try:
    os.remove(log_fname)
except:
    pass

logging.basicConfig(filename=log_fname, level=logging.DEBUG)
logging.debug('This message should go to the log file')
logging.info('So should this')
logging.warning('And this, too')
logging.error('And non-ASCII stuff, too, like Øresund and Malmö')

test_function()