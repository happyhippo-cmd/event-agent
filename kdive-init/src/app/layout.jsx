import './globals.css';
import { KdiveProvider } from '@/store/KdiveContext';

export const metadata = {
  title: 'K-Dive',
  description: 'Dive into Korea through K-Pop',
};

export default function RootLayout({ children }) {
  return (
    <html lang="ko">
      <head>
        <link rel="preconnect" href="https://open.spotify.com" />
        <link rel="preconnect" href="https://i.scdn.co" />
        <link rel="dns-prefetch" href="https://open.spotify.com" />
        <link rel="dns-prefetch" href="https://i.scdn.co" />
        <link
          href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=Pretendard:wght@300;400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <KdiveProvider>{children}</KdiveProvider>
      </body>
    </html>
  );
}
