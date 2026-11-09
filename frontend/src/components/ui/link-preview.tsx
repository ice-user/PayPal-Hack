import * as HoverCardPrimitive from "@radix-ui/react-hover-card";
import { encode } from "qss";
import React from "react";
import { AnimatePresence, motion, useMotionValue, useSpring } from "framer-motion";
import { cn } from "@/lib/utils";

// Ported from the Aceternity UI component for Next.js: next/image and next/link are plain
// <img> and <a> here (this app is Vite + React), and `onClick` lets the page intercept the
// click (the landing page uses it to transition into the demo instead of navigating).
type LinkPreviewProps = {
  children: React.ReactNode;
  url: string;
  className?: string;
  width?: number;
  height?: number;
  onClick?: (event: React.MouseEvent<HTMLAnchorElement>) => void;
} & (
  | { isStatic: true; imageSrc: string }
  | { isStatic?: false; imageSrc?: never }
);

export const LinkPreview = ({
  children,
  url,
  className,
  width = 200,
  height = 125,
  isStatic = false,
  imageSrc = "",
  onClick,
}: LinkPreviewProps) => {
  let src: string;
  if (!isStatic) {
    // Live screenshot of the URL through microlink.io (needs a public URL).
    const params = encode({
      url,
      screenshot: true,
      meta: false,
      embed: "screenshot.url",
      colorScheme: "dark",
      "viewport.isMobile": true,
      "viewport.deviceScaleFactor": 1,
      "viewport.width": width * 3,
      "viewport.height": height * 3,
    });
    src = `https://api.microlink.io/?${params}`;
  } else {
    src = imageSrc;
  }

  const [isOpen, setOpen] = React.useState(false);
  const [isMounted, setIsMounted] = React.useState(false);

  React.useEffect(() => {
    setIsMounted(true);
  }, []);

  const springConfig = { stiffness: 100, damping: 15 };
  const x = useMotionValue(0);
  const translateX = useSpring(x, springConfig);

  const handleMouseMove = (event: React.MouseEvent<HTMLAnchorElement>) => {
    const targetRect = event.currentTarget.getBoundingClientRect();
    const eventOffsetX = event.clientX - targetRect.left;
    const offsetFromCenter = (eventOffsetX - targetRect.width / 2) / 2; // reduced, so the card sways subtly
    x.set(offsetFromCenter);
  };

  return (
    <>
      {isMounted ? (
        // Preload the preview so it appears instantly on hover.
        <div className="hidden">
          <img src={src} width={width} height={height} alt="" />
        </div>
      ) : null}

      <HoverCardPrimitive.Root openDelay={50} closeDelay={100} onOpenChange={(open) => setOpen(open)}>
        <HoverCardPrimitive.Trigger
          onMouseMove={handleMouseMove}
          onClick={onClick}
          className={cn("text-white", className)}
          href={url}
        >
          {children}
        </HoverCardPrimitive.Trigger>

        <HoverCardPrimitive.Content
          className="z-50 [transform-origin:var(--radix-hover-card-content-transform-origin)]"
          side="top"
          align="center"
          sideOffset={10}
        >
          <AnimatePresence>
            {isOpen && (
              <motion.div
                initial={{ opacity: 0, y: 20, scale: 0.6 }}
                animate={{
                  opacity: 1,
                  y: 0,
                  scale: 1,
                  transition: { type: "spring", stiffness: 260, damping: 20 },
                }}
                exit={{ opacity: 0, y: 20, scale: 0.6 }}
                className="rounded-xl shadow-xl"
                style={{ x: translateX }}
              >
                <a
                  href={url}
                  onClick={onClick}
                  className="block rounded-xl border-2 border-transparent bg-white p-1 shadow hover:border-neutral-200"
                  style={{ fontSize: 0 }}
                >
                  <img src={src} width={width} height={height} className="rounded-lg" alt="Preview of the demo" />
                </a>
              </motion.div>
            )}
          </AnimatePresence>
        </HoverCardPrimitive.Content>
      </HoverCardPrimitive.Root>
    </>
  );
};
