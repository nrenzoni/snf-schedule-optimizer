export function reportWebVitals(metric: {
  name: string;
  value: number;
  rating?: string;
}) {
  if (process.env.NODE_ENV !== "production") {
    console.info("[web-vitals]", metric.name, metric.value, metric.rating);
  }
}
