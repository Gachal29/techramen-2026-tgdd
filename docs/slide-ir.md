# SlideIR の Page 型

`page_to_slideir_page()` の出力と、テストデータの `expected_slideir_page` を書くための資料。
LTooL の SlideIR の仕様から、Page 型に関わる部分を抜き出してまとめた。

| 項目 | 内容 |
|---|---|
| 対象の SlideIR | 0.1 |
| 名前空間 | `https://docs.ltool.io/ns/slide-ir` |

## 1. SlideIR と Page 型

SlideIR（Slide Intermediate Representation）は、LTooL のスライドの内容と構造を独自のタグの XML で表すデータ形式である。

**Page 型は 1 つの要素ではない。** 次の 5 種類のページの直和型で、XML では種類ごとに要素名が変わる。`<Page>` という要素は存在しない。

| `type`（JSON） | XML の要素名 | 使いどころ |
|---|---|---|
| `cover` | `<CoverPage>` | 表紙 |
| `heading` | `<HeadingPage>` | 見出しだけのページ。本文を持たず、見出しを中央に大きく置く |
| `general` | `<GeneralPage>` | 見出しと本文を持つ基本のページ。上に見出し、その下に本文を並べる |
| `body` | `<BodyPage>` | 本文だけのページ。見出しを持たず、本文を並べる |
| `figure` | `<FigurePage>` | 図だけのページ。見出しを持たず、図・メディア 1 つを中央に大きく置く |

ページは、ルート `<SlideIR>` の下の `<PagePool>`（順番を持たないページの集まり）か `<Pickset>`（発表で選んだ順に並べたもの）の子として置かれる。

```xml
<SlideIR xmlns="https://docs.ltool.io/ns/slide-ir" version="0.1">
  <PagePool>
    <CoverPage id="cover">…</CoverPage>
    <GeneralPage id="p1">…</GeneralPage>
  </PagePool>
</SlideIR>
```

## 2. ページの型の境界

どのページも、見出しの有無と本文の中身から、ちょうど 1 つの型に決まるようにする。`CoverPage` だけは構造ではなく役割（LTの題名）で決まる。

型名は、ページが持つ領域（見出し・本文・図）で付ける。`GeneralPage` は見出しと本文を持つ基本の型で、`HeadingPage` はそこから本文を除いたもの、`BodyPage` は見出しを除いたものにあたる。

### 2.1 判定の順番

1. LTの題名を示すページなら `CoverPage`
2. 見出しがあるとき
    - 本文があれば `GeneralPage`
    - 本文がなければ `HeadingPage`
3. 見出しがないとき
    - 本文が図・メディア 1 つだけなら `FigurePage`
    - それ以外なら `BodyPage`
4. 見出しも本文もないページは作らない

### 2.2 型ごとの境界

| 型 | 見出し | 本文 | 項目 | レイアウト |
|---|---|---|---|---|
| `CoverPage` | 題名（必須）・副題 | なし | `title`（必須）・`subtitle` | 題名・副題・発表者を中央に置く |
| `HeadingPage` | あり | なし | `title`（必須） | 見出しを中央に大きく置く |
| `GeneralPage` | あり | 1 つ以上 | `title`（必須）・`blocks`（必須） | 上に見出し、その下に本文を並べる |
| `BodyPage` | なし | 1 つ以上。図・メディア 1 つだけの場合を除く | `blocks`（必須） | 本文を並べる |
| `FigurePage` | なし | 図・メディア 1 つだけ | `figure`（必須） | 図を中央に大きく置く |

- 見出しがあるとは、`title` にインラインが 1 つ以上あること。空白だけの見出しは作らない
- 本文の数は `blocks` の要素の数で数える。ブロックの中身は問わない
- `title`・`subtitle` は RichText（インラインの配列）。見出しの中で改行するときは `break` を使う
- 図・メディアは、SlideIR の Figure にあたる 7 種類（`ImageFigure`・`VideoFigure`・`AudioFigure`・`EmbedFigure`・`FileFigure`・`ChartFigure`・`DiagramFigure`）
- 表（Table）は図・メディアに含めない。見出しのない表だけのページは `BodyPage` にする
- `figure` に置けるのは図・メディアだけ。Cluster・表・文章（TextBlock）は置けない
- `HeadingPage` と `FigurePage` は、どちらも 1 つだけを中央に大きく置く型で、見出し 1 つか図 1 つかで分かれる
- `CoverPage` は PagePool にちょうど 1 つ置き、`id` は `cover` にする。ピックセットは発表で見せた順番の記録で、同じページが何回現れてもよいため、表紙も何回現れてもよい（最後に表紙へ戻った場合など）

### 2.3 テキストから作るときの対応

| 見出しにあたる行 | 箇条書きがある | 箇条書きがない |
|---|---|---|
| テキスト | `GeneralPage` | `HeadingPage` |
| 図・メディア | `BodyPage`（図と箇条書きを並べる） | `FigurePage` |
| 表 | `BodyPage` | `BodyPage` |
| コードブロック | `BodyPage` | `BodyPage` |

### 2.4 確かめ方

境界はすべて JSON Schema（2020-12）で確かめられる。

- `BodyPage` の「図・メディア 1 つだけの場合を除く」は `not` で書く
- `CoverPage` が PagePool にちょうど 1 つであることは、PagePool の `pages` に `contains` と `minContains`・`maxContains`（どちらも 1）で書く

`id` が PagePool の中で一意であることは JSON Schema で確かめられないので、コードで確かめる。

## メモ

### ページの型名の見直し

中身の意味ではなく、レイアウトを表す名前にする。決めた内容は LTooL にも適用する。

| 現在 | 新しい型名 | 状態 |
|---|---|---|
| `CoverPage` | `CoverPage` | 変更なし |
| `ClaimPage` | `HeadingPage` | 決定 |
| `GeneralPage` | `GeneralPage` | 変更なし |
| `InfoPage` | `BodyPage` | 決定 |
| `VisualPage` | `FigurePage` | 決定 |

`HeadingPage` にした理由: 他の型にない性質は「見出しだけで、本文がない」こと。中央に大きく置くのは、見出ししかないことの結果として説明できる。Cosense の変換規則でも、見出しの行は箇条書きが続けば `general` の `title`、続かなければ `claim` の `block` になる。

`GeneralPage` を変えない理由: 見出しと本文を持つ基本の型として扱う。他の型は、`GeneralPage` との違い（本文を除く、見出しを除く、置き方を変えるなど）で名前を付ける。`HeadingPage` は `GeneralPage` から本文を除いたものにあたる。

`BodyPage` にした理由: `GeneralPage` から見出しを除いたもの。`HeadingPage`（見出しだけ）、`GeneralPage`（見出し＋本文）と並べて意味が通る。

`FigurePage` にした理由: 見出しがなく、図・メディア 1 つだけを中央に置く型。SlideIR の Figure とそのまま対応するので、境界を型で書ける。今の変換のコードは `visual` に見出しを付けず、`blocks` は常に 1 つなので、実際の使われ方とも合う。

`HeadingPage` の中身を `title` にした理由: `GeneralPage` から本文を除いたもの、という定義と合う。

`FigurePage` の中身を `figure` にした理由: 図が 1 つだけであることを、データの形で表せる。見出しは `title`、本文は `blocks`、図は `figure` と、領域と項目が 1 対 1 で対応する。

### このプロジェクト（TGDD）で決めたこと

[plans/2026-11-20-first-implementation.md](./plans/2026-11-20-first-implementation.md) の 2 章で決めた。

- 作業メモの記法（Markdown 風）と、見出し・本文・図の対応
- `page_to_slideir_page()` の出力は、名前空間なしの、ページの要素 1 つの XML。`id` は表紙が `cover`、ほかは `p1`・`p2`・…
- `FigurePage` の `figure` は、XML では図・メディアの要素をページの直下に置く（`<figure>` で包まない）。例: `<FigurePage id="p1"><ImageFigure src="…" /></FigurePage>`
- 期待値の検査は `tools/validate_test_data.py`、比較は `tests/helpers.py`

### LTooL に適用するときの作業

- バージョンは 0.1 のまま変える。古い型名のデータとバージョンでは見分けられないので、保存済みのデータは一度に全部移行し、古い型名の XML（書き出したものなど）が外に残っていないか確かめる
- 保存済みの `Slide.page_pool` を書き換えるデータ移行
    - `type` の値: `claim` → `heading`、`info` → `body`、`visual` → `figure`
    - `HeadingPage`: `block`（TextBlock）の段落を `break` でつないで `title` にする
    - `FigurePage`: `blocks` の 1 つ目を `figure` にする
- 保存済みのデータに、2 章の境界に合わないもの（見出し付きの `visual`、表だけの `visual`、本文が空の `general`・`info`、表紙がちょうど 1 つでないものなど）がないか確かめ、移行先の型を決める
- `cosense_convert.py` で、表だけのページを `body` にする（今は `heading.value["type"] == "table"` を `visual` にしている）。旧 LTooL の資料には表がないので、`legacy_import/convert.py` は型名の変更だけ
- 仕様書: `slide-ir.md`・`slide-ir.webidl`・`slide-ir.schema.json`・`sources/cosense.md`（5.2・6.3 の表）・`docs/ui/presentation.md`（種別のバッジ `choices[].kind` とレイアウトの表）
- コード: `slide_ir.py`・`cosense_convert.py`・`legacy_import/convert.py`・フロントエンドの `types.ts`・`utils.ts`・`SlideRenderer.tsx`、それぞれのテスト
