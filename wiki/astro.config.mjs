import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: process.env.SITE_URL || 'https://xiayinglu-wiki.dongjingyuan282.workers.dev',
  output: 'static',
  devToolbar: {
    enabled: false,
  },
  integrations: [sitemap()],
  build: {
    format: 'directory',
  },
  vite: {
    build: {
      cssMinify: 'lightningcss',
    },
  },
});
