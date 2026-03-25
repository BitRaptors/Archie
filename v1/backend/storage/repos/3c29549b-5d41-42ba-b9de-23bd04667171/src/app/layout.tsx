import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Header from "@/components/Header";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "PinLaunch — AI Landing Page Builder",
  description: "Collect inspiration, connect your repo, generate landing pages with AI",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className={inter.className}>
        <Header />
        <main className="px-4 py-6">{children}</main>
      </body>
    </html>
  );
}
