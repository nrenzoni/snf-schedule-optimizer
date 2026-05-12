import type { MetadataRoute } from "next";

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    {
      url: "/",
      changeFrequency: "weekly",
      priority: 1,
    },
    {
      url: "/schedule",
      changeFrequency: "weekly",
      priority: 0.6,
    },
  ];
}
