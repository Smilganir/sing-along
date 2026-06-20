import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

import ChordDiagram from './ChordDiagram.jsx';
import {
  adaptAgcSvgForDarkBg,
  buildAgcProxyUrl,
  chordDiagramApiUrl,
  getLocalChordShape,
  hasDiagramSupport,
  usesLocalDiagram,
} from '../utils/chordDiagram.js';

const HIDE_DELAY_MS = 120;
const VIEWPORT_MARGIN = 10;
const POPOVER_GAP = 8;
const POPOVER_ESTIMATED_WIDTH = 200;

function clampPopoverPosition(tokenRect, popoverWidth, popoverHeight) {
  const halfWidth = popoverWidth / 2;
  const left = Math.max(
    VIEWPORT_MARGIN + halfWidth,
    Math.min(window.innerWidth - VIEWPORT_MARGIN - halfWidth, tokenRect.left + tokenRect.width / 2),
  );

  const spaceAbove = tokenRect.top - POPOVER_GAP;
  const spaceBelow = window.innerHeight - tokenRect.bottom - POPOVER_GAP;
  const placeBelow = spaceAbove < popoverHeight && spaceBelow > spaceAbove;

  return {
    left,
    top: placeBelow ? tokenRect.bottom + POPOVER_GAP : tokenRect.top - POPOVER_GAP,
    placement: placeBelow ? 'below' : 'above',
  };
}

export default function ChordToken({ chord, children }) {
  const canDiagram = hasDiagramSupport(chord);
  const preferLocal = usesLocalDiagram(chord);
  const localShape = canDiagram ? getLocalChordShape(chord) : null;
  const [open, setOpen] = useState(false);
  const [svgMarkup, setSvgMarkup] = useState('');
  const [diagramSource, setDiagramSource] = useState(preferLocal ? 'local' : 'loading');
  const [position, setPosition] = useState({ top: 0, left: 0, placement: 'above' });
  const tokenRef = useRef(null);
  const popoverRef = useRef(null);
  const hideTimerRef = useRef(null);

  const hasPopover = canDiagram;

  const updatePosition = useCallback(() => {
    const el = tokenRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const popover = popoverRef.current;
    const popoverWidth = popover?.offsetWidth || POPOVER_ESTIMATED_WIDTH;
    const popoverHeight = popover?.offsetHeight || 220;
    setPosition(clampPopoverPosition(rect, popoverWidth, popoverHeight));
  }, []);

  const show = useCallback(() => {
    if (!hasPopover) return;
    window.clearTimeout(hideTimerRef.current);
    setSvgMarkup('');
    setDiagramSource(preferLocal ? 'local' : 'loading');
    updatePosition();
    setOpen(true);
  }, [hasPopover, preferLocal, updatePosition]);

  const hide = useCallback(() => {
    hideTimerRef.current = window.setTimeout(() => setOpen(false), HIDE_DELAY_MS);
  }, []);

  const cancelHide = useCallback(() => {
    window.clearTimeout(hideTimerRef.current);
  }, []);

  useEffect(() => {
    if (!open || preferLocal) return undefined;

    let cancelled = false;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 12_000);

    const loadSvg = async () => {
      setDiagramSource('loading');
      const sources = [chordDiagramApiUrl(chord)];
      if (import.meta.env.DEV) {
        const proxyUrl = buildAgcProxyUrl(chord);
        if (proxyUrl) sources.push(proxyUrl);
      }

      for (const url of sources) {
        try {
          const res = await fetch(url, { cache: 'no-store', signal: controller.signal });
          if (!res.ok) continue;
          const text = await res.text();
          if (!text.includes('<svg')) continue;
          if (!cancelled) {
            setSvgMarkup(adaptAgcSvgForDarkBg(text));
            setDiagramSource('agc');
          }
          return;
        } catch {
          // try next source
        }
      }

      if (!cancelled) {
        const fallback = getLocalChordShape(chord);
        setDiagramSource(fallback ? 'local' : 'missing');
      }
    };

    loadSvg();

    return () => {
      cancelled = true;
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [open, chord, preferLocal]);

  useLayoutEffect(() => {
    if (!open) return;
    updatePosition();
  }, [open, svgMarkup, diagramSource, updatePosition]);

  useEffect(() => {
    if (!open) return undefined;
    updatePosition();
    window.addEventListener('scroll', updatePosition, true);
    window.addEventListener('resize', updatePosition);
    return () => {
      window.removeEventListener('scroll', updatePosition, true);
      window.removeEventListener('resize', updatePosition);
    };
  }, [open, updatePosition]);

  useEffect(
    () => () => {
      window.clearTimeout(hideTimerRef.current);
    },
    [],
  );

  if (!hasPopover) {
    return <span>{children}</span>;
  }

  const showAgc = diagramSource === 'agc' && svgMarkup;
  const showLocal = diagramSource === 'local' && localShape;

  return (
    <>
      <span
        ref={tokenRef}
        className="sing-chord-token"
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={hide}
        tabIndex={0}
        aria-label={`${chord} chord diagram`}
      >
        {children}
      </span>
      {open &&
        createPortal(
          <div
            ref={popoverRef}
            className="sing-chord-diagram-popover"
            style={{
              top: `${position.top}px`,
              left: `${position.left}px`,
              transform:
                position.placement === 'below' ? 'translate(-50%, 0)' : 'translate(-50%, -100%)',
            }}
            onMouseEnter={cancelHide}
            onMouseLeave={hide}
            role="tooltip"
          >
            {showLocal ? (
              <div className="sing-chord-diagram-local" aria-label={`${chord} chord diagram`}>
                <ChordDiagram chord={localShape} size={1.5} coloredFingers />
                {localShape.partial && (
                  <p className="sing-chord-diagram-note">* simplified voicing</p>
                )}
              </div>
            ) : showAgc ? (
              <div
                className="sing-chord-diagram-svg"
                aria-label={`${chord} chord diagram`}
                dangerouslySetInnerHTML={{ __html: svgMarkup }}
              />
            ) : diagramSource === 'missing' ? (
              <p className="sing-chord-diagram-missing">No diagram for {chord}</p>
            ) : (
              <p className="sing-chord-diagram-missing">Loading…</p>
            )}
          </div>,
          document.body,
        )}
    </>
  );
}
