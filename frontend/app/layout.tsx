import type { Metadata } from "next";
import { Newsreader, Source_Sans_3 } from "next/font/google";
import { AppChrome } from "@/components/AppChrome";
import "./globals.css";

const newsreader = Newsreader({
  subsets: ["latin"],
  variable: "--font-newsreader",
  display: "swap",
});

const sourceSans = Source_Sans_3({
  subsets: ["latin"],
  variable: "--font-source",
  display: "swap",
});

export const metadata: Metadata = {
  title: "CallMeMaybe",
  description:
    "An AI agent that makes the phone calls you've been putting off, and hands you the phone only when a human decision is required.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${newsreader.variable} ${sourceSans.variable} min-h-screen bg-canvas antialiased`}
      >
        <AppChrome>{children}</AppChrome>
      </body>
    </html>
  );
}
