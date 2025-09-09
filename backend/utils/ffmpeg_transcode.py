import subprocess
from tempfile import NamedTemporaryFile


def transcode_wav_to_opus_bytes_sync(wav_bytes: bytes, bitrate: str = "32k") -> bytes:
    # запись во временный файл, запуск ffmpeg, чтение результата
    with NamedTemporaryFile(suffix=".wav") as in_f, NamedTemporaryFile(
        suffix=".opus"
    ) as out_f:
        in_f.write(wav_bytes)
        in_f.flush()
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            in_f.name,
            "-c:a",
            "libopus",
            "-b:a",
            bitrate,
            "-vbr",
            "on",
            out_f.name,
        ]
        subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        out_f.flush()
        out_f.seek(0)
        return out_f.read()
