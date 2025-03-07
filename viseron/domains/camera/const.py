"""Camera domain constants."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "camera"

UPDATE_TOKEN_INTERVAL_MINUTES: Final = 5

# Event topic constants
EVENT_STATUS = "{camera_identifier}/camera/status"
EVENT_STATUS_DISCONNECTED = "disconnected"
EVENT_STATUS_CONNECTED = "connected"

EVENT_RECORDER_START = "{camera_identifier}/recorder/start"
EVENT_RECORDER_STOP = "{camera_identifier}/recorder/stop"
EVENT_RECORDER_COMPLETE = "{camera_identifier}/recorder/complete"

EVENT_CAMERA_START = "{camera_identifier}/camera/start"
EVENT_CAMERA_STOP = "{camera_identifier}/camera/stop"
EVENT_CAMERA_STARTED = "{camera_identifier}/camera/started"
EVENT_CAMERA_STOPPED = "{camera_identifier}/camera/stopped"


# MJPEG_STREAM_SCHEMA constants
CONFIG_MJPEG_WIDTH = "width"
CONFIG_MJPEG_HEIGHT = "height"
CONFIG_MJPEG_DRAW_OBJECTS = "draw_objects"
CONFIG_MJPEG_DRAW_MOTION = "draw_motion"
CONFIG_MJPEG_DRAW_MOTION_MASK = "draw_motion_mask"
CONFIG_MJPEG_DRAW_OBJECT_MASK = "draw_object_mask"
CONFIG_MJPEG_DRAW_ZONES = "draw_zones"
CONFIG_MJPEG_ROTATE = "rotate"
CONFIG_MJPEG_MIRROR = "mirror"

DEFAULT_MJPEG_WIDTH = 0
DEFAULT_MJPEG_HEIGHT = 0
DEFAULT_MJPEG_DRAW_OBJECTS = False
DEFAULT_MJPEG_DRAW_MOTION = False
DEFAULT_MJPEG_DRAW_MOTION_MASK = False
DEFAULT_MJPEG_DRAW_OBJECT_MASK = False
DEFAULT_MJPEG_DRAW_ZONES = False
DEFAULT_MJPEG_ROTATE = 0
DEFAULT_MJPEG_MIRROR = False

DESC_MJPEG_WIDTH = "Frame will be rezied to this width. Required if height is set."
DESC_MJPEG_HEIGHT = "Frame will be rezied to this height. Required if width is set."
DESC_MJPEG_DRAW_OBJECTS = "If set, found objects will be drawn."
DESC_MJPEG_DRAW_MOTION = "If set, detected motion will be drawn."
DESC_MJPEG_DRAW_MOTION_MASK = "If set, configured motion masks will be drawn."
DESC_MJPEG_DRAW_OBJECT_MASK = "If set, configured object masks will be drawn."
DESC_MJPEG_DRAW_ZONES = "If set, configured zones will be drawn."
DESC_MJPEG_ROTATE = (
    "Degrees to rotate the image. "
    "Positive/negative values rotate clockwise/counter clockwise respectively"
)
DESC_MJPEG_MIRROR = "If set, mirror the image horizontally."


# THUMBNAIL_SCHEMA constants
CONFIG_SAVE_TO_DISK = "save_to_disk"

DEFAULT_SAVE_TO_DISK = True

DESC_SAVE_TO_DISK = (
    "If <code>true</code>, the thumbnail that is created on start of recording is "
    "saved to <code>{folder}/{camera_identifier}/latest_thumbnail.jpg</code>"
)


# RECORDER_SCHEMA constants
CONFIG_LOOKBACK = "lookback"
CONFIG_IDLE_TIMEOUT = "idle_timeout"
CONFIG_RETAIN = "retain"
CONFIG_FOLDER = "folder"
CONFIG_FILENAME_PATTERN = "filename_pattern"
CONFIG_EXTENSION = "extension"
CONFIG_THUMBNAIL = "thumbnail"

DEFAULT_LOOKBACK = 5
DEFAULT_IDLE_TIMEOUT = 10
DEFAULT_RETAIN = 7
DEFAULT_FOLDER = "/recordings"
DEFAULT_FILENAME_PATTERN = "%H:%M:%S"
DEFAULT_EXTENSION = "mp4"
DEFAULT_THUMBNAIL = None

DESC_LOOKBACK = "Number of seconds to record before a detected object."
DESC_IDLE_TIMEOUT = "Number of seconds to record after all events are over."
DESC_RETAIN = "Number of days to save recordings before deletion."
DESC_FOLDER = "What folder to store recordings in."
DESC_FILENAME_PATTERN = (
    "A <a href=https://strftime.org/>strftime</a> pattern for saved recordings.<br>"
    "Default pattern results in filenames like: <code>23:59:59.jpg</code>."
)
DESC_EXTENSION = "The file extension used for recordings."
DESC_THUMBNAIL = "Options for the thumbnail created on start of a recording."
DESC_FILENAME_PATTERN_THUMBNAIL = (
    "A <a href=https://strftime.org/>strftime</a> pattern for saved thumbnails.<br>"
    "Default pattern results in filenames like: <code>23:59:59.jpg</code>."
)


# BASE_CONFIG_SCHEMA constants
CONFIG_NAME = "name"
CONFIG_MJPEG_STREAMS = "mjpeg_streams"
CONFIG_RECORDER = "recorder"

DEFAULT_NAME = None
DEFAULT_MJPEG_STREAMS = None
DEFAULT_RECORDER = None

DESC_NAME = "Camera friendly name."
DESC_MJPEG_STREAMS = "MJPEG streams config."
DESC_RECORDER = "Recorder config."
DESC_MJPEG_STREAM = (
    "Name of the MJPEG stream. Used to build the URL to access the stream.<br>"
    "Valid characters are lowercase a-z, numbers and underscores."
)
