import type { Metadata } from "next";
import { SiteHeader } from "@/components/SiteHeader";
import "./globals.css";

export const metadata: Metadata = {
  title: "CampusLens AI — визуальный профиль кампуса",
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
    <html lang="ru">
      <body>
        <SiteHeader />
        {children}
      </body>
    </html>
  );
}
