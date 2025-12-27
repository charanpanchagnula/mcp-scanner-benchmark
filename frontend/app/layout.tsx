import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Shield, LayoutDashboard, Trophy } from "lucide-react";
import Link from "next/link";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "MCP Scanner Benchmark",
  description: "Agentic evaluation of MCP scanners",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${inter.className} min-h-screen bg-slate-50 text-slate-900`}>
        <div className="flex flex-col min-h-screen">
          {/* Top Navbar */}
          <header className="sticky top-0 z-30 flex h-16 items-center gap-4 border-b bg-white px-6 shadow-sm">
            <Link href="/" className="flex items-center gap-2 font-bold text-lg text-indigo-600">
              <Shield className="h-6 w-6" />
              <span>MCP Benchmark</span>
            </Link>
          </header>

          <main className="flex-1 p-6 lg:p-10">
            <div className="mx-auto max-w-6xl">
              {children}
            </div>
          </main>
        </div>
      </body>
    </html>
  );
}
