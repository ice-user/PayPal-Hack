import { lazy, Suspense, useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Landing } from "./components/Landing";

// The dashboard (charts, tables, API client) loads only once someone enters the demo, so the landing page stays light.
const App = lazy(() => import("./App"));

type View = "landing" | "demo";

// "#demo" is the dashboard, an empty hash is the landing page. Other hashes (the dashboard's
// own in-page links such as "#decision") leave the current view alone.
const fromHash = (hash: string, current: View | null): View =>
  hash === "#demo" ? "demo" : hash === "" || hash === "#" ? "landing" : (current ?? "demo");

export default function Root() {
  const [view, setView] = useState<View>(() => fromHash(window.location.hash, null));

  useEffect(() => {
    const onHash = () => setView((v) => fromHash(window.location.hash, v));
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    document.title = view === "landing" ? "MediateAI" : "MediateAI demo";
    window.scrollTo(0, 0);
  }, [view]);

  return (
    <AnimatePresence mode="wait" initial={false}>
      {view === "landing" ? (
        <motion.div
          key="landing"
          exit={{ opacity: 0, scale: 1.04, filter: "blur(8px)" }}
          transition={{ duration: 0.45, ease: [0.4, 0, 0.2, 1] }}
        >
          <Landing onEnter={() => { window.location.hash = "demo"; }} />
        </motion.div>
      ) : (
        <motion.div
          key="demo"
          initial={{ opacity: 0, scale: 0.985 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        >
          <Suspense fallback={<div style={{ minHeight: "100vh", background: "var(--bg, #0a0a0a)" }} />}>
            <App />
          </Suspense>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
