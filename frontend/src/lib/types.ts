import { AxiosError } from "axios";

type WebSocketPongResponse = {
  command_id: number;
  type: "pong";
};

export type WebSocketEventResponse = {
  command_id: number;
  type: "event";
  event: Event;
};

export type WebSocketResultResponse = {
  command_id: number;
  type: "result";
  success: true;
  result: any;
};

export type WebSocketResultErrorResponse = {
  command_id: number;
  type: "result";
  success: false;
  error: {
    code: string;
    message: string;
  };
};

export type WebSocketResponse =
  | WebSocketPongResponse
  | WebSocketEventResponse
  | WebSocketResultResponse
  | WebSocketResultErrorResponse;

export type APISuccessResponse = {
  success: true;
};

export type APIErrorResponse = AxiosError<{
  status: number;
  error: string;
}>;

export type AuthEnabledResponse = {
  enabled: boolean;
  onboarding_complete: boolean;
};

export type AuthTokenResponse = {
  header: string;
  payload: string;
  expires_in: number;
  expires_at: number;
  session_expires_at: number;
};

export type AuthUserResponse = {
  name: string;
  username: string;
  group: string;
};

export type AuthLoginResponse = AuthTokenResponse;
export type OnboardingResponse = AuthTokenResponse;

export interface Recording {
  date: string;
  filename: string;
  path: string;
  thumbnail_path: string;
}

export interface RecordingsAll {
  [identifier: string]: {
    [date: string]: {
      [filename: string]: Recording;
    };
  };
}

export interface RecordingsCamera {
  [date: string]: {
    [filename: string]: Recording;
  };
}

export interface Camera {
  identifier: string;
  name: string;
  width: number;
  height: number;
  access_token: string;
  failed: false;
}

export interface Cameras {
  [identifier: string]: Camera;
}

export interface FailedCamera {
  identifier: string;
  name: string;
  width: number;
  height: number;
  error: string;
  retrying: boolean;
  failed: true;
}

export interface FailedCameras {
  [identifier: string]: FailedCamera;
}

export interface DetectedObject {
  label: string;
  confidence: number;
  rel_width: number;
  rel_height: number;
  rel_x1: number;
  rel_y1: number;
  rel_x2: number;
  rel_y2: number;
}

export type EventBase = {
  timestamp: number;
};

export type Event = EventBase & {
  name: string;
  data: { [key: string]: any };
};

export type EventCameraRegistered = Event & {
  name: "camera_registered";
  data: Camera;
};

export type EventRecorderComplete = Event & {
  name: "recorder_complete";
  data: {
    camera: Camera;
    recording: Recording & {
      start_time: string;
      start_timestamp: number;
      end_time: string;
      end_timestamp: number;
      objects: [DetectedObject];
    };
  };
};

export interface EntityAttributes {
  name: string;
  domain: string;
  [key: string]: any;
}

export interface Entity {
  entity_id: string;
  state: string;
  attributes: EntityAttributes;
}

export interface Entities {
  [index: string]: Entity;
}

export interface State {
  entity_id: string;
  state: string;
  attributes: EntityAttributes;
  timestamp: number;
}

export type StateChangedEvent = EventBase & {
  name: "state_changed";
  data: {
    entity_id: string;
    current_state: State;
    previous_state: State;
  };
};
