import { useEffect } from "react";
import { motion } from "framer-motion";
import { ArrowRight, Scale } from "lucide-react";
import { LinkPreview } from "@/components/ui/link-preview";

// Always dark: the page sets its own colours and ignores the dashboard's light/dark toggle.
const rise = (i: number) => ({
  initial: { opacity: 0, y: 18 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.6, delay: 0.12 * i, ease: [0.22, 1, 0.36, 1] as const },
});

export function Landing({ onEnter }: { onEnter: () => void }) {
  // The dashboard restores its own saved theme when it mounts.
  useEffect(() => {
    document.documentElement.dataset.theme = "dark";
  }, []);

  const enter = (e: React.MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault();
    onEnter();
  };

  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden bg-[#0a0a0a] text-neutral-100">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(60%_50%_at_50%_0%,rgba(96,165,250,0.14),transparent_70%)]"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(40%_35%_at_85%_100%,rgba(168,85,247,0.10),transparent_70%)]"
      />

      <header className="relative z-10 flex items-center gap-2.5 px-6 py-5 md:px-10">
        <span className="grid size-8 place-items-center rounded-lg bg-neutral-100 text-neutral-900">
          <Scale className="size-4" strokeWidth={2.4} aria-hidden="true" />
        </span>
        <span className="text-base font-semibold tracking-tight">MediateAI</span>
      </header>

      <main className="relative z-10 flex flex-1 items-center px-6 pb-16 md:px-10">
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-8">
          <motion.span
            {...rise(0)}
            className="w-fit rounded-full border border-neutral-800 bg-neutral-900/70 px-3 py-1 text-xs font-medium text-neutral-400"
          >
            Built for PayPal merchants
          </motion.span>

          <motion.h1
            {...rise(1)}
            className="text-4xl font-semibold leading-[1.08] tracking-tight text-neutral-50 md:text-6xl"
          >
            Resolve payment conflicts{" "}
            <span className="bg-gradient-to-br from-sky-300 via-blue-400 to-violet-400 bg-clip-text text-transparent">
              with precedent, not guesswork.
            </span>
          </motion.h1>

          <motion.p {...rise(2)} className="max-w-2xl text-lg leading-relaxed text-neutral-400 md:text-xl">
            At MediateAI we solve the conflicts that cost merchants money. We read a merchant&apos;s PayPal account, work
            out what actually happened, and respond the way similar past cases were won, never the way that backfired.
          </motion.p>

          <motion.p {...rise(3)} className="max-w-2xl text-base leading-relaxed text-neutral-500 md:text-lg">
            Take TechKart, an electronics store whose item-not-received disputes jumped fourfold in a week. MediateAI
            sorts every open dispute by what really happened to the parcel: delivered ones get proof, parcels still in
            transit get an honest delivery update, lost ones get a refund. Each step cites the past cases behind it, and
            nothing reaches the buyer or PayPal until the merchant clicks approve.
          </motion.p>

          <motion.p {...rise(4)} className="text-xl text-neutral-300 md:text-2xl">
            Ready to see it work?{" "}
            <LinkPreview
              url="#demo"
              onClick={enter}
              isStatic
              imageSrc="/demo-preview.svg"
              width={320}
              height={200}
              className="font-semibold text-white underline decoration-2 underline-offset-[6px] transition-colors hover:text-sky-300"
            >
              View the demo
            </LinkPreview>
            <ArrowRight className="ml-1.5 inline size-5 -translate-y-px text-neutral-500" aria-hidden="true" />
          </motion.p>
        </div>
      </main>

      <footer className="relative z-10 px-6 pb-6 text-xs text-neutral-600 md:px-10">
        Decision support, not financial advice. PayPal sandbox only; the order feed is synthetic.
      </footer>
    </div>
  );
}
