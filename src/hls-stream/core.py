from typing import Callable, Any
import ffmpeg
import enum
import numpy as np
import time
import os
import cv2
from logger import logger
import threading
from pathlib import Path
import json
import shutil


class HLSPresets(enum.Enum):
    DEFAULT_CPU = {
        "vcodec": "libx264",
        "preset": "veryfast",
        "video_bitrate": "6M",
        "maxrate": "6M",
        "bufsize": "6M",
    }
    DEFAULT_GPU = {
        "vcodec": "h264_nvenc",
        "preset": "p3",  # https://gist.github.com/nico-lab/e1ba48c33bf2c7e1d9ffdd9c1b8d0493
        "tune": "ll",
        "video_bitrate": "6M",
        "maxrate": "6M",
        "bufsize": "6M",
    }


# For preset settings
# https://obsproject.com/blog/streaming-with-x264#:~:text=x264%20has%20several%20CPU%20presets,%2C%20slower%2C%20veryslow%2C%20placebo.


class HLSEncoder:
    def __init__(
        self,
        out_path: Path,
        shape: tuple[int, int] = (1080, 1920),
        input_fps: int = 30,
        use_wallclock_pts: bool = False,
        preset: HLSPresets = HLSPresets.DEFAULT_CPU,
        **hls_kwargs,
    ) -> None:
        self.out_path = out_path
        self.shape = shape

        self.inp_settings = {
            "format": "rawvideo",
            "pix_fmt": "rgb24",
            "s": "{}x{}".format(shape[1], shape[0]),
            "r": input_fps,
            "use_wallclock_as_timestamps": use_wallclock_pts,
        }
        self.enc_settings = {
            "format": "hls",
            "pix_fmt": "yuv420p",
            "hls_time": 2,
            "hls_list_size": 2 * 60 / 2,  # 10 minutes keep
            "hls_flags": "delete_segments",  # remove outdated segments from disk
            "start_number": 0,
            **preset.value,
            **hls_kwargs,
        }
        # Compute keyframe interval for most precise segment duration
        # Note, -g (GOP) and keyint_min is necessary to get exact duration segments.
        # https://sites.google.com/site/linuxencoding/x264-ffmpeg-mapping#:~:text=%2Dg%20(FFmpeg,Recommended%20default%3A%20250
        nkey = self.enc_settings["hls_time"] * self.inp_settings["r"]
        self.enc_settings["g"] = nkey
        self.enc_settings["keyint_min"] = nkey

        self.proc: Callable[[np.ndarray[np.uint8, Any]]] = None
        self.time: float = 0.0

    def __enter__(self) -> "HLSEncoder":
        self.time = 0.0
        self.proc = (
            ffmpeg.input("pipe:", **self.inp_settings)
            .output(str(self.out_path), **self.enc_settings, loglevel="quiet")
            .overwrite_output()
            .run_async(pipe_stdin=True)
        )
        return self

    def __exit__(self, type, value, traceback):
        self.proc.stdin.close()
        self.proc = None

    def __call__(self, rgb24: np.ndarray[np.uint8, Any]) -> float:
        if self.inp_settings["use_wallclock_as_timestamps"]:
            start_time = time.time()  # not very precise
        else:
            start_time = self.time
            self.time += 1 / self.inp_settings["r"]
        self.proc.stdin.write(rgb24.tobytes())
        return start_time


class HLSStream(threading.Thread):
    def __init__(self, encoder: HLSEncoder, cap: cv2.VideoCapture, id: str) -> None:
        self.encoder = encoder
        self.cap = cap
        self.id = id
        self.running = True
        super().__init__()

        # Start the thread
        self.start()

    def run(self) -> None:
        with self.encoder:
            while self.running:
                ret, frame = self.cap.read()
                if not ret:
                    logger.debug(f"Failed to read frame {self.id}")
                    continue
                self.encoder(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

    def stop(self) -> None:
        self.running = False


class HLSManager:
    def __init__(self, path) -> None:
        self.config_path = path
        self.config = json.load(open(path, "r"))
        self.encoders = {}
        self.streams = {}

        os.makedirs("stream", exist_ok=True)
        for stream in self.config:
            id, rtsp_url = stream, self.config[stream]["rtsp_url"]
            self.start_stream(id, rtsp_url)

    def start_stream(self, id: str, rtsp_url: str):
        logger.info(f"Creating HLS encoder for stream {id}")
        try:
            os.makedirs(os.path.join("stream", id), exist_ok=True)
            out_path = os.path.join("stream", id, f"index.m3u8")
            cap = cv2.VideoCapture(rtsp_url)
            fps = int(cap.get(cv2.CAP_PROP_FPS))
            shape = (
                int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            )
            self.encoders[id] = HLSEncoder(
                out_path,
                shape=shape,
                input_fps=fps,
                use_wallclock_pts=False,
                preset=HLSPresets.DEFAULT_CPU,
            )
            self.streams[id] = HLSStream(self.encoders[id], cap, id)
            return self.encoders[id]
        except Exception as e:
            logger.error(f"Failed to create HLS encoder for stream {id}: {e}")
            return None

    def add_stream(self, id: str, rtsp_url: str):

        if id in self.config:
            logger.error(f"Stream {id} already exists")
            return

        res = self.start_stream(id, rtsp_url)
        if res is not None:
            self.config[id] = {
                "rtsp_url": rtsp_url,
                "hls_postfix": f"/stream/{id}/index.m3u8",
            }
            json.dump(self.config, open(self.config_path, "w"), indent=4)

        return res

    def remove_stream(self, id: str) -> None:
        logger.info(f"Removing HLS encoder for stream {id}")
        stream = self.streams.pop(id, None)
        if stream is not None:
            stream.stop()

        self.encoders.pop(id, None)
        self.config.pop(id, None)
        json.dump(self.config, open(self.config_path, "w"), indent=4)
        shutil.rmtree(os.path.join("stream", id))

    def stop(self):
        for id in self.streams:
            self.streams[id].stop()
            shutil.rmtree(os.path.join("stream", id))
            self.streams[id].join()


def main():
    pass


if __name__ == "__main__":
    main()
