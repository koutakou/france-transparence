"use client";

import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";

/**
 * Conteneur à défilement horizontal atteignable au clavier (WCAG 2.1.1,
 * règle axe `scrollable-region-focusable`).
 *
 * Un tableau plus large que l'écran (390 px) se fait défiler à la souris
 * ou au doigt ; au clavier, il faut que la zone elle-même prenne le focus.
 * Elle ne le prend QUE lorsqu'elle déborde réellement : un arrêt de
 * tabulation sur chaque tableau qui tient à l'écran serait un arrêt muet de
 * plus. Quand elle déborde, elle devient un groupe nommé (`libelle`) :
 * `group` et non `region`, qui est un REPÈRE ; deux tableaux aux mêmes
 * en-têtes sur une page (scrutins AN et Sénat) feraient deux repères
 * homonymes (axe `landmark-unique`).
 *
 * Sans JavaScript, le tableau reste rendu et défilable au doigt/à la souris.
 */
export function ZoneDefilante({
  libelle,
  className,
  style,
  children,
}: {
  libelle: string;
  className?: string;
  style?: CSSProperties;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [deborde, setDeborde] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const mesurer = () =>
      setDeborde(el.scrollWidth > el.clientWidth + 1 || el.scrollHeight > el.clientHeight + 1);
    mesurer();
    const observateur = new ResizeObserver(mesurer);
    observateur.observe(el);
    if (el.firstElementChild) observateur.observe(el.firstElementChild);
    return () => observateur.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      className={className}
      style={style}
      tabIndex={deborde ? 0 : undefined}
      role={deborde ? "group" : undefined}
      aria-label={deborde ? libelle : undefined}
    >
      {children}
    </div>
  );
}
