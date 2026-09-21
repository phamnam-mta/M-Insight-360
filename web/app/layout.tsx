import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "M-Insight 360 | MSB",
  description: "Trợ lý AI thẩm định tín dụng MSB",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="vi">
      <body className="font-sans">{children}</body>
    </html>
  );
}
