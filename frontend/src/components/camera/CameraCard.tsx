import Image from "@jy95/material-ui-image";
import Card from "@mui/material/Card";
import CardActions from "@mui/material/CardActions";
import CardContent from "@mui/material/CardContent";
import CardMedia from "@mui/material/CardMedia";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import { useCallback, useContext, useEffect, useRef, useState } from "react";
import { usePageVisibility } from "react-page-visibility";

import {
  CardActionButtonHref,
  CardActionButtonLink,
} from "components/CardActionButton";
import { AuthContext } from "context/AuthContext";
import { ViseronContext } from "context/ViseronContext";
import useOnScreen from "hooks/UseOnScreen";
import { useCamera } from "lib/api/camera";
import queryClient from "lib/api/client";
import { subscribeStates } from "lib/commands";
import * as types from "lib/types";
import { SubscriptionUnsubscribe } from "lib/websockets";

interface CameraCardProps {
  camera_identifier: string;
}

const blankImage =
  "data:image/svg+xml;charset=utf8,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%3E%3C/svg%3E";

const useCameraToken = (camera_identifier: string, auth_enabled: boolean) => {
  const { connected, connection } = useContext(ViseronContext);
  const unsubRef = useRef<SubscriptionUnsubscribe | null>(null);

  useEffect(() => {
    // If auth is disabled, we dont need to sub for tokens
    if (!auth_enabled) {
      return;
    }
    const stateChanged = async (
      _stateChangedEvent: types.StateChangedEvent
    ) => {
      queryClient.invalidateQueries(["camera", camera_identifier]);
    };

    const unsubscribeEntities = async () => {
      if (unsubRef.current) {
        await unsubRef.current();
      }
      unsubRef.current = null;
    };

    const subcscribeEntities = async () => {
      if (connection && connected) {
        unsubRef.current = await subscribeStates(
          connection,
          stateChanged,
          `sensor.${camera_identifier}_access_token`,
          undefined,
          false
        );
      } else if (connection && !connected && unsubRef.current) {
        await unsubscribeEntities();
      }
    };
    subcscribeEntities();
    // eslint-disable-next-line consistent-return
    return () => {
      unsubscribeEntities();
    };
  }, [auth_enabled, camera_identifier, connected, connection]);
};

export default function CameraCard({ camera_identifier }: CameraCardProps) {
  const { connected } = useContext(ViseronContext);
  const { auth } = useContext(AuthContext);
  const theme = useTheme();
  const ref: any = useRef<HTMLDivElement>();
  const onScreen = useOnScreen<HTMLDivElement>(ref, "-1px");
  const isVisible = usePageVisibility();
  const [initialRender, setInitialRender] = useState(true);
  const cameraQuery = useCamera(camera_identifier, false, {
    enabled: connected,
  });

  const generateSnapshotURL = useCallback(
    (width = null) =>
      `/api/v1/camera/${camera_identifier}/snapshot?rand=${(Math.random() + 1)
        .toString(36)
        .substring(7)}${width ? `&width=${Math.trunc(width)}` : ""}`,
    [camera_identifier]
  );
  const [snapshotURL, setSnapshotURL] = useState({
    // Show blank image on start
    url: blankImage,
    disableSpinner: false,
    disableTransition: false,
    loading: true,
  });
  const updateSnapshot = useRef<NodeJS.Timer | null>();
  const updateImage = useCallback(() => {
    setSnapshotURL((prevSnapshotURL) => {
      if (cameraQuery.isFetching) {
        // Dont load new image if we are loading token
        return prevSnapshotURL;
      }
      if (prevSnapshotURL.loading && !initialRender) {
        // Dont load new image if we are still loading
        return prevSnapshotURL;
      }
      if (initialRender) {
        // Make sure we show the spinner on the first image fetched.
        setInitialRender(false);
        return {
          url: generateSnapshotURL(
            ref.current ? ref.current.offsetWidth : null
          ),
          disableSpinner: false,
          disableTransition: false,
          loading: true,
        };
      }
      return {
        ...prevSnapshotURL,
        url: generateSnapshotURL(ref.current ? ref.current.offsetWidth : null),
        loading: true,
      };
    });
  }, [cameraQuery.isFetching, generateSnapshotURL, initialRender]);

  useEffect(() => {
    // If element is on screen and browser is visible, start interval to fetch images
    if (onScreen && isVisible && connected && cameraQuery.isSuccess) {
      updateImage();
      updateSnapshot.current = setInterval(() => {
        updateImage();
      }, 10000);
      // If element is hidden or browser loses focus, stop updating images
    } else if (updateSnapshot.current) {
      clearInterval(updateSnapshot.current);
    }
    return () => {
      // Stop updating on unmount
      if (updateSnapshot.current) {
        clearInterval(updateSnapshot.current);
      }
    };
  }, [updateImage, isVisible, onScreen, connected, cameraQuery.isSuccess]);

  useCameraToken(camera_identifier, auth.enabled);

  return (
    <div ref={ref}>
      {cameraQuery.data && (
        <Card
          ref={ref}
          variant="outlined"
          sx={{
            // Vertically space items evenly to accommodate different aspect ratios
            height: "100%",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
          }}
        >
          <CardContent>
            <Typography variant="h5" align="center">
              {cameraQuery.data.name}
            </Typography>
          </CardContent>
          <CardMedia>
            {/* 'alt=""' in combination with textIndent is a neat trick to hide the broken image icon */}
            <Image
              alt=""
              imageStyle={{ textIndent: "-10000px" }}
              src={`${snapshotURL.url}${
                auth.enabled
                  ? `&access_token=${cameraQuery.data?.access_token}`
                  : ""
              }`}
              disableSpinner={snapshotURL.disableSpinner}
              disableTransition={snapshotURL.disableTransition}
              animationDuration={1000}
              aspectRatio={cameraQuery.data.width / cameraQuery.data.height}
              color={theme.palette.background.default}
              onLoad={() => {
                setSnapshotURL((prevSnapshotURL) => ({
                  ...prevSnapshotURL,
                  disableSpinner: true,
                  disableTransition: true,
                  loading: false,
                }));
              }}
              errorIcon={Image.defaultProps!.loading}
              onError={() => {
                setSnapshotURL((prevSnapshotURL) => ({
                  ...prevSnapshotURL,
                  disableSpinner: false,
                  disableTransition: false,
                  loading: false,
                }));
              }}
            />
          </CardMedia>
          <CardActions>
            <CardActionButtonLink
              title="Recordings"
              target={`/recordings/${cameraQuery.data.identifier}`}
            />
            <CardActionButtonHref
              title="Live View"
              target={`/${cameraQuery.data.identifier}/mjpeg-stream`}
            />
          </CardActions>
        </Card>
      )}
    </div>
  );
}
