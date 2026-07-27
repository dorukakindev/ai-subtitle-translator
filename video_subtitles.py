import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path


VIDEO_EXTENSIONS = {
    ".mkv", ".mp4", ".m4v", ".mov", ".avi", ".webm", ".m2ts",
}

TEXT_SUBTITLE_CODECS = {
    "ass", "jacosub", "microdvd", "mov_text", "mpl2", "pjs", "realtext",
    "sami", "scc", "ssa", "stl", "subrip", "subviewer", "subviewer1",
    "text", "ttml", "vplayer", "webvtt",
}

BITMAP_SUBTITLE_CODECS = {
    "dvb_subtitle", "dvd_subtitle", "hdmv_pgs_subtitle", "xsub",
}


class VideoSubtitleError(RuntimeError):
    pass


@dataclass(frozen=True)
class SubtitleStream:
    index: int
    codec: str
    language: str = ""
    title: str = ""

    @property
    def supported(self) -> bool:
        return self.codec.lower() in TEXT_SUBTITLE_CODECS

    @property
    def label(self) -> str:
        language = self.language or "dil bilinmiyor"
        title = f" — {self.title}" if self.title else ""
        return f"Akış {self.index} · {language} · {self.codec}{title}"


def is_video_path(path) -> bool:
    return Path(path).suffix.lower() in VIDEO_EXTENSIONS


def _tool_path(name: str, which=shutil.which) -> str:
    path = which(name)
    if not path:
        exe_name = f"{name}.exe" if os.name == "nt" else name
        local_path = Path(__file__).resolve().parent / "tools" / "ffmpeg" / exe_name
        if local_path.is_file():
            path = str(local_path)
    if not path:
        raise VideoSubtitleError(
            f"{name} bulunamadı. Video içinden altyazı çıkarmak için "
            "FFmpeg kurulmalı veya tools/ffmpeg klasörüne yerleştirilmelidir.")
    return path


def _run(command, runner=subprocess.run, timeout=120):
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        return runner(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            creationflags=creationflags,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise VideoSubtitleError(
            f"{Path(command[0]).name} {timeout} saniye içinde tamamlanamadı."
        ) from exc


def probe_subtitle_streams(video_path, runner=subprocess.run, which=shutil.which):
    video = Path(video_path)
    if not video.is_file():
        raise VideoSubtitleError(f"Video dosyası bulunamadı: {video}")
    ffprobe = _tool_path("ffprobe", which=which)
    command = [
        ffprobe, "-v", "error", "-select_streams", "s",
        "-show_entries", "stream=index,codec_name:stream_tags=language,title",
        "-of", "json", str(video),
    ]
    result = _run(command, runner=runner, timeout=30)
    if result.returncode:
        detail = (result.stderr or result.stdout or "bilinmeyen ffprobe hatası").strip()
        raise VideoSubtitleError(f"Video altyazıları okunamadı: {detail}")
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise VideoSubtitleError(f"ffprobe geçersiz JSON döndürdü: {exc}") from exc
    streams = []
    for item in payload.get("streams") or []:
        try:
            index = int(item["index"])
        except (KeyError, TypeError, ValueError):
            continue
        tags = item.get("tags") or {}
        streams.append(SubtitleStream(
            index=index,
            codec=str(item.get("codec_name") or "unknown").strip().lower(),
            language=str(tags.get("language") or "").strip(),
            title=str(tags.get("title") or "").strip(),
        ))
    return streams


def _source_fingerprint(video: Path) -> str:
    stat = video.stat()
    identity = (
        f"{video.resolve()}\0{stat.st_size}\0{stat.st_mtime_ns}"
    ).encode("utf-8", errors="surrogatepass")
    return hashlib.sha256(identity).hexdigest()[:20]


def _safe_name(value: str, fallback: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", value).strip(" ._")
    return cleaned[:100] or fallback


def _cache_root(video: Path) -> Path:
    return (
        Path(tempfile.gettempdir())
        / "openai-subtitle-translator"
        / "video-subtitles"
        / _source_fingerprint(video)
    )


def _origin_sidecar(subtitle_path: Path) -> Path:
    return subtitle_path.with_name(f"{subtitle_path.name}.origin.json")


def _write_json_atomic(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temp_path, path)
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass


def extracted_video_origin(subtitle_path):
    path = Path(subtitle_path)
    sidecar = _origin_sidecar(path)
    if not sidecar.is_file():
        return None
    try:
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        source = Path(str(payload.get("source_video") or ""))
        if source.is_absolute():
            return source
    except Exception:
        pass
    return None


def logical_subtitle_path(subtitle_path) -> Path:
    path = Path(subtitle_path)
    source_video = extracted_video_origin(path)
    if source_video is None:
        return path
    return source_video.parent / path.name


def extract_subtitle_stream(
        video_path, stream: SubtitleStream, runner=subprocess.run,
        which=shutil.which) -> Path:
    video = Path(video_path)
    if not video.is_file():
        raise VideoSubtitleError(f"Video dosyası bulunamadı: {video}")
    if not stream.supported:
        if stream.codec in BITMAP_SUBTITLE_CODECS:
            reason = "görüntü tabanlı altyazı OCR gerektiriyor"
        else:
            reason = "altyazı biçimi metne dönüştürülemiyor"
        raise VideoSubtitleError(f"{stream.label}: {reason}.")
    ffmpeg = _tool_path("ffmpeg", which=which)
    stem = _safe_name(video.stem, "video")
    language = _safe_name(stream.language.lower(), "und")
    output = _cache_root(video) / f"{stem}.track-{stream.index}.{language}.srt"
    sidecar = _origin_sidecar(output)
    if output.is_file() and output.stat().st_size > 0 and sidecar.is_file():
        return output
    output.parent.mkdir(parents=True, exist_ok=True)
    temp_output = output.with_name(f".{output.stem}.{uuid.uuid4().hex}.tmp.srt")
    command = [
        ffmpeg, "-y", "-v", "error", "-i", str(video),
        "-map", f"0:{stream.index}", "-c:s", "srt", str(temp_output),
    ]
    try:
        result = _run(command, runner=runner, timeout=300)
        if result.returncode:
            detail = (result.stderr or result.stdout or "bilinmeyen ffmpeg hatası").strip()
            raise VideoSubtitleError(f"{stream.label} çıkarılamadı: {detail}")
        if not temp_output.is_file() or temp_output.stat().st_size == 0:
            raise VideoSubtitleError(f"{stream.label} boş çıktı üretti.")
        os.replace(temp_output, output)
        _write_json_atomic(sidecar, {
            "source_video": str(video.resolve()),
            "stream_index": stream.index,
            "codec": stream.codec,
            "language": stream.language,
            "title": stream.title,
        })
        return output
    finally:
        try:
            temp_output.unlink(missing_ok=True)
        except Exception:
            pass
