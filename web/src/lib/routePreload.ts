const routeLoaders = {
  live: () => import("@/pages/Live"),
  review: () => import("@/pages/Events"),
  explore: () => import("@/pages/Explore"),
  export: () => import("@/pages/Exports"),
  config: () => import("@/pages/ConfigEditor"),
  system: () => import("@/pages/System"),
  settings: () => import("@/pages/Settings"),
  playground: () => import("@/pages/UIPlayground"),
  faces: () => import("@/pages/FaceLibrary"),
  classification: () => import("@/pages/ClassificationModel"),
  chat: () => import("@/pages/Chat"),
  logs: () => import("@/pages/Logs"),
  unauthorized: () => import("@/pages/AccessDenied"),
  replay: () => import("@/pages/Replay"),
} as const;

const loaderByPath: Record<string, () => Promise<unknown>> = {
  "/": routeLoaders.live,
  "/review": routeLoaders.review,
  "/explore": routeLoaders.explore,
  "/export": routeLoaders.export,
  "/config": routeLoaders.config,
  "/system": routeLoaders.system,
  "/settings": routeLoaders.settings,
  "/playground": routeLoaders.playground,
  "/faces": routeLoaders.faces,
  "/classification": routeLoaders.classification,
  "/chat": routeLoaders.chat,
  "/logs": routeLoaders.logs,
  "/unauthorized": routeLoaders.unauthorized,
  "/replay": routeLoaders.replay,
};

export function preloadRoute(url: string) {
  const pathname = url.split(/[?#]/, 1)[0];
  void loaderByPath[pathname]?.();
}

export default routeLoaders;
