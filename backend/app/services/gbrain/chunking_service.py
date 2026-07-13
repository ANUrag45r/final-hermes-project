"""
Chunking service (Stage 4).

Splits a raw transcript into speaker-attributed turns. Handles the common
"Speaker:\\n utterance" layout from the spec and degrades gracefully to
paragraph chunks when no speaker labels are present.
"""
import re

# "Alice:" or "Alice Smith:" at the start of a line.
_SPEAKER_RE = re.compile(r"^\s*([A-Z][\w .'-]{0,48}?):\s*$|^\s*([A-Z][\w .'-]{0,48}?):\s+(.*)$")


class ChunkingService:
    def chunk(self, transcript: str) -> list[dict]:
        lines = transcript.splitlines()
        chunks: list[dict] = []
        current_speaker: str | None = None
        buffer: list[str] = []

        def flush() -> None:
            text = " ".join(s.strip() for s in buffer if s.strip()).strip()
            if text:
                chunks.append(
                    {
                        "chunk_index": len(chunks),
                        "speaker": current_speaker,
                        "content": text,
                    }
                )
            buffer.clear()

        for line in lines:
            m = _SPEAKER_RE.match(line)
            if m:
                # A new speaker label starts a new chunk.
                flush()
                current_speaker = (m.group(1) or m.group(2) or "").strip()
                inline = m.group(3)
                if inline:
                    buffer.append(inline)
            elif line.strip():
                buffer.append(line)
        flush()

        # Fallback: no speaker structure at all -> paragraph chunks.
        if not chunks:
            for para in re.split(r"\n\s*\n", transcript):
                para = para.strip()
                if para:
                    chunks.append(
                        {"chunk_index": len(chunks), "speaker": None, "content": para}
                    )
        return chunks
