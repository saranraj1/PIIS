# PIIS UI-1 Design System Specification: NOC Operational Tokens

**Milestone:** UI-1  
**Target:** React 19 + Tailwind CSS v4  
**WCAG Compliance:** 2.1 Level AA Contrast & Keyboard Accessibility  

---

## 1. Overview & Philosophy

The Production Incident Intelligence System (PIIS) Design System is engineered specifically for high-stress telecom Network Operations Center (NOC) environments. Key design principles:

1. **Information Density without Clutter:** Clean borders, mono-spaced data alignments, and clear structural hierarchy.
2. **Epistemic Clarity:** Every assertion, prediction, and recommendation is visually tagged with a deterministic epistemic badge.
3. **No False Certainty:** Visual weights reflect evidentiary backing. Unconfirmed hypotheses and AI predictions are visibly distinct from verified telemetry.
4. **Contrast Accessibility:** High contrast in both dark and light modes, meeting or exceeding WCAG 2.1 AA standards (4.5:1 for normal text, 3:1 for large text and UI components).

---

## 2. Color System & CSS Custom Properties

Design tokens are declared via CSS custom properties in `src/index.css` under `:root` (Light Theme) and `.dark` (Dark Theme):

### 2.1 Theme Palette

| Token Variable | Dark Mode Value | Light Mode Value | Semantic Role |
|---|---|---|---|
| `--bg-canvas` | `#0b1120` (Slate 950) | `#f8fafc` (Slate 50) | Top-level viewport background |
| `--bg-surface` | `#111c30` (Navy Dark) | `#ffffff` (Pure White) | Primary containers, cards, tables |
| `--bg-card` | `#17233d` (Navy Elevated) | `#f1f5f9` (Slate 100) | Secondary panels, rows, inputs |
| `--border-subtle` | `#1e293b` (Slate 800) | `#e2e8f0` (Slate 200) | Default divider and card borders |
| `--border-strong` | `#334155` (Slate 700) | `#cbd5e1` (Slate 300) | Active boundaries, focused inputs |
| `--text-primary` | `#f8fafc` (Slate 50) | `#0f172a` (Slate 900) | Primary headings, critical data |
| `--text-secondary`| `#94a3b8` (Slate 400) | `#475569` (Slate 600) | Body copy, secondary labels |
| `--text-muted` | `#64748b` (Slate 500) | `#64748b` (Slate 500) | Timestamps, metadata, hints |
| `--primary-accent`| `#38bdf8` (Sky 400) | `#0284c7` (Sky 600) | Interactive accents, links, active tab |

### 2.2 Severity Status Colors

| Severity Level | Foreground | Background (Dark) | Background (Light) |
|---|---|---|---|
| **CRITICAL** | `#ef4444` (Red 500) | `rgba(239, 68, 68, 0.15)` | `#fee2e2` (Red 100) |
| **MAJOR** | `#f59e0b` (Amber 500) | `rgba(245, 158, 11, 0.15)` | `#fef3c7` (Amber 100) |
| **MINOR** | `#3b82f6` (Blue 500) | `rgba(59, 130, 246, 0.15)` | `#dbeafe` (Blue 100) |
| **WARNING** | `#eab308` (Yellow 500) | `rgba(234, 179, 8, 0.15)` | `#fef9c3` (Yellow 100) |
| **INFO** | `#06b6d4` (Cyan 500) | `rgba(6, 182, 212, 0.15)` | `#cffafe` (Cyan 100) |

---

## 3. Epistemic Classification Badges

The 6 epistemic badges are defined in `src/components/epistemic/EpistemicBadge.tsx` and styled via custom token variables:

```css
/* Epistemic Badges (Dark Mode Default) */
--tag-fact-bg: rgba(2, 132, 199, 0.15);
--tag-fact-text: #38bdf8;
--tag-fact-border: #0284c7;

--tag-pred-bg: rgba(124, 58, 237, 0.15);
--tag-pred-text: #c084fc;
--tag-pred-border: #7c3aed;

--tag-hypo-bg: rgba(217, 119, 6, 0.15);
--tag-hypo-text: #fbbf24;
--tag-hypo-border: #d97706;

--tag-reco-bg: rgba(5, 150, 105, 0.15);
--tag-reco-text: #34d399;
--tag-reco-border: #059669;

--tag-decision-bg: rgba(8, 145, 178, 0.15);
--tag-decision-text: #22d3ee;
--tag-decision-border: #0891b2;

--tag-rootcause-bg: rgba(225, 29, 72, 0.15);
--tag-rootcause-text: #fb7185;
--tag-rootcause-border: #e11d48;
```

Each badge component carries explicit accessibility attributes:
- `role="status"`
- `aria-label="[CATEGORY]: Definition"`
- Distinct visual glyph (`●`, `◆`, `▲`, `▶`, `✓`, `■`) alongside text to avoid color-only differentiation.

---

## 4. Typography

- **System Sans:** Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif. Used for headings, body copy, descriptions, and button labels.
- **Data Monospace:** ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace. Used for Incident IDs, node names, timestamps, IP addresses, cryptographic hashes, and epistemic tags.

---

## 5. Layout Shell Components

- **StatusBanner (`StatusBanner.tsx`):**
  - Persistent operational safety strip at the top of the viewport.
  - Informs the user of the strictly read-only execution policy.
- **AppHeader (`AppHeader.tsx`):**
  - Top navigation bar featuring the PIIS mark, environment subtitle, theme toggle switch, and user credentials pill.
  - Allows ephemeral token entry via modal without storing tokens to disk.
- **EpistemicLegend (`EpistemicLegend.tsx`):**
  - Persistent horizontal legend strip directly beneath the header reminding operators of the 6 epistemic tiers.
- **AppSidebar (`AppSidebar.tsx`):**
  - Left navigation drawer for desktop and collapsible modal drawer for mobile viewports.
  - Direct routes to all 9 NOC views with active indicator state and system version tags.
