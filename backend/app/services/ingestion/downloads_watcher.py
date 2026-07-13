import datetime
import threading
import time
from pathlib import Path

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.auto_ingest_settings import AutoIngestSettings
from app.models.meeting import Meeting
from app.models.processed_file import ProcessedFile
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.meeting_repository import MeetingRepository
from app.schemas.meeting_schema import MeetingUpload
from app.services.hermes.control_service import HermesControlService
from app.services.ingestion.meeting_ingestion import MeetingIngestionService
from app.utils.logger import get_logger

logger = get_logger("downloads_watcher")

_stop_event = threading.Event()
_watcher_thread = None


def watch_downloads():
    logger.info("Downloads watcher thread running.")
    downloads_path = Path.home() / "Downloads"

    while not _stop_event.is_set():
        try:
            db = SessionLocal()
            try:
                # 1. Fetch settings.
                settings = db.query(AutoIngestSettings).first()
                if not settings or not settings.enabled:
                    # Not enabled, sleep and continue
                    _stop_event.wait(3)
                    continue

                if settings.activated_at is None:
                    settings.activated_at = datetime.datetime.now().isoformat()
                    db.commit()

                activated_at_dt = datetime.datetime.fromisoformat(settings.activated_at)

                if not downloads_path.exists():
                    _stop_event.wait(3)
                    continue

                # 2. Scan downloads folder for .txt and .md files
                files = list(downloads_path.glob("*.txt")) + list(
                    downloads_path.glob("*.md")
                )
                for filepath in files:
                    # Check modification time
                    try:
                        mtime_dt = datetime.datetime.fromtimestamp(filepath.stat().st_mtime)
                    except Exception as stat_err:
                        logger.error(f"Failed to stat file {filepath.name}: {stat_err}")
                        continue

                    # Skip files modified more than 2 minutes before the toggle activation time
                    if mtime_dt < activated_at_dt - datetime.timedelta(minutes=2):
                        continue

                    filepath_str = str(filepath.resolve())

                    # Check if already processed
                    already_processed = (
                        db.query(ProcessedFile)
                        .filter_by(filepath=filepath_str)
                        .first()
                    )
                    if already_processed and already_processed.meeting_id:
                        meeting_exists = (
                            db.query(Meeting)
                            .filter_by(meeting_id=already_processed.meeting_id)
                            .first()
                        )
                        if meeting_exists:
                            continue
                        else:
                            # Meeting was deleted, delete record and allow reprocessing
                            db.delete(already_processed)
                            db.commit()
                            already_processed = None

                    # Read transcript content
                    try:
                        content = filepath.read_text(
                            encoding="utf-8", errors="replace"
                        )
                    except Exception as read_err:
                        logger.error(
                            f"Failed to read file {filepath_str}: {read_err}"
                        )
                        continue

                    if not content.strip():
                        continue

                    # 3. Derive title and ID
                    first_line = (
                        content.splitlines()[0].strip() if content.strip() else ""
                    )
                    if first_line.startswith("#"):
                        title = first_line.lstrip("#").strip()
                    elif first_line.startswith("Title:"):
                        title = first_line[len("Title:") :].strip()
                    else:
                        title = (
                            filepath.stem.replace("_", " ")
                            .replace("-", " ")
                            .title()
                        )

                    # Duplicate prevention check by title
                    existing_by_title = (
                        db.query(Meeting)
                        .filter(Meeting.title == title)
                        .first()
                    )
                    if existing_by_title:
                        # Link it to the existing meeting to prevent future duplicate processing
                        if already_processed:
                            already_processed.meeting_id = existing_by_title.meeting_id
                            db.commit()
                        else:
                            processed = ProcessedFile(
                                filepath=filepath_str,
                                processed_at=datetime.datetime.now().isoformat(),
                                meeting_id=existing_by_title.meeting_id,
                            )
                            db.add(processed)
                            db.commit()
                        continue

                    # If not existing but was marked as processed (legacy NULL or deleted), delete record and proceed
                    if already_processed:
                        db.delete(already_processed)
                        db.commit()

                    count = db.query(Meeting).count()
                    meeting_id = f"AUTO-{count + 1:03d}"
                    while (
                        db.query(Meeting)
                        .filter(Meeting.meeting_id == meeting_id)
                        .first()
                        is not None
                    ):
                        count += 1
                        meeting_id = f"AUTO-{count + 1:03d}"

                    logger.info(
                        f"Auto-ingesting meeting from {filepath.name}: ID={meeting_id}, Title='{title}'"
                    )

                    # 4. Perform SQLite Ingestion
                    from app.core.dependencies import get_gbrain

                    gbrain_service = get_gbrain(db)
                    meeting_repo = MeetingRepository(db)
                    chunk_repo = ChunkRepository(db)
                    ingestion_svc = MeetingIngestionService(
                        gbrain_service, meeting_repo, chunk_repo
                    )

                    payload = MeetingUpload(
                        meeting_id=meeting_id,
                        title=title,
                        transcript=content,
                        project_id=None,
                    )
                    ingestion_svc.ingest(payload)
                    db.commit()

                    # 5. Save to Hermes GBrain
                    try:
                        settings_obj = get_settings()
                        hermes_ctrl = HermesControlService(settings_obj)
                        if hermes_ctrl.available():
                            hermes_ctrl.save_to_gbrain(meeting_id, title, content)
                            logger.info(
                                f"Saved meeting {meeting_id} to Hermes gbrain."
                            )
                    except Exception as hermes_err:
                        logger.error(
                            f"Failed to save meeting {meeting_id} to Hermes gbrain: {hermes_err}"
                        )

                    # 6. Record as processed
                    processed = ProcessedFile(
                        filepath=filepath_str,
                        processed_at=datetime.datetime.now().isoformat(),
                        meeting_id=meeting_id,
                    )
                    db.add(processed)
                    db.commit()
                    logger.info(f"Successfully processed file: {filepath_str}")

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Error in watch_downloads loop: {e}")

        _stop_event.wait(3)


def start_downloads_watcher():
    global _watcher_thread
    _stop_event.clear()
    if _watcher_thread and _watcher_thread.is_alive():
        logger.info("Downloads watcher already running.")
        return
    _watcher_thread = threading.Thread(target=watch_downloads, daemon=True)
    _watcher_thread.start()
    logger.info("Downloads watcher background thread started.")


def stop_downloads_watcher():
    global _watcher_thread
    _stop_event.set()
    if _watcher_thread:
        _watcher_thread.join(timeout=2)
        _watcher_thread = None
    logger.info("Downloads watcher background thread stopped.")
