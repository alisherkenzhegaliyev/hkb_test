from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from imap_tools import MailBox, MailMessageFlags, AND

from src.config import settings

logger = logging.getLogger(__name__)

RESUME_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}

last_poll_time: datetime | None = None


async def fetch_and_process_emails(db_factory) -> int:
    """Poll IMAP inbox for unseen emails with resume attachments. Returns count of processed files."""
    global last_poll_time

    if not settings.imap_host or not settings.imap_user or not settings.imap_password:
        logger.warning("IMAP credentials not configured — skipping email fetch")
        return 0

    loop = asyncio.get_event_loop()
    count = await loop.run_in_executor(None, _fetch_sync, db_factory)
    last_poll_time = datetime.now(timezone.utc)
    return count


def _fetch_sync(db_factory) -> int:
    from src.pipeline import process_resume_file
    import asyncio

    count = 0
    save_dir = Path(settings.resumes_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    try:
        with MailBox(settings.imap_host, settings.imap_port).login(
            settings.imap_user, settings.imap_password, initial_folder=settings.imap_mailbox
        ) as mb:
            msgs = list(mb.fetch(AND(seen=False), mark_seen=False))
            logger.info("Found %d unseen emails", len(msgs))

            for msg in msgs:
                processed_any = False
                for att in msg.attachments:
                    ext = Path(att.filename).suffix.lower()
                    if ext not in RESUME_EXTENSIONS:
                        continue
                    save_path = save_dir / att.filename
                    if save_path.exists():
                        base = save_path.stem
                        suffix = save_path.suffix
                        save_path = save_dir / f"{base}_{msg.uid}{suffix}"
                    save_path.write_bytes(att.payload)
                    logger.info("Saved attachment: %s", save_path)

                    try:
                        asyncio.run(_process_async(save_path, db_factory))
                        count += 1
                        processed_any = True
                    except Exception as exc:
                        logger.error("Failed to process %s: %s", save_path, exc)

                if processed_any:
                    mb.flag([msg.uid], [MailMessageFlags.SEEN], True)
    except Exception as exc:
        logger.error("IMAP fetch failed: %s", exc)

    return count


async def _process_async(file_path: Path, db_factory) -> None:
    from src.pipeline import process_resume_file
    async with db_factory() as db:
        await process_resume_file(file_path, db)
