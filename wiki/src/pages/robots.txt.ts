import type { APIRoute } from 'astro';

export const GET: APIRoute = ({ site }) => {
  const baseUrl = site ?? new URL('https://wiki.example.com');
  const sitemapUrl = new URL('sitemap-index.xml', baseUrl);

  return new Response(`User-agent: *\nAllow: /\n\nSitemap: ${sitemapUrl}\n`, {
    headers: {
      'Content-Type': 'text/plain; charset=utf-8',
    },
  });
};
