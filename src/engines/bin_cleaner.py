from .base_cleaner import BaseFolderCleaner
from src.network import network

class BinFolderCleaner(BaseFolderCleaner):
    def __init__(self, thread_name, folder_name, stopper, record, imap_data, shared_lists=None):
        super().__init__(thread_name, folder_name, stopper, record, imap_data, shared_lists=shared_lists)

    @network.online
    def _bucking(self, mailbox):
        categories = {"to_delete": []}
        for msg in mailbox.fetch(headers_only=True):
            if self.stopper.is_set():
                return {}
            categories["to_delete"].append(msg.uid)
        return categories

    @network.online
    def _applying(self, mailbox, categories):
        if not categories or not categories.get("to_delete"):
            return

        uids_to_delete = categories["to_delete"]
        total = len(uids_to_delete)
        chunk_size = 500

        self.record(f"BinCleaner: Preparing to permanently delete {total} messages...")

        for i in range(0, total, chunk_size):
            if self.stopper.is_set():
                return
            chunk = uids_to_delete[i:i + chunk_size]
            try:
                mailbox.delete(chunk)
                self.record(f"BinCleaner: Permanently deleted batch of {len(chunk)} messages.")
            except Exception as e:
                self.record(f"BinCleaner Error deleting batch: {e}")
