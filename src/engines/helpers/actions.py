import re
import smtplib
import requests
from urllib.parse import parse_qs
from email.message import EmailMessage
from src.network import network

@network.online
def unsubscribe_from(msg, smtp_data=None):
    headers = msg.headers.get('list-unsubscribe', [])
    if not headers:
        return False

    links = re.findall(r'<(.*?)>', headers[0])
    http_links = [l for l in links if l.startswith('http')]
    mailto_links = [l for l in links if l.startswith('mailto:')]

    post_req = msg.headers.get('list-unsubscribe-post', [])
    is_one_click = bool(post_req and 'List-Unsubscribe=One-Click' in post_req[0])

    for link in http_links:
        try:
            if is_one_click:
                if requests.post(link, data={'List-Unsubscribe': 'One-Click'}, timeout=3).status_code in (200, 202):
                    return True
            if requests.get(link, timeout=3).status_code in (200, 202):
                return True
        except Exception:
            continue

    if mailto_links and smtp_data:
        for link in mailto_links:
            try:
                target = link.replace("mailto:", "", 1)

                if "?" in target:
                    email, query = target.split("?", 1)
                    params = parse_qs(query)
                    subject = params.get("subject", ["Unsubscribe"])[0]
                    body = params.get("body", [f"Unsubscribe request for msg {msg.uid}"])[0]
                else:
                    email = target
                    subject = "Unsubscribe"
                    body = f"Please unsubscribe me. Reference ID: {msg.uid}"

                out_msg = EmailMessage()
                out_msg["From"] = smtp_data["user"]
                out_msg["To"] = email
                out_msg["Subject"] = subject
                out_msg.set_content(body)

                port = smtp_data.get("port")
                if port == 465:
                    with smtplib.SMTP_SSL(smtp_data["host"], port, timeout=5) as smtp_server:
                        smtp_server.login(smtp_data["user"], smtp_data["password"])
                        smtp_server.send_message(out_msg)
                else:
                    with smtplib.SMTP(smtp_data["host"], port, timeout=5) as smtp_server:
                        smtp_server.starttls()
                        smtp_server.login(smtp_data["user"], smtp_data["password"])
                        smtp_server.send_message(out_msg)
                return True
            except Exception:
                continue

    return False
