import "./globals.css";
import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "合规问答 — 金融监管合规知识库",
  description:
    "面向证券公司金融创新与场外衍生品业务的法规知识库问答系统。支持产品结构识别、法规检索和合规判断。",
  applicationName: "合规问答",
  keywords: [
    "合规",
    "监管",
    "金融衍生品",
    "场外衍生品",
    "收益互换",
    "场外期权",
    "收益凭证",
    "法规检索",
    "证券公司",
  ],
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="antialiased">{children}</body>
    </html>
  );
}
