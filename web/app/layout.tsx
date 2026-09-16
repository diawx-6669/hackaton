import type { Metadata } from "next";
import { Inter, JetBrains_Mono, Unbounded } from "next/font/google";
import { CosmicScene } from "@/components/CosmicScene";
import { SiteHeader } from "@/components/SiteHeader";
import "./globals.css";

// Unbounded — крупные заголовки (геометрия под космическую тему),
// Inter — интерфейс, JetBrains Mono — цифры, баллы и таймер.
// Все три с кириллицей.
const sans = Inter({
  subsets: ["latin", "cyrillic"],
  variable: "--font-sans",
  display: "swap",
});

const display = Unbounded({
  subsets: ["latin", "cyrillic"],
  weight: ["400", "500", "600"],
  variable: "--font-display",
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
    <html
      lang="ru"
      className={`${sans.variable} ${display.variable} ${mono.variable}`}
    >
      <body>
        <CosmicScene />
        <SiteHeader />
        {children}
      </body>
    </html>
  );
}
