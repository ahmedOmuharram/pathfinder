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
      <body className="h-full overflow-hidden bg-slate-50 text-slate-900">
        <div
          className="h-[125vh] w-[125vw] origin-top-left overflow-hidden"
          style={{ zoom: 0.8 }}
        >
          <main className="h-full">{children}</main>
        </div>
      </body>
    </html>
  );
}
