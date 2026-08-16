import os, json
from imap_tools import AND, MailMessageFlags
from src.utils import FOLDER_NAMES
from .base_cleaner import BaseFolderCleaner
from .helpers.questions import (
    is_expired,
    is_promotional,
    is_only_text,
    has_unsubscribe_header,
    has_suspicious_docs,
    has_malevolent_text,
    has_malware,
    has_spy_pixel
)
from .helpers.actions import unsubscribe_from
from src.network import network


class InboxFolderCleaner(BaseFolderCleaner):
    def __init__(self, thread_name, folder_name, stopper, record, imap_data, smtp_data, vt_groq_data, queue_update, shared_lists):
        super().__init__(thread_name, folder_name, stopper, record, imap_data, shared_lists=shared_lists)

        self.smtp_data = smtp_data
        self.vt_groq_data = vt_groq_data
        self.queue_update = queue_update

    @network.online
    def _bucking(self, mailbox):
        whitelist = self.shared_lists.get("whitelist", set())
        blacklist = self.shared_lists.get("blacklist", set())
        graylist = self.shared_lists.get("graylist", set())

        categories = {
            "to_bin": [],
            "to_unsubscribe": [],
            "for_file_analysis": [],
            "for_text_analysis": [],
            "to_graylist": [],
            "to_blacklist": [],
            "safe": []
        }
        uids_to_fetch = []

        for msg in mailbox.fetch(reverse=True, headers_only=True):
            if self.stopper.is_set():
                return {}
            if not msg.from_:
                continue

            if is_expired(msg, 30):
                categories["to_bin"].append(msg)
                continue

            if msg.from_ in blacklist:
                if has_unsubscribe_header(msg):
                    categories["to_unsubscribe"].append(msg)
                    self.record(f"Blacklist: Found unsubscribe header for {msg.from_}.")
                categories["to_bin"].append(msg)
                self.record(f"Blacklist: Sender {msg.from_} is blacklisted. Moving to trash.")
                continue

            if msg.from_ not in whitelist and msg.from_ not in graylist:
                categories["to_graylist"].append(msg)
                self.record(f"New Sender: Found unknown sender {msg.from_}. Moving to graylist.")
                continue

            uids_to_fetch.append(msg.uid)

        if uids_to_fetch and not self.stopper.is_set():
            for full_msg in mailbox.fetch(AND(uid=uids_to_fetch)):

                if full_msg.from_ in whitelist:
                    if is_promotional(full_msg):
                        categories["to_bin"].append(full_msg)
                        self.record(f"Whitelist Promo: Whitelisted sender {full_msg.from_} sent a promo. Moving to trash.")
                    continue

                if has_malware(full_msg):
                    categories["to_bin"].append(full_msg)
                    categories["to_blacklist"].append(full_msg)
                    self.record(f"Malware: Found dangerous attachment from {full_msg.from_}. Blacklisting.")
                    continue

                if has_suspicious_docs(full_msg):
                    categories["for_file_analysis"].append(full_msg)
                    self.record(f"Suspicious Document: Potential threat from {full_msg.from_}. Sending to BombSquad.")
                    continue

                if has_spy_pixel(full_msg):
                    categories["to_bin"].append(full_msg)
                    self.record(f"Spy Pixel: Found tracking pixel from {full_msg.from_}. Moving to trash.")
                    continue

                if is_promotional(full_msg):
                    categories["to_bin"].append(full_msg)
                    self.record(f"Promotion: Graylisted sender {full_msg.from_} sent a promo. Moving to trash.")
                    continue

                if is_only_text(full_msg):
                    categories["for_text_analysis"].append(full_msg)
                    continue

                categories["safe"].append(full_msg)
                self.record(f"Safe: Email from {full_msg.from_} passed triage. Leaving in Inbox.")

        return categories

    @network.online
    def _applying(self, mailbox, categories):
        if not categories:
            return

        processed_uids = list({msg.uid for sublist in categories.values() for msg in sublist})
        mailbox.flag(processed_uids, MailMessageFlags.SEEN, True)

        if categories["for_file_analysis"]:
            uids = [msg.uid for msg in categories["for_file_analysis"]]
            mailbox.move(uids, FOLDER_NAMES["bomb_squad"])

        for msg in categories["to_graylist"]:
            self.queue_update.put({"action": "add_graylist", "value": msg.from_})
        for msg in categories["to_blacklist"]:
            self.queue_update.put({"action": "add_blacklist", "value": msg.from_})

        bin_uids = [msg.uid for msg in categories["to_bin"]]
        for msg in categories["for_text_analysis"]:
            if has_malevolent_text(msg, self.vt_groq_data):
                self.queue_update.put({"action": "add_blacklist", "value": msg.from_})
                bin_uids.append(msg.uid)

        if bin_uids:
            try:
                mailbox.move(list(set(bin_uids)), FOLDER_NAMES["bin"])
            except Exception as e:
                self.record(f"Error moving to trash: {e}")

        if categories["to_unsubscribe"]:
            for msg in categories["to_unsubscribe"]:
                if unsubscribe_from(msg, self.smtp_data):
                    self.record(f"Unsubscribe: Successfully unsubscribed from {msg.from_}.")
                else:
                    self.record(f"Unsubscribe: Failed request for {msg.from_}.")
