import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ReviewPulse AI — Product Review Analytics",
  description:
    "Paste a product URL and get AI-powered review analysis with pros, cons, and sentiment — in English, Vietnamese, Spanish, or Japanese.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
