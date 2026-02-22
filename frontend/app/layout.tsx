import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "@copilotkit/react-ui/styles.css";
import "./globals.css";
import { CopilotKit } from "@copilotkit/react-core";

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
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <CopilotKit
          runtimeUrl="/api/copilotkit"
          agent="my_agent"
          showDevConsole={false}
        >
          <div className="app-shell">{children}</div>
        </CopilotKit>
      </body>
    </html>
  );
}