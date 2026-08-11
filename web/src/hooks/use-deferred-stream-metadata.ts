import { baseUrl } from "@/api/baseUrl";
import { useCallback, useEffect, useState, useMemo } from "react";
import useSWR from "swr";
import { LiveStreamMetadata } from "@/types/live";

const FETCH_TIMEOUT_MS = 10000;
const DEFER_DELAY_MS = 500;
const emptyObject: Readonly<{ [key: string]: LiveStreamMetadata }> =
  Object.freeze({});

/**
 * Hook that fetches go2rtc stream metadata with deferred loading.
 *
 * Metadata fetching is delayed to prevent blocking initial page load
 * and camera image requests.
 *
 * @param streamNames - Array of stream names to fetch metadata for
 * @returns Object containing stream metadata keyed by stream name
 */
export default function useDeferredStreamMetadata(streamNames: string[]) {
  const [fetchEnabled, setFetchEnabled] = useState(false);

  useEffect(() => {
    const timeoutId = setTimeout(() => {
      setFetchEnabled(true);
    }, DEFER_DELAY_MS);

    return () => clearTimeout(timeoutId);
  }, []);

  const swrKey = useMemo(() => {
    if (!fetchEnabled || streamNames.length === 0) return null;
    // Use spread to avoid mutating the original array
    return `deferred-streams:${[...streamNames].sort().join(",")}`;
  }, [fetchEnabled, streamNames]);

  const fetcher = useCallback(async (key: string) => {
    const names = new Set(
      key.replace("deferred-streams:", "").split(",").filter(Boolean),
    );
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);

    try {
      const response = await fetch(`${baseUrl}api/go2rtc/streams`, {
        priority: "low",
        signal: controller.signal,
      });

      if (!response.ok) {
        return {};
      }

      const allMetadata = (await response.json()) as Record<
        string,
        LiveStreamMetadata
      >;

      return Object.fromEntries(
        Object.entries(allMetadata).filter(([name]) => names.has(name)),
      );
    } catch (error) {
      if ((error as Error).name !== "AbortError") {
        // eslint-disable-next-line no-console
        console.error("Failed to fetch stream metadata:", error);
      }
      return {};
    } finally {
      clearTimeout(timeoutId);
    }
  }, []);

  const { data: metadata = emptyObject } = useSWR<{
    [key: string]: LiveStreamMetadata;
  }>(swrKey, fetcher, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    revalidateIfStale: false,
    dedupingInterval: 60000,
  });

  return metadata;
}
