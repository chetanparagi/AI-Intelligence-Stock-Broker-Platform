import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = { title: 'Zerodha AI Intelligence', description: 'Live market intelligence and portfolio analysis.' };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
