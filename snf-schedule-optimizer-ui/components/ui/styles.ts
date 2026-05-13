import { cva } from "class-variance-authority";

export const iconButtonVariants = cva(
  "transition-colors",
  {
    variants: {
      shape: {
        default: "rounded-lg p-1",
        full: "rounded-full p-1",
      },
      tone: {
        default: "text-muted-foreground hover:bg-card hover:text-foreground",
        soft: "text-muted-foreground hover:bg-muted hover:text-foreground",
      },
      disabled: {
        true: "cursor-not-allowed opacity-30",
        false: "",
      },
    },
    defaultVariants: {
      shape: "default",
      tone: "default",
      disabled: false,
    },
  },
);

export const segmentedButtonVariants = cva(
  "rounded-lg transition-colors",
  {
    variants: {
      size: {
        sm: "px-3 py-1 text-xs font-bold",
        md: "flex items-center gap-2 px-3 py-1.5 text-sm font-medium",
      },
      active: {
        true: "bg-card text-primary shadow-none",
        false: "text-muted-foreground hover:bg-card hover:text-foreground",
      },
    },
    defaultVariants: {
      size: "md",
      active: false,
    },
  },
);

export const statusBadgeVariants = cva(
  "inline-flex items-center rounded-lg px-2 py-1 text-xs font-medium ring-1",
  {
    variants: {
      tone: {
        neutral: "bg-muted text-muted-foreground ring-border",
        success: "bg-accent text-primary ring-primary/20",
        warning: "bg-amber-50 text-amber-700 ring-amber-300/50",
        danger: "bg-red-50 text-red-700 ring-red-200",
      },
    },
    defaultVariants: {
      tone: "neutral",
    },
  },
);

export const statPanelVariants = cva(
  "rounded-lg border p-3",
  {
    variants: {
      tone: {
        neutral: "border-border bg-card text-foreground",
        success: "border-primary/20 bg-accent text-foreground",
        warning: "border-amber-300/50 bg-amber-50 text-foreground",
        danger: "border-red-200 bg-red-50 text-foreground",
      },
    },
    defaultVariants: {
      tone: "neutral",
    },
  },
);

export const statValueVariants = cva(
  "text-xl font-black",
  {
    variants: {
      tone: {
        neutral: "text-foreground",
        success: "text-primary",
        warning: "text-amber-600",
        danger: "text-rose-600",
      },
    },
    defaultVariants: {
      tone: "neutral",
    },
  },
);

export const selectableCardVariants = cva(
  "rounded-lg border p-3 text-left transition duration-150",
  {
    variants: {
      tone: {
        neutral: "border-border bg-card",
        success: "border-primary/30 bg-accent",
        warning: "border-amber-300/50 bg-amber-50",
        danger: "border-red-200 bg-red-50",
      },
      selected: {
        true: "border-primary bg-accent ring-1 ring-ring",
        false: "",
      },
      interactive: {
        true: "hover:border-primary/60 hover:bg-accent",
        false: "",
      },
    },
    defaultVariants: {
      tone: "neutral",
      selected: false,
      interactive: true,
    },
  },
);

export const toggleTrackVariants = cva(
  "relative inline-flex h-6 w-11 items-center rounded-full transition-colors",
  {
    variants: {
      checked: {
        true: "bg-primary",
        false: "bg-input",
      },
    },
    defaultVariants: {
      checked: false,
    },
  },
);

export const toggleThumbVariants = cva(
  "inline-block h-4 w-4 rounded-full bg-white transition-transform",
  {
    variants: {
      checked: {
        true: "translate-x-6",
        false: "translate-x-1",
      },
    },
    defaultVariants: {
      checked: false,
    },
  },
);

export const metricToneVariants = cva(
  "rounded-lg p-1.5 ring-1",
  {
    variants: {
      tone: {
        success: "bg-accent text-primary ring-primary/20",
        warning: "bg-amber-50 text-amber-700 ring-amber-300/50",
        neutral: "bg-muted text-muted-foreground ring-border",
      },
    },
    defaultVariants: {
      tone: "neutral",
    },
  },
);
