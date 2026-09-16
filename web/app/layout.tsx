import type { Metadata } from "next";
import { JetBrains_Mono, Manrope } from "next/font/google";
import { SiteHeader } from "@/components/SiteHeader";
import "./globals.css";

// Manrope — заголовки и текст, JetBrains Mono — цифры, баллы и таймер.
// Обе с кириллицей: проект русскоязычный.
const manrope = Manrope({
  subsets: ["latin", "cyrillic"],
  variable: "--font-sans",
  display: "swap",
});

const mono = JetBrains_Mono({
  subsets: ["latin", "cyrillic"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "CampusLens AI — как выглядит кампус на самом деле",
  description:
    "Университеты показывают рекламу. CampusLens показывает, как там на самом деле: проверенный визуальный профиль кампуса по названию вуза — с источниками, лицензиями и разбором достоверности.",
  openGraph: {
    title: "CampusLens AI",
    description:
      "Проверенный визуальный профиль кампуса по названию вуза: источники, лицензии, разбор достоверности.",
    type: "website",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru" className={`${manrope.variable} ${mono.variable}`}>
      <body>
        <SiteHeader />
        {children}
      </body>
    </html>
  );
}
