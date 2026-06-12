import './globals.css';

import React from 'react';

export const metadata = {
  title: 'REPOWISE - Multi-Agent Repo Explorer',
  description: 'Understand any GitHub repository with multi-agent AI analysis',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="m-0 p-0">{children}</body>
    </html>
  );
}
