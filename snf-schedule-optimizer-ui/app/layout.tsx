import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { NuqsAdapter } from "nuqs/adapters/next/app";
import ThemeProvider from "@/components/theme-provider";
import ClientObservability from "@/components/client-observability";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default: "SNF Schedule Optimizer",
    template: "%s | SNF Schedule Optimizer",
  },
  description:
    "Interactive staffing demo for skilled nursing schedule planning, scenario analysis, and forecast review.",
  applicationName: "SNF Schedule Optimizer",
  metadataBase: process.env.NEXT_PUBLIC_SITE_URL
    ? new URL(process.env.NEXT_PUBLIC_SITE_URL)
    : undefined,
  keywords: [
    "snf",
    "scheduling",
    "staffing",
    "optimizer",
    "healthcare demo",
  ],
  openGraph: {
    title: "SNF Schedule Optimizer",
    description:
      "Interactive staffing demo for skilled nursing schedule planning, scenario analysis, and forecast review.",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "SNF Schedule Optimizer",
    description:
      "Interactive staffing demo for skilled nursing schedule planning.",
  },
  icons: {
    icon: "/icon.svg",
    shortcut: "/icon.svg",
    apple: "/icon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <ThemeProvider>
          <NuqsAdapter>
            <ClientObservability />
            {children}
          </NuqsAdapter>
        </ThemeProvider>
      </body>
    </html>
  );
}
