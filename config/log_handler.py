import os
import time
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler


class DailyRotatingFileHandler(TimedRotatingFileHandler):
    """
    Writes to logs/<prefix>_YYYY-MM-DD.log.
    On midnight rollover, opens a new file for the new date automatically.
    """

    def __init__(self, log_dir: str, prefix: str, backup_count: int = 30, encoding: str = 'utf-8'):
        self.log_dir = log_dir
        self.prefix = prefix
        filename = self._dated_filename()
        super().__init__(
            filename,
            when='midnight',
            interval=1,
            backupCount=backup_count,
            encoding=encoding,
            delay=False,
        )

    def _dated_filename(self) -> str:
        date_str = datetime.now().strftime('%Y-%m-%d')
        return os.path.join(self.log_dir, f"{self.prefix}_{date_str}.log")

    def doRollover(self):
        if self.stream:
            self.stream.close()
            self.stream = None
        self.baseFilename = self._dated_filename()
        self.stream = self._open()
        self.rolloverAt = self.computeRollover(int(time.time()))
