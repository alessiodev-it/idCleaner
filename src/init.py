import json, os, sys
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
from pyprojroot import here

from src.utils import (
    THREAD_NAMES,
    SUB_THREAD_NAMES,
    DEFAULT_LISTS,
    DEFAULT_ENV,
    DEFAULT_STATE
)
from tools.recorder.recorder import Recorder

ROOT_DIR = here()
_PRINT = True


def bootstrap():
    records_dir = ROOT_DIR / "records"
    records_dir.mkdir(exist_ok=True, parents=True)

    with Recorder(records_dir / "bootstrap.json", _print=_PRINT) as rec:
        for step in (_api, _data, _recorders):
            try:
                step()
                rec(f"Succed during '{step.__name__}'")
            except Exception as e:
                err_msg = f"Failed during '{step.__name__}': {e}"
                rec(err_msg)
                sys.exit(err_msg)
#  ========== ========== ==========

def _api():
    def get_var(k):
        return os.getenv(k)

    if all(get_var(k) for k in DEFAULT_ENV):
        return

    env_file = find_dotenv()
    if env_file:
        load_dotenv(env_file, override=False)

    missing = [k.upper() for k in DEFAULT_ENV if not get_var(k)]

    if missing:
        raise RuntimeError(
            f"Environment variables incomplete: missing {missing}. "
            f"Check GitHub Secrets or local .env file."
        )


def _data():
    data_dir = ROOT_DIR / "data"
    data_dir.mkdir(exist_ok=True, parents=True)

    list_path = data_dir / "list.json"
    if not list_path.exists() or list_path.stat().st_size == 0:
        with open(list_path, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_LISTS, f, indent=2)
    os.environ["LIST_PATH"] = str(list_path.resolve())

    state_path = data_dir / "state.json"
    if not state_path.exists() or state_path.stat().st_size == 0:
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_STATE, f, indent=2)
    os.environ["STATE_PATH"] = str(state_path.resolve())

    try:
        with open(state_path, "r", encoding="utf-8") as f:
            state_data = json.load(f)
            os.environ["FIRST_TIME"] = str(state_data.get("first_time", True))
    except Exception:
        os.environ["FIRST_TIME"] = "True"

    raw_list_path = data_dir / "raw_list.txt"
    raw_list_path.touch(exist_ok=True)
    os.environ["RAW_LIST_PATH"] = str(raw_list_path.resolve())


def _recorders():
    records_dir = ROOT_DIR / "records"
    records_dir.mkdir(exist_ok=True, parents=True)

    sub_records_dir = records_dir / "mail_worker"
    sub_records_dir.mkdir(exist_ok=True, parents=True)
    os.environ[f"RECORDER_{sub_records_dir.name.upper()}_PATH"] = str(sub_records_dir / f"{sub_records_dir.name}.json")
    os.environ["RECORDER_MAIN_PATH"] = str(records_dir / "main.json")

    for t_name in THREAD_NAMES:
        if t_name != "mail_worker":
            os.environ[f"RECORDER_{t_name.upper()}_PATH"] = str(records_dir / f"{t_name}.json")

    for t_name in SUB_THREAD_NAMES:
        os.environ[f"RECORDER_{t_name.upper()}_PATH"] = str(sub_records_dir / f"{t_name}.json")


"""
ENVIRONMENT VARIABLES:
    STATE:
        FIRST_TIME

    API:
        IMAP_HOST, IMAP_PORT, IMAP_USERNAME, IMAP_PASSWORD,
        SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD,
        VT_API_KEY, GROQ_API_KEY

    DATA:
        LIST_PATH
        STATE_PATH
        RAW_LIST_PATH

    RECORDERS:
        RECORDER_MAIN_PATH
        RECORDER_LOADER_JSON_PATH
        RECORDER_MAIL_WORKER_PATH
            RECORDER_INBOX_CLEANER_PATH
            RECORDER_SPAM_CLEANER_PATH
            RECORDER_BIN_CLEANER_PATH
        RECORDER_IDENTITY_WORKER_PATH

    Access: os.getenv('NAME')
"""
