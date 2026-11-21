"""テストの仕組みそのもののテスト

手で書いた固定の入力で確かめる。テスト対象（target.py）の出来には依存しない
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from helpers import diff_page_groups, diff_xml, normalize_page_text, validate_page_xml, validate_test_data

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((ROOT / "docs" / "test_data.schema.json").read_text(encoding="utf-8"))

sys.path.insert(0, str(ROOT / "tools"))
import validate_test_data as tool  # noqa: E402

# -- 分割の結果の比較 --


def test_page_text_ignores_trailing_spaces_and_outer_blank_lines():
    assert normalize_page_text("\n\n## a  \n- b\t\n\n") == "## a\n- b"


def test_page_text_keeps_indent_and_inner_blank_lines():
    assert normalize_page_text("## a\n\n  - b") == "## a\n\n  - b"


def test_page_groups_equal():
    assert diff_page_groups(["## a\n- b"], ["## a  \n- b\n"]) is None


@pytest.mark.parametrize(
    "actual",
    [
        [],  # ページがない
        ["## a"],  # 中身が違う
        ["## a\n- b", "## c"],  # ページが多い
        ["## a", "- b"],  # 分け方が違う
        ["  ## a\n- b"],  # 行頭の空白が違う
        "## a\n- b",  # 配列ではない
        None,
        [1],
    ],
)
def test_page_groups_differ(actual: Any):
    assert diff_page_groups(["## a\n- b"], actual)


# -- XML の比較 --

EXPECTED = '<BodyPage id="p1"><blocks><TextBlock><Paragraph><Str>a </Str><Break /><Str>b</Str></Paragraph></TextBlock><ImageFigure src="https://x/a.png" alt="z" /></blocks></BodyPage>'


@pytest.mark.parametrize(
    "actual",
    [
        EXPECTED,
        # 属性の順序、空要素の書き方、字下げ、前後の空白
        """
        <BodyPage id="p1">
          <blocks>
            <TextBlock>
              <Paragraph>
                <Str>a </Str>
                <Break/>
                <Str>b</Str>
              </Paragraph>
            </TextBlock>
            <ImageFigure alt="z" src="https://x/a.png"></ImageFigure>
          </blocks>
        </BodyPage>
        """,
        # 引用符と XML 宣言
        "<?xml version='1.0' encoding='UTF-8'?>" + EXPECTED.replace('"', "'"),
    ],
)
def test_xml_equal(actual: str):
    assert diff_xml(EXPECTED, actual) is None


@pytest.mark.parametrize(
    "actual",
    [
        EXPECTED.replace("<Str>a </Str>", "<Str>a</Str>"),  # 文字列の末尾の空白
        EXPECTED.replace("<Str>b</Str>", "<Str> b</Str>"),  # 文字列の先頭の空白
        EXPECTED.replace("<Str>b</Str>", "<Str>B</Str>"),  # 文字列
        EXPECTED.replace('alt="z"', 'alt="y"'),  # 属性の値
        EXPECTED.replace(' alt="z"', ""),  # 属性がない
        EXPECTED.replace('id="p1"', 'id="p1" order="1"'),  # 属性が多い
        EXPECTED.replace("BodyPage", "GeneralPage"),  # 要素名
        EXPECTED.replace("<Break />", ""),  # 要素がない
        EXPECTED.replace("<Str>a </Str><Break />", "<Break /><Str>a </Str>"),  # 要素の順序
        EXPECTED.replace("<BodyPage ", '<BodyPage xmlns="https://docs.ltool.io/ns/slide-ir" '),  # 名前空間
        "<BodyPage",  # 整形式ではない
        "",
        None,  # 文字列ではない
    ],
)
def test_xml_differ(actual: Any):
    assert diff_xml(EXPECTED, actual)


def test_xml_whitespace_only_string_is_compared():
    """空白だけの <Str> は中身として比べる（字下げとして無視しない）"""
    one = "<HeadingPage id='p1'><title><Str> </Str></title></HeadingPage>"
    two = "<HeadingPage id='p1'><title><Str>  </Str></title></HeadingPage>"
    assert diff_xml(one, one) is None
    assert diff_xml(one, two)


# -- ページの XML の検査 --

TITLE = "<title><Str>t</Str></title>"
TEXT = "<TextBlock><Paragraph><Str>a</Str></Paragraph></TextBlock>"
IMAGE = '<ImageFigure src="https://x/a.png" />'

VALID_PAGES = [
    f'<CoverPage id="cover">{TITLE}<subtitle><Str>s</Str></subtitle></CoverPage>',
    f'<HeadingPage id="p1">{TITLE}</HeadingPage>',
    f'<GeneralPage id="p1">{TITLE}<blocks>{TEXT}</blocks><notes>メモ\n2 行目</notes><option>補足</option></GeneralPage>',
    f'<GeneralPage id="p1">{TITLE}<blocks>{IMAGE}</blocks></GeneralPage>',
    f'<BodyPage id="p1"><blocks>{TEXT}</blocks></BodyPage>',
    f'<BodyPage id="p1"><blocks>{IMAGE}{IMAGE}</blocks></BodyPage>',
    f'<BodyPage id="p1"><blocks><Table><TableRow><TableCell header="true">{TEXT}</TableCell></TableRow></Table></blocks></BodyPage>',
    f'<BodyPage id="p1"><blocks><Cluster ordered="true" marker="true">{TEXT}<Cluster marker="true">{IMAGE}</Cluster></Cluster></blocks></BodyPage>',
    f'<FigurePage id="p1">{IMAGE}</FigurePage>',
    '<FigurePage id="p1"><EmbedFigure url="https://www.youtube.com/watch?v=x" provider="youtube" alt="a" /></FigurePage>',
    '<HeadingPage id="p1"><title><Str>a</Str><Strong><Em><Str>b</Str></Em></Strong><Code>c</Code><Break />'
    '<Anchor href="https://x/"><Strong><Str>d</Str></Strong></Anchor><Highlight style="x"><Str>e</Str></Highlight></title></HeadingPage>',
]


@pytest.mark.parametrize("xml", VALID_PAGES)
def test_valid_page(xml: str):
    assert validate_page_xml(xml) == []


INVALID_PAGES = {
    "整形式ではない": "<HeadingPage id='p1'><title>",
    "存在しない要素 <Page>": f'<Page id="p1">{TITLE}</Page>',
    "古い型名": f'<ClaimPage id="p1">{TEXT}</ClaimPage>',
    "名前空間付き": f'<HeadingPage xmlns="https://docs.ltool.io/ns/slide-ir" id="p1">{TITLE}</HeadingPage>',
    "id がない": f"<HeadingPage>{TITLE}</HeadingPage>",
    "id の形": f'<HeadingPage id="p 1">{TITLE}</HeadingPage>',
    "order を持つ": f'<HeadingPage id="p1" order="1">{TITLE}</HeadingPage>',
    "表紙の id が cover ではない": f'<CoverPage id="p1">{TITLE}</CoverPage>',
    "表紙ではないのに cover": f'<HeadingPage id="cover">{TITLE}</HeadingPage>',
    "表紙に本文": f'<CoverPage id="cover">{TITLE}<blocks>{TEXT}</blocks></CoverPage>',
    "HeadingPage に本文": f'<HeadingPage id="p1">{TITLE}<blocks>{TEXT}</blocks></HeadingPage>',
    "HeadingPage に見出しがない": '<HeadingPage id="p1"></HeadingPage>',
    "見出しが空": '<HeadingPage id="p1"><title></title></HeadingPage>',
    "見出しに文字列を直接書く": '<HeadingPage id="p1"><title>t</title></HeadingPage>',
    "GeneralPage に本文がない": f'<GeneralPage id="p1">{TITLE}</GeneralPage>',
    "GeneralPage の本文が空": f'<GeneralPage id="p1">{TITLE}<blocks></blocks></GeneralPage>',
    "GeneralPage に見出しがない": f'<GeneralPage id="p1"><blocks>{TEXT}</blocks></GeneralPage>',
    "子要素の順序": f'<GeneralPage id="p1"><blocks>{TEXT}</blocks>{TITLE}</GeneralPage>',
    "見出しが 2 つ": f'<HeadingPage id="p1">{TITLE}{TITLE}</HeadingPage>',
    "BodyPage に見出し": f'<BodyPage id="p1">{TITLE}<blocks>{TEXT}</blocks></BodyPage>',
    "BodyPage の本文が図 1 つだけ": f'<BodyPage id="p1"><blocks>{IMAGE}</blocks></BodyPage>',
    "BodyPage の本文が空": '<BodyPage id="p1"><blocks /></BodyPage>',
    "FigurePage に図がない": '<FigurePage id="p1"></FigurePage>',
    "FigurePage に図が 2 つ": f'<FigurePage id="p1">{IMAGE}{IMAGE}</FigurePage>',
    "FigurePage に見出し": f'<FigurePage id="p1">{TITLE}{IMAGE}</FigurePage>',
    "FigurePage に文章": f'<FigurePage id="p1">{TEXT}</FigurePage>',
    "FigurePage に blocks": f'<FigurePage id="p1"><blocks>{IMAGE}</blocks></FigurePage>',
    "図に src がない": '<FigurePage id="p1"><ImageFigure alt="a" /></FigurePage>',
    "URL が http・https ではない": '<FigurePage id="p1"><ImageFigure src="javascript:alert(1)" /></FigurePage>',
    "図に知らない属性": '<FigurePage id="p1"><ImageFigure src="https://x/a.png" caption="a" /></FigurePage>',
    "width が数値ではない": '<FigurePage id="p1"><ImageFigure src="https://x/a.png" width="100px" /></FigurePage>',
    "知らないブロック": f'<BodyPage id="p1"><blocks><CodeBlock>x</CodeBlock>{TEXT}</blocks></BodyPage>',
    "blocks にインライン": '<BodyPage id="p1"><blocks><Str>a</Str></blocks></BodyPage>',
    "TextBlock に文字列を直接書く": '<BodyPage id="p1"><blocks><TextBlock>a</TextBlock></blocks></BodyPage>',
    "Paragraph の外にインライン": '<BodyPage id="p1"><blocks><TextBlock><Str>a</Str></TextBlock></blocks></BodyPage>',
    "知らないインライン": '<HeadingPage id="p1"><title><Bold><Str>a</Str></Bold></title></HeadingPage>',
    "Str の中に改行": '<HeadingPage id="p1"><title><Str>a\nb</Str></title></HeadingPage>',
    "Str の中に要素": '<HeadingPage id="p1"><title><Str><Strong>a</Strong></Str></title></HeadingPage>',
    "Anchor の中に Anchor": '<HeadingPage id="p1"><title><Anchor href="https://x/"><Anchor href="https://y/"><Str>a</Str></Anchor></Anchor></title></HeadingPage>',
    "Anchor に href がない": '<HeadingPage id="p1"><title><Anchor><Str>a</Str></Anchor></title></HeadingPage>',
    "marker が true・false ではない": f'<BodyPage id="p1"><blocks><Cluster marker="yes">{TEXT}</Cluster></blocks></BodyPage>',
    "Table の中身": f'<BodyPage id="p1"><blocks><Table><TableCell>{TEXT}</TableCell></Table></blocks></BodyPage>',
}


@pytest.mark.parametrize("xml", INVALID_PAGES.values(), ids=INVALID_PAGES.keys())
def test_invalid_page(xml: str):
    assert validate_page_xml(xml)


# -- テストデータの検査 --


def _case(**overrides: Any) -> dict[str, Any]:
    case = {
        "test_data_id": "a1",
        "input_text": "## t",
        "expected_page_group": ["## t"],
        "expected_slideir_page": [f'<HeadingPage id="p1">{TITLE}</HeadingPage>'],
    }
    return {**case, **overrides}


def test_valid_test_data():
    assert validate_test_data([_case(), _case(test_data_id="a2")], SCHEMA) == []


def test_empty_input_is_valid():
    """空の作業メモ（ページなし）もテストデータにできる"""
    assert validate_test_data([_case(input_text="", expected_page_group=[], expected_slideir_page=[])], SCHEMA) == []


INVALID_TEST_DATA = {
    "配列ではない": _case(),
    "空の配列": [],
    "項目がない": [{key: value for key, value in _case().items() if key != "input_text"}],
    "知らない項目": [_case(note="x")],
    "test_data_id の形": [_case(test_data_id="a 1")],
    "test_data_id の重複": [_case(), _case()],
    "数が違う": [_case(expected_page_group=["## t", "## u"])],
    "空のページ": [_case(expected_page_group=[" \n"])],
    "存在しない要素 <Page>": [_case(expected_slideir_page=[f'<Page id="p1">{TITLE}</Page>'])],
    "ページの中身が境界に合わない": [_case(expected_slideir_page=[f'<GeneralPage id="p1">{TITLE}</GeneralPage>'])],
    "id の重複": [
        _case(
            expected_page_group=["## t", "## t"],
            expected_slideir_page=[f'<HeadingPage id="p1">{TITLE}</HeadingPage>'] * 2,
        )
    ],
}


@pytest.mark.parametrize("data", INVALID_TEST_DATA.values(), ids=INVALID_TEST_DATA.keys())
def test_invalid_test_data(data: Any):
    assert validate_test_data(data, SCHEMA)


def test_tool_checks_file_name(tmp_path: Path):
    good = tmp_path / "2026-11-20-09.json"
    good.write_text(json.dumps([_case()]), encoding="utf-8")
    assert tool.validate_file(good) == []
    assert tool.main([str(good)]) == 0

    for name in ("2026_11_20_09.json", "2026-11-20-24.json", "2026-13-01-00.json", "data.json"):
        bad = tmp_path / name
        bad.write_text(json.dumps([_case()]), encoding="utf-8")
        assert tool.validate_file(bad), name
        assert tool.main([str(bad)]) == 1

    broken = tmp_path / "2026-11-20-10.json"
    broken.write_text("[", encoding="utf-8")
    assert tool.validate_file(broken)


def test_committed_test_data_is_valid():
    """リポジトリにあるテストデータは、すべて検査を通る"""
    files = sorted((ROOT / "tests" / "test_data").glob("*.json"))
    assert files
    for path in files:
        assert tool.validate_file(path) == [], path.name


# -- テストガチャの集計 --
# テスト対象を差し替えて test_gacha.py を別のプロセスで実行し、結果の JSON を確かめる

CASES = [
    _case(test_data_id="one"),
    _case(
        test_data_id="two",
        input_text="## t\n\n## t",
        expected_page_group=["## t", "## t"],
        expected_slideir_page=[f'<HeadingPage id="p1">{TITLE}</HeadingPage>', f'<HeadingPage id="p2">{TITLE}</HeadingPage>'],
    ),
]

FAKE_TARGETS = {
    # 常に正しい値を返す
    "correct": """
def text_to_page_grouper(raw_text):
    return [block for block in raw_text.split("\\n\\n") if block]

def page_to_slideir_page(page_text, page_id):
    return f'<HeadingPage id="{page_id}"><title><Str>t</Str></title></HeadingPage>'
""",
    # 分割だけ間違う
    "wrong_grouper": """
def text_to_page_grouper(raw_text):
    return [raw_text]

def page_to_slideir_page(page_text, page_id):
    return f'<HeadingPage id="{page_id}"><title><Str>t</Str></title></HeadingPage>'
""",
    # 変換だけ、2 ページ目で間違う
    "wrong_second_page": """
def text_to_page_grouper(raw_text):
    return [block for block in raw_text.split("\\n\\n") if block]

def page_to_slideir_page(page_text, page_id):
    title = "t" if page_id == "p1" else "x"
    return f'<HeadingPage id="{page_id}"><title><Str>{title}</Str></title></HeadingPage>'
""",
    # 例外を出す・XML ではないものを返す
    "broken": """
def text_to_page_grouper(raw_text):
    raise RuntimeError("boom")

def page_to_slideir_page(page_text, page_id):
    return "<HeadingPage"
""",
}


def _run_gacha(
    tmp_path: Path,
    target: str,
    cases: list[dict[str, Any]] = CASES,
    excluded: list[dict[str, str]] | None = None,
) -> tuple[int, dict[str, Any] | None]:
    (tmp_path / f"fake_{target}.py").write_text(FAKE_TARGETS[target], encoding="utf-8")
    excluded_file = tmp_path / "excluded.json"
    excluded_file.write_text(json.dumps(excluded or [], ensure_ascii=False), encoding="utf-8")
    data = tmp_path / "2026-01-01-00.json"
    data.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
    result_file = tmp_path / "result.json"
    env = {
        **os.environ,
        "TGDD_TEST_DATA": str(data),
        "TGDD_RESULT_FILE": str(result_file),
        "TGDD_TARGET_MODULE": f"fake_{target}",
        "TGDD_EXCLUDED_FILE": str(excluded_file),
        "PYTHONPATH": str(tmp_path),
    }
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_gacha.py", "-q", "-p", "no:cacheprovider"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    result = json.loads(result_file.read_text(encoding="utf-8")) if result_file.exists() else None
    return completed.returncode, result


def _failed(result: dict[str, Any]) -> list[tuple[str, str]]:
    return sorted((entry["test_data_id"], entry["target"]) for entry in result["failed"])


def test_gacha_all_passed(tmp_path: Path):
    code, result = _run_gacha(tmp_path, "correct")
    assert code == 0
    assert result == {"test_data_file": "2026-01-01-00.json", "total": 2, "failed_test_data": 0, "failed": []}


def test_gacha_reports_grouper_failure_only(tmp_path: Path):
    """分割の間違いは、変換の結果に波及しない"""
    code, result = _run_gacha(tmp_path, "wrong_grouper")
    assert code == 1
    assert result is not None
    assert _failed(result) == [("two", "text_to_page_grouper")]
    assert result["total"] == 2
    assert result["failed_test_data"] == 1


def test_gacha_reports_page_failure_with_page_number(tmp_path: Path):
    code, result = _run_gacha(tmp_path, "wrong_second_page")
    assert code == 1
    assert result is not None
    assert _failed(result) == [("two", "page_to_slideir_page")]
    message = result["failed"][0]["message"]
    assert "2 ページ目" in message
    assert "1 ページ目" not in message


def test_gacha_continues_after_exceptions(tmp_path: Path):
    """例外や不正な戻り値があっても止まらず、すべてのテストデータの結果が出る"""
    code, result = _run_gacha(tmp_path, "broken")
    assert code == 1
    assert result is not None
    assert _failed(result) == [
        ("one", "page_to_slideir_page"),
        ("one", "text_to_page_grouper"),
        ("two", "page_to_slideir_page"),
        ("two", "text_to_page_grouper"),
    ]
    assert result["failed_test_data"] == 2
    assert any("boom" in entry["message"] for entry in result["failed"])


def test_gacha_skips_excluded_test_data(tmp_path: Path):
    """除外したテストデータは実行せず、結果にも数えない"""
    code, result = _run_gacha(tmp_path, "wrong_grouper", excluded=[{"test_data_id": "two", "reason": "期待値の誤り"}])
    assert code == 0
    assert result == {"test_data_file": "2026-01-01-00.json", "total": 1, "failed_test_data": 0, "failed": []}


def test_committed_excluded_and_regression_data_are_well_formed():
    """除外の一覧は test_data_id と理由を持ち、再発のテストのデータはテストデータと同じ検査を通る"""
    excluded = json.loads((ROOT / "tests" / "excluded_test_data.json").read_text(encoding="utf-8"))
    assert isinstance(excluded, list)
    for entry in excluded:
        assert set(entry) == {"test_data_id", "reason"}, entry
        assert entry["test_data_id"] and entry["reason"].strip(), entry
    ids = [entry["test_data_id"] for entry in excluded]
    assert len(ids) == len(set(ids))

    regression = json.loads((ROOT / "tests" / "regression_data.json").read_text(encoding="utf-8"))
    assert isinstance(regression, list)
    if regression:
        assert validate_test_data(regression, SCHEMA) == []
