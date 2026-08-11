import ReactDOM from "react-dom/client";
import App from "./App.tsx";
import "./index.css";
import "@/utils/i18n";
import "react-i18next";
import routeLoaders from "@/lib/routePreload";

ReactDOM.createRoot(document.getElementById("root")!).render(<App />);

const preloadReview = () => {
  void routeLoaders.review();
};

// Start fetching the Review route as soon as the initial dashboard frame is
// painted. Waiting for an idle period can take seconds while live streams are
// decoding, especially on iOS.
requestAnimationFrame(preloadReview);
