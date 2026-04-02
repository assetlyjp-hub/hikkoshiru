"""
ヒッコシル 記事自動生成スクリプト
================================
Claude API を使って、keywords.json のパターンから引越し関連の記事を自動生成する。

使い方:
  pip install anthropic
  export ANTHROPIC_API_KEY="your-api-key"
  python scripts/generate-articles.py --type route --limit 2

オプション:
  --type    : 記事タイプ (route / timing / household / company_review / route_household)
  --limit   : 一度に生成する記事数（API料金を抑えるため、デフォルト2）
  --dry-run : 記事は生成せず、生成予定のキーワードだけ表示
"""

import anthropic
import json
import os
import sys
import argparse
from pathlib import Path
from datetime import date

# === パス設定 ===
# このスクリプトの場所から相対パスで各ファイルを参照
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_DIR = PROJECT_DIR / "src" / "data"
ARTICLES_DIR = PROJECT_DIR / "src" / "content" / "articles"

# === データ読み込み ===
def load_json(filename):
    """JSONファイルを読み込んで辞書として返す"""
    with open(DATA_DIR / filename, "r", encoding="utf-8") as f:
        return json.load(f)

# === 引越し会社データを名前で引けるようにする ===
def build_company_lookup(companies_data):
    """会社IDをキーにした辞書を作る"""
    return {c["id"]: c for c in companies_data["companies"]}

# === 記事生成プロンプト ===
# 記事タイプごとにプロンプトテンプレートを定義

PROMPTS = {
    "route": """
あなたは引越しの専門ライターです。以下のルートの引越し費用・おすすめ業者を紹介する記事を書いてください。

## ルート: {from_city}から{to_city}への引越し

## 利用可能な引越し会社データ
{all_companies_info}

## 記事の要件
- 記事タイトル: 「{from_city}から{to_city}の引越し費用の相場は？おすすめ業者も紹介」
- 2,000〜3,000文字程度
- 一人暮らし・二人暮らし・家族別の費用相場を掲載
- おすすめの引越し会社を3社紹介
- 費用を安くするコツを3つ以上
- ですます調で親しみやすく

## 出力形式
Markdownのみ。frontmatter（---で囲まれた部分）は不要。記事本文のみ出力してください。
""",

    "timing": """
あなたは引越しの専門ライターです。以下の時期の引越し料金について記事を書いてください。

## テーマ: {month}の引越し費用・注意点

## 記事の要件
- 記事タイトル: 「{month}の引越し費用はいくら？相場と安くするコツ」
- 2,000〜3,000文字程度
- その月の繁忙度と料金傾向
- 一人暮らし・家族別の料金相場
- その月特有の注意点（天候、イベントなど）
- 費用を安くするためのアドバイス
- ですます調で親しみやすく

## 出力形式
Markdownのみ。frontmatter（---で囲まれた部分）は不要。記事本文のみ出力してください。
""",

    "household": """
あなたは引越しの専門ライターです。以下の世帯タイプの引越しガイドを書いてください。

## テーマ: {household_type}の引越しガイド

## 利用可能な引越し会社データ
{all_companies_info}

## 記事の要件
- 記事タイトル: 「{household_type}の引越し費用と業者の選び方【完全ガイド】」
- 2,500〜3,500文字程度
- 距離別の費用相場表
- おすすめの引越し会社・プランを紹介
- 荷造りのコツ・注意点
- 費用を安くするためのアドバイス
- ですます調で親しみやすく

## 出力形式
Markdownのみ。frontmatter（---で囲まれた部分）は不要。記事本文のみ出力してください。
""",

    "company_review": """
あなたは引越しの専門ライターです。以下の引越し会社のレビュー記事を書いてください。

## 対象会社
{company_info}

## 記事の要件
- 記事タイトル: 「{company_name}の評判・口コミは？料金・サービスを本音レビュー」
- 2,500〜3,500文字程度
- メリット5つ、デメリット3〜4つを具体的に
- 料金プランの詳細比較表
- 「向いている人」「向いていない人」を明確に
- 他社との簡単な比較
- 最後にまとめを入れる
- ですます調で親しみやすく

## 出力形式
Markdownのみ。frontmatter（---で囲まれた部分）は不要。記事本文のみ出力してください。
""",

    "route_household": """
あなたは引越しの専門ライターです。以下の条件の引越し費用について記事を書いてください。

## テーマ: {from_city}から{to_city}への{household_type}の引越し

## 利用可能な引越し会社データ
{all_companies_info}

## 記事の要件
- 記事タイトル: 「{from_city}から{to_city}へ{household_type}の引越し費用と業者おすすめ」
- 2,000〜3,000文字程度
- そのルート×世帯に特化した料金相場
- おすすめの引越し会社とプランを紹介
- 費用を安くするコツ
- ですます調で親しみやすく

## 出力形式
Markdownのみ。frontmatter（---で囲まれた部分）は不要。記事本文のみ出力してください。
""",
}

# === frontmatter 生成 ===
def make_frontmatter(title, description, category, tags, related_services, article_type):
    """記事のfrontmatter（YAML）を生成する"""
    today = date.today().isoformat()
    tags_str = json.dumps(tags, ensure_ascii=False)
    services_str = json.dumps(related_services, ensure_ascii=False)
    return f"""---
title: "{title}"
description: "{description}"
category: "{category}"
tags: {tags_str}
publishedAt: "{today}"
relatedServices: {services_str}
articleType: "{article_type}"
---

"""

# === 記事生成メイン処理 ===
def generate_article(client, prompt, model="claude-sonnet-4-6"):
    """Claude API を呼び出して記事を生成する"""
    message = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    return message.content[0].text

def generate_route(client, route, companies_data):
    """ルート別引越し記事を生成する"""
    prompt = PROMPTS["route"].format(
        from_city=route["from"],
        to_city=route["to"],
        all_companies_info=json.dumps(companies_data["companies"], ensure_ascii=False, indent=2),
    )
    body = generate_article(client, prompt)

    title = f"{route['from']}から{route['to']}の引越し費用の相場は？おすすめ業者も紹介"
    desc = f"{route['from']}から{route['to']}への引越し費用を一人暮らし・家族別に解説。おすすめの引越し業者も紹介。"
    fm = make_frontmatter(title, desc, "cost",
        [route["from"], route["to"], "引越し費用", "相場"],
        [], "guide")

    filepath = ARTICLES_DIR / f"route-{route['slug']}.md"
    return filepath, fm + body

def generate_timing(client, timing):
    """時期別引越し記事を生成する"""
    prompt = PROMPTS["timing"].format(month=timing["label"])
    body = generate_article(client, prompt)

    title = f"{timing['label']}の引越し費用はいくら？相場と安くするコツ"
    desc = f"{timing['label']}の引越し料金の相場を解説。繁忙度や注意点、費用を安くする方法も紹介。"
    fm = make_frontmatter(title, desc, "cost",
        [timing["label"], "引越し費用", "時期"],
        [], "guide")

    filepath = ARTICLES_DIR / f"moving-in-{timing['slug']}.md"
    return filepath, fm + body

def generate_household(client, household, companies_data):
    """世帯別引越しガイド記事を生成する"""
    prompt = PROMPTS["household"].format(
        household_type=household["label"],
        all_companies_info=json.dumps(companies_data["companies"], ensure_ascii=False, indent=2),
    )
    body = generate_article(client, prompt)

    title = f"{household['label']}の引越し費用と業者の選び方【完全ガイド】"
    desc = f"{household['label']}の引越し費用の相場とおすすめの業者・プランを解説。"
    fm = make_frontmatter(title, desc, "tips",
        [household["label"], "引越し費用", "業者選び"],
        [], "guide")

    filepath = ARTICLES_DIR / f"moving-{household['slug']}-guide.md"
    return filepath, fm + body

def generate_company_review(client, company_id, companies):
    """引越し会社のレビュー記事を生成する"""
    c = companies[company_id]
    prompt = PROMPTS["company_review"].format(
        company_name=c["name"],
        company_info=json.dumps(c, ensure_ascii=False, indent=2),
    )
    body = generate_article(client, prompt)

    title = f"{c['name']}の評判・口コミは？料金・サービスを本音レビュー"
    desc = f"{c['name']}のメリット・デメリットを正直にレビュー。料金プランや向いている人がわかります。"
    fm = make_frontmatter(title, desc, "company",
        [c["name"], "評判", "口コミ", "レビュー"],
        [company_id], "review")

    filepath = ARTICLES_DIR / f"{company_id}-review.md"
    return filepath, fm + body

def generate_route_household(client, combo, companies_data):
    """ルート×世帯の掛け合わせ記事を生成する"""
    prompt = PROMPTS["route_household"].format(
        from_city=combo["from"],
        to_city=combo["to"],
        household_type=combo["household"],
        all_companies_info=json.dumps(companies_data["companies"], ensure_ascii=False, indent=2),
    )
    body = generate_article(client, prompt)

    title = f"{combo['from']}から{combo['to']}へ{combo['household']}の引越し費用と業者おすすめ"
    desc = f"{combo['from']}から{combo['to']}への{combo['household']}の引越し費用と、おすすめ業者を紹介。"
    fm = make_frontmatter(title, desc, "cost",
        [combo["from"], combo["to"], combo["household"], "引越し費用"],
        [], "guide")

    filepath = ARTICLES_DIR / f"route-{combo['slug']}.md"
    return filepath, fm + body

# === メイン ===
def main():
    parser = argparse.ArgumentParser(description="ヒッコシル 記事自動生成")
    parser.add_argument("--type", required=True,
        choices=["route", "timing", "household", "company_review", "route_household"],
        help="生成する記事タイプ")
    parser.add_argument("--limit", type=int, default=2, help="生成する記事数（デフォルト2）")
    parser.add_argument("--dry-run", action="store_true", help="生成せずキーワードだけ表示")
    args = parser.parse_args()

    # データ読み込み
    companies_data = load_json("companies.json")
    keywords_data = load_json("keywords.json")
    companies = build_company_lookup(companies_data)

    # 生成タスクのリストを作る（既に記事がある場合はスキップ）
    tasks = []

    if args.type == "route":
        for route in keywords_data["patterns"]["route"]["routes"]:
            filepath = ARTICLES_DIR / f"route-{route['slug']}.md"
            if not filepath.exists():
                tasks.append(("route", route))

    elif args.type == "timing":
        # 月別と時期別を統合
        items = keywords_data["patterns"]["timing"]["months"] + keywords_data["patterns"]["timing"]["seasons"]
        for item in items:
            filepath = ARTICLES_DIR / f"moving-in-{item['slug']}.md"
            if not filepath.exists():
                tasks.append(("timing", item))

    elif args.type == "household":
        for ht in keywords_data["patterns"]["household"]["types"]:
            filepath = ARTICLES_DIR / f"moving-{ht['slug']}-guide.md"
            if not filepath.exists():
                tasks.append(("household", ht))

    elif args.type == "company_review":
        for cid in keywords_data["patterns"]["company_review"]["companies"]:
            filepath = ARTICLES_DIR / f"{cid}-review.md"
            if not filepath.exists():
                tasks.append(("company_review", cid))

    elif args.type == "route_household":
        for combo in keywords_data["patterns"]["route_household"]["combinations"]:
            filepath = ARTICLES_DIR / f"route-{combo['slug']}.md"
            if not filepath.exists():
                tasks.append(("route_household", combo))

    # limitで絞る
    tasks = tasks[:args.limit]

    if not tasks:
        print("生成する記事がありません（すべて生成済み）")
        return

    print(f"=== {len(tasks)}件の記事を生成します ===")
    for i, task in enumerate(tasks):
        print(f"  {i+1}. {task}")

    if args.dry_run:
        print("\n--dry-run モードのため、ここで終了します。")
        return

    # Claude APIクライアント初期化
    client = anthropic.Anthropic()  # ANTHROPIC_API_KEY 環境変数を使用

    # 記事を順番に生成
    for i, task in enumerate(tasks):
        task_type = task[0]
        task_data = task[1]

        print(f"\n[{i+1}/{len(tasks)}] 生成中...")

        if task_type == "route":
            filepath, content = generate_route(client, task_data, companies_data)
        elif task_type == "timing":
            filepath, content = generate_timing(client, task_data)
        elif task_type == "household":
            filepath, content = generate_household(client, task_data, companies_data)
        elif task_type == "company_review":
            filepath, content = generate_company_review(client, task_data, companies)
        elif task_type == "route_household":
            filepath, content = generate_route_household(client, task_data, companies_data)

        # ファイル保存
        filepath.write_text(content, encoding="utf-8")
        print(f"  -> 保存: {filepath.name}")

    print(f"\n=== 完了！{len(tasks)}件の記事を生成しました ===")

if __name__ == "__main__":
    main()
