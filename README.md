# idCleaner

*Finally. My inbox is clean, and it feels so good.*

---

## Overview

idCleaner is an automated email triage and cleanup tool. It connects to your IMAP mailbox, applies configurable rules, and organises messages into whitelist, blacklist, and graylist categories. It leverages multiple detection layers – including VirusTotal, Groq AI, local file analysis, and heuristics – to identify spam, phishing, malware, and unwanted promotional content. Suspicious messages are moved to a dedicated "BombSquad" folder for deep scanning, while safe messages remain in the inbox.

The core logic resides in `main.py` and the `src/` directory. External utilities (networking, file location, recording) are kept in `tools/` but are not detailed here; they are shared modules used across projects.

---

## Key Features

- Automatic classification of incoming email senders into whitelist, blacklist, or graylist.
- Periodic scanning of inbox, spam, and trash folders.
- Deep analysis of attachments (executables, office documents, archives) using YARA, oletools, pefile, and entropy checks.
- Integration with VirusTotal for URL reputation and Groq AI for natural‑language threat detection.
- Removal of tracking pixels, unsubscribe links, and expired messages.
- First‑run clean‑up of messages older than a configurable threshold.
- Persistent state and list storage (JSON).

---

## Installation

```bash
git clone https://github.com/alessiodev-it/idCleaner.git
cd idCleaner
python -m venv venv
source venv/bin/activate      # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

---

## Configuration

Create a `.env` file in the project root. The following variables are required:

| Variable          | Description                               |
|-------------------|-------------------------------------------|
| `imap_host`       | IMAP server hostname                      |
| `imap_port`       | IMAP port (e.g., 993)                    |
| `imap_username`   | IMAP login username                       |
| `imap_password`   | IMAP login password                       |
| `smtp_host`       | SMTP server hostname (for unsubscribe)    |
| `smtp_port`       | SMTP port (465 or 587)                   |
| `smtp_username`   | SMTP login username                       |
| `smtp_password`   | SMTP login password                       |
| `vt_api_key`      | VirusTotal API key (optional)             |
| `groq_api_key`    | Groq Cloud API key (optional)             |

All other paths (state, lists, recorders) are created automatically on first run.

---

## Usage

Start the main script:

```bash
python main.py
```

The program runs continuously, scanning folders every 5 minutes. It can be managed as a systemd service or a cron job, depending on your preference.

---

## How It Works

- `main.py` bootstraps the environment, loads configuration, and starts two core threads:
  - **loader_json** – watches `list.json` for changes and broadcasts updated whitelist/blacklist/graylist to the mail worker.
  - **mail_worker** – manages four sub‑threads (cleaners) for Inbox, Spam, Bin, and BombSquad.

- Each cleaner connects to the IMAP server, applies its specific logic, and moves messages accordingly:
  - **InboxCleaner** – triages new senders, checks for malware, promotional content, tracking pixels, and suspicious text. Unknown senders are added to the graylist; malicious ones go to blacklist and are moved to Bin.
  - **SpamCleaner** – recovers messages from whitelist/graylist senders and moves others to Bin.
  - **BinCleaner** – permanently deletes messages in the Bin folder (in chunks).
  - **BombSquadCleaner** – performs deep scanning on attachments (YARA, entropy, PE structure, VBA macros) and either blacklists or restores the sender.

- The `load` worker persists list updates and provides the current payload to the mail worker via a queue.

- A `state.json` file tracks whether this is the first run, triggering an initial clean‑up of old messages.

---

## File Structure

```
idCleaner/
├── main.py                # Entry point
├── .env                   # Environment configuration (created by user)
├── data/                  # Persistent lists and state
│   ├── list.json          # Whitelist, blacklist, graylist
│   ├── state.json         # first_time flag
│   └── raw_list.txt       # Flat list for quick reference
├── records/               # JSON logs for each component (for debugging)
└── src/
    ├── init.py            # Environment and data initialisation
    ├── utils.py           # Thread helpers, constants, defaults
    ├── workers/
    │   ├── load.py        # List watcher and payload broadcaster
    │   └── mail.py        # Mail worker orchestrating cleaners
    └── engines/
        ├── base_cleaner.py   # Abstract cleaner with first‑run and polling
        ├── inbox_cleaner.py
        ├── spam_cleaner.py
        ├── bin_cleaner.py
        ├── bombsquad_cleaner.py
        └── helpers/          # Questions, actions, constants, and security (deep_scanner, YARA)
```

The `identity_worker` (defined in `src/workers/identity.py`) is currently a placeholder for future identity‑verification logic and is not active.

---

## Dependencies

- `imap_tools` – IMAP communication.
- `oletools`, `pefile`, `yara_python` – file analysis.
- `python-magic` – MIME detection.
- `Requests` – HTTP calls to VirusTotal and Groq.
- `python-dotenv` – environment variable management.

See `requirements.txt` for exact versions.

---

## License
GNU General Public License v3

---

*Maintained by [Alessio Iacoviello](https://github.com/alessiodev-it) — built for resilience, designed for automation.*
