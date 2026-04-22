import type { Metadata } from "next";
import { Frank_Ruhl_Libre, Public_Sans } from "next/font/google";
import "./globals.css";
import Providers from "./providers";

// Headlines — Frank Ruhl Libre Light. Never Regular, never Bold per the
// Lighthouse Canton brand guideline (bold looks wrong in this face).
const display = Frank_Ruhl_Libre({
  subsets: ["latin"],
  weight: ["300"],
  display: "swap",
  variable: "--font-display",
});

// Body — Public Sans Light/Regular, with Bold available for sub-headlines + CTAs.
const sans = Public_Sans({
  subsets: ["latin"],
  weight: ["300", "400", "600", "700"],
  display: "swap",
  variable: "--font-sans",
});

export const metadata: Metadata = {
  title: "Lighthouse Canton · Wealth Planning",
  description: "Private wealth advisory console for Lighthouse Canton",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${display.variable} ${sans.variable}`}>
      <body className="font-sans antialiased bg-lc-black text-lc-white selection:bg-lc-red selection:text-lc-white">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
