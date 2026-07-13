import time
from pathlib import Path
from app.core.database import SessionLocal, init_db
from app.models.auto_ingest_settings import AutoIngestSettings
from app.models.meeting import Meeting
from app.models.processed_file import ProcessedFile
from app.services.ingestion.downloads_watcher import watch_downloads

def test_downloads_watcher(tmp_path, monkeypatch):
    # 1. Initialize DB tables
    init_db()
    # Setup DB session and clear tables
    db_session = SessionLocal()
    try:
        db_session.query(AutoIngestSettings).delete()
        db_session.query(ProcessedFile).delete()
        db_session.query(Meeting).delete()
        db_session.commit()

        # 2. Mock Path.home() to return our tmp_path so it watches a test Downloads folder
        downloads_dir = tmp_path / "Downloads"
        downloads_dir.mkdir()
        
        def mock_home():
            return tmp_path
            
        monkeypatch.setattr(Path, "home", mock_home)
        
        # 3. Enable auto-ingest settings in DB
        settings = AutoIngestSettings(enabled=True)
        db_session.add(settings)
        db_session.commit()
        
        # 4. Create a test transcript file in the dummy Downloads folder
        transcript_file = downloads_dir / "Weekly Status Sync.txt"
        transcript_file.write_text("# Weekly Sync\nAlice:\nI will own the deployment.", encoding="utf-8")
        
        # 5. Mock _stop_event.wait to set the event and exit the loop cleanly after one iteration
        import app.services.ingestion.downloads_watcher as dw
        dw._stop_event.clear()
        def mock_wait(*args, **kwargs):
            dw._stop_event.set()
            return True
        monkeypatch.setattr(dw._stop_event, "wait", mock_wait)
        
        # Mock hermes save_to_gbrain to verify
        from app.services.hermes.control_service import HermesControlService
        saved_meetings = []
        def mock_save_to_gbrain(self, meeting_id, title, transcript):
            saved_meetings.append((meeting_id, title, transcript))
            return {"ok": True}
        def mock_available(self):
            return True
            
        monkeypatch.setattr(HermesControlService, "save_to_gbrain", mock_save_to_gbrain)
        monkeypatch.setattr(HermesControlService, "available", mock_available)
        
        # 6. Run the watcher (will run once, process the file, and then exit cleanly)
        watch_downloads()
            
        # 7. Verify database records
        meetings = db_session.query(Meeting).all()
        assert len(meetings) == 1
        assert meetings[0].title == "Weekly Sync"
        assert "Alice" in meetings[0].raw_transcript
        assert meetings[0].meeting_id.startswith("AUTO-")
        
        processed = db_session.query(ProcessedFile).all()
        assert len(processed) == 1
        assert processed[0].filepath == str(transcript_file.resolve())
        
        assert len(saved_meetings) == 1
        assert saved_meetings[0][1] == "Weekly Sync"
    finally:
        try:
            db_session.query(AutoIngestSettings).delete()
            db_session.query(ProcessedFile).delete()
            db_session.query(Meeting).delete()
            db_session.commit()
        except Exception:
            pass
        db_session.close()
