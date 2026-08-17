import time, json, os


def handle_subthreads(threads, stopper, record=None):
    record = _if_recorder(recorder)

    for t in threads:
        t.start()
        record(f"Sub thread [{t.name}] spawned.")

    stopper.wait()

    for t in threads:
        t.join()
        record(f"Sub thread [{t.name}] joined.")

    record("End of all sub-threads worker")
    record.join()
# ========== ========== ==========

def handle_threads(threads, stopper, record=None):
    record = _if_recorder(recorder)

    for t in threads:
        t.start()
        record(f"Core thread [{t.name}] spawned.")

    try:
        while not stopper.is_set():
            stopper.wait(timeout=1.0)
    except Exception as e:
        record(str(e))
    except KeyboardInterrupt:
        record("Keyboard interrupt")
    finally:
        stopper.set()

        for t in threads:
            t.join()
            record(f"Core thread [{t.name}] killed")

        record("Script closed")
        record.join()
# ========== ========== ==========

def polling(stopper, seconds):
    for _ in range(seconds):
        if stopper.is_set():
            return
        time.sleep(1)
# ========== ========== ==========

def _if_recorder(record):
    if record:
        return record
    noop = lambda *args, **kwargs: None
    noop.join = lambda: None
    return noop
# ========== ========== ==========

FOLDER_NAMES = {
    "inbox": "INBOX",
    "spam": "[Gmail]/Spam",
    "bin": "[Gmail]/Bin",
    "bomb_squad": "BombSquad"
}

THREAD_NAMES = ["loader_json", "mail_worker", "identity_worker"]
SUB_THREAD_NAMES = ["inbox_cleaner", "spam_cleaner", "bin_cleaner", "bombsquad_cleaner"]

DEFAULT_LISTS = {
    "whitelist": [],
    "blacklist": [],
    "graylist": []
}

DEFAULT_ENV = [
    "IMAP_HOST", "IMAP_PORT", "IMAP_USERNAME", "IMAP_PASSWORD",
    "SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD",
    "VT_API_KEY", "GROQ_API_KEY"
]

DEFAULT_STATE = {"FIRST_TIME": True}
