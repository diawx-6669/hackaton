import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CampusLens AI — визуальный профиль кампуса",
  description:
    "Собирает проверенный визуальный профиль кампуса по названию вуза: фото из открытых источников с уликами и ссылками.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
