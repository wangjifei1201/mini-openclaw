import type { Metadata } from 'next'
import { AppProvider } from '@/lib/store'
import './globals.css'

export const metadata: Metadata = {
  title: 'Omin-OpenClaw',
  description: '轻量级、全透明的 AI Agent 系统',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{
          __html: `(function(){var t=localStorage.getItem('theme');if(t==='dark')document.documentElement.classList.add('dark')})()`,
        }} />
      </head>
      <body>
        <AppProvider>
          {children}
        </AppProvider>
      </body>
    </html>
  )
}
