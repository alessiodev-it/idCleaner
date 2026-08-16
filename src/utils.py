import time, json, os


def handle_subthreads(threads, stopper, record=None):
    for t in threads:
        t.start()
        if record:
            record(f"Sub thread [{t.name}] spawned.")

    stopper.wait()

    for t in threads:
        t.join()
        if record:
            record(f"Sub thread [{t.name}] joined.")


def handle_threads(threads, stopper, record=None):
    for t in threads:
        t.start()
        if record:
            record(f"Core thread [{t.name}] spawned.")

    try:
        while not stopper.is_set():
            stopper.wait(timeout=1.0)
    except Exception as e:
        if record:
            record(str(e))
    except KeyboardInterrupt:
        if record:
            record("Keyboard interrupt")
    finally:
        stopper.set()

        for t in threads:
            t.join()
            if record:
                record(f"Core thread [{t.name}] killed")

        if record:
            record("Script closed")
            record.join()
# ========== ========== ==========

def polling(stopper, seconds):
    for _ in range(seconds):
        if stopper.is_set():
            return
        time.sleep(1)
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
