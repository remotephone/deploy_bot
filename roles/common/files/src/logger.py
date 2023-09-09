import logging


import json
import logging


class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_dict = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "path": record.pathname,
            "line": record.lineno,
        }
        return json.dumps(log_dict)


deploy_logger = logging.getLogger("deploy_bot_logger")
deploy_logger.setLevel(logging.DEBUG)
fhandler = logging.FileHandler(filename="deploy_bot.log", encoding="utf-8", mode="w")
fhandler.setFormatter(JsonFormatter())
fhandler.setLevel(logging.ERROR)
shandler = logging.StreamHandler()
shandler.setFormatter(JsonFormatter())
shandler.setLevel(logging.INFO)
deploy_logger.addHandler(fhandler)
deploy_logger.addHandler(shandler)
