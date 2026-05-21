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
// DESIGN TOKENS — Addiuva palette (identical to Finanzas)
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
// GLOBAL STYLES — identical hover containment fix as Finanzas
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
    .d3-arc  { transition: filter 220ms ease, transform 220ms ease; cursor: pointer; }
    .chart-card:hover .d3-arc { filter: drop-shadow(0 0 10px rgba(231, 92, 224, 0.5)); }

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
      opacity: 0; color: #FFF; font-size: 10px; line-height: 1;
      font-weight: 900; transition: opacity 160ms ease;
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

    /* ===== Construction badge (chart overlay) ===== */
    .construction-badge {
      display: inline-flex; align-items: center; gap: 6px;
      padding: 5px 12px;
      border-radius: 999px;
      background: rgba(67, 92, 200, 0.18);
      border: 1px solid rgba(67, 92, 200, 0.4);
      color: #9DB2FF;
      font-size: 10px; font-weight: 700;
      letter-spacing: 0.08em; text-transform: uppercase;
      backdrop-filter: blur(6px);
    }
    .construction-badge::before {
      content: ""; width: 7px; height: 7px; border-radius: 50%;
      background: ${tokens.colors.bluePurple};
      box-shadow: 0 0 8px ${tokens.colors.bluePurple};
      animation: pulse 1.6s ease-in-out infinite;
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.4; transform: scale(0.8); }
    }

    /* ===== Multi-value rows (Expedientes card) ===== */
    .mv-row {
      display: flex; align-items: center; justify-content: space-between;
      padding: 7px 0;
      border-bottom: 1px solid rgba(255,255,255,0.05);
    }
    .mv-row:last-child { border-bottom: 0; }
    .mv-label {
      display: flex; align-items: center; gap: 8px;
      font-size: 12px; font-weight: 500;
      color: ${tokens.colors.textSecondary};
    }
    .mv-dot {
      width: 8px; height: 8px; border-radius: 2px; flex-shrink: 0;
    }
    .mv-value {
      font-size: 17px; font-weight: 700;
      color: ${tokens.colors.textPrimary};
      font-variant-numeric: tabular-nums;
    }
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
function formatPct(v, decimals = 1) {
  return `${(v * 100).toFixed(decimals)}%`;
}
function formatNumber(v) {
  return new Intl.NumberFormat("es-MX").format(v);
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
// MULTI-SELECT DROPDOWN (cloned from Finanzas)
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

  const selectedLabels = options.filter((o) => selected.includes(o.value)).map((o) => o.label);

  let triggerText;
  if (selected.length === 0) triggerText = placeholder;
  else if (selected.length <= maxBadgeText) triggerText = selectedLabels.join(", ");
  else triggerText = `${selectedLabels.slice(0, maxBadgeText).join(", ")}…`;

  return (
    <div style={{ position: "relative", display: "inline-block" }} ref={containerRef}>
      {label && <div className="slicer-label">{label}</div>}
      <button className={`dropdown-trigger${open ? " active" : ""}`} onClick={() => setOpen(!open)} type="button">
        <span className="dropdown-trigger-text">{triggerText}</span>
        {selected.length > 0 && <span className="dropdown-trigger-count">{selected.length}</span>}
        <span className="dropdown-trigger-arrow">▾</span>
      </button>
      {open && (
        <div className="dropdown-menu">
          <div className="dropdown-actions">
            <button className="dropdown-action" onClick={() => onChange(options.map((o) => o.value))}>Todos</button>
            <button className="dropdown-action" onClick={() => onChange([])}>Limpiar</button>
          </div>
          {options.map((opt) => {
            const isSelected = selected.includes(opt.value);
            return (
              <div key={opt.value} className={`dropdown-option${isSelected ? " selected" : ""}`} onClick={() => toggle(opt.value)}>
                <span className="dropdown-checkbox"><span className="dropdown-checkbox-tick">✓</span></span>
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
const TargetBadge = ({ target }) => (
  <div className="target-pill" style={{
    borderRadius: 10, padding: "6px 10px",
    fontSize: tokens.typography.fontSize.target,
    fontWeight: tokens.typography.fontWeight.medium,
    display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap",
    letterSpacing: "0.02em",
  }}>
    <span style={{ fontWeight: tokens.typography.fontWeight.semibold, opacity: 0.88 }}>Meta</span>
    <span>{target.text}</span>
    {target.periodLabel && <span style={{ opacity: 0.7 }}>· {target.periodLabel}</span>}
    {target.extra && <span style={{ marginLeft: "auto", opacity: 0.85 }}>{target.extra}</span>}
  </div>
);

// ==============================
// KPICard — handles value | pending | multi-value
// ==============================
const KPICard = ({ data, hideStatus }) => {
  const isPending = data.value === null && !data.rows;
  const hasRows = Array.isArray(data.rows);

  return (
    <div className="glass-card" style={{
      fontFamily: tokens.typography.fontFamily,
      display: "flex", flexDirection: "column",
      padding: tokens.spacing.cardPadding, paddingTop: "20px",
      gap: 10, minHeight: 184,
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8, flexShrink: 0 }}>
        <h3 style={{
          margin: 0, fontSize: tokens.typography.fontSize.title,
          fontWeight: tokens.typography.fontWeight.semibold,
          color: tokens.colors.textSecondary,
          lineHeight: 1.3, letterSpacing: "0.04em", textTransform: "uppercase",
        }}>{data.title}</h3>
        {!hideStatus && <StatusDot status={data.status} />}
      </div>

      {/* VALUE ZONE */}
      {hasRows ? (
        <div style={{ flexShrink: 0 }}>
          {data.rows.map((r) => (
            <div className="mv-row" key={r.label}>
              <span className="mv-label">
                <span className="mv-dot" style={{ background: r.color }} />
                {r.label}
              </span>
              <span className="mv-value">{formatNumber(r.value)}</span>
            </div>
          ))}
        </div>
      ) : isPending ? (
        <div style={{ display: "flex", alignItems: "baseline", gap: 8, flexShrink: 0 }}>
          <span className="kpi-value-pending" style={{
            fontSize: tokens.typography.fontSize.value,
            fontWeight: tokens.typography.fontWeight.bold,
            lineHeight: 1.1, letterSpacing: "-0.01em",
          }}>{data.pendingLabel ?? "TBD"}</span>
        </div>
      ) : (
        <div style={{ display: "flex", alignItems: "baseline", gap: 8, flexShrink: 0 }}>
          <span className="kpi-value-bright" style={{
            fontSize: tokens.typography.fontSize.value,
            fontWeight: tokens.typography.fontWeight.bold,
            lineHeight: 1, fontVariantNumeric: "tabular-nums", letterSpacing: "-0.02em",
          }}>{data.displayValue}</span>
          {data.valuePeriodLabel && (
            <span style={{
              fontSize: tokens.typography.fontSize.valuePeriod,
              color: tokens.colors.textTertiary,
              fontWeight: tokens.typography.fontWeight.medium,
            }}>{data.valuePeriodLabel}</span>
          )}
        </div>
      )}

      {/* SUBTITLE / CONTEXT */}
      {data.subtitle && (
        <div style={{
          flexShrink: 0, fontSize: "11px", color: tokens.colors.textTertiary,
          lineHeight: 1.4,
        }}>{data.subtitle}</div>
      )}

      <div style={{ flex: 1 }} />

      <div style={{ flexShrink: 0 }}>
        <TargetBadge target={data.target} />
      </div>

      <div style={{
        flexShrink: 0, fontSize: tokens.typography.fontSize.okr,
        color: tokens.colors.textAnnotation,
        fontStyle: "italic", letterSpacing: "0.04em",
        textTransform: "uppercase", fontWeight: tokens.typography.fontWeight.medium,
      }}>OKR · {data.okrLabel}</div>
    </div>
  );
};

// ==============================
// LineChart — % series with target line (SLA / FCR style)
// ==============================
const LineChart = ({ data, dimensions, config = {}, margin = { top: 44, right: 30, bottom: 30, left: 48 } }) => {
  const cfg = { showGridlines: true, yMin: 85, yMax: 99, ...config };
  const xAxisRef = useRef(null);
  const yAxisRef = useRef(null);
  const gradId = useMemo(() => `ln-${Math.random().toString(36).slice(2, 8)}`, []);

  const innerWidth = dimensions.width - margin.left - margin.right;
  const innerHeight = dimensions.height - margin.top - margin.bottom;

  const xScale = useMemo(
    () => d3.scalePoint().domain(MONTHS.map((m) => m.label)).range([0, innerWidth]).padding(0.5),
    [innerWidth]
  );
  const yScale = useMemo(
    () => d3.scaleLinear().domain([cfg.yMin, cfg.yMax]).range([innerHeight, 0]),
    [innerHeight, cfg.yMin, cfg.yMax]
  );

  const lineGen = useMemo(
    () => d3.line().defined((d) => d.value != null).x((d) => xScale(d.label)).y((d) => yScale(d.value)).curve(d3.curveMonotoneX),
    [xScale, yScale]
  );

  useEffect(() => {
    if (!xAxisRef.current || !yAxisRef.current) return;
    const xAxis = d3.axisBottom(xScale).tickSize(0).tickPadding(10);
    const yAxis = d3.axisLeft(yScale).ticks(7).tickFormat((v) => `${v}`)
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
  }, [xScale, yScale, innerWidth, cfg.showGridlines]);

  const series = data.series ?? [];
  const targetVal = data.targetLine;

  return (
    <svg width={dimensions.width} height={dimensions.height} role="img">
      <defs>
        <linearGradient id={gradId} x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor={tokens.colors.purple} />
          <stop offset="55%" stopColor={tokens.colors.magenta} />
          <stop offset="100%" stopColor={tokens.colors.gold} />
        </linearGradient>
      </defs>

      {cfg.title && (
        <text x={dimensions.width / 2} y={22} textAnchor="middle"
          fontFamily={tokens.typography.fontFamily} fontSize="12px"
          fontWeight={tokens.typography.fontWeight.semibold}
          fill={tokens.colors.textSecondary}
          style={{ textTransform: "uppercase", letterSpacing: "0.12em" }}>{cfg.title}</text>
      )}

      {cfg.yAxisUnit && (
        <text x={13} y={margin.top + innerHeight / 2} textAnchor="middle"
          transform={`rotate(-90, 13, ${margin.top + innerHeight / 2})`}
          fontFamily={tokens.typography.fontFamily} fontSize="10px"
          fontWeight={tokens.typography.fontWeight.semibold}
          fill={tokens.colors.textTertiary}
          style={{ textTransform: "uppercase", letterSpacing: "0.16em" }}>{cfg.yAxisUnit}</text>
      )}

      <g transform={`translate(${margin.left},${margin.top})`}>
        <g ref={yAxisRef} />
        <g ref={xAxisRef} transform={`translate(0,${innerHeight})`} />

        {/* Target reference line */}
        {targetVal != null && (
          <g>
            <line x1={0} x2={innerWidth} y1={yScale(targetVal)} y2={yScale(targetVal)}
              stroke={tokens.colors.gold} strokeWidth={1.25} strokeDasharray="5,4" opacity={0.6} />
            <text x={innerWidth} y={yScale(targetVal) - 6} textAnchor="end"
              fontFamily={tokens.typography.fontFamily} fontSize="9px" fontWeight="700"
              fill={tokens.colors.gold} opacity={0.85}>META {targetVal}%</text>
          </g>
        )}

        {/* Main actual series */}
        <path className="d3-line" d={lineGen(series) ?? ""} fill="none" stroke={`url(#${gradId})`}
          strokeWidth={2.25} strokeLinejoin="round" strokeLinecap="round" />

        {series.filter((d) => d.value != null).map((d, i) => (
          <g key={`pt-${i}`}>
            <circle cx={xScale(d.label)} cy={yScale(d.value)} r={6} fill={tokens.colors.magenta} opacity="0.18" />
            <circle className="d3-point" cx={xScale(d.label)} cy={yScale(d.value)} r={3.5}
              fill={tokens.colors.abyss} stroke={tokens.colors.magenta} strokeWidth={1.75} />
          </g>
        ))}

        {/* Construction badge overlay */}
        {cfg.construction && (
          <foreignObject x={innerWidth / 2 - 75} y={innerHeight / 2 - 16} width={150} height={32}>
            <div style={{ display: "flex", justifyContent: "center" }}>
              <span className="construction-badge">En construcción</span>
            </div>
          </foreignObject>
        )}
      </g>
    </svg>
  );
};

// ==============================
// DonutChart — NEW atom for Estandarización
// ==============================
const DonutChart = ({ data, dimensions, config = {} }) => {
  const cfg = { innerRadiusRatio: 0.62, ...config };
  const gradCompleted = useMemo(() => `donut-c-${Math.random().toString(36).slice(2, 8)}`, []);

  const size = Math.min(dimensions.width, dimensions.height - 40);
  const radius = size / 2;
  const innerR = radius * cfg.innerRadiusRatio;
  const cx = dimensions.width / 2;
  const cy = (dimensions.height - 40) / 2 + 40;

  const total = data.segments.reduce((s, seg) => s + seg.value, 0);
  const pie = d3.pie().value((d) => d.value).sort(null).startAngle(0).endAngle(2 * Math.PI);
  const arcGen = d3.arc().innerRadius(innerR).outerRadius(radius).cornerRadius(3).padAngle(0.02);
  const arcs = pie(data.segments);

  const SEG_COLORS = [tokens.colors.purple, tokens.colors.gold];

  return (
    <svg width={dimensions.width} height={dimensions.height} role="img">
      <defs>
        <linearGradient id={gradCompleted} x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor={tokens.colors.magenta} />
          <stop offset="100%" stopColor={tokens.colors.purple} />
        </linearGradient>
      </defs>

      {cfg.title && (
        <text x={dimensions.width / 2} y={22} textAnchor="middle"
          fontFamily={tokens.typography.fontFamily} fontSize="12px"
          fontWeight={tokens.typography.fontWeight.semibold}
          fill={tokens.colors.textSecondary}
          style={{ textTransform: "uppercase", letterSpacing: "0.12em" }}>{cfg.title}</text>
      )}

      <g transform={`translate(${cx},${cy})`}>
        {arcs.map((a, i) => (
          <path key={i} className="d3-arc" d={arcGen(a)}
            fill={i === 0 ? `url(#${gradCompleted})` : SEG_COLORS[1]}
            opacity={i === 0 ? 1 : 0.55} />
        ))}
        {/* Center label */}
        <text textAnchor="middle" dy="-2"
          fontFamily={tokens.typography.fontFamily} fontSize="30px" fontWeight="700"
          fill={tokens.colors.textPrimary} className="kpi-value-bright">
          {formatPct(data.segments[0].value / total, 0)}
        </text>
        <text textAnchor="middle" dy="20"
          fontFamily={tokens.typography.fontFamily} fontSize="10px" fontWeight="600"
          fill={tokens.colors.textTertiary}
          style={{ textTransform: "uppercase", letterSpacing: "0.1em" }}>
          {data.centerLabel}
        </text>
      </g>

      {/* Legend */}
      <g transform={`translate(${dimensions.width / 2}, ${dimensions.height - 14})`}>
        {data.segments.map((seg, i) => {
          const spacing = 90;
          const xPos = (i - (data.segments.length - 1) / 2) * spacing;
          return (
            <g key={i} transform={`translate(${xPos}, 0)`}>
              <rect x={-42} y={-8} width={10} height={10} rx={2}
                fill={i === 0 ? tokens.colors.purple : SEG_COLORS[1]} opacity={i === 0 ? 1 : 0.55} />
              <text x={-28} y={1} fontFamily={tokens.typography.fontFamily} fontSize="10px"
                fontWeight="500" fill={tokens.colors.textSecondary}>
                {seg.label} {formatPct(seg.value / total, 0)}
              </text>
            </g>
          );
        })}
      </g>
    </svg>
  );
};

// ==============================
// DonutCard — wraps a compact donut inside a KPI-sized glass card
// so Estandarización sits beside the other tarjetas (not as a full chart)
// ==============================
const DonutCard = ({ data, title, subtitle }) => {
  const [ref, size] = useResizeObserver();
  const total = data.segments.reduce((s, seg) => s + seg.value, 0);

  // Compact donut geometry — fits inside the card body.
  // SVG canvas is larger than the donut itself so the arc corners and the
  // hover drop-shadow have breathing room and don't clip at the edges.
  const radius = 52;
  const innerR = radius * 0.62;
  const pad = 16;                       // margin around the donut for glow/shadow
  const svgSize = radius * 2 + pad * 2;  // total SVG canvas
  const center = svgSize / 2;
  const gradId = useMemo(() => `dcard-${Math.random().toString(36).slice(2, 8)}`, []);
  const pie = d3.pie().value((d) => d.value).sort(null).startAngle(0).endAngle(2 * Math.PI);
  const arcGen = d3.arc().innerRadius(innerR).outerRadius(radius).cornerRadius(3).padAngle(0.02);
  const arcs = pie(data.segments);
  const SEG_COLORS = [tokens.colors.purple, tokens.colors.gold];

  return (
    <div ref={ref} className="glass-card chart-card" style={{
      fontFamily: tokens.typography.fontFamily,
      display: "flex", flexDirection: "column",
      padding: tokens.spacing.cardPadding, paddingTop: "20px",
      gap: 8, minHeight: 184,
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8, flexShrink: 0 }}>
        <h3 style={{
          margin: 0, fontSize: tokens.typography.fontSize.title,
          fontWeight: tokens.typography.fontWeight.semibold,
          color: tokens.colors.textSecondary,
          lineHeight: 1.3, letterSpacing: "0.04em", textTransform: "uppercase",
        }}>{title}</h3>
        <StatusDot status="on-track" />
      </div>

      <div style={{
        flex: 1, display: "flex", alignItems: "center", justifyContent: "center",
        gap: 12, minHeight: 0,
      }}>
        {/* Donut — SVG canvas padded so nothing clips */}
        <svg width={svgSize} height={svgSize} role="img" style={{ flexShrink: 0, overflow: "visible" }}>
          <defs>
            <linearGradient id={gradId} x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor={tokens.colors.magenta} />
              <stop offset="100%" stopColor={tokens.colors.purple} />
            </linearGradient>
          </defs>
          <g transform={`translate(${center},${center})`}>
            {arcs.map((a, i) => (
              <path key={i} className="d3-arc" d={arcGen(a)}
                fill={i === 0 ? `url(#${gradId})` : SEG_COLORS[1]} opacity={i === 0 ? 1 : 0.55} />
            ))}
            <text textAnchor="middle" dy="-1" className="kpi-value-bright"
              fontFamily={tokens.typography.fontFamily} fontSize="22px" fontWeight="700"
              fill={tokens.colors.textPrimary}>
              {formatPct(data.segments[0].value / total, 0)}
            </text>
            <text textAnchor="middle" dy="15"
              fontFamily={tokens.typography.fontFamily} fontSize="7px" fontWeight="600"
              fill={tokens.colors.textTertiary}
              style={{ textTransform: "uppercase", letterSpacing: "0.1em" }}>
              {data.centerLabel}
            </text>
          </g>
        </svg>

        {/* Vertical legend — compact, stacks label over value to avoid overflow */}
        <div style={{ display: "flex", flexDirection: "column", gap: 10, minWidth: 0 }}>
          {data.segments.map((seg, i) => (
            <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 7, minWidth: 0 }}>
              <span style={{
                width: 9, height: 9, borderRadius: 2, flexShrink: 0, marginTop: 3,
                background: i === 0 ? tokens.colors.purple : SEG_COLORS[1],
                opacity: i === 0 ? 1 : 0.55,
              }} />
              <div style={{ display: "flex", flexDirection: "column", lineHeight: 1.1, minWidth: 0 }}>
                <span style={{
                  fontSize: 10, color: tokens.colors.textTertiary, fontWeight: 500,
                  whiteSpace: "nowrap",
                }}>{seg.label}</span>
                <span style={{
                  fontSize: 15, color: tokens.colors.textPrimary, fontWeight: 700,
                  fontVariantNumeric: "tabular-nums",
                }}>{formatPct(seg.value / total, 0)}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {subtitle && (
        <div className="target-pill" style={{
          flexShrink: 0, borderRadius: 10, padding: "6px 10px",
          fontSize: tokens.typography.fontSize.target,
          fontWeight: tokens.typography.fontWeight.medium,
          display: "flex", alignItems: "center", gap: 6, letterSpacing: "0.02em",
        }}>
          <span style={{ fontWeight: tokens.typography.fontWeight.semibold, opacity: 0.88 }}>Meta</span>
          <span>{subtitle}</span>
        </div>
      )}

      <div style={{
        flexShrink: 0, fontSize: tokens.typography.fontSize.okr,
        color: tokens.colors.textAnnotation,
        fontStyle: "italic", letterSpacing: "0.04em",
        textTransform: "uppercase", fontWeight: tokens.typography.fontWeight.medium,
      }}>OKR · Estandarización 70%</div>
    </div>
  );
};

// ==============================
// DashboardHeader with OKR subtitle
// ==============================
const DashboardHeader = ({ area, axis, okrText, variant = "expanded" }) => {
  const isCompact = variant === "compact";
  return (
    <div className="dashboard-header-card" style={{
      color: tokens.colors.textPrimary,
      padding: isCompact ? "14px 16px" : "18px 22px",
      fontFamily: tokens.typography.fontFamily,
      display: "flex", flexDirection: "column", justifyContent: "center",
      height: "100%", minHeight: isCompact ? 60 : 100, position: "relative",
    }}>
      <div style={{
        position: "absolute", top: -40, right: -40,
        width: 160, height: 160, borderRadius: "50%",
        background: `radial-gradient(circle, ${tokens.colors.gold}33 0%, transparent 70%)`,
        pointerEvents: "none",
      }} />
      <div style={{ display: "flex", alignItems: "baseline", gap: 14, flexWrap: "wrap" }}>
        <h1 style={{
          margin: 0, fontSize: isCompact ? "18px" : "26px",
          fontWeight: tokens.typography.fontWeight.bold,
          letterSpacing: "0.06em", lineHeight: 1,
        }}>{area}</h1>
        <span style={{ fontSize: "11px", opacity: 0.78, letterSpacing: "0.02em" }}>{axis}</span>
      </div>
      {okrText && (
        <div style={{
          marginTop: isCompact ? 6 : 10, paddingTop: isCompact ? 6 : 8,
          borderTop: "1px solid rgba(255,255,255,0.12)",
          fontSize: isCompact ? "10px" : "11px",
          color: "rgba(255, 204, 109, 0.92)",
          fontStyle: "italic", fontWeight: tokens.typography.fontWeight.medium,
          letterSpacing: "0.02em", lineHeight: 1.4,
        }}>
          <span style={{
            fontWeight: tokens.typography.fontWeight.bold, fontStyle: "normal",
            letterSpacing: "0.08em", textTransform: "uppercase", marginRight: 6, opacity: 0.85,
          }}>OKR</span>
          {okrText}
        </div>
      )}
    </div>
  );
};

// ==============================
// SLICER BAR (cloned from Finanzas)
// ==============================
const SlicerBar = ({ filters, setFilters }) => (
  <div className="slicer-bar" style={{
    padding: "14px 18px", display: "flex", flexWrap: "wrap",
    alignItems: "flex-end", gap: 18, rowGap: 14, position: "relative",
  }}>
    <MultiSelectDropdown label="País" placeholder="Consolidado (todos)"
      options={COUNTRIES.map((c) => ({ value: c.code, label: c.label }))}
      selected={filters.paises} onChange={(v) => setFilters((f) => ({ ...f, paises: v }))} />
    <MultiSelectDropdown label="Año" placeholder="Todos"
      options={YEARS.map((y) => ({ value: y, label: String(y) }))}
      selected={filters.años} onChange={(v) => setFilters((f) => ({ ...f, años: v }))} />
    <MultiSelectDropdown label="Mes" placeholder="Todos"
      options={MONTHS} selected={filters.meses} onChange={(v) => setFilters((f) => ({ ...f, meses: v }))} />
    <div style={{ flex: 1, minWidth: 12 }} />
    <div style={{ display: "flex", flexDirection: "column" }}>
      <div className="slicer-label">Pronóstico</div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, height: 34 }}>
        <div className={`toggle-switch${filters.conFcst ? " on" : ""}`}
          onClick={() => setFilters((f) => ({ ...f, conFcst: !f.conFcst }))}
          role="switch" aria-checked={filters.conFcst}>
          <div className="toggle-thumb" />
        </div>
        <span style={{
          fontSize: 11, fontWeight: 600,
          color: filters.conFcst ? tokens.colors.textPrimary : tokens.colors.textTertiary,
          letterSpacing: "0.02em", transition: tokens.transition,
        }}>{filters.conFcst ? "Con FCST" : "Sin FCST"}</span>
      </div>
    </div>
  </div>
);

// ==============================
// ChartSlot
// ==============================
const ChartSlot = ({ minHeight, gridColumn, children }) => {
  const [ref, size] = useResizeObserver();
  return (
    <div ref={ref} className="glass-card chart-card" style={{ width: "100%", minHeight, gridColumn, padding: 8 }}>
      {size.width > 0 && children({ width: size.width - 16, height: Math.max(size.height - 16, minHeight - 16) })}
    </div>
  );
};

// ==============================
// GRID — rebalanced layout (6 cards + 3 charts)
// ==============================
const OperacionesGrid = ({ kpiCards, slaData, fcrData, donutData, settings, dimensions, conFcst }) => {
  const bp = getBreakpoint(dimensions.width);
  const isWide = bp === "wide";
  const isMobile = bp === "mobile";
  const isTablet = bp === "tablet";
  const isDesktop = bp === "desktop";

  const cols = isWide ? 12 : isDesktop ? 4 : isTablet ? 2 : 1;
  const gap = isMobile ? 10 : isTablet ? 12 : 14;
  // 6 cards across 12 cols → each spans 2 → 6 per row on wide
  const cardSpan = isWide ? "span 2" : "span 1";
  const chartMinH = isMobile ? 220 : 240;

  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`,
      gridAutoRows: "minmax(184px, auto)",
      alignItems: "stretch", gap,
      padding: isMobile ? 12 : 18, paddingTop: 8,
      fontFamily: tokens.typography.fontFamily,
    }}>
      <div style={{ gridColumn: `span ${cols}`, height: "100%" }}>
        <DashboardHeader area={settings.area} axis={settings.axisLabel}
          okrText={settings.globalOKR} variant={isWide || isDesktop ? "expanded" : "compact"} />
      </div>

      {/* 6 KPI cards — on wide, each spans 3 of 12 = 4 per row.
          The donut card is interleaved right after Índice de Abandono. */}
      {kpiCards.map((card) => (
        <React.Fragment key={card.id}>
          <div style={{ gridColumn: isWide ? "span 3" : cardSpan, height: "100%" }}>
            <KPICard data={card} hideStatus={isMobile} />
          </div>
          {/* Drop the Estandarización donut card immediately after Abandono */}
          {card.id === "ABANDONO" && (
            <div style={{ gridColumn: isWide ? "span 3" : cardSpan, height: "100%" }}>
              <DonutCard data={donutData} title="Estandarización" subtitle="58% de 70% · 2026" />
            </div>
          )}
        </React.Fragment>
      ))}

      {/* Bottom row — only the two time series, half width each */}
      <ChartSlot minHeight={chartMinH} gridColumn={isWide ? "span 6" : `span ${cols}`}>
        {(dims) => (
          <LineChart data={fcrData} dimensions={dims}
            config={{ title: "FCR Mensual (%) — Meta 95% · 2026", yAxisUnit: "Porcentaje (%)" }} />
        )}
      </ChartSlot>

      <ChartSlot minHeight={chartMinH} gridColumn={isWide ? "span 6" : `span ${cols}`}>
        {(dims) => (
          <LineChart data={slaData} dimensions={dims}
            config={{ title: "SLA Mensual (%) — Meta 95% · 2026", yAxisUnit: "Porcentaje (%)" }} />
        )}
      </ChartSlot>
    </div>
  );
};

// ==============================
// TopBar
// ==============================
const TopBar = ({ compact }) => (
  <div className="topbar" style={{
    padding: compact ? "12px 16px" : "14px 22px",
    display: "flex", alignItems: "center", justifyContent: "space-between",
    gap: 12, position: "sticky", top: 0, zIndex: 10,
  }}>
    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
      <AddiuvaLogo height={compact ? 24 : 28} />
      {!compact && (
        <div style={{
          marginLeft: 8, paddingLeft: 14, borderLeft: `1px solid ${tokens.colors.border}`,
          fontSize: 11, color: tokens.colors.textTertiary,
          letterSpacing: "0.14em", textTransform: "uppercase", fontWeight: 600,
        }}>Business Intelligence</div>
      )}
    </div>
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <div style={{
        fontSize: 11, color: tokens.colors.textSecondary,
        letterSpacing: "0.04em", fontWeight: 500, padding: "6px 12px", borderRadius: 999,
        background: tokens.colors.surface, border: `1px solid ${tokens.colors.border}`,
      }}>Feb 2026 · MTD</div>
      <div style={{
        width: 32, height: 32, borderRadius: "50%",
        background: `linear-gradient(135deg, ${tokens.colors.purple}, ${tokens.colors.magenta}, ${tokens.colors.gold})`,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 11, fontWeight: 700, color: "#FFF", border: `1px solid ${tokens.colors.border}`,
      }}>LV</div>
    </div>
  </div>
);

// ==============================
// MOCK DATA — Operaciones KPIs
// ==============================
const buildKpis = () => [
  {
    id: "COST_TO_SERVE",
    title: "Cost to Serve (reduction)",
    value: 0.10, displayValue: "10%",
    subtitle: "USD / cliente atendido (directo + indirecto) · reducción objetivo del año",
    target: { text: "≤ desde costo operativo", periodLabel: "2026" },
    okrLabel: "Optimización OPEX Addiuva", status: "on-track",
  },
  {
    id: "FCR",
    title: "First Call Resolution (FCR)",
    value: null, pendingLabel: "TBD",
    subtitle: "Meta alcanzada en Febrero",
    target: { text: "95%", periodLabel: "2026" },
    okrLabel: "FCR & Satisfacción", status: "on-track",
  },
  {
    id: "SLA_GLOBAL",
    title: "SLA Cumplimiento Global",
    value: 0.91, displayValue: "91%",
    subtitle: "Nivel de servicio cumplido · Febrero",
    target: { text: "≥ 95%", periodLabel: "2026" },
    okrLabel: "FCR & Satisfacción", status: "off-track",
  },
  {
    id: "ESTANDARIZACION",
    title: "Estandarización Procesos",
    value: 0.58, displayValue: "58%",
    subtitle: "% procesos alto impacto sistematizados",
    target: { text: "70%", periodLabel: "2026", extra: "Feb procesos completados" },
    okrLabel: "Estandarización 70%", status: "on-track",
  },
  {
    id: "EXPEDIENTES_COORD",
    title: "Expedientes atendidos × Coordinador",
    rows: [
      { label: "Addiuva", value: 259, color: tokens.colors.magenta },
      { label: "MCS", value: 522, color: tokens.colors.purple },
      { label: "TSC", value: 441, color: tokens.colors.gold },
    ],
    valuePeriodLabel: "Feb",
    subtitle: "Expedientes por agente · Febrero",
    target: { text: "≥ de acuerdo al pronóstico", periodLabel: "2026" },
    okrLabel: "Optimización OPEX Addiuva", status: "at-risk",
  },
  {
    id: "ABANDONO",
    title: "Índice Abandono Clientes",
    value: 0.007, displayValue: "0.7%",
    subtitle: "% índice de abandono de clientes · Feb 0.7% vs Ene 1.5%",
    target: { text: "3%", periodLabel: "2026", extra: "↘ mejor" },
    okrLabel: "Optimización OPEX Addiuva", status: "on-track",
  },
];

// FCR monthly: actual through Feb, then forecast climbing to 95
const FCR_DATA = {
  targetLine: 95,
  series: [
    { label: "Ene", value: 91.5 }, { label: "Feb", value: 91.0 },
    { label: "Mar", value: 91.0 }, { label: "Abr", value: 91.5 },
    { label: "May", value: 92.0 }, { label: "Jun", value: 92.5 },
    { label: "Jul", value: 93.5 }, { label: "Ago", value: 95.0 },
    { label: "Sep", value: 95.0 }, { label: "Oct", value: 95.0 },
    { label: "Nov", value: 95.0 }, { label: "Dic", value: 95.0 },
  ],
};

const SLA_DATA = {
  targetLine: 95,
  series: [
    { label: "Ene", value: 92.0 }, { label: "Feb", value: 91.0 },
    { label: "Mar", value: 91.2 }, { label: "Abr", value: 91.5 },
    { label: "May", value: 92.0 }, { label: "Jun", value: 92.8 },
    { label: "Jul", value: 93.5 }, { label: "Ago", value: 94.8 },
    { label: "Sep", value: 95.0 }, { label: "Oct", value: 95.0 },
    { label: "Nov", value: 95.0 }, { label: "Dic", value: 95.0 },
  ],
};

const DONUT_DATA = {
  centerLabel: "Completado",
  segments: [
    { label: "Completado", value: 58 },
    { label: "Pendiente", value: 42 },
  ],
};

// ==============================
// MAIN APP
// ==============================
export default function App() {
  const [ref, size] = useResizeObserver();
  const bp = getBreakpoint(size.width || 1400);
  const isSmall = bp === "mobile" || bp === "tablet";

  const [filters, setFilters] = useState({ paises: [], años: [], meses: [], conFcst: true });
  const kpiCards = useMemo(() => buildKpis(), []);

  return (
    <>
      <GlobalStyles />
      <div className="addiuva-root addiuva-bg addiuva-grain" ref={ref} style={{
        position: "relative", width: "100%", minHeight: "100vh", overflow: "auto",
      }}>
        <TopBar compact={isSmall} />
        {size.width > 0 && (
          <div style={{
            padding: isSmall ? "12px 12px 0" : "16px 18px 0",
            position: "relative", zIndex: 50,
          }}>
            <SlicerBar filters={filters} setFilters={setFilters} />
          </div>
        )}
        {size.width > 0 && (
          <div style={{ position: "relative", zIndex: 1 }}>
            <OperacionesGrid
              kpiCards={kpiCards}
              slaData={SLA_DATA}
              fcrData={FCR_DATA}
              donutData={DONUT_DATA}
              settings={{
                area: "OPERACIONES",
                axisLabel: "Eje · Excelencia Operativa y CX Omnicanal",
                globalOKR: "Optimización OPEX Addiuva · FCR & Satisfacción · Estandarización",
              }}
              dimensions={{ width: size.width, height: Math.max(size.height, 900) }}
              conFcst={filters.conFcst}
            />
          </div>
        )}
      </div>
    </>
  );
}
