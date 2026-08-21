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

# Konum/stil etiketleri taşıyan akışlar: SRT'ye çevrilmeden ham kopyalanır.
ASS_SUBTITLE_CODECS = {"ass", "ssa"}


class VideoSubtitleError(RuntimeError):
    pass


# ffprobe disposition bayrakları modele hiç taşınmıyordu: seçim penceresi
# İngilizce olan İLK akışı varsayılan yapıyordu, yani yaygın
# '#2 forced / #3 SDH / #4 full [default]' sırasında forced track
# seçiliyordu (denetim 2026-08-21, madde 27).
@dataclass(frozen=True)
class SubtitleStream:
    index: int
    codec: str
    language: str = ""
    title: str = ""
    default: bool = False
    forced: bool = False
    hearing_impaired: bool = False
    commentary: bool = False

    @property
    def supported(self) -> bool:
        return self.codec.lower() in TEXT_SUBTITLE_CODECS

    @property
    def restricted(self) -> bool:
        """Tam diyalog taşımayan akış (forced / SDH / yorum)."""
        if self.forced or self.hearing_impaired or self.commentary:
            return True
        # Disposition eksikse başlık İKİNCİL kanıttır.
        title = self.title.casefold()
        return any(token in title for token in (
            "forced", "sdh", "commentary", "comment", "hearing",
            "descriptive", "description", "narration"))

    @property
    def selection_rank(self) -> tuple:
        """Küçük olan önce seçilir: tam+default → tam → kısıtlı."""
        return (
            1 if self.restricted else 0,
            0 if self.default else 1,
            self.index,
        )

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
    except OSError as exc:
        raise VideoSubtitleError(
            f"{Path(command[0]).name} başlatılamadı: {exc}"
        ) from exc


def probe_subtitle_streams(video_path, runner=subprocess.run, which=shutil.which):
    video = Path(video_path)
    if not video.is_file():
        raise VideoSubtitleError(f"Video dosyası bulunamadı: {video}")
    ffprobe = _tool_path("ffprobe", which=which)
    command = [
        ffprobe, "-v", "error", "-select_streams", "s",
        "-show_entries",
        "stream=index,codec_name,disposition:stream_tags=language,title",
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
    if not isinstance(payload, dict):
        raise VideoSubtitleError("ffprobe geçersiz altyazı akışı verisi döndürdü.")
    raw_streams = payload.get("streams") or []
    if not isinstance(raw_streams, list):
        raise VideoSubtitleError("ffprobe geçersiz altyazı akışı listesi döndürdü.")
    streams = []
    for item in raw_streams:
        if not isinstance(item, dict):
            continue
        try:
            index = int(item["index"])
        except (KeyError, TypeError, ValueError):
            continue
        tags = item.get("tags") or {}
        if not isinstance(tags, dict):
            tags = {}
        disposition = item.get("disposition") or {}
        if not isinstance(disposition, dict):
            disposition = {}
        streams.append(SubtitleStream(
            index=index,
            codec=str(item.get("codec_name") or "unknown").strip().lower(),
            language=str(tags.get("language") or "").strip(),
            title=str(tags.get("title") or "").strip(),
            default=bool(disposition.get("default")),
            forced=bool(disposition.get("forced")),
            hearing_impaired=bool(disposition.get("hearing_impaired")),
            commentary=bool(disposition.get("comment")
                            or disposition.get("descriptions")),
        ))
    return streams


def _source_fingerprint(video: Path) -> str:
    """Videonun kimliği. Örnekleme baş/son ile SINIRLI DEĞİL.

    Eskiden yalnız boyut, mtime ve ilk/son 64 KiB kapsanıyordu; aynı boyut ve
    mtime ile ortası değiştirilmiş bir video eski gömülü altyazı cache'ini geri
    veriyordu (denetim 2026-08-20, madde 26). Artık dosya boyunca eşit aralıklı
    parçalar da örneklenir: tam hash büyük videolarda pahalı, çoklu örnekleme
    ise orta bölge değişimini yakalar.
    """
    stat = video.stat()
    sample_size = 65536
    digest = hashlib.sha256()
    with video.open("rb") as handle:
        handle.seek(0)
        digest.update(handle.read(sample_size))
        if stat.st_size > sample_size:
            # Dosya boyunca 8 ara nokta: ortadaki değişiklikler de imzaya girer.
            for step in range(1, 9):
                offset = (stat.st_size * step) // 9
                handle.seek(max(0, min(offset, stat.st_size - 1)))
                digest.update(b"\0")
                digest.update(handle.read(sample_size))
            handle.seek(max(stat.st_size - sample_size, 0))
            digest.update(b"\0")
            digest.update(handle.read(sample_size))
    identity = (
        f"{video.resolve()}\0{stat.st_size}\0{stat.st_mtime_ns}\0"
        f"{digest.hexdigest()}"
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


def extracted_video_metadata(subtitle_path) -> dict:
    path = Path(subtitle_path)
    sidecar = _origin_sidecar(path)
    if not sidecar.is_file():
        return {}
    try:
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return {}
        source = Path(str(payload.get("source_video") or ""))
        if not source.is_absolute() or not source.is_file():
            return {}
        if path.resolve().parent != _cache_root(source).resolve():
            return {}
        return payload
    except Exception:
        pass
    return {}


def extracted_video_origin(subtitle_path):
    payload = extracted_video_metadata(subtitle_path)
    source = Path(str(payload.get("source_video") or ""))
    if source.is_absolute():
        return source
    return None


def extracted_video_language(subtitle_path) -> str:
    return str(extracted_video_metadata(subtitle_path).get("language") or "").strip()


_SUBTITLE_TIMESTAMP_RE = re.compile(
    r"\d{1,2}:\d{2}:\d{2}[.,]\d{2,3}\s*(?:-->|,)")


def _payload_has_timestamp(path: Path) -> bool:
    """Dosyada en az bir altyazı zaman damgası var mı (SRT/VTT/ASS ortak)."""
    try:
        head = path.read_bytes()[:65536].decode("utf-8", errors="replace")
    except OSError:
        return False
    return bool(_SUBTITLE_TIMESTAMP_RE.search(head))


def _cached_extraction_matches(output: Path, video: Path,
                               stream: SubtitleStream) -> bool:
    if not output.is_file() or output.stat().st_size <= 0:
        return False
    payload = extracted_video_metadata(output)
    try:
        cached_source = Path(str(payload.get("source_video") or "")).resolve()
        cached_index = int(payload.get("stream_index"))
    except (OSError, TypeError, ValueError):
        return False
    # Cache yalnız 'boş değil' diye geçerli sayılıyordu; bozuk ama dolu
    # payload yeniden çıkarımı engelliyordu (denetim 2026-08-20, madde 31).
    # Biçimden bağımsız asgari bütünlük: en az bir zaman damgası olmalı.
    if not _payload_has_timestamp(output):
        return False
    return (
        cached_source == video.resolve()
        and cached_index == int(stream.index)
        and str(payload.get("codec") or "").strip().lower()
        == stream.codec.strip().lower()
    )


def logical_subtitle_path(subtitle_path) -> Path:
    path = Path(subtitle_path)
    source_video = extracted_video_origin(path)
    if source_video is None:
        return path
    marker = f"{source_video.stem}."
    tail = path.name[len(marker):] if path.name.startswith(marker) else path.name
    video_ext = source_video.suffix.lstrip(".") or "video"
    return source_video.parent / f"{source_video.stem}.{video_ext}.{tail}"


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
    # ASS/SSA akışlarını SRT'ye dönüştürmek `{\an8}` gibi ekran konumlarını ve
    # tabela stillerini ffmpeg'de kırpar; projenin parse_ass + _restore_tags_blocks
    # motoru bunları geri yükleyemez. Bu akışları olduğu gibi kopyalayıp .ass yazıyoruz.
    keep_ass = stream.codec.strip().lower() in ASS_SUBTITLE_CODECS
    suffix = "ass" if keep_ass else "srt"
    output = _cache_root(video) / f"{stem}.track-{stream.index}.{language}.{suffix}"
    sidecar = _origin_sidecar(output)
    if _cached_extraction_matches(output, video, stream):
        return output
    output.parent.mkdir(parents=True, exist_ok=True)
    temp_output = output.with_name(f".{output.stem}.{uuid.uuid4().hex}.tmp.{suffix}")
    command = [
        ffmpeg, "-y", "-v", "error", "-i", str(video),
        "-map", f"0:{stream.index}",
        "-c:s", "copy" if keep_ass else "srt", str(temp_output),
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
