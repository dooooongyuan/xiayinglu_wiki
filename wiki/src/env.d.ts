/// <reference types="astro/client" />

interface ImportMetaEnv {
  readonly PUBLIC_REPO_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
