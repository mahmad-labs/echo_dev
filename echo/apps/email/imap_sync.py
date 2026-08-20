from __future__ import annotations

import email
import imaplib
import os
from email.header import decode_header, make_header
from typing import Any

from django.db import transaction
from django.utils import timezone

from .models import EmailAccount, EmailMessage, EmailThread


class EmailSyncError(RuntimeError):
    pass


class IMAPSyncService:
    """Synchronize message metadata from an IMAP account using environment-backed secrets."""

    @staticmethod
    def _decode(value: str | None) -> str:
        return str(make_header(decode_header(value or "")))

    @classmethod
    @transaction.atomic
    def sync(cls, account: EmailAccount, limit: int = 50) -> dict[str, Any]:
        config = account.configuration or {}
        host = config.get("imap_host")
        username = config.get("username")
        password_env = config.get("password_env")
        password = os.getenv(str(password_env), "") if password_env else ""
        if not host or not username or not password:
            raise EmailSyncError("IMAP host, username, and password_env are required.")
        port = int(config.get("imap_port", 993))
        mailbox = str(config.get("mailbox", "INBOX"))
        client = imaplib.IMAP4_SSL(host, port, timeout=30)
        imported = 0
        try:
            client.login(username, password)
            status, _ = client.select(mailbox, readonly=True)
            if status != "OK":
                raise EmailSyncError(f"Unable to select mailbox {mailbox!r}.")
            status, data = client.uid("search", None, "ALL")
            if status != "OK":
                raise EmailSyncError("IMAP search failed.")
            uids = data[0].split()[-max(1, min(limit, 500)) :]
            for uid in uids:
                status, message_data = client.uid("fetch", uid, "(BODY.PEEK[HEADER])")
                if status != "OK" or not message_data or not isinstance(message_data[0], tuple):
                    continue
                parsed = email.message_from_bytes(message_data[0][1])
                message_id = parsed.get("Message-ID") or f"imap:{uid.decode()}"
                thread_key = parsed.get("References") or parsed.get("In-Reply-To") or message_id
                thread, _ = EmailThread.objects.get_or_create(
                    owner=account.owner,
                    name=str(thread_key)[:255],
                    defaults={
                        "title": cls._decode(parsed.get("Subject")) or "Email thread",
                        "status": "active",
                        "category": "imap",
                        "configuration": {"account_id": str(account.pk)},
                    },
                )
                _, created = EmailMessage.objects.update_or_create(
                    owner=account.owner,
                    name=str(message_id)[:255],
                    defaults={
                        "title": cls._decode(parsed.get("Subject")) or "Email message",
                        "description": cls._decode(parsed.get("From")),
                        "status": "synchronized",
                        "category": "imap",
                        "configuration": {
                            "account_id": str(account.pk),
                            "thread_id": str(thread.pk),
                            "imap_uid": uid.decode(),
                            "from": cls._decode(parsed.get("From")),
                            "to": cls._decode(parsed.get("To")),
                            "date": parsed.get("Date", ""),
                            "message_id": message_id,
                        },
                    },
                )
                imported += int(created)
        except imaplib.IMAP4.error as exc:
            raise EmailSyncError(f"IMAP authentication or protocol failure: {exc}") from exc
        finally:
            try:
                client.logout()
            except (imaplib.IMAP4.error, OSError):
                pass
        account.status = "active"
        account.configuration = {**config, "last_synced_at": timezone.now().isoformat()}
        account.save(update_fields=["status", "configuration", "updated_at"])
        return {"imported": imported, "examined": len(uids), "mailbox": mailbox}
