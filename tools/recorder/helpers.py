from functools import wraps
from datetime import datetime
import json
import platform
import getpass

TIME_FORMAT = "%Y-%m-%dT%H:%M:%S:%f"
ENCODING = "utf-8"
AUTHOR = "alessiodev-it"

def locked(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        with self.lock:
            return method(self, *args, **kwargs)
    return wrapper

def get_signature(record: dict | None) -> str:
    if not record:
        return ""
    content = {k: v for k, v in record.items() if k != "ts"}
    return json.dumps(content, sort_keys=True, ensure_ascii=True)

def get_header(author: str | None = None) -> dict:
    return {
        "author": author or AUTHOR or getpass.getuser(),
        "host": platform.node(),
        "ts": datetime.now().strftime(TIME_FORMAT)
    }
