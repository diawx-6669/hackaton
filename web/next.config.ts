import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // В dev-режиме Next блокирует свои ресурсы при обращении не по localhost:
  // без этого HMR не поднимается, если открыть сайт по IP (телефон в той же сети).
  allowedDevOrigins: ["127.0.0.1", "localhost"],
};

export default nextConfig;
