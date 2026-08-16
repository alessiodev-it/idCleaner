import json
import os
from src.utils import FOLDER_NAMES
from .base_cleaner import BaseFolderCleaner
from src.network import network

class SpamFolderCleaner(BaseFolderCleaner):
    def __init__(self, thread_name, folder_name, stopper, record, imap_data, shared_lists=None):
        super().__init__(thread_name, folder_name, stopper, record, imap_data, shared_lists=shared_lists)

    @network.online
    def _bucking(self, mailbox):
        categories = {"to_inbox": [], "to_bin": []}
        whitelist = {w.lower().strip() for w in self.shared_lists.get("whitelist", set())}
        graylist = {g.lower().strip() for g in self.shared_lists.get("graylist", set())}

        for msg in mailbox.fetch(headers_only=True):
            if self.stopper.is_set():
                return {}
            if not msg.from_:
                continue

            sender = msg.from_.lower().strip()
            if any(w in sender for w in whitelist) or any(g in sender for g in graylist):
                categories["to_inbox"].append(msg.uid)
                self.record(f"SpamCleaner: Recovering email from {msg.from_} to Inbox.")
            else:
                categories["to_bin"].append(msg.uid)

        return categories

    @network.online
    def _applying(self, mailbox, categories):
        if not categories:
            return

        to_inbox = categories.get("to_inbox", [])
        to_bin = categories.get("to_bin", [])

        if to_inbox:
            mailbox.move(to_inbox, FOLDER_NAMES["inbox"])

        if to_bin:
            mailbox.move(to_bin, FOLDER_NAMES["bin"])
