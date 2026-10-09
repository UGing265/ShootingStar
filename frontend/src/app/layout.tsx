import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'ShootingStar — Nền tảng Nghiên cứu Định lượng',
  description: 'Nền tảng nghiên cứu định lượng dự đoán hướng giá BTC/USDT 30 phút với cam kết minh bạch tuyệt đối về phương pháp.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="vi">
      <body>{children}</body>
    </html>
  );
}
