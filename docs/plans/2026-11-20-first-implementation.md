# 実装計画書: TGDD の検証を始めるための最初の実装

| 項目 | 内容 |
|---|---|
| 作成日 | 2026-11-20 |
| 目的 | TGDD のサイクル（テストデータの生成 → テスト → 考慮漏れの発見 → 修正）を回し始められる状態にする |
| 参照 | [AGENTS.md](../../AGENTS.md)、[slide-ir.md](../slide-ir.md) |

## 1. 方針

- **テスト対象（`target.py`）は、欠陥のある単純な実装でよい。** 考慮漏れが見つかることが TGDD の出発点なので、最初から網羅しない
- **テストの仕組みは、正しく動く必要がある。** テストが間違っていると、失敗が「考慮漏れ」なのか「テストの誤り」なのか区別できず、検証が成り立たない
- そのため、この計画では作業の大半をテストの仕組み（比較・集計・通知・テストデータの検査）に割き、仕組みそのものにもテストを書く

## 2. この計画で決める仕様

[slide-ir.md](../slide-ir.md) の未決事項を、次のとおり決める。

### 2.1 作業メモの記法（最初の版）

作業メモは Markdown 風のテキストとする。記法を強制する仕組みはなく、下の表にない書き方も入力に現れる。それらをどう扱うかは決めず、TGDD で見つけた考慮漏れとして順に決めていく。

| 作業メモの行 | 扱い |
|---|---|
| `# 文字` | LT の題名。表紙（`CoverPage`）になる |
| `## 文字` | 見出し。ページの始まり |
| `- 文字`（字下げは半角空白 2 つで 1 段） | 箇条書き。直前の見出しのページの本文 |
| `![代替テキスト](URL)` だけの行 | 図（`ImageFigure`） |
| それ以外の文字のある行 | 段落。直前の見出しのページの本文 |
| 空行 | 読み飛ばす |

### 2.2 `text_to_page_grouper(raw_text: str) -> list[str]`

- 作業メモを、ページごとのテキストに分ける。戻り値の各要素は、作業メモの行を改行でつないだもの（前後の空白と空行は除く）
- 期待される分け方: `# ` の行で 1 ページ（表紙）、`## ` の行から次の `## ` の行の前までで 1 ページ。見出しの前に置かれた図だけの行は、それだけで 1 ページ

### 2.3 `page_to_slideir_page(page_text: str, page_id: str) -> str`

- 1 ページ分のテキストを、ページの要素 1 つの XML 文字列にする
- 型は [slide-ir.md](../slide-ir.md) の 2 章の境界で決める
- XML は名前空間を付けない断片とする（例: `<HeadingPage id="p1"><title><Str>まとめ</Str></title></HeadingPage>`）。`<SlideIR>` に入れるときに名前空間を付ける想定で、その処理は今回の対象外
- `FigurePage` は、図・メディアの要素をページの直下に置く（例: `<FigurePage id="p1"><ImageFigure src="…" alt="…" /></FigurePage>`）
- 段落は、1 行を段落 1 つの `<TextBlock>` にして `<blocks>` の直下に置く。箇条書きは `marker="true"` の `<Cluster>` にし、字下げは `<Cluster>` の入れ子で表す
- `id` は呼び出す側が渡す。表紙は `cover`、それ以外は現れた順に `p1`・`p2`・…。`order` は付けない
- インラインの記法（`**太字**`、リンクなど）は最初の版では解析せず、すべて `<Str>` にする。期待値の側は正しく解析した形で書くので、ここは最初から失敗する見込みの箇所になる

### 2.4 最初の実装に、わざと残す欠陥

最初の実装は 2.1 の表のうち、次のものだけに対応する。

- 分割: `## ` の行だけを区切りにする（表紙・見出しの前の図は考慮しない）
- 変換: 見出しと、字下げのない箇条書きだけ（`GeneralPage`・`HeadingPage`）。入れ子の箇条書き・図・段落・インラインの記法は考慮しない

欠陥の一覧は残さない。何が漏れているかは、テストガチャで見つける。

## 3. テストの仕組み

### 3.1 構成

```
target.py                     テスト対象
tests/
├── conftest.py               テストデータの読み込み、結果の集計
├── helpers.py                XML の比較、テストデータの検査
├── test_gacha.py             考慮漏れを見つけるテスト
├── test_regression.py        再発を見つけるテスト（最初は空）
├── test_helpers.py           テストの仕組みそのもののテスト
└── test_data/YYYY-MM-DD-hh.json
tools/
├── validate_test_data.py     テストデータの検査（CI とローカルの両方で使う）
└── notify_discord.py         結果を Discord に通知する
docs/test_data.schema.json
.github/workflows/
├── validate-test-data.yml    claude-* ブランチの検査と自動マージ
└── gacha.yml                 テストガチャの実行（dispatch）と通知
pyproject.toml                依存: pytest・jsonschema（uv で管理）
```

### 3.2 `test_gacha.py`

- 読み込むテストデータは 1 ファイル。環境変数 `TGDD_TEST_DATA` で指定し、指定がなければ `tests/test_data/` の中でファイル名が最も新しいもの
- テストデータ 1 件につき、次の 2 つを別々のテストケースにする（pytest の `parametrize`。ID は `test_data_id`）
    1. `text_to_page_grouper(input_text)` が `expected_page_group` と一致する
    2. `expected_page_group` の各要素を `page_to_slideir_page()` に渡した結果が、`expected_slideir_page` と一致する
- 2 の入力には、1 の実際の結果ではなく期待値を使う。分割の考慮漏れが変換のテストに波及せず、どちらのモジュールの考慮漏れかがわかる
- 2 に渡す `id` は、テストデータの期待値の XML の `id` 属性から取る
- 1 件が失敗しても止めない（pytest の通常の動作）。テスト対象が例外を出した場合も、そのケースの失敗として扱う
- 最後に、結果を `gacha-result.json` に書き出す（`conftest.py` のフックで集計）

```json
{
  "test_data_file": "2026-11-20-09.json",
  "total": 20,
  "failed": [
    { "test_data_id": "a1b2c3d4", "target": "page_to_slideir_page", "message": "…" }
  ]
}
```

### 3.3 比較の方法

- 分割の結果: 文字列の配列の完全一致。各要素は、行末の空白と前後の空行を除いてから比べる
- XML: `xml.etree.ElementTree.canonicalize()` で正規化してから比べる。属性の順序、`<Break/>` と `<Break />` の違い、要素の間の空白は無視する
- 要素の間の空白だけを無視し、`<Str>` の中の文字列の前後の空白は比べる。`canonicalize(strip_text=True)` は後者も取り除いてしまうので使わず、空白だけのテキストノードを取り除く処理を `helpers.py` に書く
- 失敗したときは、期待値と実際の値の差分を表示する

### 3.4 テストデータの検査（`validate_test_data.py`）

テストデータは AI が作るので、期待値が間違っている可能性がある。機械的に確かめられる誤りは、マージの前に弾く。

- [test_data.schema.json](../test_data.schema.json) に合っている
- `test_data_id` がファイルの中で重複していない
- `expected_page_group` と `expected_slideir_page` の要素数が同じ
- `expected_slideir_page` の各要素が、整形式の XML で、ルートが 5 種類のページのどれかで、`id` が付いていて、1 件の中で `id` が重複しない
- ページの中身が [slide-ir.md](../slide-ir.md) の 2.2 の境界に合っている（例: `HeadingPage` は `title` だけ、`FigurePage` は図 1 つだけ）
- ファイル名が `YYYY-MM-DD-hh.json` の形

あわせて `test_data.schema.json` を直す。

- `expected_slideir_page` のパターンを、`<Page>` ではなく 5 種類のページの要素名に合わせる

### 3.5 テストの仕組みのテスト（`test_helpers.py`）

仕組みが正しいことを、手で書いた固定の入力で確かめる。テスト対象の出来には依存させない。

- XML の比較: 属性の順序・空要素の書き方・字下げが違っても一致する。文字列の中の空白、要素の順序、属性の値が違えば一致しない
- テストデータの検査: 3.4 の各項目について、通る例と弾かれる例
- 集計: 失敗するテストデータを含むファイルで実行し、`gacha-result.json` に失敗した `test_data_id` と対象が正しく入る。テスト対象を差し替えて確かめる（常に正しい値を返すもの、常に間違うもの、例外を出すもの）

### 3.6 通知（`notify_discord.py`）

- `gacha-result.json` を読み、失敗が 1 件以上あれば Discord の Webhook に投稿する。内容は、テストデータのファイル名、失敗の件数、失敗した `test_data_id` と対象、Actions の実行結果への URL
- 失敗がなければ投稿しない
- Webhook の URL は、リポジトリの Secrets（`DISCORD_WEBHOOK_URL`）から環境変数で渡す

## 4. GitHub Actions

### 4.1 `validate-test-data.yml`

- `claude-*` ブランチからのプルリクエストで動く
- 変更が `tests/test_data/` へのファイルの追加 1 つだけであることを確かめる（既存のファイルの変更・削除、ほかの場所の変更があれば失敗）
- `validate_test_data.py` を実行する
- どちらも通れば自動でマージする

### 4.2 `gacha.yml`

- `workflow_dispatch` で動く。入力でテストデータのファイル名を指定できる（省略時は最新）
- `test_helpers.py` と `test_regression.py` を実行する。失敗したら、仕組みか過去の修正が壊れているので、テストガチャに進まずに止める
- `test_gacha.py` を実行し、`notify_discord.py` を実行する。テストガチャの失敗ではワークフローを失敗にしない（考慮漏れの発見は正常な結果のため）

### 4.3 `ci.yml`

- `main` への push と、`claude-*` 以外のプルリクエストで動く
- テストガチャ以外のテスト（テストの仕組み、ツール、再発を見つけるテスト）を実行する
- `target.py` やテストの仕組みを直したときに、壊していないことを確かめる

## 5. テストデータの生成（Claude のスケジュールタスク）

- 毎時 00 分に、`tests/test_data/YYYY-MM-DD-hh.json` を 1 つ作り、`claude-YYYY-MM-DD-hh` ブランチに push してプルリクエストを作る
- タスクへの指示には、次を含める
    - 2 章の仕様と [slide-ir.md](../slide-ir.md)、テストデータのスキーマ
    - `target.py` の実装は読まない（実装に合わせた期待値にならないようにする）
    - 過去のテストデータと `test_regression.py` を読み、同じ観点を繰り返さない
    - 記法にない書き方（記号の揺れ、全角の記号、字下げの乱れ、空行の有無など）を入力に混ぜる
    - push の前に `validate_test_data.py` を実行する
- 指示の文面は `docs/test-data-generation.md` に置く

## 6. 作業の順番

| 順 | 作業 | 完了の条件 |
|---|---|---|
| 1 | `pyproject.toml`、`helpers.py`（XML の比較）、`test_helpers.py` | `uv run pytest tests/test_helpers.py` が通る |
| 2 | `test_data.schema.json` の修正、`validate_test_data.py`、そのテスト | 通る例と弾かれる例のテストが通る |
| 3 | 手で書いたテストデータ 1 ファイル（5 件ほど。2.1 の表の各行を含む） | `validate_test_data.py` が通る |
| 4 | `conftest.py`・`test_gacha.py`（集計を含む）、集計のテスト | 差し替えたテスト対象での集計のテストが通る |
| 5 | `target.py` の最初の実装（2.4） | 3 のテストデータで `test_gacha.py` を実行し、一部が通り、一部が失敗する |
| 6 | `notify_discord.py`、`gacha.yml` | dispatch で実行し、Discord に失敗の通知が届く |
| 7 | `validate-test-data.yml` | 正しいテストデータのプルリクエストがマージされ、不正なものが止まる |
| 8 | テストデータの生成の指示、スケジュールタスクの登録 | 毎時、テストデータがマージされる |
| 9 | AGENTS.md・README.md の更新 | テストデータの例とファイル名の書き方が、実装と一致している |

5 の「一部が失敗する」は、TGDD の検証を始められる状態になったことの確認である。全部が通る場合は実装が手厚すぎるか、テストデータが易しすぎる。

## 7. 考慮漏れを見つけたあとの流れ

1. Discord の通知から、失敗したテストデータを確かめる
2. 失敗が考慮漏れか、期待値の誤りかを判断する
    - 期待値の誤りなら、テストデータを直す。同じ誤りを機械的に弾けるなら `validate_test_data.py` に検査を足す
    - 仕様が決まっていない書き方なら、扱いを決めて 2 章に足す
3. 考慮漏れなら `target.py` を直し、そのテストデータを `test_regression.py` に写す
4. 過去のテストデータで `test_gacha.py` を実行し直し、直ったことを確かめる

## 8. リスク

| リスク | 対応 |
|---|---|
| AI が作る期待値が間違っている | 3.4 の検査で形の誤りを弾く。意味の誤り（分け方の解釈の違いなど）は 7 章の 2 で人が判断する |
| 「ユーザーの意図した単位」が入力だけからは決まらず、期待値が揺れる | 2 章の仕様を期待値の根拠にする。仕様にない書き方は、見つけるたびに扱いを決めて仕様に足す |
| 自動マージで、不正なファイルが main に入る | 4.1 で、変更がテストデータの追加 1 つだけであることを確かめる |
| Webhook の URL が漏れる | Secrets に置き、ログに出さない |
