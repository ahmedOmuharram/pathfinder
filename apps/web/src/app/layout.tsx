import type { Metadata } from "next";
import "@/styles/globals.css";

export const metadata: Metadata = {
  title: "PathFinder - VEuPathDB Strategy Builder",
  description: "AI-powered search strategy builder for VEuPathDB",
  icons: {
    icon: "/favicon.svg",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-slate-50 text-slate-900">
        <main className="min-h-screen">{children}</main>
      </body>
    </html>
  );
}
