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
function formatCompact(v) {
  const abs = Math.abs(v);
  if (abs >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${Math.round(v / 1e3)}K`;
  return `${v}`;
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
        <div style={{ display: "flex", flexDirection: "column", gap: 2, flexShrink: 0 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
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
          {data.secondaryLine && (
            <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
              <span style={{
                fontSize: "13px", color: tokens.colors.textSecondary,
                fontWeight: tokens.typography.fontWeight.medium,
              }}>{data.secondaryLine.label}</span>
              <span style={{
                fontSize: "18px", color: tokens.colors.textPrimary,
                fontWeight: tokens.typography.fontWeight.bold,
                fontVariantNumeric: "tabular-nums",
              }}>{data.secondaryLine.value}</span>
            </div>
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

  // x categories configurable: default to month labels, but any array works (e.g. quarters)
  const categories = cfg.categories ?? MONTHS.map((m) => m.label);

  const xScale = useMemo(
    () => d3.scalePoint().domain(categories).range([0, innerWidth]).padding(0.5),
    [innerWidth, categories]
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
      </g>
    </svg>
  );
};

// ==============================
// DonutChart — NEW atom for Estandarización
// ==============================
// Multi-segment palette (used by donut charts with N slices)
const SEGMENT_PALETTE = [
  tokens.colors.bluePurple,  // 0 — dominant (Asistencia)
  tokens.colors.gold,        // 1
  tokens.colors.magenta,     // 2
  tokens.colors.purple,      // 3
];

const DonutChart = ({ data, dimensions, config = {} }) => {
  const cfg = { innerRadiusRatio: 0.62, ...config };
  const gradId = useMemo(() => `donut-c-${Math.random().toString(36).slice(2, 8)}`, []);

  const size = Math.min(dimensions.width, dimensions.height - 56);
  const radius = size / 2;
  const innerR = radius * cfg.innerRadiusRatio;
  const cx = dimensions.width / 2;
  const cy = (dimensions.height - 56) / 2 + 40;

  const total = data.segments.reduce((s, seg) => s + seg.value, 0);
  const pie = d3.pie().value((d) => d.value).sort(null).startAngle(0).endAngle(2 * Math.PI);
  const arcGen = d3.arc().innerRadius(innerR).outerRadius(radius).cornerRadius(3).padAngle(0.02);
  const arcs = pie(data.segments);

  const segColor = (i) => SEGMENT_PALETTE[i % SEGMENT_PALETTE.length];

  return (
    <svg width={dimensions.width} height={dimensions.height} role="img">
      <defs>
        <linearGradient id={gradId} x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor={tokens.colors.bluePurple} />
          <stop offset="100%" stopColor={tokens.colors.purple} />
        </linearGradient>
      </defs>

      {cfg.title && (
        <text x={dimensions.width / 2} y={18} textAnchor="middle"
          fontFamily={tokens.typography.fontFamily} fontSize="12px"
          fontWeight={tokens.typography.fontWeight.semibold}
          fill={tokens.colors.textSecondary}
          style={{ textTransform: "uppercase", letterSpacing: "0.12em" }}>{cfg.title}</text>
      )}
      {cfg.subtitle && (
        <text x={dimensions.width / 2} y={34} textAnchor="middle"
          fontFamily={tokens.typography.fontFamily} fontSize="9px"
          fontWeight={tokens.typography.fontWeight.medium}
          fill={tokens.colors.textTertiary}
          style={{ letterSpacing: "0.06em" }}>{cfg.subtitle}</text>
      )}

      <g transform={`translate(${cx},${cy})`}>
        {arcs.map((a, i) => (
          <path key={i} className="d3-arc" d={arcGen(a)}
            fill={i === 0 ? `url(#${gradId})` : segColor(i)}
            opacity={i === 0 ? 1 : 0.7} />
        ))}
        {/* Center: dominant segment */}
        <text textAnchor="middle" dy="-2"
          fontFamily={tokens.typography.fontFamily} fontSize="28px" fontWeight="700"
          fill={tokens.colors.textPrimary} className="kpi-value-bright">
          {formatPct(data.segments[0].value / total, 0)}
        </text>
        <text textAnchor="middle" dy="18"
          fontFamily={tokens.typography.fontFamily} fontSize="9px" fontWeight="600"
          fill={tokens.colors.textTertiary}
          style={{ textTransform: "uppercase", letterSpacing: "0.1em" }}>
          {data.centerLabel}
        </text>
      </g>

      {/* Legend — wraps for up to 4 segments */}
      <g transform={`translate(${dimensions.width / 2}, ${dimensions.height - 12})`}>
        {data.segments.map((seg, i) => {
          const spacing = Math.min(110, (dimensions.width - 20) / data.segments.length);
          const xPos = (i - (data.segments.length - 1) / 2) * spacing;
          return (
            <g key={i} transform={`translate(${xPos}, 0)`}>
              <rect x={-spacing / 2 + 4} y={-8} width={9} height={9} rx={2}
                fill={segColor(i)} opacity={i === 0 ? 1 : 0.7} />
              <text x={-spacing / 2 + 17} y={0} fontFamily={tokens.typography.fontFamily} fontSize="9px"
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
// GroupedBarChart — NEW atom: multiple series side-by-side per month
// (Crecimiento en las 3 Verticales: Asist / Log y Cons / Tecn)
// ==============================
const GroupedBarChart = ({ data, dimensions, config = {}, margin = { top: 44, right: 20, bottom: 42, left: 52 } }) => {
  const cfg = { showGridlines: true, ...config };
  const xAxisRef = useRef(null);
  const yAxisRef = useRef(null);

  const innerWidth = dimensions.width - margin.left - margin.right;
  const innerHeight = dimensions.height - margin.top - margin.bottom;

  const categories = data.categories;          // e.g. month labels
  const series = data.series;                   // [{ name, color, values: [...] }]

  const x0 = useMemo(
    () => d3.scaleBand().domain(categories).range([0, innerWidth]).paddingInner(0.25),
    [categories, innerWidth]
  );
  const x1 = useMemo(
    () => d3.scaleBand().domain(series.map((s) => s.name)).range([0, x0.bandwidth()]).padding(0.08),
    [series, x0]
  );
  const yMax = useMemo(
    () => d3.max(series.flatMap((s) => s.values)) * 1.15,
    [series]
  );
  const yScale = useMemo(
    () => d3.scaleLinear().domain([0, yMax]).range([innerHeight, 0]).nice(),
    [yMax, innerHeight]
  );

  useEffect(() => {
    if (!xAxisRef.current || !yAxisRef.current) return;
    const xAxis = d3.axisBottom(x0).tickSize(0).tickPadding(10);
    const yAxis = d3.axisLeft(yScale).ticks(6).tickFormat((v) => formatCompact(+v))
      .tickSize(cfg.showGridlines ? -innerWidth : 0).tickPadding(10);
    d3.select(xAxisRef.current).call(xAxis)
      .call((g) => g.select(".domain").remove())
      .call((g) => g.selectAll("text").attr("font-family", tokens.typography.fontFamily)
        .attr("font-size", "9px").attr("font-weight", "500").attr("fill", tokens.colors.chartAxis));
    d3.select(yAxisRef.current).call(yAxis)
      .call((g) => g.select(".domain").remove())
      .call((g) => g.selectAll(".tick line").attr("stroke", tokens.colors.chartGrid).attr("stroke-dasharray", "2,3"))
      .call((g) => g.selectAll("text").attr("font-family", tokens.typography.fontFamily)
        .attr("font-size", "9px").attr("font-weight", "500").attr("fill", tokens.colors.chartAxis));
  }, [x0, yScale, innerWidth, cfg.showGridlines]);

  return (
    <svg width={dimensions.width} height={dimensions.height} role="img">
      {cfg.title && (
        <text x={dimensions.width / 2} y={22} textAnchor="middle"
          fontFamily={tokens.typography.fontFamily} fontSize="12px"
          fontWeight={tokens.typography.fontWeight.semibold}
          fill={tokens.colors.textSecondary}
          style={{ textTransform: "uppercase", letterSpacing: "0.12em" }}>{cfg.title}</text>
      )}

      <g transform={`translate(${margin.left},${margin.top})`}>
        <g ref={yAxisRef} />
        <g ref={xAxisRef} transform={`translate(0,${innerHeight})`} />

        {categories.map((cat, ci) => (
          <g key={cat} transform={`translate(${x0(cat)},0)`}>
            {series.map((s) => (
              <rect key={s.name} className="d3-bar"
                x={x1(s.name)} y={yScale(s.values[ci])}
                width={x1.bandwidth()} height={Math.max(0, innerHeight - yScale(s.values[ci]))}
                rx={2} ry={2} fill={s.color} />
            ))}
          </g>
        ))}

        {/* Optional horizontal reference line (e.g. Expuestos) */}
        {cfg.referenceLine != null && (
          <g>
            <line x1={0} x2={innerWidth} y1={yScale(cfg.referenceLine.value)} y2={yScale(cfg.referenceLine.value)}
              stroke={tokens.colors.gold} strokeWidth={1.5} strokeDasharray="5,4" opacity={0.7} />
            <text x={innerWidth} y={yScale(cfg.referenceLine.value) - 6} textAnchor="end"
              fontFamily={tokens.typography.fontFamily} fontSize="9px" fontWeight="700"
              fill={tokens.colors.gold} opacity={0.9}>
              {cfg.referenceLine.label} {formatCompact(cfg.referenceLine.value)}
            </text>
          </g>
        )}
      </g>

      {/* Legend */}
      <g transform={`translate(${margin.left}, ${dimensions.height - 12})`}>
        {series.map((s, i) => {
          const spacing = Math.min(130, innerWidth / series.length);
          return (
            <g key={s.name} transform={`translate(${i * spacing}, 0)`}>
              <rect x={0} y={-8} width={9} height={9} rx={2} fill={s.color} />
              <text x={14} y={0} fontFamily={tokens.typography.fontFamily} fontSize="9px"
                fontWeight="500" fill={tokens.colors.textSecondary}>{s.name}</text>
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
// GRID — Tecnología layout (6 cards + 2 charts)
// ==============================
const TecnologiaGrid = ({ kpiCards, disponibilidadData, disponibilidadCats, cicloData, settings, dimensions }) => {
  const bp = getBreakpoint(dimensions.width);
  const isWide = bp === "wide";
  const isMobile = bp === "mobile";
  const isTablet = bp === "tablet";
  const isDesktop = bp === "desktop";

  const cols = isWide ? 12 : isDesktop ? 4 : isTablet ? 2 : 1;
  const gap = isMobile ? 10 : isTablet ? 12 : 14;
  const cardSpan = isWide ? "span 4" : "span 1";   // 3 per row on wide
  const chartMinH = isMobile ? 240 : 280;

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

      {/* 6 KPI cards — each spans 4 of 12 = 3 per row on wide (2 rows of 3) */}
      {kpiCards.map((card) => (
        <div key={card.id} style={{ gridColumn: cardSpan, height: "100%" }}>
          <KPICard data={card} hideStatus={isMobile} />
        </div>
      ))}

      {/* 2 charts — half width each */}
      <ChartSlot minHeight={chartMinH} gridColumn={isWide ? "span 6" : `span ${cols}`}>
        {(dims) => (
          <LineChart data={disponibilidadData} dimensions={dims}
            config={{ title: "Disponibilidad Plataforma (%) — Meta 99.5%",
              yAxisUnit: "Porcentaje (%)", categories: disponibilidadCats,
              yMin: 98, yMax: 100 }} />
        )}
      </ChartSlot>

      <ChartSlot minHeight={chartMinH} gridColumn={isWide ? "span 6" : `span ${cols}`}>
        {(dims) => (
          <GroupedBarChart data={cicloData} dimensions={dims}
            config={{ title: "Ciclo de Desarrollo (días) — Meta: −40%" }} />
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
// MOCK DATA — Tecnología, IA & Automatización KPIs
// ==============================
const buildKpis = () => [
  {
    id: "AGENTE_SOPHI",
    title: "Agente Digital Sophi",
    value: null, pendingLabel: "En Progreso",
    subtitle: "Soluciones automatizadas en producción",
    target: { text: "Go-Live Q4", periodLabel: "2026", extra: "▲ Fase liberación próxima" },
    okrLabel: "Automatización procesos", status: "on-track",
  },
  {
    id: "REDUCCION_CICLO",
    title: "Reducción Ciclo Desarrollo",
    value: null, pendingLabel: "−40% · actual?",
    subtitle: "% reducción tiempo vs baseline",
    target: { text: "−40% objetivo | Cumplimiento", periodLabel: "2026", extra: "▲ Progresando" },
    okrLabel: "Automatización IA", status: "on-track",
  },
  {
    id: "DISPONIBILIDAD",
    title: "Disponibilidad Plataforma",
    value: 0.991, displayValue: "99.1%",
    subtitle: "% Uptime servicios y ambientes",
    target: { text: "≥ 99.5%", periodLabel: "2027", extra: "▶ +0.4pp" },
    okrLabel: "Aseguramiento disponibilidad", status: "on-track",
  },
  {
    id: "LATENCIA",
    title: "Latencia de los Servicios",
    value: 20, displayValue: "20ms",
    valuePeriodLabel: "(milisegundos)",
    subtitle: "Red | Aplicativo | Arquitectura | Infraestructura | Datos",
    target: { text: "0.9%", periodLabel: "Diario", extra: "▲" },
    okrLabel: "Automatización procesos", status: "on-track",
  },
  {
    id: "COSTO_DESARROLLO",
    title: "Costo de Desarrollo Ikatech vs Mercado",
    value: -0.62, displayValue: "−62%",
    subtitle: "Rate 30 USD Ikatech vs 80 USD promedio Europa–USA",
    target: { text: "30–35 USD rate x hora | Acelerador", periodLabel: "", extra: "▲ Optimiza budget IT" },
    okrLabel: "Automatización IA", status: "on-track",
  },
  {
    id: "ADOPCION_TEC",
    title: "Adopción Tecnológica (Global y País)",
    value: null, pendingLabel: "TBD",
    subtitle: "Usabilidad = Proveedores Activos / Proveedores Registrados",
    target: { text: "≥ 99.5%", periodLabel: "2027", extra: "▶ +0.4pp" },
    okrLabel: "Aseguramiento disponibilidad", status: "on-track",
  },
];

// Disponibilidad Plataforma (%) — line, quarterly Q1'26 → Q1'27
const DISPONIBILIDAD_DATA = {
  targetLine: 99.5,
  series: [
    { label: "Q1'26", value: 99.0 }, { label: "Q2'26", value: 99.0 },
    { label: "Q3'26", value: 99.1 }, { label: "Q4'26", value: 99.1 },
    { label: "Q1'27", value: 99.2 },
  ],
};
const DISPONIBILIDAD_CATS = ["Q1'26", "Q2'26", "Q3'26", "Q4'26", "Q1'27"];

// Ciclo de Desarrollo (días) — descending bars, Baseline → Q1'26
const CICLO_DATA = {
  categories: ["Baseline", "Q1'26", "Q2'26", "Q3'26", "Q4'26", "Q1'27"],
  series: [
    { name: "Días ciclo", color: tokens.colors.bluePurple,
      values: [45, 43, 40, 38, 35, 32] },
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
            <TecnologiaGrid
              kpiCards={kpiCards}
              disponibilidadData={DISPONIBILIDAD_DATA}
              disponibilidadCats={DISPONIBILIDAD_CATS}
              cicloData={CICLO_DATA}
              settings={{
                area: "TECNOLOGÍA, IA & AUTOMATIZACIÓN",
                axisLabel: "Eje · Desarrollo Digital · IA · Disponibilidad",
                globalOKR: "Automatización procesos · Automatización IA · Aseguramiento disponibilidad",
              }}
              dimensions={{ width: size.width, height: Math.max(size.height, 900) }}
            />
          </div>
        )}
      </div>
    </>
  );
}
