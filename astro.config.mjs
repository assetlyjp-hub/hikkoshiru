// @ts-check
// Astro の設定ファイル
// サイトURL・プラグイン・Markdownの表示設定をここで管理する
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import mdx from '@astrojs/mdx';

// https://astro.build/config
export default defineConfig({
  // 本番サイトのURL（SEO・サイトマップ生成に使う）
  site: 'https://hikkoshiru.com',

  // 使用するプラグイン
  integrations: [
    sitemap(),  // サイトマップ自動生成（Google検索に必要）
    mdx(),      // MDX（Markdownの拡張）サポート
  ],

  // Markdownの表示設定
  markdown: {
    shikiConfig: {
      theme: 'github-light', // コードブロックの見た目
    },
  },
});
