import sys
import logging

# class DefaultStreamHandler(logging.StreamHandler):
#     def __init__(self, stream=sys.__stdout__):
#         # Use the original sys.__stdout__ to write to stdout
#         # for this handler, as sys.stdout will write out to logger.
#         super().__init__(stream)

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
