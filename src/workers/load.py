from src.utils import polling
from tools.recorder.recorder import Recorder
from pathlib import Path
import os, json, queue


def json_data(stopper, queue_mail, queue_update):
    record = Recorder(Path(os.getenv("recorder_loader_json_path")))

    list_path = os.getenv("list_path")
    raw_list_path = os.getenv("raw_list_path")

    last_payload = None
    file_need_update = False

    while not stopper.is_set():
        try:
            with open(list_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            while not queue_update.empty():
                try:
                    cmd = queue_update.get(timeout=1.0)
                    action, value = cmd.get("action"), cmd.get("value")

                    if not action or not value:
                        continue

                    value = value.strip().lower()
                    target_section = action.removeprefix("add_")
                    if target_section not in data:
                        continue

                    for s in ["whitelist", "blacklist", "graylist"]:
                        if s != target_section:
                            before_len = len(data[s])
                            data[s] = [x for x in data[s] if x.strip().lower() != value]
                            if len(data[s]) != before_len:
                                file_need_update = True

                    current_items = [x.strip().lower() for x in data[target_section]]
                    if value not in current_items:
                        data[target_section].append(value)
                        file_need_update = True

                except queue.Empty:
                    break

            if file_need_update:
                with open(list_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                file_need_update = False
                record("Payload synced with file")

            w = set(data.get("whitelist", []))
            b = set(data.get("blacklist", []))
            g = set(data.get("graylist",  []))

            w, b, g = _fix_lists(w, b, g)
            current_payload = {
                "whitelist": w,
                "blacklist": b,
                "graylist":  g
            }

            if current_payload != last_payload:
                queue_mail.put(current_payload)
                last_payload = current_payload
                record("Update sent to threads")

                _update_raw_list(raw_list_path, last_payload)
                record("Payload synced with raw file")

        except FileNotFoundError:
            record("List file not found")
        except json.JSONDecodeError:
            record("JSON decode error")
        except Exception as e:
            record(f"Exception: {e}")

        polling(stopper, 60)
# ========== ========== ==========

def _fix_lists(w, b, g):
    clean_w = w
    clean_b = b - clean_w
    clean_g = g - (clean_w | clean_b)
    return list(sorted(clean_w)), list(sorted(clean_b)), list(sorted(clean_g))

def _update_raw_list(raw_list_path, last_payload):
    if not raw_list_path or not last_payload:
        return

    senders = set()
    for sender_list in last_payload.values():
        senders.update(sender_list)

    with open(raw_list_path, "w", encoding="utf-8") as f:
        for s in sorted(senders):
            f.write(f"{s}\n")
