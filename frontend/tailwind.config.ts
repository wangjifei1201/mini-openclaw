import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // 克莱因蓝
        'klein-blue': '#002FA7',
        // 活力橙
        'vibrant-orange': '#FF6B35',
        // Apple 风格背景色
        'apple-gray': '#fafafa',
        'apple-border': '#e5e5e5',
      },
      backdropBlur: {
        'frosted': '20px',
      },
      boxShadow: {
        'frosted': '0 8px 32px rgba(0, 0, 0, 0.1)',
      },
    },
  },
  plugins: [],
}

export default config
