import NavigationPage from "./pages/NavigationPage";
import OpsPreviewPage from "./pages/OpsPreviewPage";

function shouldRenderOpsPreview(): boolean {
  if (typeof window === "undefined") return false;
  return new URLSearchParams(window.location.search).has("screen");
}

export default function App() {
  if (shouldRenderOpsPreview()) return <OpsPreviewPage />;
  return <NavigationPage />;
}
