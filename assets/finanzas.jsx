import React, { useEffect, useMemo, useRef, useState } from "react";
import * as d3 from "d3";

// ==============================
// COUNTRY DICTIONARY (mirrors backend Diccionarios/diccionario_paises.py)
// ==============================
const COUNTRIES = [
  { code: "ar", label: "Argentina" },
  { code: "bo", label: "Bolivia" },
  { code: "br", label: "Brasil" },
  { code: "cl", label: "Chile" },
  { code: "co", label: "Colombia" },
  { code: "cr", label: "Costa Rica" },
  { code: "do", label: "República Dominicana" },
  { code: "ec", label: "Ecuador" },
  { code: "eg", label: "Egipto" },
  { code: "es", label: "España" },
  { code: "gt", label: "Guatemala" },
  { code: "hn", label: "Honduras" },
  { code: "mx", label: "México" },
  { code: "ni", label: "Nicaragua" },
  { code: "pa", label: "Panamá" },
  { code: "pe", label: "Perú" },
  { code: "pr", label: "Puerto Rico" },
  { code: "py", label: "Paraguay" },
  { code: "sv", label: "El Salvador" },
  { code: "us", label: "Estados Unidos" },
  { code: "uy", label: "Uruguay" },
  { code: "ve", label: "Venezuela" },
];

const YEARS = [2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026];

const MONTHS = [
  { value: 1,  label: "Ene" }, { value: 2,  label: "Feb" }, { value: 3,  label: "Mar" },
  { value: 4,  label: "Abr" }, { value: 5,  label: "May" }, { value: 6,  label: "Jun" },
  { value: 7,  label: "Jul" }, { value: 8,  label: "Ago" }, { value: 9,  label: "Sep" },
  { value: 10, label: "Oct" }, { value: 11, label: "Nov" }, { value: 12, label: "Dic" },
];

// ==============================
// DESIGN TOKENS
// ==============================
const tokens = {
  colors: {
    abyss: "#050214", deepIndigo: "#0C0728", indigo: "#1E1041",
    violet: "#2B1661", bluePurple: "#435CC8", purple: "#8B46CD",
    magenta: "#E75CE0", gold: "#FFCC6D",
    surface: "rgba(255, 255, 255, 0.035)",
    surfaceHover: "rgba(255, 255, 255, 0.06)",
    surfaceStrong: "rgba(255, 255, 255, 0.08)",
    border: "rgba(255, 255, 255, 0.08)",
    borderHover: "rgba(139, 70, 205, 0.45)",
    textPrimary: "#F5F3FF",
    textSecondary: "rgba(245, 243, 255, 0.62)",
    textTertiary: "rgba(245, 243, 255, 0.38)",
    textAnnotation: "rgba(255, 204, 109, 0.82)",
    alertText: "#FB7185", positiveText: "#34D399",
    statusOnTrack: "#34D399", statusAtRisk: "#FFCC6D",
    statusOffTrack: "#E75CE0", statusPending: "rgba(245, 243, 255, 0.35)",
    chartGrid: "rgba(245, 243, 255, 0.05)",
    chartAxis: "rgba(245, 243, 255, 0.38)",
  },
  typography: {
    fontFamily: "'Maven Pro', system-ui, -apple-system, 'SF Pro Display', sans-serif",
    fontSize: {
      title: "12px", value: "32px", valuePeriod: "13px",
      comparison: "11px", target: "10px", okr: "9px", pending: "19px",
    },
    fontWeight: { regular: 400, medium: 500, semibold: 600, bold: 700 },
  },
  spacing: { cardPadding: "16px 18px", cardRadius: "16px" },
  transition: "all 320ms cubic-bezier(0.4, 0, 0.2, 1)",
};

// ==============================
// GLOBAL STYLES — bug-fixed hover containment
// ==============================
const GlobalStyles = () => (
  <style>{`
    @import url('https://fonts.googleapis.com/css2?family=Maven+Pro:wght@400;500;600;700&display=swap');
    * { box-sizing: border-box; }

    .addiuva-root {
      font-family: ${tokens.typography.fontFamily};
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
    }

    .addiuva-bg {
      background:
        radial-gradient(ellipse 80% 60% at 20% 0%, rgba(139, 70, 205, 0.18) 0%, transparent 55%),
        radial-gradient(ellipse 70% 50% at 100% 100%, rgba(231, 92, 224, 0.10) 0%, transparent 55%),
        radial-gradient(ellipse 60% 40% at 80% 20%, rgba(67, 92, 200, 0.12) 0%, transparent 50%),
        linear-gradient(180deg, ${tokens.colors.deepIndigo} 0%, ${tokens.colors.abyss} 100%);
    }
    .addiuva-grain::before {
      content: ""; position: absolute; inset: 0; pointer-events: none;
      opacity: 0.3;
      background-image: url("data:image/svg+xml;utf8,<svg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 0.035 0'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>");
      mix-blend-mode: overlay;
    }

    /* ===== GLASS CARD with HOVER ISOLATION (bug fix v2) =====
       Multi-layer clipping strategy:
       - overflow: hidden     → clips static DOM content
       - contain: layout paint → tells the browser this is a self-contained subtree
       - isolation: isolate   → forces new stacking context for pseudo-elements
       - clip-path: inset(0 round X) → SVG-based clipping mechanism, respected
         even by GPU-composited filter() outputs (overflow:hidden alone is NOT)
    */
    .glass-card {
      background: ${tokens.colors.surface};
      border: 1px solid ${tokens.colors.border};
      border-radius: ${tokens.spacing.cardRadius};
      backdrop-filter: blur(20px) saturate(140%);
      -webkit-backdrop-filter: blur(20px) saturate(140%);
      transition: ${tokens.transition};
      position: relative;
      overflow: hidden;
      contain: layout paint;
      isolation: isolate;
      clip-path: inset(0 round ${tokens.spacing.cardRadius});
      height: 100%;
    }
    .glass-card::before {
      content: "";
      position: absolute; top: 0; left: 0; right: 0;
      height: 3px;
      background: linear-gradient(90deg,
        ${tokens.colors.bluePurple} 0%,
        ${tokens.colors.purple} 25%,
        ${tokens.colors.magenta} 60%,
        ${tokens.colors.gold} 100%);
      box-shadow:
        0 0 10px rgba(231, 92, 224, 0.75),
        0 0 22px rgba(231, 92, 224, 0.35),
        0 2px 12px rgba(139, 70, 205, 0.45);
      transition: all 320ms ease;
      z-index: 2;
      pointer-events: none;
    }
    /* ::after diffuse glow — replaces previous filter:blur (which leaks via GPU
       compositor) with a static radial-gradient that achieves the same soft
       falloff but is purely paint-based, so clip-path/overflow honor it. */
    .glass-card::after {
      content: "";
      position: absolute;
      top: 0; left: 0; right: 0;
      height: 28px;
      background: radial-gradient(ellipse 60% 100% at 50% 0%,
        rgba(231, 92, 224, 0.55) 0%,
        rgba(231, 92, 224, 0.18) 40%,
        transparent 75%);
      opacity: 0.55;
      transition: opacity 320ms ease;
      pointer-events: none;
      z-index: 1;
    }
    .glass-card:hover {
      background: ${tokens.colors.surfaceHover};
      border-color: ${tokens.colors.borderHover};
      transform: translateY(-2px);
      box-shadow:
        0 12px 40px rgba(139, 70, 205, 0.25),
        inset 0 1px 0 rgba(255, 255, 255, 0.06);
    }
    .glass-card:hover::before {
      box-shadow:
        0 0 16px rgba(231, 92, 224, 0.95),
        0 0 30px rgba(231, 92, 224, 0.55),
        0 2px 18px rgba(255, 204, 109, 0.35);
    }
    .glass-card:hover::after { opacity: 0.85; }

    .chart-card:hover .d3-bar  { filter: brightness(1.18) drop-shadow(0 0 10px rgba(231, 92, 224, 0.55)); }
    .chart-card:hover .d3-line { filter: drop-shadow(0 0 8px rgba(231, 92, 224, 0.55)); }
    .d3-bar { transition: filter 200ms ease; cursor: pointer; }
    .d3-bar:hover { filter: brightness(1.35) drop-shadow(0 0 12px rgba(255, 204, 109, 0.65)) !important; }
    .d3-point { transition: r 220ms ease, filter 220ms ease; cursor: pointer; }
    .d3-point:hover { filter: drop-shadow(0 0 10px rgba(231, 92, 224, 0.9)); }
    .d3-line { transition: filter 220ms ease; }

    .addiuva-logo-text {
      background: linear-gradient(135deg, #FFFFFF 0%, #F5F3FF 50%, rgba(255, 204, 109, 0.85) 100%);
      -webkit-background-clip: text; background-clip: text;
      -webkit-text-fill-color: transparent; color: transparent;
      font-weight: 600; letter-spacing: -0.02em;
    }
    .kpi-value-bright {
      background: linear-gradient(180deg, #FFFFFF 0%, #C4B5FD 100%);
      -webkit-background-clip: text; background-clip: text;
      -webkit-text-fill-color: transparent; color: transparent;
    }
    .kpi-value-pending {
      background: linear-gradient(135deg, ${tokens.colors.purple} 0%, ${tokens.colors.magenta} 55%, ${tokens.colors.gold} 100%);
      -webkit-background-clip: text; background-clip: text;
      -webkit-text-fill-color: transparent; color: transparent;
      font-style: italic;
    }
    .mom-skeleton {
      display: inline-block;
      width: 110px; height: 11px;
      border-radius: 3px;
      background: linear-gradient(90deg,
        rgba(255,255,255,0.04) 0%,
        rgba(255,255,255,0.10) 50%,
        rgba(255,255,255,0.04) 100%);
      background-size: 200% 100%;
      animation: shimmer 1.8s ease-in-out infinite;
    }
    @keyframes shimmer {
      0% { background-position: 200% 0; }
      100% { background-position: -200% 0; }
    }

    .target-pill {
      background: rgba(255, 204, 109, 0.06);
      border: 1px solid rgba(255, 204, 109, 0.22);
      color: rgba(255, 204, 109, 0.92);
      transition: ${tokens.transition};
    }
    .glass-card:hover .target-pill {
      background: rgba(255, 204, 109, 0.1);
      border-color: rgba(255, 204, 109, 0.4);
    }

    .dashboard-header-card {
      background: linear-gradient(135deg,
        ${tokens.colors.indigo} 0%, ${tokens.colors.violet} 35%,
        ${tokens.colors.purple} 75%, ${tokens.colors.magenta} 100%);
      border: 1px solid rgba(231, 92, 224, 0.22);
      border-radius: ${tokens.spacing.cardRadius};
      transition: ${tokens.transition};
      overflow: hidden;
      contain: layout paint;
      isolation: isolate;
      clip-path: inset(0 round ${tokens.spacing.cardRadius});
    }
    .dashboard-header-card:hover {
      filter: brightness(1.06);
      box-shadow: 0 12px 40px rgba(139, 70, 205, 0.28);
    }

    .status-dot { position: relative; transition: ${tokens.transition}; }
    .status-dot::after {
      content: ""; position: absolute; inset: -4px; border-radius: 50%;
      background: inherit; opacity: 0.35; filter: blur(4px); z-index: -1;
    }

    .topbar {
      backdrop-filter: blur(24px) saturate(180%);
      -webkit-backdrop-filter: blur(24px) saturate(180%);
      background: rgba(10, 6, 32, 0.55);
      border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }

    .slicer-bar {
      background: rgba(255, 255, 255, 0.025);
      border: 1px solid ${tokens.colors.border};
      border-radius: 14px;
      backdrop-filter: blur(18px) saturate(140%);
      -webkit-backdrop-filter: blur(18px) saturate(140%);
      transition: ${tokens.transition};
    }
    .slicer-bar:hover { border-color: rgba(255, 255, 255, 0.14); }

    .slicer-label {
      font-size: 9px; font-weight: 700;
      letter-spacing: 0.18em; text-transform: uppercase;
      color: ${tokens.colors.textTertiary};
      margin-bottom: 6px;
    }

    /* ===== MULTI-SELECT DROPDOWN ===== */
    .dropdown-trigger {
      display: flex; align-items: center; gap: 8px;
      min-width: 160px; max-width: 280px;
      height: 34px;
      padding: 0 12px;
      background: rgba(0, 0, 0, 0.25);
      border: 1px solid ${tokens.colors.border};
      border-radius: 10px;
      color: ${tokens.colors.textPrimary};
      font-family: inherit; font-size: 11px;
      font-weight: 600; letter-spacing: 0.02em;
      cursor: pointer;
      transition: ${tokens.transition};
    }
    .dropdown-trigger:hover {
      border-color: ${tokens.colors.borderHover};
      background: rgba(139, 70, 205, 0.08);
    }
    .dropdown-trigger.active {
      border-color: ${tokens.colors.purple};
      box-shadow: 0 0 0 1px ${tokens.colors.purple}, 0 0 14px rgba(139, 70, 205, 0.25);
    }
    .dropdown-trigger-text {
      flex: 1; text-align: left;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .dropdown-trigger-count {
      display: inline-flex; align-items: center; justify-content: center;
      min-width: 18px; height: 18px; padding: 0 6px;
      border-radius: 9px;
      background: linear-gradient(135deg, ${tokens.colors.purple}, ${tokens.colors.magenta});
      color: #FFF; font-size: 10px; font-weight: 700;
      box-shadow: 0 1px 6px rgba(231, 92, 224, 0.35);
    }
    .dropdown-trigger-arrow {
      color: ${tokens.colors.textTertiary};
      transition: transform 220ms ease;
    }
    .dropdown-trigger.active .dropdown-trigger-arrow { transform: rotate(180deg); }

    .dropdown-menu {
      position: absolute; top: calc(100% + 6px); left: 0;
      min-width: 100%; max-width: 320px;
      max-height: 320px; overflow-y: auto;
      background: rgba(12, 7, 40, 0.96);
      border: 1px solid rgba(139, 70, 205, 0.32);
      border-radius: 12px;
      backdrop-filter: blur(28px) saturate(180%);
      -webkit-backdrop-filter: blur(28px) saturate(180%);
      box-shadow:
        0 12px 40px rgba(0, 0, 0, 0.45),
        0 0 0 1px rgba(255, 255, 255, 0.04) inset;
      padding: 6px;
      z-index: 1000;
      animation: dropdownIn 180ms cubic-bezier(0.4, 0, 0.2, 1);
    }
    @keyframes dropdownIn {
      from { opacity: 0; transform: translateY(-4px); }
      to   { opacity: 1; transform: translateY(0); }
    }
    .dropdown-menu::-webkit-scrollbar { width: 6px; }
    .dropdown-menu::-webkit-scrollbar-track { background: transparent; }
    .dropdown-menu::-webkit-scrollbar-thumb {
      background: rgba(139, 70, 205, 0.35); border-radius: 3px;
    }

    .dropdown-actions {
      display: flex; gap: 4px;
      padding: 4px;
      border-bottom: 1px solid ${tokens.colors.border};
      margin-bottom: 4px;
    }
    .dropdown-action {
      flex: 1;
      padding: 5px 8px;
      font-size: 10px; font-weight: 600;
      letter-spacing: 0.04em;
      color: ${tokens.colors.textSecondary};
      background: transparent;
      border: 0; border-radius: 6px;
      cursor: pointer;
      font-family: inherit;
      transition: ${tokens.transition};
    }
    .dropdown-action:hover {
      color: ${tokens.colors.textPrimary};
      background: rgba(139, 70, 205, 0.15);
    }
    .dropdown-option {
      display: flex; align-items: center; gap: 10px;
      padding: 7px 10px;
      font-size: 11px; font-weight: 500;
      color: ${tokens.colors.textSecondary};
      cursor: pointer;
      border-radius: 7px;
      transition: ${tokens.transition};
      letter-spacing: 0.01em;
    }
    .dropdown-option:hover {
      background: rgba(139, 70, 205, 0.18);
      color: ${tokens.colors.textPrimary};
    }
    .dropdown-option.selected {
      color: ${tokens.colors.textPrimary};
      background: rgba(231, 92, 224, 0.12);
    }
    .dropdown-checkbox {
      flex-shrink: 0;
      width: 14px; height: 14px;
      border: 1.5px solid rgba(139, 70, 205, 0.55);
      border-radius: 4px;
      display: flex; align-items: center; justify-content: center;
      transition: ${tokens.transition};
      background: rgba(0,0,0,0.2);
    }
    .dropdown-option.selected .dropdown-checkbox {
      background: linear-gradient(135deg, ${tokens.colors.purple}, ${tokens.colors.magenta});
      border-color: ${tokens.colors.magenta};
      box-shadow: 0 0 8px rgba(231, 92, 224, 0.5);
    }
    .dropdown-checkbox-tick {
      opacity: 0;
      color: #FFF;
      font-size: 10px;
      line-height: 1;
      font-weight: 900;
      transition: opacity 160ms ease;
    }
    .dropdown-option.selected .dropdown-checkbox-tick { opacity: 1; }

    .toggle-switch {
      position: relative;
      width: 42px; height: 22px;
      border-radius: 22px;
      background: rgba(0, 0, 0, 0.35);
      border: 1px solid ${tokens.colors.border};
      cursor: pointer;
      transition: ${tokens.transition};
    }
    .toggle-switch.on {
      background: linear-gradient(135deg, ${tokens.colors.purple}, ${tokens.colors.magenta});
      border-color: rgba(231, 92, 224, 0.5);
      box-shadow: 0 0 14px rgba(231, 92, 224, 0.35);
    }
    .toggle-thumb {
      position: absolute; top: 2px; left: 2px;
      width: 16px; height: 16px; border-radius: 50%;
      background: #FFFFFF;
      box-shadow: 0 2px 4px rgba(0, 0, 0, 0.35);
      transition: ${tokens.transition};
    }
    .toggle-switch.on .toggle-thumb { left: 22px; }
  `}</style>
);

// ==============================
// ADDIUVA LOGO
// ==============================
const AddiuvaLogo = ({ height = 28 }) => (
  <svg viewBox="0 0 160 44" height={height} style={{ display: "block" }} aria-label="Addiuva">
    <defs>
      <linearGradient id="addiuvaMarkGrad" x1="10%" y1="100%" x2="90%" y2="0%">
        <stop offset="0%" stopColor="#8B46CD" />
        <stop offset="45%" stopColor="#E75CE0" />
        <stop offset="100%" stopColor="#FFCC6D" />
      </linearGradient>
      <linearGradient id="addiuvaMarkGradBack" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stopColor="#435CC8" stopOpacity="0.9" />
        <stop offset="100%" stopColor="#8B46CD" stopOpacity="0.9" />
      </linearGradient>
    </defs>
    <path d="M 6 36 L 20 8 L 26 8 L 14 36 Z" fill="url(#addiuvaMarkGradBack)" />
    <path d="M 10 36 L 22 12 L 34 36 L 28 36 L 22 24 L 16 36 Z" fill="url(#addiuvaMarkGrad)" />
    <text x="44" y="30" fontFamily="Maven Pro, sans-serif" fontSize="22" fontWeight="600" fill="#F5F3FF" letterSpacing="-0.5">
      Addiuva
    </text>
  </svg>
);

// ==============================
// UTILS
// ==============================
function formatCompactNumber(value, decimalsOverride) {
  const abs = Math.abs(value);
  if (abs >= 1e9) return `${(value / 1e9).toFixed(decimalsOverride ?? 2)}B`;
  if (abs >= 1e6) return `${(value / 1e6).toFixed(decimalsOverride ?? 3)}M`;
  if (abs >= 1e3) return `${(value / 1e3).toFixed(decimalsOverride ?? 2)}K`;
  return value.toFixed(decimalsOverride ?? 2);
}
function formatValue(v, f, unit) {
  switch (f) {
    case "currency": return `${formatCompactNumber(v)} ${unit}`;
    case "percent":  return `${(v * 100).toFixed(2)}%`;
    case "ratio":    return v.toFixed(3);
    default:         return `${formatCompactNumber(v)} ${unit}`;
  }
}
function formatDelta(deltaPct) {
  const pct = deltaPct * 100;
  if (Math.abs(pct) < 1)  return `${pct.toFixed(3)}%`;
  if (Math.abs(pct) < 10) return `${pct.toFixed(1)}%`;
  return `${Math.round(pct)}%`;
}

const BREAKPOINTS = { mobile: 500, tablet: 768, desktop: 1024 };
function getBreakpoint(width) {
  if (width < BREAKPOINTS.mobile) return "mobile";
  if (width < BREAKPOINTS.tablet) return "tablet";
  if (width < BREAKPOINTS.desktop) return "desktop";
  return "wide";
}
function useResizeObserver() {
  const ref = useRef(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      setSize({ width, height });
    });
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, size];
}

// ==============================
// MoM CALCULATOR (PURE, backend-ready)
// ==============================
function computeMoM(currentValue, previousValue, currentMonthLabel, prevMonthLabel) {
  if (currentValue == null || previousValue == null || previousValue === 0) {
    return { pending: true, currentMonthLabel, prevMonthLabel };
  }
  return {
    pending: false,
    deltaPct: (currentValue - previousValue) / previousValue,
    currentMonthLabel, prevMonthLabel,
  };
}

// ==============================
// MULTI-SELECT DROPDOWN
// ==============================
const MultiSelectDropdown = ({
  label, options, selected, onChange, placeholder = "Seleccionar…", maxBadgeText = 3,
}) => {
  const [open, setOpen] = useState(false);
  const containerRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    const onClickOut = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) setOpen(false);
    };
    const onEsc = (e) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onClickOut);
    document.addEventListener("keydown", onEsc);
    return () => {
      document.removeEventListener("mousedown", onClickOut);
      document.removeEventListener("keydown", onEsc);
    };
  }, [open]);

  const toggle = (val) => {
    const set = new Set(selected);
    set.has(val) ? set.delete(val) : set.add(val);
    onChange([...set]);
  };

  const selectedLabels = options
    .filter((o) => selected.includes(o.value))
    .map((o) => o.label);

  let triggerText;
  if (selected.length === 0) triggerText = placeholder;
  else if (selected.length <= maxBadgeText) triggerText = selectedLabels.join(", ");
  else triggerText = `${selectedLabels.slice(0, maxBadgeText).join(", ")}…`;

  return (
    <div style={{ position: "relative", display: "inline-block" }} ref={containerRef}>
      {label && <div className="slicer-label">{label}</div>}
      <button
        className={`dropdown-trigger${open ? " active" : ""}`}
        onClick={() => setOpen(!open)}
        type="button"
      >
        <span className="dropdown-trigger-text">{triggerText}</span>
        {selected.length > 0 && <span className="dropdown-trigger-count">{selected.length}</span>}
        <span className="dropdown-trigger-arrow">▾</span>
      </button>

      {open && (
        <div className="dropdown-menu">
          <div className="dropdown-actions">
            <button className="dropdown-action" onClick={() => onChange(options.map((o) => o.value))}>
              Todos
            </button>
            <button className="dropdown-action" onClick={() => onChange([])}>
              Limpiar
            </button>
          </div>
          {options.map((opt) => {
            const isSelected = selected.includes(opt.value);
            return (
              <div
                key={opt.value}
                className={`dropdown-option${isSelected ? " selected" : ""}`}
                onClick={() => toggle(opt.value)}
              >
                <span className="dropdown-checkbox">
                  <span className="dropdown-checkbox-tick">✓</span>
                </span>
                <span>{opt.label}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

// ==============================
// StatusDot
// ==============================
const STATUS_COLORS = {
  "on-track": tokens.colors.statusOnTrack,
  "at-risk": tokens.colors.statusAtRisk,
  "off-track": tokens.colors.statusOffTrack,
  "pending": tokens.colors.statusPending,
};
const StatusDot = ({ status, size = 10 }) => (
  <span className="status-dot" role="status" aria-label={`KPI status: ${status}`}
    style={{
      width: size, height: size, borderRadius: "50%",
      background: STATUS_COLORS[status], flexShrink: 0,
      boxShadow: `0 0 10px ${STATUS_COLORS[status]}88`,
    }}
  />
);

// ==============================
// TargetBadge
// ==============================
const TargetBadge = ({ target, valueFormat }) => {
  const formatted = target.formatted ?? (
    target.value === null ? "TBD" : formatValue(target.value, valueFormat, target.unit)
  );
  return (
    <div className="target-pill" style={{
      borderRadius: 10, padding: "6px 10px",
      fontSize: tokens.typography.fontSize.target,
      fontWeight: tokens.typography.fontWeight.medium,
      display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap",
      letterSpacing: "0.02em",
    }}>
      <span style={{ fontWeight: tokens.typography.fontWeight.semibold, opacity: 0.88 }}>Meta</span>
      <span>≥ {formatted}</span>
      {target.periodLabel && <span style={{ opacity: 0.7 }}>· {target.periodLabel}</span>}
      {target.growthLabel && <span style={{ marginLeft: "auto", opacity: 0.85 }}>↗ {target.growthLabel}</span>}
    </div>
  );
};

// ==============================
// KPICard
// ==============================
const KPICard = ({ data, onClick, hideStatus }) => {
  const isPending = data.value === null;
  const clickable = !!onClick;
  const mom = data.mom;
  const deltaPositive = mom && !mom.pending && mom.deltaPct > 0;
  const deltaNegative = mom && !mom.pending && mom.deltaPct < 0;

  return (
    <div
      className="glass-card"
      onClick={clickable ? () => onClick(data.id) : undefined}
      style={{
        fontFamily: tokens.typography.fontFamily,
        cursor: clickable ? "pointer" : "default",
        display: "flex", flexDirection: "column",
        padding: tokens.spacing.cardPadding,
        paddingTop: "20px",
        gap: 10,
        minHeight: 184,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8, flexShrink: 0 }}>
        <h3 style={{
          margin: 0,
          fontSize: tokens.typography.fontSize.title,
          fontWeight: tokens.typography.fontWeight.semibold,
          color: tokens.colors.textSecondary,
          lineHeight: 1.3, letterSpacing: "0.04em",
          textTransform: "uppercase",
        }}>
          {data.title}
          {data.titleAnnotation && (
            <span style={{
              display: "block", marginTop: 2, fontSize: "10px",
              color: data.titleAnnotation.tone === "warning"
                ? tokens.colors.alertText : tokens.colors.textTertiary,
              fontWeight: tokens.typography.fontWeight.regular,
              fontStyle: "italic", textTransform: "none", letterSpacing: "0",
            }}>{data.titleAnnotation.text}</span>
          )}
        </h3>
        {!hideStatus && <StatusDot status={data.status} />}
      </div>

      <div style={{ display: "flex", alignItems: "baseline", gap: 8, flexShrink: 0 }}>
        {isPending ? (
          <span className="kpi-value-pending" style={{
            fontSize: tokens.typography.fontSize.pending,
            fontWeight: tokens.typography.fontWeight.bold,
            lineHeight: 1.1, letterSpacing: "-0.01em",
          }}>{data.pendingLabel ?? data.title}</span>
        ) : (
          <>
            <span className="kpi-value-bright" style={{
              fontSize: tokens.typography.fontSize.value,
              fontWeight: tokens.typography.fontWeight.bold,
              lineHeight: 1, fontVariantNumeric: "tabular-nums",
              letterSpacing: "-0.02em",
            }}>{formatValue(data.value, data.valueFormat, data.valueUnit)}</span>
            {data.valuePeriodLabel && (
              <span style={{
                fontSize: tokens.typography.fontSize.valuePeriod,
                color: tokens.colors.textTertiary,
                fontWeight: tokens.typography.fontWeight.medium,
              }}>{data.valuePeriodLabel}</span>
            )}
          </>
        )}
      </div>

      {isPending && data.emptyReason && (
        <div style={{
          flexShrink: 0, marginTop: 2,
          fontSize: "11px", lineHeight: 1.45,
          color: tokens.colors.textTertiary,
          fontStyle: "italic",
        }}>{data.emptyReason}</div>
      )}

      {mom && !isPending && (
        <div style={{ flexShrink: 0 }}>
          {mom.pending ? (
            <div style={{
              display: "flex", alignItems: "center", gap: 6,
              fontSize: tokens.typography.fontSize.comparison,
              color: tokens.colors.textTertiary,
            }}>
              <span style={{ fontSize: "10px", opacity: 0.5 }}>↗</span>
              <span style={{ opacity: 0.55 }}>MoM vs {mom.prevMonthLabel}</span>
              <span className="mom-skeleton" />
            </div>
          ) : (
            <div style={{
              fontSize: tokens.typography.fontSize.comparison,
              color: deltaNegative ? tokens.colors.alertText
                  : deltaPositive ? tokens.colors.positiveText
                  : tokens.colors.textSecondary,
              fontWeight: tokens.typography.fontWeight.medium,
              display: "flex", alignItems: "center", gap: 4,
            }}>
              <span style={{ fontSize: "10px" }}>{deltaNegative ? "↘" : deltaPositive ? "↗" : "→"}</span>
              <span>MoM {formatDelta(mom.deltaPct)} vs {mom.prevMonthLabel}</span>
            </div>
          )}
          {data.comparisonContext && (
            <div style={{
              fontSize: "10px", color: tokens.colors.textTertiary,
              fontStyle: "italic", lineHeight: 1.35, marginTop: 2,
            }}>{data.comparisonContext}</div>
          )}
        </div>
      )}

      <div style={{ flex: 1 }} />

      <div style={{ flexShrink: 0 }}>
        <TargetBadge target={data.target} valueFormat={data.valueFormat} />
      </div>

      <div style={{
        flexShrink: 0,
        fontSize: tokens.typography.fontSize.okr,
        color: tokens.colors.textAnnotation,
        fontStyle: "italic", letterSpacing: "0.04em",
        textTransform: "uppercase",
        fontWeight: tokens.typography.fontWeight.medium,
      }}>OKR · {data.okrLabel}</div>
    </div>
  );
};

// ==============================
// ErrorBar
// ==============================
const ErrorBar = ({ x, yLower, yUpper, capWidth = 5, stroke = "currentColor", strokeWidth = 1.25, opacity = 0.55 }) => (
  <g stroke={stroke} strokeWidth={strokeWidth} opacity={opacity} fill="none" strokeLinecap="round">
    <line x1={x} x2={x} y1={yLower} y2={yUpper} />
    <line x1={x - capWidth} x2={x + capWidth} y1={yLower} y2={yLower} />
    <line x1={x - capWidth} x2={x + capWidth} y1={yUpper} y2={yUpper} />
  </g>
);

// ==============================
// TrendLineChart
// ==============================
const TREND_CURVE_MAP = {
  linear: d3.curveLinear,
  curveMonotoneX: d3.curveMonotoneX,
  curveCatmullRom: d3.curveCatmullRom.alpha(0.5),
};

const TrendLineChart = ({ data, dimensions, config = {}, margin = { top: 40, right: 26, bottom: 30, left: 56 } }) => {
  const cfg = {
    showErrorBars: true, showPointLabels: true, showGridlines: true,
    interpolation: "curveMonotoneX", strokeWidth: 2,
    pointRadius: { normal: 3.5, highlighted: 5 },
    showArea: true, ...config,
  };
  const xAxisRef = useRef(null);
  const yAxisRef = useRef(null);
  const gradientId = useMemo(() => `trend-grad-${Math.random().toString(36).slice(2, 8)}`, []);
  const areaGradId = useMemo(() => `area-grad-${Math.random().toString(36).slice(2, 8)}`, []);

  const innerWidth = dimensions.width - margin.left - margin.right;
  const innerHeight = dimensions.height - margin.top - margin.bottom;

  const { xScale, yScale } = useMemo(() => {
    const allDates = data.points.map((p) => p.date);
    const allValues = data.points.flatMap((p) => [p.value, p.ci_lower ?? p.value, p.ci_upper ?? p.value]);
    const xDomain = d3.extent(allDates);
    const [yMin, yMax] = d3.extent(allValues);
    const yPad = (yMax - yMin) * 0.12;
    return {
      xScale: d3.scaleTime().domain(xDomain).range([0, innerWidth]).nice(),
      yScale: d3.scaleLinear().domain([Math.max(0, yMin - yPad), yMax + yPad]).range([innerHeight, 0]).nice(),
    };
  }, [data, innerWidth, innerHeight]);

  const curve = TREND_CURVE_MAP[cfg.interpolation];
  const lineGen = useMemo(
    () => d3.line().x((d) => xScale(d.date)).y((d) => yScale(d.value)).curve(curve),
    [xScale, yScale, curve]
  );
  const areaGen = useMemo(
    () => d3.area().x((d) => xScale(d.date)).y0(innerHeight).y1((d) => yScale(d.value)).curve(curve),
    [xScale, yScale, innerHeight, curve]
  );

  useEffect(() => {
    if (!xAxisRef.current || !yAxisRef.current) return;
    const xFormat = cfg.xAxisFormat ?? ((d) => d.getFullYear().toString());
    const yFormat = cfg.yAxisFormat ?? ((v) => formatCompactNumber(v, 0));
    const xAxis = d3.axisBottom(xScale)
      .tickValues(data.points.map((p) => p.date))
      .tickFormat((d) => xFormat(d))
      .tickSize(0).tickPadding(10);
    const yAxis = d3.axisLeft(yScale).ticks(5).tickFormat((v) => yFormat(+v))
      .tickSize(cfg.showGridlines ? -innerWidth : 0).tickPadding(10);
    d3.select(xAxisRef.current).call(xAxis)
      .call((g) => g.select(".domain").remove())
      .call((g) => g.selectAll("text").attr("font-family", tokens.typography.fontFamily)
        .attr("font-size", "10px").attr("font-weight", "500").attr("fill", tokens.colors.chartAxis));
    d3.select(yAxisRef.current).call(yAxis)
      .call((g) => g.select(".domain").remove())
      .call((g) => g.selectAll(".tick line").attr("stroke", tokens.colors.chartGrid).attr("stroke-dasharray", "2,3"))
      .call((g) => g.selectAll("text").attr("font-family", tokens.typography.fontFamily)
        .attr("font-size", "10px").attr("font-weight", "500").attr("fill", tokens.colors.chartAxis));
  }, [xScale, yScale, innerWidth, data.points, cfg.xAxisFormat, cfg.yAxisFormat, cfg.showGridlines]);

  const linePath = lineGen(data.points) ?? "";
  const areaPath = areaGen(data.points) ?? "";

  return (
    <svg width={dimensions.width} height={dimensions.height} role="img">
      <defs>
        <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor={tokens.colors.purple} />
          <stop offset="55%" stopColor={tokens.colors.magenta} />
          <stop offset="100%" stopColor={tokens.colors.gold} />
        </linearGradient>
        <linearGradient id={areaGradId} x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor={tokens.colors.magenta} stopOpacity="0.35" />
          <stop offset="70%" stopColor={tokens.colors.purple} stopOpacity="0.08" />
          <stop offset="100%" stopColor={tokens.colors.purple} stopOpacity="0" />
        </linearGradient>
      </defs>

      {cfg.title && (
        <text x={dimensions.width / 2} y={24} textAnchor="middle"
          fontFamily={tokens.typography.fontFamily} fontSize="12px"
          fontWeight={tokens.typography.fontWeight.semibold}
          fill={tokens.colors.textSecondary}
          style={{ textTransform: "uppercase", letterSpacing: "0.14em" }}>
          {cfg.title}
        </text>
      )}

      {cfg.yAxisUnit && (
        <text
          x={14}
          y={margin.top + innerHeight / 2}
          textAnchor="middle"
          transform={`rotate(-90, 14, ${margin.top + innerHeight / 2})`}
          fontFamily={tokens.typography.fontFamily}
          fontSize="10px"
          fontWeight={tokens.typography.fontWeight.semibold}
          fill={tokens.colors.textTertiary}
          style={{ textTransform: "uppercase", letterSpacing: "0.16em" }}
        >
          {cfg.yAxisUnit}
        </text>
      )}

      <g transform={`translate(${margin.left},${margin.top})`}>
        <g ref={yAxisRef} />
        <g ref={xAxisRef} transform={`translate(0,${innerHeight})`} />
        {cfg.showArea && <path d={areaPath} fill={`url(#${areaGradId})`} />}
        {cfg.showErrorBars && data.points.map((p, i) =>
          p.ci_lower !== undefined && p.ci_upper !== undefined ? (
            <ErrorBar key={`eb-${i}`} x={xScale(p.date)}
              yLower={yScale(p.ci_lower)} yUpper={yScale(p.ci_upper)}
              stroke={tokens.colors.magenta} opacity={0.35} />
          ) : null
        )}
        <path className="d3-line" d={linePath} fill="none" stroke={`url(#${gradientId})`}
          strokeWidth={cfg.strokeWidth} strokeLinejoin="round" strokeLinecap="round" />
        {data.points.map((p, i) => (
          <g key={`pt-${i}`}>
            <circle cx={xScale(p.date)} cy={yScale(p.value)}
              r={p.highlighted ? cfg.pointRadius.highlighted + 4 : cfg.pointRadius.normal + 3}
              fill={tokens.colors.magenta} opacity="0.18" />
            <circle className="d3-point" cx={xScale(p.date)} cy={yScale(p.value)}
              r={p.highlighted ? cfg.pointRadius.highlighted : cfg.pointRadius.normal}
              fill={tokens.colors.abyss} stroke={tokens.colors.magenta}
              strokeWidth={p.highlighted ? 2 : 1.5} />
          </g>
        ))}
        {cfg.showPointLabels && data.points.map((p, i) => {
          const label = p.label ?? formatCompactNumber(p.value, 0);
          return (
            <text key={`lbl-${i}`} x={xScale(p.date)}
              y={yScale(p.value) - (p.highlighted ? 12 : 10)}
              textAnchor="middle" fontFamily={tokens.typography.fontFamily}
              fontSize="10px" fontWeight={tokens.typography.fontWeight.semibold}
              fill={tokens.colors.textPrimary}
              style={{ fontVariantNumeric: "tabular-nums" }}>{label}</text>
          );
        })}
      </g>
    </svg>
  );
};

// ==============================
// BarChartWithTrendLine
// ==============================
const BAR_CURVE_MAP = {
  monotoneX: d3.curveMonotoneX,
  basis: d3.curveBasis,
  catmullRom: d3.curveCatmullRom.alpha(0.5),
};
function msToPx(scale, ms) {
  const base = scale.domain()[0].getTime();
  return scale(new Date(base + ms)) - scale(new Date(base));
}

const BarChartWithTrendLine = ({ data, dimensions, config = {}, margin = { top: 40, right: 26, bottom: 30, left: 52 } }) => {
  const cfg = {
    showTrendLine: true, trendInterpolation: "monotoneX",
    showGridlines: true, showBarLabels: true, showErrorBars: false,
    showAxisDomain: true, yTicks: 5, projectedOpacity: 0.4, barCornerRadius: 6,
    ...config,
  };
  const xAxisRef = useRef(null);
  const yAxisRef = useRef(null);
  const barGradId = useMemo(() => `bar-grad-${Math.random().toString(36).slice(2, 8)}`, []);
  const baseGradId = useMemo(() => `base-grad-${Math.random().toString(36).slice(2, 8)}`, []);

  const innerWidth = dimensions.width - margin.left - margin.right;
  const innerHeight = dimensions.height - margin.top - margin.bottom;

  const { xScale, yScale, barWidth } = useMemo(() => {
    const allDates = [...data.bars.map((b) => b.date), ...(data.trendLine ?? []).map((t) => t.date)];
    const allValues = [
      ...data.bars.flatMap((b) => [b.value, b.ci_lower ?? b.value, b.ci_upper ?? b.value]),
      ...(data.trendLine ?? []).map((t) => t.value),
    ];
    const xExtent = d3.extent(allDates);
    const rangePad = (xExtent[1].getTime() - xExtent[0].getTime()) * 0.06;
    const xDomain = [new Date(xExtent[0].getTime() - rangePad), new Date(xExtent[1].getTime() + rangePad)];
    const xs = d3.scaleTime().domain(xDomain).range([0, innerWidth]);
    const [yMin, yMax] = d3.extent(allValues);
    const yPad = (yMax - yMin) * 0.18;
    const ys = d3.scaleLinear()
      .domain([Math.max(0, yMin - yPad), yMax + yPad])
      .range([innerHeight, 0]).nice();
    const sortedDates = data.bars.map((b) => b.date.getTime()).sort((a, b) => a - b);
    const gaps = sortedDates.slice(1).map((d, i) => d - sortedDates[i]);
    const minGapMs = gaps.length > 0 ? Math.min(...gaps) : 365 * 86400000;
    const autoBarWidth = Math.min(36, Math.max(12, msToPx(xs, minGapMs) * 0.55));
    return { xScale: xs, yScale: ys, barWidth: cfg.barWidth ?? autoBarWidth };
  }, [data, innerWidth, innerHeight, cfg.barWidth]);

  const trendPath = useMemo(() => {
    if (!cfg.showTrendLine) return null;
    const series = data.trendLine ?? data.bars.map((b) => ({ date: b.date, value: b.value }));
    const line = d3.line().x((d) => xScale(d.date)).y((d) => yScale(d.value))
      .curve(BAR_CURVE_MAP[cfg.trendInterpolation]);
    return line(series);
  }, [data, xScale, yScale, cfg.showTrendLine, cfg.trendInterpolation]);

  useEffect(() => {
    if (!xAxisRef.current || !yAxisRef.current) return;
    const xFormat = cfg.xAxisFormat ?? ((d) => d.getFullYear().toString());
    const yFormat = cfg.yAxisFormat ?? ((v) => formatCompactNumber(v, 0));
    const xAxis = d3.axisBottom(xScale)
      .tickValues(data.bars.map((b) => b.date))
      .tickFormat((d) => xFormat(d))
      .tickSize(0).tickPadding(10);
    const yAxis = d3.axisLeft(yScale).ticks(cfg.yTicks).tickFormat((v) => yFormat(+v))
      .tickSize(cfg.showGridlines ? -innerWidth : 0).tickPadding(10);
    d3.select(xAxisRef.current).call(xAxis)
      .call((g) => g.select(".domain").remove())
      .call((g) => g.selectAll("text").attr("font-family", tokens.typography.fontFamily)
        .attr("font-size", "10px").attr("font-weight", "500").attr("fill", tokens.colors.chartAxis));
    d3.select(yAxisRef.current).call(yAxis)
      .call((g) => g.select(".domain").remove())
      .call((g) => g.selectAll(".tick line").attr("stroke", tokens.colors.chartGrid).attr("stroke-dasharray", "2,3"))
      .call((g) => g.selectAll("text").attr("font-family", tokens.typography.fontFamily)
        .attr("font-size", "10px").attr("font-weight", "500").attr("fill", tokens.colors.chartAxis));
  }, [xScale, yScale, innerWidth, data.bars, cfg]);

  return (
    <svg width={dimensions.width} height={dimensions.height} role="img">
      <defs>
        <linearGradient id={barGradId} x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor={tokens.colors.magenta} />
          <stop offset="100%" stopColor={tokens.colors.purple} />
        </linearGradient>
        <linearGradient id={baseGradId} x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor={tokens.colors.gold} />
          <stop offset="100%" stopColor={tokens.colors.magenta} />
        </linearGradient>
      </defs>

      {cfg.title && (
        <text x={dimensions.width / 2} y={24} textAnchor="middle"
          fontFamily={tokens.typography.fontFamily} fontSize="12px"
          fontWeight={tokens.typography.fontWeight.semibold}
          fill={tokens.colors.textSecondary}
          style={{ textTransform: "uppercase", letterSpacing: "0.14em" }}>
          {cfg.title}
        </text>
      )}

      {cfg.yAxisUnit && (
        <text
          x={14}
          y={margin.top + innerHeight / 2}
          textAnchor="middle"
          transform={`rotate(-90, 14, ${margin.top + innerHeight / 2})`}
          fontFamily={tokens.typography.fontFamily}
          fontSize="10px"
          fontWeight={tokens.typography.fontWeight.semibold}
          fill={tokens.colors.textTertiary}
          style={{ textTransform: "uppercase", letterSpacing: "0.16em" }}
        >
          {cfg.yAxisUnit}
        </text>
      )}

      <g transform={`translate(${margin.left},${margin.top})`}>
        <g ref={yAxisRef} />
        <g ref={xAxisRef} transform={`translate(0,${innerHeight})`} />

        {data.bars.map((b, i) => {
          const x = xScale(b.date) - barWidth / 2;
          const y = yScale(b.value);
          const h = innerHeight - y;
          const fill = b.isBaseline ? `url(#${baseGradId})` : `url(#${barGradId})`;
          const opacity = b.isProjected ? cfg.projectedOpacity : 1;
          return (
            <rect key={`bar-${i}`} className="d3-bar" x={x} y={y}
              width={barWidth} height={Math.max(0, h)}
              rx={cfg.barCornerRadius} ry={cfg.barCornerRadius}
              fill={fill} opacity={opacity} />
          );
        })}

        {cfg.showTrendLine && trendPath && (
          <path className="d3-line" d={trendPath} fill="none"
            stroke={tokens.colors.gold} strokeWidth={1.5}
            strokeDasharray="4,3" strokeLinejoin="round" strokeLinecap="round" opacity={0.75} />
        )}

        {cfg.showBarLabels && data.bars.map((b, i) => {
          const label = b.label ?? formatCompactNumber(b.value, 0);
          return (
            <text key={`lbl-${i}`} x={xScale(b.date)} y={yScale(b.value) - 6}
              textAnchor="middle" fontFamily={tokens.typography.fontFamily}
              fontSize="10px" fontWeight={tokens.typography.fontWeight.semibold}
              fill={tokens.colors.textPrimary}
              style={{ fontVariantNumeric: "tabular-nums" }}>
              {label}
            </text>
          );
        })}
      </g>
    </svg>
  );
};

// ==============================
// DashboardHeader with embedded OKR subtitle
// ==============================
const DashboardHeader = ({ area, axis, okrText, variant = "expanded" }) => {
  const isCompact = variant === "compact";
  return (
    <div className="dashboard-header-card" style={{
      color: tokens.colors.textPrimary,
      padding: isCompact ? "14px 16px" : "18px 22px",
      fontFamily: tokens.typography.fontFamily,
      display: "flex", flexDirection: "column", justifyContent: "center",
      height: "100%",
      minHeight: isCompact ? 60 : 100,
      position: "relative",
    }}>
      <div style={{
        position: "absolute", top: -40, right: -40,
        width: 160, height: 160, borderRadius: "50%",
        background: `radial-gradient(circle, ${tokens.colors.gold}33 0%, transparent 70%)`,
        pointerEvents: "none",
      }} />
      <div style={{
        display: "flex", alignItems: "baseline", gap: 14, flexWrap: "wrap",
      }}>
        <h1 style={{
          margin: 0,
          fontSize: isCompact ? "18px" : "26px",
          fontWeight: tokens.typography.fontWeight.bold,
          letterSpacing: "0.06em", lineHeight: 1,
        }}>{area}</h1>
        <span style={{
          fontSize: "11px",
          opacity: 0.78, letterSpacing: "0.02em",
        }}>{axis}</span>
      </div>
      {okrText && (
        <div style={{
          marginTop: isCompact ? 6 : 10,
          paddingTop: isCompact ? 6 : 8,
          borderTop: "1px solid rgba(255,255,255,0.12)",
          fontSize: isCompact ? "10px" : "11px",
          color: "rgba(255, 204, 109, 0.92)",
          fontStyle: "italic",
          fontWeight: tokens.typography.fontWeight.medium,
          letterSpacing: "0.02em",
          lineHeight: 1.4,
        }}>
          <span style={{
            fontWeight: tokens.typography.fontWeight.bold,
            fontStyle: "normal",
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            marginRight: 6,
            opacity: 0.85,
          }}>OKR</span>
          {okrText}
        </div>
      )}
    </div>
  );
};

// ==============================
// SLICER BAR
// ==============================
const SlicerBar = ({ filters, setFilters, real }) => {
  // Filtro principal: COMPAÑÍA (antes «País»). Las opciones vienen del payload;
  // el consolidado es "todas". Con el extracto actual hay una sola compañía
  // sintética; cuando la vista exponga company_id aparecen las ~34 sociedades y
  // el mismo filtro rebana del lado del cliente sin más cambios.
  const companyOptions = (real?.meta?.companies || []).map(
    (c) => ({ value: c.company_id, label: c.company_name })
  );

  // Elegir compañía: multi/ninguna fuerza USD (consolidado).
  const onCompanias = (v) =>
    setFilters((f) => ({ ...f, companias: v, moneda: v.length === 1 ? f.moneda : "USD" }));

  // Local deshabilitado: el extracto viene en USD. Moneda local exige conversión
  // desde la vista, no en el front (sumar divisas mezcladas no tiene sentido).
  const monedaOptions = [
    { value: "ML", label: "Local", disabled: true },
    { value: "USD", label: "USD" },
  ];

  return (
  <div className="slicer-bar" style={{
    padding: "14px 18px",
    display: "flex", flexWrap: "wrap",
    alignItems: "flex-end", gap: 18, rowGap: 14,
    position: "relative",
  }}>
    <MultiSelectDropdown
      label="Compañía"
      placeholder="Consolidado (todas)"
      options={companyOptions}
      selected={filters.companias}
      onChange={onCompanias}
    />
    <MultiSelectDropdown
      label="Año"
      placeholder="Todos"
      options={YEARS.map((y) => ({ value: y, label: String(y) }))}
      selected={filters.años}
      onChange={(v) => setFilters((f) => ({ ...f, años: v }))}
    />
    <MultiSelectDropdown
      label="Mes"
      placeholder="Todos"
      options={MONTHS}
      selected={filters.meses}
      onChange={(v) => setFilters((f) => ({ ...f, meses: v }))}
    />
    {real && (
      <SegmentedControl
        label="Moneda"
        value={filters.moneda}
        options={monedaOptions}
        onChange={(m) => setFilters((f) => ({ ...f, moneda: m }))}
      />
    )}
    <div style={{ flex: 1, minWidth: 12 }} />
    <div style={{ display: "flex", flexDirection: "column" }}>
      <div className="slicer-label">Presupuesto</div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, height: 34 }}>
        <div
          className={`toggle-switch${filters.conPpto ? " on" : ""}`}
          onClick={() => setFilters((f) => ({ ...f, conPpto: !f.conPpto }))}
          role="switch"
          aria-checked={filters.conPpto}
        >
          <div className="toggle-thumb" />
        </div>
        <span style={{
          fontSize: 11, fontWeight: 600,
          color: filters.conPpto ? tokens.colors.textPrimary : tokens.colors.textTertiary,
          letterSpacing: "0.02em", transition: tokens.transition,
        }}>{filters.conPpto ? "Con ppto" : "Sin ppto"}</span>
      </div>
    </div>
  </div>
  );
};

// ==============================
// ChartSlot
// ==============================
const ChartSlot = ({ minHeight, gridColumn, children }) => {
  const [ref, size] = useResizeObserver();
  return (
    <div ref={ref} className="glass-card chart-card" style={{
      width: "100%", minHeight, gridColumn, padding: 8,
    }}>
      {size.width > 0 && children({
        width: size.width - 16,
        height: Math.max(size.height - 16, minHeight - 16),
      })}
    </div>
  );
};

// Placeholder de chart vacío (estado sin datos). Se renderiza EN LUGAR del chart
// para no montar el componente con series vacías (evita ejes/escala sobre []).
const EmptyChartMsg = ({ dims, title }) => (
  <div style={{
    width: dims.width, height: dims.height,
    display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
    gap: 6, fontFamily: tokens.typography.fontFamily, color: tokens.colors.textTertiary,
  }}>
    <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase" }}>{title}</div>
    <div style={{ fontSize: 12, opacity: 0.8 }}>Sin datos</div>
  </div>
);

// ==============================
// Grid
// ==============================
const FinanzasDashboardGrid = ({
  kpiCards, trendChartData, barChartData, settings, dimensions, onKPIClick, conPpto,
}) => {
  const bp = getBreakpoint(dimensions.width);
  const isWide = bp === "wide";
  const isMobile = bp === "mobile";
  const isTablet = bp === "tablet";
  const isDesktop = bp === "desktop";

  const cols = isWide ? 8 : isDesktop ? 4 : isTablet ? 2 : 1;
  const gap = isMobile ? 10 : isTablet ? 12 : 14;
  const cardSpan = isWide ? "span 2" : "span 1";
  const chartMinH = isMobile ? 200 : isTablet ? 220 : 220;

  const topCards = kpiCards.slice(0, 8);
  const eficienciaCard = kpiCards[8];

  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`,
      gridAutoRows: "minmax(184px, auto)",
      alignItems: "stretch",
      gap,
      padding: isMobile ? 12 : 18,
      paddingTop: 8,
      fontFamily: tokens.typography.fontFamily,
    }}>
      <div style={{ gridColumn: `span ${cols}`, height: "100%" }}>
        <DashboardHeader
          area={settings.area} axis={settings.axisLabel}
          okrText={settings.globalOKR}
          variant={isWide || isDesktop ? "expanded" : "compact"}
        />
      </div>

      {topCards.map((card) => (
        <div key={card.id} style={{ gridColumn: cardSpan, height: "100%" }}>
          <KPICard data={card} onClick={onKPIClick} hideStatus={isMobile} />
        </div>
      ))}

      {eficienciaCard && (
        <div style={{ gridColumn: isWide ? "span 2" : cardSpan, height: "100%" }}>
          <KPICard data={eficienciaCard} onClick={onKPIClick} hideStatus={isMobile} />
        </div>
      )}

      <ChartSlot minHeight={chartMinH} gridColumn={isWide ? "span 3" : `span ${cols}`}>
        {(dims) => (barChartData && barChartData.bars && barChartData.bars.length ? (
          <BarChartWithTrendLine
            data={barChartData} dimensions={dims}
            config={{
              title: "EBITDA % a través del tiempo",
              yAxisUnit: "Porcentaje (%)",
              showTrendLine: conPpto,
              trendInterpolation: "monotoneX",
              yTicks: 5,
              yAxisFormat: (v) => `${v}%`,
            }}
          />
        ) : <EmptyChartMsg dims={dims} title="EBITDA % a través del tiempo" />)}
      </ChartSlot>

      <ChartSlot minHeight={chartMinH} gridColumn={isWide ? "span 3" : `span ${cols}`}>
        {(dims) => (trendChartData && trendChartData.points && trendChartData.points.length ? (
          <TrendLineChart
            data={trendChartData} dimensions={dims}
            config={{
              title: "Tendencia de Ingresos",
              yAxisUnit: "Millones (USD)",
              interpolation: "curveMonotoneX",
              showErrorBars: conPpto,
            }}
          />
        ) : <EmptyChartMsg dims={dims} title="Tendencia de Ingresos" />)}
      </ChartSlot>
    </div>
  );
};

// ==============================
// TopBar
// ==============================
const TopBar = ({ compact, periodLabel }) => (
  <div className="topbar" style={{
    padding: compact ? "12px 16px" : "14px 22px",
    display: "flex", alignItems: "center", justifyContent: "space-between",
    gap: 12, position: "sticky", top: 0, zIndex: 10,
  }}>
    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
      <AddiuvaLogo height={compact ? 24 : 28} />
      {!compact && (
        <div style={{
          marginLeft: 8, paddingLeft: 14,
          borderLeft: `1px solid ${tokens.colors.border}`,
          fontSize: 11, color: tokens.colors.textTertiary,
          letterSpacing: "0.14em", textTransform: "uppercase", fontWeight: 600,
        }}>Business Intelligence</div>
      )}
    </div>
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <div style={{
        fontSize: 11, color: tokens.colors.textSecondary,
        letterSpacing: "0.04em", fontWeight: 500,
        padding: "6px 12px", borderRadius: 999,
        background: tokens.colors.surface,
        border: `1px solid ${tokens.colors.border}`,
      }}>{periodLabel ?? "Feb 2026 · MTD"}</div>
      <div style={{
        width: 32, height: 32, borderRadius: "50%",
        background: `linear-gradient(135deg, ${tokens.colors.purple}, ${tokens.colors.magenta}, ${tokens.colors.gold})`,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 11, fontWeight: 700, color: "#FFF",
        border: `1px solid ${tokens.colors.border}`,
      }}>LV</div>
    </div>
  </div>
);

// ==============================
// MOCK DATA — backend integration points
// ==============================
const buildMockKpis = () => [
  {
    id: "EBITDA_CONS",
    title: "EBITDA Consolidado",
    value: 866560, valueUnit: "USD", valueFormat: "currency",
    valuePeriodLabel: "Feb",
    mom: computeMoM(866560, null, "Feb", "Ene"),
    target: { value: 17566000, unit: "USD", periodLabel: "2026", growthLabel: "+36% · 2035" },
    okrLabel: "CAGR sostenible", status: "on-track",
  },
  {
    id: "INGRESOS_CONS",
    title: "Total Ingresos",
    value: 7514000, valueUnit: "USD", valueFormat: "currency",
    mom: computeMoM(7514000, null, "Feb", "Ene"),
    target: { value: 7514000, unit: "USD", periodLabel: "Feb 2026" },
    okrLabel: "CAGR sostenible", status: "on-track",
  },
  {
    id: "SINIESTRALIDAD",
    title: "Siniestralidad",
    value: 3569000, valueUnit: "USD", valueFormat: "currency",
    mom: computeMoM(3569000, null, "Feb", "Ene"),
    comparisonContext: "% de cumplimiento vs presupuesto en todos los rubros",
    target: { value: null, unit: "%", periodLabel: "TBD", growthLabel: "+xx2pp", formatted: "TBD%" },
    okrLabel: "CAGR sostenible", status: "at-risk",
  },
  {
    id: "GASTOS_GAV",
    title: "Gastos Generales de Administración y Ventas",
    value: 1434000, valueUnit: "USD", valueFormat: "currency",
    mom: computeMoM(1434000, null, "Feb", "Ene"),
    target: { value: null, unit: "%", periodLabel: "Acordado", formatted: "18%" },
    okrLabel: "CAGR sostenible", status: "on-track",
  },
  {
    id: "BALANCE_GENERAL",
    title: "Balance General",
    value: 1592000, valueUnit: "USD", valueFormat: "currency",
    valuePeriodLabel: "YTD",
    target: { value: null, unit: "USD", periodLabel: "2026", formatted: "Net 15.011 USD" },
    okrLabel: "CAGR sostenible", status: "on-track",
  },
  {
    id: "FCF_INCREMENTAL",
    title: "Incremental Free Cash Flow",
    pendingLabel: "Incremental Free Cash Flow",
    value: null, valueUnit: "USD", valueFormat: "currency",
    target: { value: null, unit: "USD", periodLabel: "Q4 2026", growthLabel: "+XX%", formatted: "$TBD" },
    okrLabel: "CAGR sostenible", status: "pending",
  },
  {
    id: "ROIC",
    title: "Return on Invested Capital",
    pendingLabel: "Return on Invested Capital",
    value: null, valueUnit: "%", valueFormat: "percent",
    target: { value: null, unit: "%", periodLabel: "Anual", growthLabel: "+xx2pp", formatted: "TBD%" },
    okrLabel: "CAGR sostenible", status: "pending",
  },
  {
    id: "BU_EBITDA",
    title: "Business Unit EBITDA",
    value: 0.18, valueUnit: "%", valueFormat: "percent",
    target: { value: 0.18, unit: "%", periodLabel: "Acordado", formatted: "18%" },
    okrLabel: "CAGR sostenible", status: "on-track",
  },
  {
    id: "EFICIENCIA_FISCAL",
    title: "Eficiencia Fiscal · Cumplimiento",
    pendingLabel: "Estrategia Tributaria",
    value: null, valueUnit: "USD", valueFormat: "currency",
    target: { value: 17566000, unit: "USD", periodLabel: "2026", growthLabel: "+18% · 2035" },
    okrLabel: "Estrategia fiscal alineada a SOX", status: "on-track",
  },
];

const MOCK_TREND_DATA = {
  points: [
    { date: new Date(2026, 0, 1), value: 101, ci_lower:  85, ci_upper: 118, highlighted: true },
    { date: new Date(2029, 0, 1), value: 209, ci_lower: 190, ci_upper: 228, highlighted: true },
    { date: new Date(2030, 0, 1), value: 268, ci_lower: 245, ci_upper: 291, highlighted: true },
    { date: new Date(2032, 0, 1), value: 439, ci_lower: 410, ci_upper: 468, highlighted: true },
    { date: new Date(2033, 0, 1), value: 561, ci_lower: 525, ci_upper: 597, highlighted: true },
    { date: new Date(2035, 0, 1), value: 920, ci_lower: 870, ci_upper: 970, highlighted: true },
  ],
};
const MOCK_BAR_DATA = {
  bars: [
    { date: new Date(2026, 0, 1), value: 15, isBaseline: true },
    { date: new Date(2029, 0, 1), value: 26 },
    { date: new Date(2030, 0, 1), value: 29 },
    { date: new Date(2032, 0, 1), value: 36 },
    { date: new Date(2033, 0, 1), value: 39 },
    { date: new Date(2035, 0, 1), value: 42 },
  ],
};

// ==============================
// REAL DATA BRIDGE — injected by shared/render.py as window.__FINANZAS_DATA__.
// Absent in production (Streamlit Cloud) -> null -> the mock above is used.
// ==============================
const FINANZAS_REAL =
  (typeof window !== "undefined" && window.__FINANZAS_DATA__) ? window.__FINANZAS_DATA__ : null;

const MONTH_ABBR = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];

// Catálogo de tarjetas (alcance Fase 3: consolidado). Orden = cascada operativa
// que CIERRA en pantalla:  Ingresos − Costos Totales − G&A = EBITDA.
// Costos Directos (AGA5) queda como DETALLE dentro de Costos Totales (no es una
// resta adicional; anotado para que nadie lo reste dos veces). Charts 9/10 abajo.
// 5/6/7 vacías con motivo (Balance sin extracto/periodo, impuestos ausente).
const CARD_CATALOG = [
  { comp: 2,    code: "AGA4",          id: "INGRESOS",   title: "Total Ingresos",               okr: "Crecimiento sostenible" },
  { comp: null, code: "COSTOS_TOT_OP", id: "COSTOS_TOT", title: "Costos Totales de Operación",  okr: "Control de costo",
    annotation: "Directos + otros + comercialización + indirectos" },
  { comp: 4,    code: "AGA25",         id: "GAV",        title: "Gastos Generales (G&A)",       okr: "Disciplina de gasto" },
  { comp: 1,    code: "AGA29",         id: "EBITDA",     title: "EBITDA",                       okr: "Crecimiento sostenible" },
  { comp: 3,    code: "AGA5",          id: "COSTOS_DIR", title: "Costos Directos de Operación", okr: "Control de costo directo",
    annotation: "Detalle · ya incluido en Costos Totales" },
  { comp: 5,    empty: true,           id: "BALANCE",    title: "Balance General",              okr: "Solidez financiera" },
  { comp: 6,    empty: true,           id: "FCF",        title: "Free Cash Flow Incremental",   okr: "Generación de caja" },
  { comp: 7,    empty: true,           id: "ROIC",       title: "Return on Invested Capital",   okr: "Rentabilidad del capital" },
];

// Compañías seleccionadas (vacío => todas => consolidado).
function selectedCompanyIds(real, filters) {
  const all = (real.meta.companies || []).map((c) => c.company_id);
  const picked = (filters.companias || []).filter((id) => all.includes(id));
  return picked.length ? picked : all;
}

// Agrega las medidas ADITIVAS entre las compañías seleccionadas, agrupando por
// (anio, mes). Los ratios NO se suman: AGA30 (EBITDA %) se recalcula sobre los
// agregados. El consolidado es este mismo camino con "todas" las compañías.
function aggregateMonths(real, filters) {
  const ids = new Set(selectedCompanyIds(real, filters));
  const hasYear = (filters.años || []).length;
  const byKey = new Map();
  for (const r of real.records) {
    if (!ids.has(r.company_id)) continue;
    if (hasYear && !filters.años.includes(r.anio)) continue;
    const key = r.anio * 100 + r.mes;
    let acc = byKey.get(key);
    if (!acc) {
      acc = { anio: r.anio, mes: r.mes, divisa: r.divisa, preliminar: false, measures: {} };
      byKey.set(key, acc);
    }
    acc.preliminar = acc.preliminar || !!r.preliminar;
    for (const code in r.measures) {
      const v = r.measures[code];
      if (v == null) continue;
      acc.measures[code] = (acc.measures[code] ?? 0) + v;
    }
  }
  const arr = [...byKey.values()].sort((a, b) => (a.anio - b.anio) || (a.mes - b.mes));
  for (const m of arr) {
    const eb = m.measures.AGA29, ing = m.measures.AGA4;   // AGA30 = ebitda / total_ingreso
    m.ebitdaPct = (ing && eb != null) ? eb / ing : null;
  }
  return arr;
}

// Periodo a mostrar: respeta filtros de año/mes; si no, el último mes CERRADO
// (el más reciente se marca preliminar) para no abrir en un periodo incompleto.
function pickPeriod(months, filters) {
  if (!months.length) return null;
  const hasYear = (filters.años || []).length;
  const hasMonth = (filters.meses || []).length;
  let pool = months;
  if (hasMonth) pool = pool.filter((m) => filters.meses.includes(m.mes));
  if (!pool.length) pool = months;
  if (!hasYear && !hasMonth) {
    const closed = pool.filter((m) => !m.preliminar);
    if (closed.length) return closed[closed.length - 1];
  }
  return pool[pool.length - 1];
}

function statusForKpi(code, value) {
  if (value == null) return "pending";
  if (code === "AGA5" || code === "AGA25" || code === "COSTOS_TOT_OP") return "at-risk";  // costo/gasto: informativo
  if (code === "AGA29" || code === "AGA46" || code === "AGA56") return value >= 0 ? "on-track" : "off-track";
  return "on-track";
}

// Tarjeta vacía con MOTIVO legible (regla de admisión del BR: sin dato -> vacío,
// nunca 0, nunca inventado).
function emptyCard(meta, reason) {
  return {
    id: meta.id, title: meta.title, value: null,
    valueUnit: "USD", valueFormat: "currency",
    pendingLabel: "Sin dato", emptyReason: reason,
    okrLabel: meta.okr, status: "pending",
    target: { value: null, unit: "USD", periodLabel: "—" },
  };
}

// Construye las tarjetas para los filtros actuales. NUNCA cae al mock cuando hay
// datos reales cargados: un slice vacío da tarjetas "sin dato" VISIBLES, no
// números inventados (arreglo del fallback silencioso).
function buildKpisFromData(real, filters) {
  const months = aggregateMonths(real, filters);
  const cur = pickPeriod(months, filters);
  const empties = real.meta.empty_components || {};
  if (!cur) {
    return CARD_CATALOG.map((meta) =>
      emptyCard(meta, meta.empty
        ? (empties[String(meta.comp)] || "No disponible")
        : "Sin datos para la compañía / período seleccionado."));
  }
  const idx = months.indexOf(cur);
  const prev = idx > 0 ? months[idx - 1] : null;
  const periodLabel = `${MONTH_ABBR[cur.mes]} ${cur.anio}`;
  const ingresos = cur.measures.AGA4;
  return CARD_CATALOG.map((meta) => {
    if (meta.empty) return emptyCard(meta, empties[String(meta.comp)] || "No disponible");
    const value = cur.measures[meta.code] ?? null;
    if (value == null) return emptyCard(meta, `Columna de ${meta.title} ausente en la vista de P&L.`);
    const prevVal = prev ? (prev.measures[meta.code] ?? null) : null;
    const pct = (ingresos && meta.code !== "AGA4") ? value / ingresos : null;
    return {
      id: meta.id,
      title: meta.title,
      titleAnnotation: meta.annotation ? { text: meta.annotation } : undefined,
      value,
      valueUnit: cur.divisa,
      valueFormat: "currency",
      valuePeriodLabel: periodLabel,
      mom: computeMoM(value, prevVal, MONTH_ABBR[cur.mes], prev ? MONTH_ABBR[prev.mes] : "—"),
      target: pct != null
        ? { value: null, unit: "%", periodLabel: "% s/ ingresos", formatted: `${(pct * 100).toFixed(1)}%` }
        : { value: null, unit: cur.divisa, periodLabel: periodLabel },
      okrLabel: meta.okr,
      status: statusForKpi(meta.code, value),
    };
  });
}

// Estado vacío GLOBAL (producción sin payload inyectado): todas las tarjetas
// vacías con motivo. NUNCA el mock — no hay números que confundir con reales.
function buildEmptyKpis(reason) {
  return CARD_CATALOG.map((meta) => emptyCard(meta, reason));
}

// --- Series para charts (solo meses CERRADOS: el preliminar se excluye para que
// un periodo incompleto nunca distorsione la tendencia) ---
function closedSeries(real, filters) {
  return aggregateMonths(real, filters).filter((m) => !m.preliminar);
}
// Comp 10 · Tendencia de Ingresos (total_ingreso en millones USD).
function buildRevenueTrend(real, filters) {
  const points = closedSeries(real, filters)
    .filter((m) => m.measures.AGA4 != null)
    .map((m) => ({ date: new Date(m.anio, m.mes - 1, 1), value: m.measures.AGA4 / 1e6, highlighted: true }));
  return { points };
}
// Comp 9 · EBITDA % en el tiempo (AGA30 derivado sobre agregados).
function buildEbitdaPctBars(real, filters) {
  const bars = closedSeries(real, filters)
    .filter((m) => m.ebitdaPct != null)
    .map((m) => ({ date: new Date(m.anio, m.mes - 1, 1), value: +(m.ebitdaPct * 100).toFixed(2) }));
  if (bars.length) bars[0].isBaseline = true;
  return { bars };
}

// Etiquetas de alcance/periodo para el encabezado y la tira de validación.
function currentScopeLabel(real, filters) {
  const ids = filters.companias || [];
  if (ids.length === 1) {
    const c = (real.meta.companies || []).find((x) => x.company_id === ids[0]);
    return c ? c.company_name : "Compañía";
  }
  return "Consolidado";
}
function currentPeriodLabel(real, filters) {
  const cur = pickPeriod(aggregateMonths(real, filters), filters);
  const scope = currentScopeLabel(real, filters);
  return cur ? `${scope} · ${MONTH_ABBR[cur.mes]} ${cur.anio}` : scope;
}

// Small Local/USD switch (Local disabled on the multi-country consolidated view).
const SegmentedControl = ({ label, value, options, onChange }) => (
  <div style={{ display: "flex", flexDirection: "column" }}>
    {label && <div className="slicer-label">{label}</div>}
    <div style={{ display: "flex", gap: 4, height: 34, alignItems: "center" }}>
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            disabled={o.disabled}
            onClick={() => !o.disabled && onChange(o.value)}
            style={{
              padding: "6px 12px", borderRadius: 9,
              fontSize: 11, fontWeight: 600, letterSpacing: "0.02em",
              cursor: o.disabled ? "not-allowed" : "pointer",
              color: active ? "#FFF" : tokens.colors.textTertiary,
              background: active ? "rgba(139,70,205,0.55)" : tokens.colors.surface,
              border: `1px solid ${active ? tokens.colors.borderHover : tokens.colors.border}`,
              opacity: o.disabled ? 0.4 : 1, transition: tokens.transition,
            }}
          >{o.label}</button>
        );
      })}
    </div>
  </div>
);

// Validation badges for the current selection (per-country reconciliation + preliminary month).
const ValidationStrip = ({ real, filters }) => {
  if (!real) return null;
  const months = aggregateMonths(real, filters);
  const cur = pickPeriod(months, filters);
  if (!cur) return null;
  const scope = currentScopeLabel(real, filters);
  const prelim = months.filter((m) => m.preliminar).slice(-1)[0] || null;
  const Badge = ({ bg, fg, brd, children }) => (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 6,
      padding: "4px 10px", borderRadius: 999, fontSize: 11, fontWeight: 600,
      background: bg, color: fg, border: `1px solid ${brd}`,
    }}>{children}</span>
  );
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center",
                  padding: "0 18px 6px" }}>
      <span style={{ fontSize: 11, color: tokens.colors.textTertiary, letterSpacing: "0.04em" }}>
        {scope} · {cur.divisa} · {MONTH_ABBR[cur.mes]} {cur.anio}
      </span>
      {prelim && (
        <Badge bg="rgba(231,92,224,0.10)" fg={tokens.colors.magenta} brd="rgba(231,92,224,0.40)">
          ⏳ {MONTH_ABBR[prelim.mes]} {prelim.anio} preliminar · excluido del titular
        </Badge>
      )}
      <span style={{ fontSize: 10, color: tokens.colors.textTertiary }}>
        Regla territorial v0.1 (excl. Voccare/Ikatech) · vista P&L
      </span>
    </div>
  );
};

// ==============================
// MAIN APP
// ==============================
export default function App() {
  const [ref, size] = useResizeObserver();
  const bp = getBreakpoint(size.width || 1400);
  const isSmall = bp === "mobile" || bp === "tablet";

  const [filters, setFilters] = useState({
    companias: [], años: [], meses: [], conPpto: true, moneda: "USD",
  });

  // Datos reales cuando se inyectan; si no (producción sin payload), ESTADO VACÍO,
  // nunca el mock: no se despliegan cifras ficticias que el CEO pueda confundir con
  // reales. Con datos reales, un slice vacío también da tarjetas "sin dato".
  const hasReal = !!FINANZAS_REAL;
  const NO_DATA = "Sin conexión a datos en este entorno";
  const kpiCards = useMemo(
    () => (hasReal ? buildKpisFromData(FINANZAS_REAL, filters) : buildEmptyKpis(NO_DATA)),
    [filters, hasReal],
  );
  const trendData = useMemo(
    () => (hasReal ? buildRevenueTrend(FINANZAS_REAL, filters) : { points: [] }),
    [filters, hasReal],
  );
  const barData = useMemo(
    () => (hasReal ? buildEbitdaPctBars(FINANZAS_REAL, filters) : { bars: [] }),
    [filters, hasReal],
  );
  const periodLabel = useMemo(
    () => (hasReal ? currentPeriodLabel(FINANZAS_REAL, filters) : "Sin datos"),
    [filters, hasReal],
  );

  return (
    <>
      <GlobalStyles />
      <div className="addiuva-root addiuva-bg addiuva-grain" ref={ref} style={{
        position: "relative", width: "100%", minHeight: "100vh", overflow: "auto",
      }}>
        <TopBar compact={isSmall} periodLabel={periodLabel} />
        {!hasReal && (
          <div style={{
            margin: isSmall ? "8px 12px 0" : "10px 18px 0",
            padding: "10px 14px", borderRadius: 10,
            background: "rgba(231,92,224,0.10)", border: "1px solid rgba(231,92,224,0.40)",
            color: tokens.colors.magenta, fontSize: 12, fontWeight: 600, lineHeight: 1.4,
          }}>
            Sin conexión a datos en este entorno · estado vacío. El tablero se puebla
            desde la vista del warehouse; no se muestran cifras.
          </div>
        )}
        {size.width > 0 && (
          <div style={{
            padding: isSmall ? "12px 12px 0" : "16px 18px 0",
            /* ↓ Z-INDEX FIX: lifts the slicer (and its dropdowns) above the
               dashboard grid. Without this, the .dashboard-header-card and
               .glass-card stacking contexts (created by isolation:isolate)
               render above the dropdown menu because they come later in DOM
               and have z-index:auto resolving in DOM order. Explicit z-index
               on this wrapper makes it always win against auto-z-index siblings. */
            position: "relative",
            zIndex: 50,
          }}>
            <SlicerBar filters={filters} setFilters={setFilters} real={FINANZAS_REAL} />
            <ValidationStrip real={FINANZAS_REAL} filters={filters} />
          </div>
        )}
        {size.width > 0 && (
          <div style={{ position: "relative", zIndex: 1 }}>
            <FinanzasDashboardGrid
              kpiCards={kpiCards}
              trendChartData={trendData}
              barChartData={barData}
              settings={{
                area: "FINANZAS",
                axisLabel: "Eje · Crecimiento y expansión",
                globalOKR: "Objectives and Key Results · Crecimiento de Ingreso Anual Sostenible + Eficiencia Fiscal",
              }}
              dimensions={{ width: size.width, height: Math.max(size.height, 900) }}
              conPpto={filters.conPpto}
              onKPIClick={(id) => console.log("[FinanzasDashboard] KPI click:", id)}
            />
          </div>
        )}
      </div>
    </>
  );
}
