import { useEffect, useRef } from "react";

export function Chart({ spec }: { spec: object }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    let finalize: (() => void) | null = null;

    import("vega-embed").then(({ default: embed }) => {
      if (!ref.current) return;
      embed(ref.current, spec as any, {
        actions: false,
        theme: "dark",
        renderer: "svg",
      })
        .then((r) => {
          finalize = () => r.finalize();
        })
        .catch(console.error);
    });

    return () => finalize?.();
  }, [spec]);

  return <div ref={ref} className="mt-3 w-full" />;
}
