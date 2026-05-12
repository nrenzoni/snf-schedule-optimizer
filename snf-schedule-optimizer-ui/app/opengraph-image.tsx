import { ImageResponse } from "next/og";

export const size = {
  width: 1200,
  height: 630,
};

export const contentType = "image/png";

export default function OpenGraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          alignItems: "stretch",
          background: "linear-gradient(135deg, #eef2ff 0%, #ffffff 45%, #e0f2fe 100%)",
          color: "#0f172a",
          display: "flex",
          flexDirection: "column",
          height: "100%",
          justifyContent: "space-between",
          padding: 56,
          width: "100%",
        }}
      >
        <div style={{ display: "flex", fontSize: 28, fontWeight: 700 }}>
          SNF Schedule Optimizer
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          <div style={{ display: "flex", fontSize: 64, fontWeight: 800, lineHeight: 1.05 }}>
            Staffing planning, scenario modeling, and forecast review in one demo.
          </div>
          <div style={{ display: "flex", fontSize: 28, color: "#475569" }}>
            Built for skilled nursing scheduling workflows.
          </div>
        </div>
        <div style={{ display: "flex", gap: 16 }}>
          {[
            "Schedule board",
            "Scenario analyzer",
            "ML forecasts",
          ].map((label) => (
            <div
              key={label}
              style={{
                border: "1px solid rgba(79, 70, 229, 0.18)",
                borderRadius: 999,
                color: "#4338ca",
                display: "flex",
                fontSize: 22,
                fontWeight: 700,
                padding: "12px 18px",
              }}
            >
              {label}
            </div>
          ))}
        </div>
      </div>
    ),
    size,
  );
}
