// Astro v6 Content Layer API を使用
// 自動生成された記事（Markdown）をコレクションとして管理する
// この設定により、frontmatter（記事の先頭のメタデータ）のバリデーションが自動で行われる
import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

// 記事コレクション: 引越しに関する記事
const articles = defineCollection({
  // glob loader: 指定フォルダ内のMarkdownファイルを自動で読み込む
  loader: glob({ pattern: '**/*.md', base: './src/content/articles' }),
  // schema: frontmatterの型を定義（間違いがあるとビルドエラーになる）
  schema: z.object({
    title: z.string(),                                          // 記事タイトル
    description: z.string(),                                    // 記事の説明
    category: z.enum(['company', 'estimate', 'cost', 'tips']),  // カテゴリ
    tags: z.array(z.string()).default([]),                       // タグ一覧
    publishedAt: z.string(),                                    // 公開日
    updatedAt: z.string().optional(),                           // 更新日（任意）
    draft: z.boolean().default(false),                          // 下書きフラグ
    relatedServices: z.array(z.string()).default([]),            // 関連サービスのID
    articleType: z.enum(['comparison', 'review', 'guide']).default('guide'), // 記事タイプ
  }),
});

// コレクションをエクスポート（Astroが自動で認識する）
export const collections = { articles };
