from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from imap_tools import MailBox, MailMessageFlags, AND, A

from src.config import settings

logger = logging.getLogger(__name__)

RESUME_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}
RESUME_FILENAME_KEYWORDS = {
    "cv", "resume", "резюме", "curriculum", "кандидат", "candidate"
}


def _is_resume_attachment(filename: str) -> bool:
    name_lower = Path(filename).stem.lower()
    return any(kw in name_lower for kw in RESUME_FILENAME_KEYWORDS)

last_poll_time: datetime | None = None


async def fetch_and_process_emails(db_factory) -> int:
    """Poll IMAP inbox for unseen emails with resume attachments. Returns count of processed files."""
    global last_poll_time

    if not settings.imap_host or not settings.imap_user or not settings.imap_password:
        logger.warning("IMAP credentials not configured — skipping email fetch")
        return 0

    # Phase 1: blocking IMAP I/O in a thread — returns saved file paths
    loop = asyncio.get_event_loop()
    saved_files = await loop.run_in_executor(None, _fetch_attachments_sync)

    # Phase 2: async pipeline processing on the main event loop (asyncpg-safe)
    from src.pipeline import process_resume_file
    count = 0
    for file_path in saved_files:
        try:
            logger.info("[IMAP] Starting pipeline for %s", file_path)
            async with db_factory() as db:
                await process_resume_file(file_path, db)
            count += 1
            logger.info("[IMAP] Pipeline done for %s (total so far: %d)", file_path, count)
        except Exception as exc:
            logger.error("[IMAP] Pipeline failed for %s: %s", file_path, exc, exc_info=True)

    last_poll_time = datetime.now(timezone.utc)
    logger.info("[IMAP] Poll complete — processed %d resume(s)", count)
    return count


def _fetch_attachments_sync() -> list[Path]:
    """Blocking IMAP fetch — downloads attachments, marks emails seen, returns saved paths."""
    save_dir = Path(settings.resumes_dir)
    save_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []

    logger.info("[IMAP] Connecting to %s:%s as %s, mailbox=%s",
                settings.imap_host, settings.imap_port, settings.imap_user, settings.imap_mailbox)
    try:
        with MailBox(settings.imap_host, settings.imap_port).login(
            settings.imap_user, settings.imap_password, initial_folder=settings.imap_mailbox
        ) as mb:
            logger.info("[IMAP] Login OK")
            since_date = (last_poll_time or datetime.now(timezone.utc) - timedelta(minutes=5)).date()
            logger.info("[IMAP] Fetching unseen emails since %s", since_date)
            msgs = list(mb.fetch(AND(seen=False, date_gte=since_date), mark_seen=False))
            logger.info("[IMAP] Found %d unseen email(s)", len(msgs))

            for msg in msgs:
                logger.info("[IMAP] Email uid=%s from=%s subject=%r attachments=%d",
                            msg.uid, msg.from_, msg.subject, len(msg.attachments))
                found_resume = False
                for att in msg.attachments:
                    ext = Path(att.filename).suffix.lower()
                    logger.info("[IMAP] Attachment: %s (ext=%s, size=%d bytes)",
                                att.filename, ext, len(att.payload))
                    if ext not in RESUME_EXTENSIONS:
                        logger.info("[IMAP] Skipping %s — not a resume extension", att.filename)
                        continue
                    if not _is_resume_attachment(att.filename):
                        logger.info("[IMAP] Skipping %s — filename doesn't match resume keywords", att.filename)
                        continue
                    save_path = save_dir / att.filename
                    if save_path.exists():
                        save_path = save_dir / f"{save_path.stem}_{msg.uid}{save_path.suffix}"
                    save_path.write_bytes(att.payload)
                    logger.info("[IMAP] Saved to %s", save_path)
                    saved.append(save_path)
                    found_resume = True

                if found_resume:
                    mb.flag([msg.uid], [MailMessageFlags.SEEN], True)
                    logger.info("[IMAP] Marked uid=%s as SEEN", msg.uid)

    except Exception as exc:
        logger.error("[IMAP] Fetch failed: %s", exc, exc_info=True)

    return saved
