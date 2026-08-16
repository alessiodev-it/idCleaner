from src.utils import polling, FOLDER_NAMES

from threading import Thread
from abc import ABC, abstractmethod
from imap_tools import MailBox, AND
from datetime import date, timedelta
import os, json


class BaseFolderCleaner(Thread, ABC):
    def __init__(self, thread_name, folder_name, stopper, record, imap_data, shared_lists=None):
        super().__init__(name=thread_name, daemon=True)

        self.folder_name = folder_name
        self.stopper = stopper
        self.record = record
        self.imap_data = imap_data
        self.shared_lists = shared_lists or {}

    def run(self):
        while not self.stopper.is_set():
            try:
                with MailBox(host=self.imap_data["host"], port=self.imap_data["port"]).login(username=self.imap_data["username"], password=self.imap_data["password"]) as mailbox:
                    if not mailbox.folder.exists(self.folder_name):
                        mailbox.folder.create(self.folder_name)

                    mailbox.folder.set(self.folder_name)

                    self._first_time_cleaning(mailbox)

                    categories = self._bucking(mailbox)
                    if categories:
                        self._applying(mailbox, categories)

            except Exception as e:
                self.record(f"Error in base cleaner: {e}")

            polling(self.stopper, 60*5)

        self.record.join()
        return

    @abstractmethod
    def _bucking(self, mailbox):
        pass

    @abstractmethod
    def _applying(self, mailbox, categories):
        pass

    def _first_time_cleaning(self, mailbox):
        def update_state():
            os.environ["first_time"] = "False"
            state_path = os.getenv("state_path")
            if state_path and os.path.exists(state_path):
                with open(state_path, "r+", encoding="utf-8") as f:
                    data = json.load(f)
                    data["first_time"] = False
                    f.seek(0)
                    json.dump(data, f, indent=2)
                    f.truncate()
                self.record("First Run: State 'first_time' updated to False.")

        if (os.getenv("first_time") or "").lower() != "true": return
        if self.folder_name == FOLDER_NAMES["bin"]: return

        self.record(f"First Run: Starting initial cleanup for '{self.folder_name}'...")
        old_uids = mailbox.uids(AND(date_lt=date.today() - timedelta(days=60)))

        if old_uids:
            self.record(f"First Run: Moving {len(old_uids)} expired messages to trash...")
            chunk_size = 500
            for i in range(0, len(old_uids), chunk_size):
                if self.stopper.is_set(): return

                chunk = old_uids[i:i + chunk_size]
                try:
                    mailbox.move(chunk, FOLDER_NAMES["bin"])
                except Exception as e:
                    self.record(f"First Run Error moving batch: {e}")
        else:
            self.record("First Run: No expired messages found.")

        update_state()
