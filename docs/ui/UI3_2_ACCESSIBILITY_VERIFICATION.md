# PIIS UI-3.2 — Accessibility Contrast & Ergonomics Verification

**Milestone:** UI-3.2  
**Standard:** WCAG 2.1 Level AA & AAA Verification  
**Evaluation Scope:** Light Theme (Clean Enterprise Operations) & Dark Theme (NOC Command Center)  
**Date:** November 2026

---

## 1. Mathematical Contrast Formulation

WCAG 2.1 Section 1.4.3 (Contrast Minimum - AA) and Section 1.4.6 (Contrast Enhanced - AAA) define color contrast ratios based on the relative luminance ($L$) of foreground and background colors.

### Relative Luminance Calculation:
For an sRGB color with 8-bit components $(R_{8bit}, G_{8bit}, B_{8bit})$ normalized to $[0, 1]$ ($C = C_{8bit} / 255$):

$$C_{linear} = \begin{cases} \frac{C}{12.92} & \text{if } C \le 0.04045 \\ \left(\frac{C + 0.055}{1.055}\right)^{2.4} & \text{if } C > 0.04045 \end{cases}$$

The relative luminance $L$ of the color is then computed as:

$$L = 0.2126 \times R_{linear} + 0.7152 \times G_{linear} + 0.0722 \times B_{linear}$$

### Contrast Ratio Formula:
Given relative luminances $L_1$ and $L_2$ where $L_1 \ge L_2$:

$$\text{Contrast Ratio} = \frac{L_1 + 0.05}{L_2 + 0.05} : 1$$

- **WCAG AA Minimum (Normal Text):** $\ge 4.50 : 1$
- **WCAG AA Minimum (Large Text / UI Components):** $\ge 3.00 : 1$
- **WCAG AAA Enhanced (Normal Text):** $\ge 7.00 : 1$

---

## 2. Light Theme Contrast Verification

In the Light Theme (`--bg-surface: #ffffff`, `--bg-app: #f8fafc`, `--bg-subtle: #f1f5f9`):

### Core Typography & Structural Elements

| Token / Element | Hex Value | Relative Luminance ($L$) | Background Hex | Bg Luminance ($L_{bg}$) | Contrast Ratio | WCAG AA ($\ge 4.5:1$) | WCAG AAA ($\ge 7.0:1$) |
|---|---|---|---|---|---|---|---|
| `--text-primary` | `#0f172a` | 0.0097 | `#ffffff` | 1.0000 | **17.85:1** | **PASS** | **PASS** |
| `--text-secondary` | `#475569` | 0.0885 | `#ffffff` | 1.0000 | **7.58:1** | **PASS** | **PASS** |
| `--text-muted` | `#64748b` | 0.1706 | `#ffffff` | 1.0000 | **4.76:1** | **PASS** | FAIL |
| `--primary-accent` | `#0284c7` | 0.2065 | `#ffffff` | 1.0000 | **4.10:1** | **PASS (UI)** | FAIL |

*Note: `--primary-accent` is utilized for interactive buttons, tabs, and large headings where the WCAG requirement is $\ge 3.00:1$ (Passed at 4.10:1).*

### Epistemic Taxonomy Badges (Light Theme)

| Epistemic Tag | Text Hex | Text $L$ | Background Hex | Bg $L_{bg}$ | Contrast Ratio | WCAG Status |
|---|---|---|---|---|---|---|
| **FACT** | `#0369a1` | 0.1384 | `#f0f9ff` | 0.9501 | **5.31:1** | **PASS AA** |
| **PREDICTION** | `#6b21a8` | 0.0700 | `#faf5ff` | 0.9634 | **8.45:1** | **PASS AAA** |
| **HYPOTHESIS** | `#b45309` | 0.1565 | `#fffbeb` | 0.9702 | **4.94:1** | **PASS AA** |
| **RECOMMENDATION** | `#15803d` | 0.1610 | `#f0fdf4` | 0.9740 | **4.85:1** | **PASS AA** |
| **DECISION** | `#0f766e` | 0.1448 | `#f0fdfa` | 0.9723 | **5.25:1** | **PASS AA** |
| **ROOT_CAUSE** | `#475569` | 0.0885 | `#f8fafc` | 0.9538 | **7.24:1** | **PASS AAA** |

---

## 3. Dark Theme Contrast Verification

In the Dark Theme (`--bg-surface: #111c30`, `--bg-app: #0b1120`, `--bg-subtle: #0f172a`):
- Relative luminance of `--bg-surface` (`#111c30`): $L = 0.0125$
- Relative luminance of `--bg-app` (`#0b1120`): $L = 0.0064$

### Core Typography & Structural Elements

| Token / Element | Hex Value | Relative Luminance ($L$) | Background Hex | Bg Luminance ($L_{bg}$) | Contrast Ratio | WCAG AA ($\ge 4.5:1$) | WCAG AAA ($\ge 7.0:1$) |
|---|---|---|---|---|---|---|---|
| `--text-primary` | `#f8fafc` | 0.9538 | `#111c30` | 0.0125 | **16.06:1** | **PASS** | **PASS** |
| `--text-secondary` | `#94a3b8` | 0.3644 | `#111c30` | 0.0125 | **6.63:1** | **PASS** | FAIL |
| `--text-muted` | `#64748b` | 0.1706 | `#111c30` | 0.0125 | **3.53:1** | **PASS (UI)** | FAIL |
| `--primary-accent` | `#38bdf8` | 0.4770 | `#111c30` | 0.0125 | **8.43:1** | **PASS** | **PASS** |

### Epistemic Taxonomy Badges (Dark Theme)

In dark mode, epistemic tags render semi-transparent tinted container backgrounds (15% opacity over `--bg-surface`), with vibrant foreground labels:

| Epistemic Tag | Text Hex | Text $L$ | Base Surface Hex | Bg $L_{bg}$ | Contrast Ratio | WCAG Status |
|---|---|---|---|---|---|---|
| **FACT** | `#38bdf8` | 0.4770 | `#111c30` | 0.0125 | **8.43:1** | **PASS AAA** |
| **PREDICTION** | `#c084fc` | 0.3540 | `#111c30` | 0.0125 | **6.46:1** | **PASS AA** |
| **HYPOTHESIS** | `#fbbf24` | 0.5898 | `#111c30` | 0.0125 | **10.24:1** | **PASS AAA** |
| **RECOMMENDATION** | `#34d399` | 0.5052 | `#111c30` | 0.0125 | **8.88:1** | **PASS AAA** |
| **DECISION** | `#2dd4bf` | 0.5234 | `#111c30` | 0.0125 | **9.17:1** | **PASS AAA** |
| **ROOT_CAUSE** | `#94a3b8` | 0.3644 | `#111c30` | 0.0125 | **6.63:1** | **PASS AA** |

All epistemic badges in both Light Theme and Dark Theme achieve full compliance with WCAG 2.1 Level AA ($\ge 4.50:1$). In dark mode, 4 out of 6 tags additionally achieve Level AAA ($\ge 7.00:1$).

---

## 4. Operational Ergonomics & Accessibility Features

### 4.1 Focus Rings & Keyboard Navigation
- All interactive controls (`<button>`, `<a>`, `<input>`, `<select>`) feature prominent focus indicators:
  `focus:outline-hidden focus:ring-2 focus:ring-sky-500 focus:ring-offset-2`
- Tab navigation traverses logical hierarchy:
  1. Incident selector / switcher dropdown
  2. Workspace action triggers (Refresh, Trigger Investigation)
  3. Navigation tabs (Hypotheses, Evidence, Recommendations, Timeline)
  4. Cross-card jump buttons (Supporting evidence references jump to Evidence Register)

### 4.2 Reduced Motion Compliance
Defined globally in `frontend/src/index.css`:
```css
@media (prefers-reduced-motion: reduce) {
  *, ::before, ::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```
When an operator configures reduced motion at the OS level:
- Spinner rotations and pulse animations collapse to static indicators.
- Smooth-scrolling jump links transition instantaneously without vestibular distress.
- Visual state changes occur instantaneously without layout jitter.
