"""GStreamer camera."""
from __future__ import annotations

import datetime
import time
from threading import Event
from typing import TYPE_CHECKING, List

import cv2
import voluptuous as vol

from viseron import Viseron
from viseron.domains.camera import (
    BASE_CONFIG_SCHEMA as BASE_CAMERA_CONFIG_SCHEMA,
    DEFAULT_RECORDER,
    RECORDER_SCHEMA as BASE_RECORDER_SCHEMA,
    AbstractCamera,
)
from viseron.domains.camera.const import (
    DOMAIN,
    EVENT_CAMERA_STARTED,
    EVENT_CAMERA_STOPPED,
)
from viseron.helpers.validators import CameraIdentifier, CoerceNoneToDict, Maybe
from viseron.watchdog.thread_watchdog import RestartableThread

from .const import (
    COMPONENT,
    CONFIG_AUDIO_CODEC,
    CONFIG_AUDIO_PIPELINE,
    CONFIG_CODEC,
    CONFIG_FFPROBE_LOGLEVEL,
    CONFIG_FPS,
    CONFIG_FRAME_TIMEOUT,
    CONFIG_GSTREAMER_LOGLEVEL,
    CONFIG_GSTREAMER_RECOVERABLE_ERRORS,
    CONFIG_HEIGHT,
    CONFIG_HOST,
    CONFIG_MUXER,
    CONFIG_PASSWORD,
    CONFIG_PATH,
    CONFIG_PORT,
    CONFIG_PROTOCOL,
    CONFIG_RECORDER,
    CONFIG_RECORDER_AUDIO_CODEC,
    CONFIG_RECORDER_CODEC,
    CONFIG_RECORDER_FILTER_ARGS,
    CONFIG_RECORDER_HWACCEL_ARGS,
    CONFIG_RTSP_TRANSPORT,
    CONFIG_SEGMENTS_FOLDER,
    CONFIG_STREAM_FORMAT,
    CONFIG_USERNAME,
    CONFIG_WIDTH,
    DEFAULT_AUDIO_CODEC,
    DEFAULT_AUDIO_PIPELINE,
    DEFAULT_CODEC,
    DEFAULT_FFPROBE_LOGLEVEL,
    DEFAULT_FPS,
    DEFAULT_FRAME_TIMEOUT,
    DEFAULT_GSTREAMER_LOGLEVEL,
    DEFAULT_GSTREAMER_RECOVERABLE_ERRORS,
    DEFAULT_HEIGHT,
    DEFAULT_MUXER,
    DEFAULT_PASSWORD,
    DEFAULT_PROTOCOL,
    DEFAULT_RECORDER_AUDIO_CODEC,
    DEFAULT_RECORDER_CODEC,
    DEFAULT_RECORDER_FILTER_ARGS,
    DEFAULT_RECORDER_HWACCEL_ARGS,
    DEFAULT_RTSP_TRANSPORT,
    DEFAULT_SEGMENTS_FOLDER,
    DEFAULT_STREAM_FORMAT,
    DEFAULT_USERNAME,
    DEFAULT_WIDTH,
    DESC_AUDIO_CODEC,
    DESC_AUDIO_PIPELINE,
    DESC_CODEC,
    DESC_FFPROBE_LOGLEVEL,
    DESC_FPS,
    DESC_FRAME_TIMEOUT,
    DESC_GSTREAMER_LOGLEVEL,
    DESC_GSTREAMER_RECOVERABLE_ERRORS,
    DESC_HEIGHT,
    DESC_HOST,
    DESC_MUXER,
    DESC_PASSWORD,
    DESC_PATH,
    DESC_PORT,
    DESC_PROTOCOL,
    DESC_RECORDER,
    DESC_RECORDER_AUDIO_CODEC,
    DESC_RECORDER_CODEC,
    DESC_RECORDER_FILTER_ARGS,
    DESC_RECORDER_HWACCEL_ARGS,
    DESC_RTSP_TRANSPORT,
    DESC_SEGMENTS_FOLDER,
    DESC_STREAM_FORMAT,
    DESC_USERNAME,
    DESC_WIDTH,
    GSTREAMER_LOGLEVELS,
    STREAM_FORMAT_MAP,
)
from .recorder import Recorder
from .stream import Stream

if TYPE_CHECKING:
    from viseron.domains.camera.shared_frames import SharedFrame
    from viseron.domains.object_detector.detected_object import DetectedObject

STREAM_SCEHMA_DICT = {
    vol.Required(CONFIG_PATH, description=DESC_PATH): vol.All(str, vol.Length(min=1)),
    vol.Required(CONFIG_PORT, description=DESC_PORT): vol.All(int, vol.Range(min=1)),
    vol.Optional(
        CONFIG_STREAM_FORMAT,
        default=DEFAULT_STREAM_FORMAT,
        description=DESC_STREAM_FORMAT,
    ): vol.In(STREAM_FORMAT_MAP.keys()),
    vol.Optional(
        CONFIG_PROTOCOL, default=DEFAULT_PROTOCOL, description=DESC_PROTOCOL
    ): Maybe(vol.Any("rtsp", "rtmp", "http", "https")),
    vol.Optional(CONFIG_WIDTH, default=DEFAULT_WIDTH, description=DESC_WIDTH): Maybe(
        int
    ),
    vol.Optional(CONFIG_HEIGHT, default=DEFAULT_HEIGHT, description=DESC_HEIGHT): Maybe(
        int
    ),
    vol.Optional(CONFIG_FPS, default=DEFAULT_FPS, description=DESC_FPS): Maybe(
        vol.All(int, vol.Range(min=1))
    ),
    vol.Optional(CONFIG_CODEC, default=DEFAULT_CODEC, description=DESC_CODEC): str,
    vol.Optional(
        CONFIG_AUDIO_CODEC, default=DEFAULT_AUDIO_CODEC, description=DESC_AUDIO_CODEC
    ): Maybe(str),
    vol.Optional(
        CONFIG_AUDIO_PIPELINE,
        default=DEFAULT_AUDIO_PIPELINE,
        description=DESC_AUDIO_PIPELINE,
    ): Maybe(str),
    vol.Optional(
        CONFIG_RTSP_TRANSPORT,
        default=DEFAULT_RTSP_TRANSPORT,
        description=DESC_RTSP_TRANSPORT,
    ): vol.Any(
        "tcp",
        "udp",
        "mcast",
    ),
    vol.Optional(
        CONFIG_FRAME_TIMEOUT,
        default=DEFAULT_FRAME_TIMEOUT,
        description=DESC_FRAME_TIMEOUT,
    ): vol.All(int, vol.Range(1, 60)),
}

RECORDER_SCHEMA = BASE_RECORDER_SCHEMA.extend(
    {
        vol.Optional(
            CONFIG_RECORDER_HWACCEL_ARGS,
            default=DEFAULT_RECORDER_HWACCEL_ARGS,
            description=DESC_RECORDER_HWACCEL_ARGS,
        ): [str],
        vol.Optional(
            CONFIG_RECORDER_CODEC,
            default=DEFAULT_RECORDER_CODEC,
            description=DESC_RECORDER_CODEC,
        ): str,
        vol.Optional(
            CONFIG_RECORDER_AUDIO_CODEC,
            default=DEFAULT_RECORDER_AUDIO_CODEC,
            description=DESC_RECORDER_AUDIO_CODEC,
        ): str,
        vol.Optional(
            CONFIG_RECORDER_FILTER_ARGS,
            default=DEFAULT_RECORDER_FILTER_ARGS,
            description=DESC_RECORDER_FILTER_ARGS,
        ): [str],
        vol.Optional(
            CONFIG_SEGMENTS_FOLDER,
            default=DEFAULT_SEGMENTS_FOLDER,
            description=DESC_SEGMENTS_FOLDER,
        ): str,
        vol.Optional(
            CONFIG_MUXER, default=DEFAULT_MUXER, description=DESC_MUXER
        ): vol.In(["mp4mux", "avimux"]),
    }
)

GSTREAMER_LOGLEVELSCHEMA = vol.Schema(vol.In(GSTREAMER_LOGLEVELS.keys()))

CAMERA_SCHEMA = BASE_CAMERA_CONFIG_SCHEMA.extend(STREAM_SCEHMA_DICT)

CAMERA_SCHEMA = CAMERA_SCHEMA.extend(
    {
        vol.Required(CONFIG_HOST, description=DESC_HOST): str,
        vol.Optional(
            CONFIG_USERNAME, default=DEFAULT_USERNAME, description=DESC_USERNAME
        ): Maybe(str),
        vol.Optional(
            CONFIG_PASSWORD, default=DEFAULT_PASSWORD, description=DESC_PASSWORD
        ): Maybe(str),
        vol.Optional(
            CONFIG_GSTREAMER_LOGLEVEL,
            default=DEFAULT_GSTREAMER_LOGLEVEL,
            description=DESC_GSTREAMER_LOGLEVEL,
        ): GSTREAMER_LOGLEVELSCHEMA,
        vol.Optional(
            CONFIG_GSTREAMER_RECOVERABLE_ERRORS,
            default=DEFAULT_GSTREAMER_RECOVERABLE_ERRORS,
            description=DESC_GSTREAMER_RECOVERABLE_ERRORS,
        ): [str],
        vol.Optional(
            CONFIG_FFPROBE_LOGLEVEL,
            default=DEFAULT_FFPROBE_LOGLEVEL,
            description=DESC_FFPROBE_LOGLEVEL,
        ): GSTREAMER_LOGLEVELSCHEMA,
        vol.Optional(
            CONFIG_RECORDER, default=DEFAULT_RECORDER, description=DESC_RECORDER
        ): vol.All(CoerceNoneToDict(), RECORDER_SCHEMA),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        CameraIdentifier(): CAMERA_SCHEMA,
    }
)


def setup(vis: Viseron, config, identifier):
    """Set up the gstreamer camera domain."""
    Camera(vis, config[identifier], identifier)
    return True


class Camera(AbstractCamera):
    """Represents a camera which is consumed via GStreamer."""

    def __init__(self, vis, config, identifier):
        self._poll_timer = None
        self._frame_reader = None

        super().__init__(vis, COMPONENT, config, identifier)
        self._capture_frames = False
        self._thread_stuck = False
        self.resolution = None
        self.decode_error = Event()

        if cv2.ocl.haveOpenCL():
            cv2.ocl.setUseOpenCL(True)
        vis.data[COMPONENT][self.identifier] = self
        self._recorder = Recorder(vis, config, self)

        self.initialize_camera()
        vis.register_domain(DOMAIN, self.identifier, self)

    def _create_frame_reader(self):
        """Return a frame reader thread."""
        return RestartableThread(
            name="viseron.camera." + self.identifier,
            target=self.read_frames,
            poll_method=self.poll_method,
            poll_target=self.poll_target,
            daemon=True,
            register=True,
            restart_method=self.start_camera,
        )

    def initialize_camera(self):
        """Start processing of camera frames."""
        self._poll_timer = None
        self._logger.debug("Initializing camera {}".format(self.name))

        self.stream = Stream(self._vis, self._config, self.identifier)

        self.resolution = self.stream.width, self.stream.height
        self._logger.debug(
            f"Resolution: {self.resolution[0]}x{self.resolution[1]} "
            f"@ {self.stream.fps} FPS"
        )

        self._logger.debug(f"Camera {self.name} initialized")

    def read_frames(self):
        """Read frames from camera."""
        self.decode_error.clear()
        self._poll_timer = datetime.datetime.now().timestamp()
        empty_frames = 0
        self._thread_stuck = False

        self.stream.start_pipe()

        while self._capture_frames:
            if self.decode_error.is_set():
                self._poll_timer = datetime.datetime.now().timestamp()
                self.connected = False
                time.sleep(5)
                self._logger.error("Restarting frame pipe")
                self.stream.close_pipe()
                self.stream.start_pipe()
                self.decode_error.clear()
                empty_frames = 0

            self.current_frame = self.stream.read()
            if self.current_frame:
                self.connected = True
                empty_frames = 0
                self._poll_timer = datetime.datetime.now().timestamp()
                self._data_stream.publish_data(
                    self.frame_bytes_topic, self.current_frame
                )
                continue

            if self._thread_stuck:
                return

            if self.stream.poll() is not None:
                self._logger.error("GStreamer process has exited")
                self.decode_error.set()
                continue

            empty_frames += 1
            if empty_frames >= 10:
                self._logger.error("Did not receive a frame")
                self.decode_error.set()

        self.connected = False
        self.stream.close_pipe()
        self._logger.debug("GStreamer frame reader stopped")

    def poll_target(self):
        """Close pipe when RestartableThread.poll_timeout has been reached."""
        self._logger.error("Timeout waiting for frame")
        self._thread_stuck = True
        self.stop_camera()

    def poll_method(self):
        """Return true on frame timeout for RestartableThread to trigger a restart."""
        now = datetime.datetime.now().timestamp()

        # Make sure we timeout at some point if we never get the first frame.
        if now - self._poll_timer > (DEFAULT_FRAME_TIMEOUT * 2):
            return True

        if not self.connected:
            return False

        if now - self._poll_timer > self._config[CONFIG_FRAME_TIMEOUT]:
            return True
        return False

    def start_camera(self):
        """Start capturing frames from camera."""
        self._logger.debug("Starting capture thread")
        self._capture_frames = True
        if not self._frame_reader or not self._frame_reader.is_alive():
            self._frame_reader = self._create_frame_reader()
            self._frame_reader.start()
            self._vis.dispatch_event(
                EVENT_CAMERA_STARTED.format(camera_identifier=self.identifier),
                None,
            )

    def stop_camera(self):
        """Release the connection to the camera."""
        self._logger.debug("Stopping capture thread")
        self._capture_frames = False
        if self._frame_reader:
            self._frame_reader.stop()
            self._frame_reader.join(timeout=5)
            if self._frame_reader.is_alive():
                self._logger.debug("Timed out trying to stop camera. Killing pipe")
                self.stream.close_pipe()

        self._vis.dispatch_event(
            EVENT_CAMERA_STOPPED.format(camera_identifier=self.identifier),
            None,
        )
        if self.is_recording:
            self.stop_recorder()

    def start_recorder(
        self, shared_frame: SharedFrame, objects_in_fov: List[DetectedObject] | None
    ):
        """Start camera recorder."""
        self._recorder.start(
            shared_frame, objects_in_fov if objects_in_fov else [], self.resolution
        )

    def stop_recorder(self):
        """Stop camera recorder."""
        self._recorder.stop()

    @property
    def poll_timer(self):
        """Return poll timer."""
        return self._poll_timer

    @property
    def output_fps(self):
        """Set stream output fps."""
        return self.stream.output_fps

    @output_fps.setter
    def output_fps(self, fps):
        self.stream.output_fps = fps

    @property
    def resolution(self):
        """Return stream resolution."""
        return self._resolution

    @resolution.setter
    def resolution(self, resolution):
        """Return stream resolution."""
        self._resolution = resolution

    @property
    def recorder(self) -> Recorder:
        """Return recorder instance."""
        return self._recorder

    @property
    def is_recording(self):
        """Return recording status."""
        return self._recorder.is_recording

    @property
    def is_on(self):
        """Return if camera is on."""
        if self._frame_reader:
            return self._frame_reader.is_alive()
        return False
