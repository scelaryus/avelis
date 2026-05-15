import { useState, useRef, useCallback, useEffect } from "react";
import {
  XMarkIcon,
  MagnifyingGlassPlusIcon,
  MagnifyingGlassMinusIcon,
  ArrowsPointingOutIcon,
  ArrowDownTrayIcon,
  ArrowTopRightOnSquareIcon,
} from "@heroicons/react/24/outline";

interface DocumentViewerProps {
  docId: string;
  filename: string;
  mimeType: string | null;
  onClose: () => void;
}

const ZOOM_STEPS = [0.25, 0.5, 0.75, 1, 1.25, 1.5, 2, 3, 4];

export default function DocumentViewer({ docId, filename, mimeType, onClose }: DocumentViewerProps) {
  const [zoom, setZoom] = useState(1);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [loaded, setLoaded] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const token = localStorage.getItem("access_token") || "";
  const src = `/api/v1/documents/${docId}/download?token=${encodeURIComponent(token)}`;
  const isImage = mimeType?.startsWith("image/") ?? false;
  const isPdf = mimeType === "application/pdf";

  const zoomIn = () => {
    const nextIdx = ZOOM_STEPS.findIndex((z) => z > zoom);
    if (nextIdx >= 0) setZoom(ZOOM_STEPS[nextIdx]);
  };

  const zoomOut = () => {
    const prevIdx = [...ZOOM_STEPS].reverse().findIndex((z) => z < zoom);
    if (prevIdx >= 0) setZoom(ZOOM_STEPS[ZOOM_STEPS.length - 1 - prevIdx]);
  };

  const resetView = () => {
    setZoom(1);
    setPosition({ x: 0, y: 0 });
  };

  // Mouse wheel zoom
  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    if (e.deltaY < 0) {
      setZoom((z) => Math.min(z * 1.15, 5));
    } else {
      setZoom((z) => Math.max(z / 1.15, 0.1));
    }
  }, []);

  // Pan with mouse drag
  const handleMouseDown = (e: React.MouseEvent) => {
    if (zoom <= 1 && !isImage) return;
    setDragging(true);
    setDragStart({ x: e.clientX - position.x, y: e.clientY - position.y });
  };

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!dragging) return;
    setPosition({
      x: e.clientX - dragStart.x,
      y: e.clientY - dragStart.y,
    });
  }, [dragging, dragStart]);

  const handleMouseUp = useCallback(() => {
    setDragging(false);
  }, []);

  useEffect(() => {
    if (dragging) {
      window.addEventListener("mousemove", handleMouseMove);
      window.addEventListener("mouseup", handleMouseUp);
      return () => {
        window.removeEventListener("mousemove", handleMouseMove);
        window.removeEventListener("mouseup", handleMouseUp);
      };
    }
  }, [dragging, handleMouseMove, handleMouseUp]);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-slate-900/95 backdrop-blur-sm">
      {/* ── Toolbar ── */}
      <div className="flex items-center justify-between px-4 py-2 bg-slate-800 border-b border-slate-700 shrink-0">
        <div className="flex items-center gap-3 min-w-0">
          <h3 className="text-sm font-medium text-white truncate max-w-md">{filename}</h3>
          <span className="text-xs text-slate-400 shrink-0">
            {mimeType?.split("/")[1]?.toUpperCase()}
          </span>
        </div>

        <div className="flex items-center gap-1">
          {/* Zoom controls */}
          <button
            onClick={zoomOut}
            className="p-1.5 rounded text-slate-300 hover:bg-slate-700 hover:text-white transition-colors"
            title="Zoom arriere"
          >
            <MagnifyingGlassMinusIcon className="h-5 w-5" />
          </button>
          <span className="text-xs text-slate-300 w-14 text-center font-mono">
            {Math.round(zoom * 100)}%
          </span>
          <button
            onClick={zoomIn}
            className="p-1.5 rounded text-slate-300 hover:bg-slate-700 hover:text-white transition-colors"
            title="Zoom avant"
          >
            <MagnifyingGlassPlusIcon className="h-5 w-5" />
          </button>
          <button
            onClick={resetView}
            className="p-1.5 rounded text-slate-300 hover:bg-slate-700 hover:text-white transition-colors"
            title="Taille reelle"
          >
            <ArrowsPointingOutIcon className="h-5 w-5" />
          </button>

          <div className="w-px h-6 bg-slate-600 mx-2" />

          {/* Open in new tab */}
          <button
            onClick={() => window.open(src, "_blank")}
            className="p-1.5 rounded text-slate-300 hover:bg-slate-700 hover:text-white transition-colors"
            title="Ouvrir dans un nouvel onglet"
          >
            <ArrowTopRightOnSquareIcon className="h-5 w-5" />
          </button>
          {/* Download */}
          <a
            href={src}
            download={filename}
            className="p-1.5 rounded text-slate-300 hover:bg-slate-700 hover:text-white transition-colors"
            title="Telecharger"
          >
            <ArrowDownTrayIcon className="h-5 w-5" />
          </a>

          <div className="w-px h-6 bg-slate-600 mx-2" />

          {/* Close */}
          <button
            onClick={onClose}
            className="p-1.5 rounded text-slate-300 hover:bg-red-600 hover:text-white transition-colors"
            title="Fermer (Echap)"
          >
            <XMarkIcon className="h-5 w-5" />
          </button>
        </div>
      </div>

      {/* ── Viewer area ── */}
      <div
        ref={containerRef}
        className={`flex-1 overflow-hidden flex items-center justify-center ${
          dragging ? "cursor-grabbing" : zoom > 1 ? "cursor-grab" : "cursor-default"
        }`}
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
      >
        {!loaded && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="h-10 w-10 animate-spin rounded-full border-4 border-teal-500 border-t-transparent" />
          </div>
        )}

        {isPdf ? (
          <iframe
            src={`${src}#zoom=${Math.round(zoom * 100)}`}
            title={filename}
            className="w-full h-full border-0"
            style={{
              transform: `scale(${zoom}) translate(${position.x / zoom}px, ${position.y / zoom}px)`,
              transformOrigin: "center center",
              width: "100%",
              height: "100%",
            }}
            onLoad={() => setLoaded(true)}
          />
        ) : isImage ? (
          <img
            src={src}
            alt={filename}
            className="max-w-none select-none"
            style={{
              transform: `scale(${zoom}) translate(${position.x / zoom}px, ${position.y / zoom}px)`,
              transformOrigin: "center center",
            }}
            draggable={false}
            onLoad={() => setLoaded(true)}
          />
        ) : (
          <div className="text-center text-slate-400">
            <p className="text-lg mb-2">Apercu non disponible pour ce format</p>
            <a
              href={src}
              download={filename}
              className="btn-primary inline-flex items-center gap-2"
            >
              <ArrowDownTrayIcon className="h-4 w-4" />
              Telecharger le fichier
            </a>
          </div>
        )}
      </div>

      {/* ── Zoom shortcuts hint ── */}
      <div className="text-center py-1.5 bg-slate-800 border-t border-slate-700">
        <span className="text-xs text-slate-500">
          Molette pour zoomer &middot; Cliquer-glisser pour d&eacute;placer &middot; Echap pour fermer
        </span>
      </div>
    </div>
  );
}
