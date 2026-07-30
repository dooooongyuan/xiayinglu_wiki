import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: process.env.SITE_URL || 'https://xylwiki.cc.cd',
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
