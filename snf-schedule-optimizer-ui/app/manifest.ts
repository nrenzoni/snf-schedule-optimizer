import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "SNF Schedule Optimizer",
    short_name: "SNF Optimizer",
    description:
      "Interactive staffing demo for skilled nursing schedule planning.",
    start_url: "/",
    display: "standalone",
    background_color: "rgb(244 246 248)",
    theme_color: "rgb(22 128 57)",
    icons: [
      {
        src: "/icon.svg",
        sizes: "any",
        type: "image/svg+xml",
      },
    ],
  };
}
