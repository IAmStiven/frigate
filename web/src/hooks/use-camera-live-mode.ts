import { CameraConfig, FrigateConfig } from "@/types/frigateConfig";
import { useCallback, useEffect, useState, useMemo } from "react";
import useSWR from "swr";
import { LivePlayerMode } from "@/types/live";
import useDeferredStreamMetadata from "./use-deferred-stream-metadata";
import { detectCameraAudioFeatures } from "@/utils/cameraUtil";

export default function useCameraLiveMode(
  cameras: CameraConfig[],
  activeStreams?: { [cameraName: string]: string },
) {
  const { data: config } = useSWR<FrigateConfig>("config");

  // Compute which streams need metadata (restreamed streams only)
  const restreamedStreamNames = useMemo(() => {
    if (!cameras || !config) return [];

    const streamNames = new Set<string>();
    cameras.forEach((camera) => {
      if (activeStreams && activeStreams[camera.name]) {
        const selectedStreamName = activeStreams[camera.name];
        const isRestreamed = Object.keys(config.go2rtc.streams || {}).includes(
          selectedStreamName,
        );

        if (isRestreamed) {
          streamNames.add(selectedStreamName);
        }
      } else {
        Object.values(camera.live.streams).forEach((streamName) => {
          const isRestreamed = Object.keys(
            config.go2rtc.streams || {},
          ).includes(streamName);

          if (isRestreamed) {
            streamNames.add(streamName);
          }
        });
      }
    });

    return Array.from(streamNames);
  }, [cameras, config, activeStreams]);

  // Fetch stream metadata with deferred loading (doesn't block initial render)
  const streamMetadata = useDeferredStreamMetadata(restreamedStreamNames);

  // Derive stream capabilities instead of copying them into state. This keeps
  // camera visibility and metadata updates from causing cascading renders.
  const liveModeStates = useMemo(() => {
    const mseSupported =
      "MediaSource" in window || "ManagedMediaSource" in window;
    const preferred: { [key: string]: LivePlayerMode } = {};
    const restreamed: { [key: string]: boolean } = {};

    cameras.forEach((camera) => {
      const selectedStreamName =
        activeStreams?.[camera.name] ?? Object.values(camera.live.streams)[0];
      const isRestreamed = Boolean(
        config &&
          Object.prototype.hasOwnProperty.call(
            config.go2rtc.streams || {},
            selectedStreamName,
          ),
      );

      restreamed[camera.name] = isRestreamed;
      preferred[camera.name] = isRestreamed
        ? mseSupported
          ? "mse"
          : "webrtc"
        : "jsmpeg";
    });

    return { preferred, restreamed };
  }, [activeStreams, cameras, config]);

  const [preferredLiveModes, setPreferredLiveModes] = useState<{
    [key: string]: LivePlayerMode;
  }>({});

  useEffect(() => {
    setPreferredLiveModes((current) => {
      const next = liveModeStates.preferred;
      const currentKeys = Object.keys(current);
      const nextKeys = Object.keys(next);
      const unchanged =
        currentKeys.length === nextKeys.length &&
        nextKeys.every((key) => current[key] === next[key]);

      return unchanged ? current : next;
    });
  }, [liveModeStates.preferred]);

  const supportsAudioOutputStates = useMemo<{
    [key: string]: {
      supportsAudio: boolean;
      cameraName: string;
    };
  }>(() => {
    const states: {
      [key: string]: { supportsAudio: boolean; cameraName: string };
    } = {};

    cameras.forEach((camera) => {
      if (liveModeStates.restreamed[camera.name]) {
        Object.values(camera.live.streams).forEach((streamName) => {
          const metadata = streamMetadata[streamName];
          const audioFeatures = detectCameraAudioFeatures(metadata);
          states[streamName] = {
            supportsAudio: audioFeatures.audioOutput,
            cameraName: camera.name,
          };
        });
      } else {
        states[camera.name] = {
          supportsAudio: false,
          cameraName: camera.name,
        };
      }
    });

    return states;
  }, [cameras, liveModeStates.restreamed, streamMetadata]);

  const resetPreferredLiveMode = useCallback(
    (cameraName: string) => {
      const mseSupported =
        "MediaSource" in window || "ManagedMediaSource" in window;
      const cameraConfig = cameras.find((camera) => camera.name === cameraName);
      const selectedStreamName =
        activeStreams?.[cameraName] ??
        (cameraConfig
          ? Object.values(cameraConfig.live.streams)[0]
          : cameraName);
      const isRestreamed =
        config &&
        Object.keys(config.go2rtc.streams || {}).includes(selectedStreamName);

      setPreferredLiveModes((prevModes) => {
        const newModes = { ...prevModes };

        if (!mseSupported) {
          newModes[cameraName] = isRestreamed ? "webrtc" : "jsmpeg";
        } else {
          newModes[cameraName] = isRestreamed ? "mse" : "jsmpeg";
        }

        return newModes;
      });
    },
    [activeStreams, cameras, config],
  );

  return {
    preferredLiveModes,
    setPreferredLiveModes,
    resetPreferredLiveMode,
    isRestreamedStates: liveModeStates.restreamed,
    supportsAudioOutputStates,
    streamMetadata,
  };
}
