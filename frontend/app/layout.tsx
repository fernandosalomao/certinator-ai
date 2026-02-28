import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "@copilotkit/react-core/v2/styles.css";
import "./globals.css";
import CopilotKitProvider from "./components/CopilotKitProvider";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "CertinatorAI | Microsoft Certification Study Copilot",
  description:
    "Multi-agent AI coach for Microsoft certifications: exam insights, study plans, and practice with feedback.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <CopilotKitProvider>
          <div className="app-shell">{children}</div>
        </CopilotKitProvider>
      </body>
    </html>
  );
}