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
            except Exception as e:
                err_msg = f"Bootstrap failed during '{step.__name__}': {e}"
                rec(err_msg)
                sys.exit(err_msg)
#  ========== ========== ==========

def _api():
    env_file = find_dotenv()

    if not env_file:
        env_file = ROOT_DIR / ".env"
        with open(env_file, "w", encoding="utf-8") as f:
            f.write("\n".join([f"{k}=" for k in DEFAULT_ENV]))

    load_dotenv(env_file, override=True)

    if any(not os.getenv(k) for k in DEFAULT_ENV):
        raise RuntimeError("Environment variables incomplete. Please fill the .env file.")


def _data():
    data_dir = ROOT_DIR / "data"
    data_dir.mkdir(exist_ok=True, parents=True)

    list_path = data_dir / "list.json"
    if not list_path.exists() or list_path.stat().st_size == 0:
        with open(list_path, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_LISTS, f, indent=2)
    os.environ["list_path"] = str(list_path.resolve())

    state_path = data_dir / "state.json"
    if not state_path.exists() or state_path.stat().st_size == 0:
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_STATE, f, indent=2)
    os.environ["state_path"] = str(state_path.resolve())

    try:
        with open(state_path, "r", encoding="utf-8") as f:
            state_data = json.load(f)
            os.environ["first_time"] = str(state_data.get("first_time", True))
    except Exception:
        os.environ["first_time"] = "True"

    raw_list_path = data_dir / "raw_list.txt"
    raw_list_path.touch(exist_ok=True)
    os.environ["raw_list_path"] = str(raw_list_path.resolve())


def _recorders():
    records_dir = ROOT_DIR / "records"
    records_dir.mkdir(exist_ok=True, parents=True)

    sub_records_dir = records_dir / "mail_worker"
    sub_records_dir.mkdir(exist_ok=True, parents=True)
    os.environ[f"recorder_{sub_records_dir.name}_path"] = str(sub_records_dir / f"{sub_records_dir.name}.json")
    os.environ["recorder_main_path"] = str(records_dir / "main.json")

    for t_name in THREAD_NAMES:
        if t_name != "mail_worker":
            os.environ[f"recorder_{t_name}_path"] = str(records_dir / f"{t_name}.json")

    for t_name in SUB_THREAD_NAMES:
        os.environ[f"recorder_{t_name}_path"] = str(sub_records_dir / f"{t_name}.json")


"""
ENVIRONMENT VARIABLES:
    STATE:
        first_time

    API:
        imap_host, imap_port, imap_username, imap_password,
        smtp_host, smtp_port, smtp_username, smtp_password,
        vt_api_key, groq_api_key

    DATA:
        list_path
        state_path
        raw_list_path

    RECORDERS:
        recorder_main_path
        recorder_loader_json_path
        recorder_mail_worker_path
            recorder_inbox_cleaner_path
            recorder_spam_cleaner_path
            recorder_bin_cleaner_path
        recorder_identity_worker_path

    Access: os.getenv('name')
"""
