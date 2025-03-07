"""Class to interact with an FFmpeog stream."""
from __future__ import annotations

import json
import logging
import os
import subprocess as sp
from typing import TYPE_CHECKING

from tenacity import (
    Retrying,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from viseron.const import (
    ENV_CUDA_SUPPORTED,
    ENV_JETSON_NANO,
    ENV_RASPBERRYPI3,
    ENV_RASPBERRYPI4,
)
from viseron.domains.camera.shared_frames import SharedFrame
from viseron.exceptions import FFprobeError, FFprobeTimeout, StreamInformationError
from viseron.helpers.logs import LogPipe, UnhelpfullLogFilter
from viseron.watchdog.subprocess_watchdog import RestartablePopen

from .const import (
    CAMERA_INPUT_ARGS,
    CAMERA_SEGMENT_ARGS,
    CONFIG_AUDIO_CODEC,
    CONFIG_CODEC,
    CONFIG_FFMPEG_LOGLEVEL,
    CONFIG_FFMPEG_RECOVERABLE_ERRORS,
    CONFIG_FFPROBE_LOGLEVEL,
    CONFIG_FPS,
    CONFIG_GLOBAL_ARGS,
    CONFIG_HEIGHT,
    CONFIG_HOST,
    CONFIG_HWACCEL_ARGS,
    CONFIG_INPUT_ARGS,
    CONFIG_PASSWORD,
    CONFIG_PATH,
    CONFIG_PIX_FMT,
    CONFIG_PORT,
    CONFIG_PROTOCOL,
    CONFIG_RECORDER,
    CONFIG_RTSP_TRANSPORT,
    CONFIG_SEGMENTS_FOLDER,
    CONFIG_STREAM_FORMAT,
    CONFIG_SUBSTREAM,
    CONFIG_USERNAME,
    CONFIG_VIDEO_FILTERS,
    CONFIG_WIDTH,
    DEFAULT_AUDIO_CODEC,
    DEFAULT_CODEC,
    ENV_FFMPEG_PATH,
    FFMPEG_LOGLEVELS,
    FFPROBE_LOGLEVELS,
    FFPROBE_TIMEOUT,
    HWACCEL_CUDA_DECODER_CODEC_MAP,
    HWACCEL_JETSON_NANO_DECODER_CODEC_MAP,
    HWACCEL_RPI3_DECODER_CODEC_MAP,
    HWACCEL_RPI4_DECODER_CODEC_MAP,
    STREAM_FORMAT_MAP,
)

if TYPE_CHECKING:
    from viseron.components.ffmpeg.camera import Camera


class Stream:
    """Represents a stream of frames from a camera."""

    def __init__(self, config, camera: Camera, camera_identifier):
        self._logger = logging.getLogger(__name__ + "." + camera_identifier)
        self._logger.addFilter(
            UnhelpfullLogFilter(config[CONFIG_FFMPEG_RECOVERABLE_ERRORS])
        )
        self._config = config
        self._camera_identifier = camera_identifier

        self._camera: Camera = camera

        self._pipe = None
        self._segment_process = None
        self._log_pipe = LogPipe(
            self._logger, FFMPEG_LOGLEVELS[config[CONFIG_FFMPEG_LOGLEVEL]]
        )

        self._ffprobe_log_pipe = LogPipe(
            self._logger, FFPROBE_LOGLEVELS[config[CONFIG_FFPROBE_LOGLEVEL]]
        )
        self._ffprobe_timeout = FFPROBE_TIMEOUT

        self._output_stream_config = config
        if config.get(CONFIG_SUBSTREAM, None):
            self._output_stream_config = config[CONFIG_SUBSTREAM]

        stream_codec = None
        stream_audio_codec = None
        # If any of the parameters are unset we need to fetch them using FFprobe
        if (
            not self._output_stream_config[CONFIG_WIDTH]
            or not self._output_stream_config[CONFIG_HEIGHT]
            or not self._output_stream_config[CONFIG_FPS]
            or not self._output_stream_config[CONFIG_CODEC]
            or self._output_stream_config[CONFIG_CODEC] == DEFAULT_CODEC
            or self._output_stream_config[CONFIG_AUDIO_CODEC] == DEFAULT_AUDIO_CODEC
        ):
            (
                width,
                height,
                fps,
                stream_codec,
                stream_audio_codec,
            ) = self.get_stream_information(self.output_stream_url)

        self.width = (
            self._output_stream_config[CONFIG_WIDTH]
            if self._output_stream_config[CONFIG_WIDTH]
            else width
        )
        self.height = (
            self._output_stream_config[CONFIG_HEIGHT]
            if self._output_stream_config[CONFIG_HEIGHT]
            else height
        )
        self.fps = (
            self._output_stream_config[CONFIG_FPS]
            if self._output_stream_config[CONFIG_FPS]
            else fps
        )
        self.stream_codec = stream_codec
        self.stream_audio_codec = stream_audio_codec
        self._output_fps = self.fps

        if self.width and self.height and self.fps:
            pass
        else:
            raise StreamInformationError(self.width, self.height, self.fps)

        self.create_symlink(self.alias)
        self.create_symlink(self.segments_alias)

        self._pixel_format = self._output_stream_config[CONFIG_PIX_FMT]
        self._color_plane_width = self.width
        self._color_plane_height = int(self.height * 1.5)
        self._frame_bytes_size = int(self.width * self.height * 1.5)

    @property
    def stream_url(self):
        """Return stream url."""
        auth = ""
        if self._config[CONFIG_USERNAME] and self._config[CONFIG_PASSWORD]:
            auth = f"{self._config[CONFIG_USERNAME]}:{self._config[CONFIG_PASSWORD]}@"

        protocol = (
            self._config[CONFIG_PROTOCOL]
            if self._config[CONFIG_PROTOCOL]
            else STREAM_FORMAT_MAP[self._config[CONFIG_STREAM_FORMAT]]["protocol"]
        )
        return (
            f"{protocol}://"
            f"{auth}"
            f"{self._config[CONFIG_HOST]}:{self._config[CONFIG_PORT]}"
            f"{self._config[CONFIG_PATH]}"
        )

    @property
    def output_stream_url(self):
        """Return output stream url."""
        auth = ""
        if self._config[CONFIG_USERNAME] and self._config[CONFIG_PASSWORD]:
            auth = f"{self._config[CONFIG_USERNAME]}:{self._config[CONFIG_PASSWORD]}@"

        protocol = (
            self._output_stream_config[CONFIG_PROTOCOL]
            if self._output_stream_config[CONFIG_PROTOCOL]
            else STREAM_FORMAT_MAP[self._output_stream_config[CONFIG_STREAM_FORMAT]][
                "protocol"
            ]
        )
        return (
            f"{protocol}://"
            f"{auth}"
            f"{self._config[CONFIG_HOST]}:{self._output_stream_config[CONFIG_PORT]}"
            f"{self._output_stream_config[CONFIG_PATH]}"
        )

    @property
    def output_args(self):
        """Return FFmpeg output args."""
        return [
            "-f",
            "rawvideo",
            "-pix_fmt",
            self._output_stream_config[CONFIG_PIX_FMT],
            "pipe:1",
        ]

    @property
    def alias(self):
        """Return FFmpeg executable alias."""
        return f"ffmpeg_{self._camera_identifier}"

    @property
    def segments_alias(self):
        """Return FFmpeg segments executable alias."""
        return f"ffmpeg_{self._camera_identifier}_seg"

    @staticmethod
    def create_symlink(alias):
        """Create a symlink to FFmpeg executable.

        This is done to know which FFmpeg command belongs to which camera.
        """
        try:
            os.symlink(os.getenv(ENV_FFMPEG_PATH), f"/home/abc/bin/{alias}")
        except FileExistsError:
            pass

    @property
    def output_fps(self):
        """Return stream output FPS."""
        return self._output_fps

    @output_fps.setter
    def output_fps(self, fps):
        self._output_fps = fps

    def run_ffprobe(
        self,
        stream_url: str,
    ) -> dict:
        """Run FFprobe command."""
        ffprobe_command = (
            [
                "ffprobe",
                "-hide_banner",
                "-loglevel",
            ]
            + [self._config[CONFIG_FFPROBE_LOGLEVEL]]
            + [
                "-print_format",
                "json",
                "-show_error",
                "-show_streams",
            ]
            + [stream_url]
        )
        self._logger.debug(f"FFprobe command: {' '.join(ffprobe_command)}")

        for attempt in Retrying(
            retry=retry_if_exception_type((sp.TimeoutExpired, FFprobeTimeout)),
            stop=stop_after_attempt(10),
            wait=wait_exponential(multiplier=2, min=1, max=30),
            before_sleep=before_sleep_log(self._logger, logging.ERROR),
            reraise=True,
        ):
            with attempt:
                pipe = sp.Popen(  # type: ignore
                    ffprobe_command,
                    stdout=sp.PIPE,
                    stderr=self._log_pipe,
                )
                try:
                    stdout, _ = pipe.communicate(timeout=self._ffprobe_timeout)
                    pipe.wait(timeout=FFPROBE_TIMEOUT)
                except sp.TimeoutExpired as error:
                    pipe.terminate()
                    pipe.wait(timeout=FFPROBE_TIMEOUT)
                    ffprobe_timeout = self._ffprobe_timeout
                    self._ffprobe_timeout += FFPROBE_TIMEOUT
                    raise FFprobeTimeout(ffprobe_timeout) from error
                self._ffprobe_timeout = FFPROBE_TIMEOUT

        try:
            # Trim away any text before start of JSON object
            trimmed_stdout = stdout[stdout.find(b"{") :]
            output: dict = json.loads(trimmed_stdout)
        except json.decoder.JSONDecodeError as error:
            raise FFprobeError(
                stdout,
            ) from error

        if output.get("error", None):
            raise FFprobeError(
                output,
            )

        return output

    def ffprobe_stream_information(self, stream_url):
        """Return stream information using FFprobe."""
        width, height, fps, codec, audio_codec = 0, 0, 0, None, None
        streams = self.run_ffprobe(stream_url)

        video_stream = None
        audio_stream = None
        for stream in streams["streams"]:
            if video_stream and audio_stream:
                break
            if stream["codec_type"] == "video":
                video_stream = stream
            elif stream["codec_type"] == "audio":
                audio_stream = stream

        if audio_stream:
            audio_codec = audio_stream.get("codec_name", None)

        try:
            numerator = int(video_stream.get("avg_frame_rate", 0).split("/")[0])
            denominator = int(video_stream.get("avg_frame_rate", 0).split("/")[1])
        except KeyError:
            return (width, height, fps, codec, audio_codec)

        try:
            fps = numerator / denominator
        except ZeroDivisionError:
            pass

        width = video_stream.get("width", 0)
        height = video_stream.get("height", 0)
        codec = video_stream.get("codec_name", None)

        return (width, height, fps, codec, audio_codec)

    def get_stream_information(self, stream_url):
        """Return stream information."""
        self._logger.debug(f"Getting stream information for {stream_url}")
        width, height, fps, codec, audio_codec = self.ffprobe_stream_information(
            stream_url
        )

        self._logger.debug(
            "Stream information from FFprobe: "
            f"Width: {width} "
            f"Height: {height} "
            f"FPS: {fps} "
            f"Video Codec: {codec} "
            f"Audio Codec: {audio_codec}"
        )
        return width, height, fps, codec, audio_codec

    @staticmethod
    def get_codec(stream_config, stream_codec):
        """Return codec set in config or from predefined codec map."""
        if stream_config[CONFIG_CODEC] and stream_config[CONFIG_CODEC] != DEFAULT_CODEC:
            return ["-c:v", stream_config[CONFIG_CODEC]]

        codec = None
        codec_map = None
        if stream_codec:
            if stream_config[CONFIG_STREAM_FORMAT] in ["rtsp", "rtmp"]:
                if os.getenv(ENV_RASPBERRYPI3) == "true":
                    codec_map = HWACCEL_RPI3_DECODER_CODEC_MAP
                elif os.getenv(ENV_RASPBERRYPI4) == "true":
                    codec_map = HWACCEL_RPI4_DECODER_CODEC_MAP
                elif os.getenv(ENV_JETSON_NANO) == "true":
                    codec_map = HWACCEL_JETSON_NANO_DECODER_CODEC_MAP
                elif os.getenv(ENV_CUDA_SUPPORTED) == "true":
                    codec_map = HWACCEL_CUDA_DECODER_CODEC_MAP
                if codec_map:
                    codec = codec_map.get(stream_codec, None)
        if codec:
            return ["-c:v", codec]
        return []

    def stream_command(self, stream_config, stream_codec, stream_url):
        """Return FFmpeg input stream."""
        if stream_config[CONFIG_INPUT_ARGS]:
            input_args = stream_config[CONFIG_INPUT_ARGS]
        else:
            input_args = (
                CAMERA_INPUT_ARGS
                + STREAM_FORMAT_MAP[self._config[CONFIG_STREAM_FORMAT]][
                    "timeout_option"
                ]
            )

        return (
            input_args
            + stream_config[CONFIG_HWACCEL_ARGS]
            + self.get_codec(stream_config, stream_codec)
            + (
                ["-rtsp_transport", stream_config[CONFIG_RTSP_TRANSPORT]]
                if self._config[CONFIG_STREAM_FORMAT] == "rtsp"
                else []
            )
            + ["-i", stream_url]
        )

    def get_audio_codec(self, stream_config, stream_audio_codec, extension):
        """Return audio codec used for saving segments."""
        if (
            stream_config[CONFIG_AUDIO_CODEC]
            and stream_config[CONFIG_AUDIO_CODEC] != DEFAULT_AUDIO_CODEC
        ):
            return ["-c:a", stream_config[CONFIG_AUDIO_CODEC]]

        if extension == "mp4" and stream_audio_codec in [
            "pcm_alaw",
            "pcm_mulaw",
        ]:
            self._logger.warning(
                f"Container mp4 does not support {stream_audio_codec} audio "
                "codec. Audio will be transcoded as aac."
            )
            return ["-c:a", "aac"]

        if (
            stream_audio_codec
            and stream_config[CONFIG_AUDIO_CODEC] == DEFAULT_AUDIO_CODEC
        ):
            return ["-c:a", "copy"]

        return []

    def segment_args(self):
        """Generate FFmpeg segment args."""
        return (
            CAMERA_SEGMENT_ARGS
            + self.get_audio_codec(
                self._config, self.stream_audio_codec, self._camera.extension
            )
            + [
                os.path.join(
                    self._config[CONFIG_RECORDER][CONFIG_SEGMENTS_FOLDER],
                    self._camera.identifier,
                    f"%Y%m%d%H%M%S.{self._camera.extension}",
                )
            ]
        )

    def filter_args(self):
        """Return filter arguments."""
        filters = self._config[CONFIG_VIDEO_FILTERS].copy()
        if self.output_fps < self.fps:
            filters.append(f"fps={self.output_fps}")

        if filters:
            return [
                "-vf",
                ",".join(filters),
            ]
        return []

    def build_segment_command(self):
        """Return command for writing segments only from main stream.

        Only used when a substream is configured.
        """
        stream_input_command = self.stream_command(
            self._config, self.stream_codec, self.stream_url
        )
        return (
            [self.segments_alias]
            + self._config[CONFIG_GLOBAL_ARGS]
            + ["-loglevel"]
            + [self._config[CONFIG_FFMPEG_LOGLEVEL]]
            + stream_input_command
            + self.segment_args()
        )

    def build_command(self):
        """Return full FFmpeg command."""
        if self._config.get(CONFIG_SUBSTREAM, None):
            stream_input_command = self.stream_command(
                self._output_stream_config,
                self.stream_codec,
                self.output_stream_url,
            )
        else:
            stream_input_command = self.stream_command(
                self._config, self.stream_codec, self.stream_url
            )

        camera_segment_args = []
        if not self._config.get(CONFIG_SUBSTREAM, None):
            camera_segment_args = self.segment_args()

        return (
            [self.alias]
            + self._config[CONFIG_GLOBAL_ARGS]
            + ["-loglevel"]
            + [self._config[CONFIG_FFMPEG_LOGLEVEL]]
            + stream_input_command
            + camera_segment_args
            + self.filter_args()
            + self.output_args
        )

    def pipe(self):
        """Return subprocess pipe for FFmpeg."""
        if self._config.get(CONFIG_SUBSTREAM, None):
            self._segment_process = RestartablePopen(
                self.build_segment_command(),
                name=f"viseron.camera.{self._camera.identifier}.segments",
                stdout=sp.PIPE,
                stderr=self._log_pipe,
            )

        return sp.Popen(
            self.build_command(),
            stdout=sp.PIPE,
            stderr=self._log_pipe,
        )

    def start_pipe(self):
        """Start piping frames from FFmpeg."""
        self._logger.debug(f"FFmpeg decoder command: {' '.join(self.build_command())}")
        if self._config.get(CONFIG_SUBSTREAM, None):
            self._logger.debug(
                f"FFmpeg segments command: {' '.join(self.build_segment_command())}"
            )

        self._pipe = self.pipe()

    def close_pipe(self):
        """Close FFmpeg pipe."""
        if self._segment_process:
            self._segment_process.terminate()

        try:
            self._pipe.terminate()
            try:
                self._pipe.communicate(timeout=5)
            except sp.TimeoutExpired:
                self._logger.debug("FFmpeg did not terminate, killing instead.")
                self._pipe.kill()
                self._pipe.communicate()
        except AttributeError as error:
            self._logger.error("Failed to close pipe: %s", error)

    def poll(self):
        """Poll pipe."""
        return self._pipe.poll()

    def read(self):
        """Return a single frame from FFmpeg pipe."""
        if self._pipe:
            try:
                frame_bytes = self._pipe.stdout.read(self._frame_bytes_size)
                if len(frame_bytes) == self._frame_bytes_size:
                    shared_frame = SharedFrame(
                        self._color_plane_width,
                        self._color_plane_height,
                        self._pixel_format,
                        (self.width, self.height),
                        self._camera_identifier,
                    )
                    self._camera.shared_frames.create(shared_frame, frame_bytes)
                    return shared_frame
            except Exception as err:  # pylint: disable=broad-except
                self._logger.error(f"Error reading frame from FFmpeg: {err}")
        return None
