export const DESIGN_TOKENS = {
  colors: {
    dark: {
      bgApp: '#09090b', // Deep Obsidian canvas
      bgSurface: '#121214', // Elevated surface
      bgSubtle: '#18181b', // Subtle interactive surface
      borderSubtle: '#27272a', // Clean 1px slate divider
      borderStrong: '#3f3f46', // High-contrast border
      textPrimary: '#f4f4f5', // High-contrast primary ink
      textSecondary: '#a1a1aa', // Secondary metadata ink
      textMuted: '#71717a', // Subtle label ink
      primaryAccent: '#f4f4f5', // Monochrome accent
      primaryHover: '#ffffff',
    },
    light: {
      bgApp: '#ffffff', // Crisp pure white Paper canvas
      bgSurface: '#f8fafc', // Subtle off-white card surface
      bgSubtle: '#f1f5f9', // Clean interactive hover surface
      borderSubtle: '#e2e8f0', // Crisp slate divider
      borderStrong: '#cbd5e1', // High-contrast border
      textPrimary: '#09090b', // High-contrast deep ink
      textSecondary: '#4b5563', // Secondary metadata ink
      textMuted: '#71717a', // Subtle label ink
      primaryAccent: '#09090b', // Monochrome accent
      primaryHover: '#18181b',
    },
    severity: {
      critical: '#ef4444',
      major: '#f59e0b',
      minor: '#38bdf8',
      warning: '#eab308',
      info: '#06b6d4',
    },
    epistemic: {
      observedFact: {
        dark: { bg: '#18181b', text: '#f4f4f5', border: '#27272a' },
        light: { bg: '#f1f5f9', text: '#09090b', border: '#e2e8f0' },
      },
      modelPrediction: {
        dark: { bg: '#18181b', text: '#f4f4f5', border: '#27272a' },
        light: { bg: '#f1f5f9', text: '#09090b', border: '#e2e8f0' },
      },
      hypothesis: {
        dark: { bg: '#18181b', text: '#f4f4f5', border: '#27272a' },
        light: { bg: '#f1f5f9', text: '#09090b', border: '#e2e8f0' },
      },
      recommendation: {
        dark: { bg: '#18181b', text: '#f4f4f5', border: '#27272a' },
        light: { bg: '#f1f5f9', text: '#09090b', border: '#e2e8f0' },
      },
      humanApproved: {
        dark: { bg: '#18181b', text: '#f4f4f5', border: '#27272a' },
        light: { bg: '#f1f5f9', text: '#09090b', border: '#e2e8f0' },
      },
      confirmedRootCause: {
        dark: { bg: '#18181b', text: '#f4f4f5', border: '#27272a' },
        light: { bg: '#f1f5f9', text: '#09090b', border: '#e2e8f0' },
      },
    },
  },
} as const
