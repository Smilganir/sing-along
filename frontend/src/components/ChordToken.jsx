import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

import ChordDiagram from './ChordDiagram.jsx';
import {
  adaptAgcSvgForDarkBg,
  chordDiagramApiUrl,
  getChordsDbShape,
  hasDiagramSupport,
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
  const fallbackShape = canDiagram ? getChordsDbShape(chord) : null;
  const [open, setOpen] = useState(false);
  const [agcFailed, setAgcFailed] = useState(false);
  const [svgMarkup, setSvgMarkup] = useState('');
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
    setAgcFailed(false);
    setSvgMarkup('');
    updatePosition();
    setOpen(true);
  }, [hasPopover, updatePosition]);

  const hide = useCallback(() => {
    hideTimerRef.current = window.setTimeout(() => setOpen(false), HIDE_DELAY_MS);
  }, []);

  const cancelHide = useCallback(() => {
    window.clearTimeout(hideTimerRef.current);
  }, []);

  useEffect(() => {
    if (!open || agcFailed) return undefined;

    let cancelled = false;
    fetch(chordDiagramApiUrl(chord), { cache: 'no-store' })
      .then((res) => {
        if (!res.ok) throw new Error('diagram fetch failed');
        return res.text();
      })
      .then((text) => {
        if (!cancelled) setSvgMarkup(adaptAgcSvgForDarkBg(text));
      })
      .catch(() => {
        if (!cancelled) setAgcFailed(true);
      });

    return () => {
      cancelled = true;
    };
  }, [open, chord, agcFailed]);

  useLayoutEffect(() => {
    if (!open) return;
    updatePosition();
  }, [open, svgMarkup, agcFailed, updatePosition]);

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

  const showFallback = agcFailed && fallbackShape;
  const showUnavailable = agcFailed && !fallbackShape;

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
            {showFallback ? (
              <ChordDiagram chord={fallbackShape} size={1.15} coloredFingers />
            ) : showUnavailable ? (
              <p className="sing-chord-diagram-missing">No diagram for {chord}</p>
            ) : svgMarkup ? (
              <div
                className="sing-chord-diagram-svg"
                aria-label={`${chord} chord diagram`}
                dangerouslySetInnerHTML={{ __html: svgMarkup }}
              />
            ) : (
              <p className="sing-chord-diagram-missing">Loading…</p>
            )}
          </div>,
          document.body,
        )}
    </>
  );
}
