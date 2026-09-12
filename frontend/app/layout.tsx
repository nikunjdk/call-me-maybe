import type { Metadata, Viewport } from "next";
import { Outfit, Source_Sans_3 } from "next/font/google";
import { AppChrome } from "@/components/AppChrome";
import "./globals.css";

const outfit = Outfit({
  subsets: ["latin"],
  variable: "--font-outfit",
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

export const viewport: Viewport = {
  themeColor: "#5a4d8c",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${outfit.variable} ${sourceSans.variable} min-h-dvh antialiased`}
      >
        <AppChrome>{children}</AppChrome>
      </body>
    </html>
  );
}
