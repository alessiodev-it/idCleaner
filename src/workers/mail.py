from tools.recorder.recorder import Recorder
from src.utils import handle_subthreads, FOLDER_NAMES, SUB_THREAD_NAMES
from src.engines.inbox_cleaner import InboxFolderCleaner
from src.engines.spam_cleaner import SpamFolderCleaner
from src.engines.bin_cleaner import BinFolderCleaner
from src.engines.bombsquad_cleaner import BombSquadFolderCleaner
from pathlib import Path
from threading import Thread
from queue import Empty
import os

_PRINT = True

def worker(stopper, queue_email, queue_update):
    record = Recorder(Path(os.getenv("RECORDER_MAIL_WORKER_PATH")), _print=_PRINT)
    record("Mail worker started.")

    shared_lists = {"whitelist": set(), "blacklist": set(), "graylist": set()}

    imap_data = {
        "host": os.getenv("IMAP_HOST"),
        "port": int(os.getenv("IMAP_PORT")),
        "username": os.getenv("SMTP_USERNAME"),
        "password": os.getenv("SMTP_PASSWORD"),
    }

    smtp_data = {
        "host": os.getenv("SMTP_HOST"),
        "port": int(os.getenv("SMTP_PORT")),
        "username": os.getenv("SMTP_USERNAME"),
        "password": os.getenv("SMTP_PASSWORD"),
    }

    vt_groq_data = {
        "vt_api_key": os.getenv("VT_API_KEY"),
        "groq_api_key": os.getenv("GROQ_API_KEY")
    }

    inbox_cleaner = InboxFolderCleaner(
        SUB_THREAD_NAMES[0],
        FOLDER_NAMES["inbox"],
        stopper,
        Recorder(Path(os.getenv("RECORDER_INBOX_CLEANER_PATH")), _print=_PRINT),
        imap_data,
        smtp_data,
        vt_groq_data,
        queue_update,
        shared_lists=shared_lists
    )

    spam_cleaner = SpamFolderCleaner(
        SUB_THREAD_NAMES[1],
        FOLDER_NAMES["spam"],
        stopper,
        Recorder(Path(os.getenv("RECORDER_SPAM_CLEANER_PATH")), _print=_PRINT),
        imap_data,
        shared_lists=shared_lists
    )

    bin_cleaner = BinFolderCleaner(
        SUB_THREAD_NAMES[2],
        FOLDER_NAMES["bin"],
        stopper,
        Recorder(Path(os.getenv("RECORDER_BIN_CLEANER_PATH")), _print=_PRINT),
        imap_data
    )

    bombsquad_cleaner = BombSquadFolderCleaner(
        SUB_THREAD_NAMES[3],
        FOLDER_NAMES["bomb_squad"],
        stopper,
        Recorder(Path(os.getenv("RECORDER_BOMBSQUAD_CLEANER_PATH")), _print=_PRINT),
        imap_data,
        vt_groq_data,
        queue_update
    )

    Thread(
        name="queue_email_listener",
        target=_queue_listener,
        daemon=True,
        args=(stopper, queue_email, shared_lists, record)
    ).start()

    handle_subthreads([inbox_cleaner, bin_cleaner, spam_cleaner, bombsquad_cleaner], stopper, record=record)
    record("End of all sub-threads worker")


def _queue_listener(stopper, queue_email, shared_lists, record):
    record("Queue email listener started.")
    while not stopper.is_set():
        try:
            payload = queue_email.get(timeout=0.5)
        except Empty:
            continue
        if not isinstance(payload, dict):
            continue

        w = set(payload.get("whitelist", []))
        b = set(payload.get("blacklist", []))
        g = set(payload.get("graylist", []))

        shared_lists["whitelist"].clear()
        shared_lists["whitelist"].update(w)
        shared_lists["blacklist"].clear()
        shared_lists["blacklist"].update(b)
        shared_lists["graylist"].clear()
        shared_lists["graylist"].update(g)

        record(f"Shared lists updated in memory: W={len(w)}, B={len(b)}, G={len(g)}")
