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
          background: "linear-gradient(135deg, rgb(232 250 239) 0%, rgb(255 255 255) 45%, rgb(244 246 248) 100%)",
          color: "rgb(33 37 41)",
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
          <div style={{ display: "flex", fontSize: 28, color: "rgb(108 117 125)" }}>
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
                border: "1px solid rgba(22, 128, 57, 0.18)",
                borderRadius: 999,
                color: "rgb(22 128 57)",
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
