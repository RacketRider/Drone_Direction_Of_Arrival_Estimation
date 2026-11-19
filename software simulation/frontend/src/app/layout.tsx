import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "EC261 — UAV Direction Finding Digital Twin & DSP Simulation Suite",
  description: "Frequency-Hopping-Aware Direction Finding for UAV Telemetry Using Switched-Interferometric SDR Arrays (IIIT Vadodara - ICD)",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#070B12] text-slate-100 min-h-screen antialiased selection:bg-cyan-500 selection:text-slate-950">
        {children}
      </body>
    </html>
  );
}

