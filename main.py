from threading import Thread, Event
from queue import Queue
from pathlib import Path
import os

from src.init import bootstrap
from src.utils import handle_threads, THREAD_NAMES
from src.workers import load, mail
from tools.recorder.recorder import Recorder

_PRINT = True


def main():
    stopper = Event()
    queue_mail, queue_update = Queue(), Queue()

    json_loader = Thread(
        name = THREAD_NAMES[0],
        target = load.json_data,
        daemon = True,
        args = (stopper, queue_mail, queue_update)
    )

    mail_worker = Thread(
        name = THREAD_NAMES[1],
        target = mail.worker,
        daemon = True,
        args = (stopper, queue_mail, queue_update)
    )

    handle_threads(
        [json_loader, mail_worker],
        stopper,
        Recorder(
            Path(os.getenv("recorder_main_path")),
            _print=_PRINT
        )
    )
# ========== ========== ==========

if __name__ == "__main__":
    bootstrap()
    main()
