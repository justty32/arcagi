"""Render the training inventory rows as a self-contained offline HTML page."""

from collections import Counter
from html import escape

COLORS = (
    "#000000",
    "#0074d9",
    "#ff4136",
    "#2ecc40",
    "#ffdc00",
    "#aaaaaa",
    "#f012be",
    "#ff851b",
    "#7fdbff",
    "#870c25",
)
LEVEL_COLORS = {"easy": "#2a9d6f", "medium": "#e0a526", "hard": "#c8553d"}
LEVEL_NAMES = {"easy": "易", "medium": "中", "hard": "難"}

# (label, plain explanation, judgement on symbolic solvability)
CATEGORY_TEXT = {
    "geometry": (
        "幾何變換",
        "整張圖旋轉或鏡射，輸出就是輸入轉個方向。",
        "最容易。八種轉法逐一試，一行規則就解。",
    ),
    "colormap": (
        "純顏色映射",
        "每個格子照一張固定的「顏色對照表」換色，位置完全不動。",
        "最容易。從範例直接讀出對照表即可。",
    ),
    "scale_tile": (
        "放大／平鋪",
        "輸出是輸入的整數倍：每格放大成方塊，或把輸入（可能翻轉過）排成拼貼。",
        "容易。倍率由尺寸算出，拼貼方式在少數候選裡枚舉。",
    ),
    "crop": (
        "裁切／物件抽取",
        "輸出原封不動地出現在輸入裡某個位置：挑出某個物件或區塊。",
        "中等。裁切本身簡單，難在「挑哪一個」：最大、唯一、顏色特殊……要寫選擇條件。",
    ),
    "split_overlay": (
        "拆格疊合",
        "輸入被分成兩三塊同樣大的面板（常有分隔線），輸出把面板疊起來做 AND／OR／XOR。",
        "容易到中等。切法固定，疊合運算只有少數幾種，適合窮舉。",
    ),
    "symmetry": (
        "對稱或規律補全",
        "輸出變成對稱或重複的圖樣，輸入原本沒有：補齊缺角、把規律延伸開。",
        "中等。偵測對稱軸或週期有標準作法，但缺損位置與遮擋色要處理。",
    ),
    "fill": (
        "加筆／填色",
        "只在背景格上畫東西，原有的格子不動：畫線、圍住的區域填色、在物件旁加記號。",
        "最雜的一類。畫線、連點、填封閉區各需不同小規則；單一規則多半短，但要先認出是哪一種。",
    ),
    "remove": (
        "刪除",
        "只把某些格子抹成背景：去雜訊、拿掉不符條件的物件。",
        "容易到中等。規則通常是「保留符合條件的物件」。",
    ),
    "recolor": (
        "依條件上色",
        "形狀不動，只有前景格換顏色；換成什麼顏色取決於物件大小、形狀或位置。",
        "中等。先切物件，再找「哪種屬性對應哪種顏色」，是典型的符號規則學習。",
    ),
    "move": (
        "移動／重排",
        "格子顏色的總數不變，只是位置變了：重力掉落、物件平移、排序。",
        "中等到難。要先找出物件和它們的移動方向或終點條件。",
    ),
    "same_mixed": (
        "同尺寸綜合變化",
        "尺寸不變，但同時有加、刪、換色；往往是多步驟組合。",
        "偏難。需要把幾個小規則串成流程。",
    ),
    "summary": (
        "小輸出／計數摘要",
        "輸出只有 9 格以內：數物件、選出最多的顏色、回答是或否。",
        "中等。輸出好猜，難在數什麼；計數與比較本身是符號的強項。",
    ),
    "shrink_other": (
        "縮小（其他）",
        "輸出比輸入小，但不是單純裁切或疊合：先抽物件再變形、壓縮重複、取出規律單元。",
        "偏難。多半是「選取＋變換」兩步以上。",
    ),
    "grow_other": (
        "放大（其他）",
        "輸出比輸入大，但不是整數倍放大：畫布延伸、依內容決定尺寸、碎形式拼貼。",
        "中等到難。要先推出輸出尺寸怎麼來。",
    ),
}

CSS = """
:root{color-scheme:light;--ink:#17324d;--blue:#1465c0;--pale:#eaf3ff;--line:#cfdeec;
--muted:#55697e}
*{box-sizing:border-box}
body{margin:0;background:#f4f8fc;color:var(--ink);font-size:17px;line-height:1.7;
font-family:system-ui,-apple-system,"Noto Sans TC",sans-serif}
header,main,footer{max-width:1080px;margin:auto;padding:20px 16px}
h1{font-size:clamp(28px,5vw,42px);line-height:1.3;margin:8px 0}h2{margin-top:0}
a{color:var(--blue)}.muted{color:var(--muted)}
nav{display:flex;flex-wrap:wrap;gap:8px}
nav a{padding:5px 12px;border-radius:30px;background:var(--pale);text-decoration:none}
.card{background:#fff;border:1px solid var(--line);border-radius:18px;padding:24px;
margin:0 0 22px;box-shadow:0 5px 16px #23445a08}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}
.tile{background:var(--pale);border-radius:14px;padding:14px}
.tile b{display:block;font-size:30px;line-height:1.2}
.cats{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:16px}
.cat{border:1px solid var(--line);border-radius:14px;padding:16px}
.cat h3{margin:0 0 4px}.ex{display:flex;align-items:center;gap:8px;flex-wrap:wrap;
margin:8px 0}.ex span{font-size:22px;color:var(--blue)}
.lv{display:inline-block;padding:0 8px;border-radius:8px;color:#fff;font-size:14px}
svg{max-width:100%;height:auto}svg text{font-family:inherit}
details{margin-top:10px}summary{cursor:pointer;color:var(--blue)}
table{border-collapse:collapse;font-size:14px;width:100%}
th,td{border-bottom:1px solid var(--line);padding:3px 6px;text-align:left}
.scroll{overflow-x:auto}code{background:var(--pale);padding:0 4px;border-radius:4px}
"""


def grid_svg(grid: list[list[int]], max_px: int = 120) -> str:
    """Draw a grid as a small inline SVG."""
    h, w = len(grid), len(grid[0])
    cell = max(2, min(16, max_px // max(h, w)))
    rects = "".join(
        f'<rect x="{c * cell}" y="{r * cell}" width="{cell}" height="{cell}" '
        f'fill="{COLORS[v]}"/>'
        for r, row in enumerate(grid)
        for c, v in enumerate(row)
    )
    return (
        f'<svg width="{w * cell}" height="{h * cell}" viewBox="0 0 {w * cell} '
        f'{h * cell}" role="img" aria-label="{h}x{w} grid">{rects}'
        f'<rect width="{w * cell}" height="{h * cell}" fill="none" '
        f'stroke="#8899aa"/></svg>'
    )


def pair_svg(task: dict) -> str:
    pair = task["train"][0]
    return (
        f'<div class="ex">{grid_svg(pair["input"])}<span>→</span>'
        f"{grid_svg(pair['output'])}</div>"
    )


def bar_chart(items: list[tuple[str, int]], color: str = "#1465c0") -> str:
    """Horizontal bar chart with labels and values."""
    top = max((v for _, v in items), default=1) or 1
    row_h, label_w, bar_w = 26, 150, 420
    parts = []
    for n, (label, value) in enumerate(items):
        y = n * row_h
        width = value / top * bar_w
        parts.append(
            f'<text x="{label_w - 8}" y="{y + 17}" text-anchor="end" '
            f'font-size="14">{escape(label)}</text>'
            f'<rect x="{label_w}" y="{y + 4}" width="{width:.1f}" height="18" '
            f'rx="3" fill="{color}"/>'
            f'<text x="{label_w + width + 6:.1f}" y="{y + 17}" font-size="14">'
            f"{value}</text>"
        )
    height = len(items) * row_h
    return (
        f'<svg viewBox="0 0 {label_w + bar_w + 50} {height}" '
        f'width="{label_w + bar_w + 50}">{"".join(parts)}</svg>'
    )


def histogram(counts: Counter, keys: list[int], label: str) -> str:
    """Vertical bar histogram over integer keys."""
    top = max(counts.values()) or 1
    col, chart_h = 18, 140
    parts = []
    for n, key in enumerate(keys):
        value = counts.get(key, 0)
        bar = value / top * chart_h
        x = n * col
        parts.append(
            f'<rect x="{x + 2}" y="{chart_h - bar + 16:.1f}" width="{col - 4}" '
            f'height="{bar:.1f}" fill="#1465c0"><title>{label} {key}：{value} 題'
            f"</title></rect>"
        )
        if value:
            parts.append(
                f'<text x="{x + col / 2}" y="{chart_h - bar + 12:.1f}" '
                f'font-size="10" text-anchor="middle">{value}</text>'
            )
        parts.append(
            f'<text x="{x + col / 2}" y="{chart_h + 30}" font-size="10" '
            f'text-anchor="middle">{key}</text>'
        )
    width = len(keys) * col
    return (
        f'<svg viewBox="0 0 {width} {chart_h + 36}" width="{width}">'
        f"{''.join(parts)}</svg>"
    )


def stacked_levels(rows_by_cat: dict[str, list[dict]]) -> str:
    """Stacked horizontal bars: per category, easy/medium/hard counts."""
    order = sorted(rows_by_cat, key=lambda c: -len(rows_by_cat[c]))
    top = max(len(v) for v in rows_by_cat.values())
    row_h, label_w, bar_w = 28, 160, 440
    parts = []
    for n, cat in enumerate(order):
        y = n * row_h
        x = label_w
        parts.append(
            f'<text x="{label_w - 8}" y="{y + 18}" text-anchor="end" '
            f'font-size="14">{CATEGORY_TEXT[cat][0]}</text>'
        )
        levels = Counter(r["symbolic"] for r in rows_by_cat[cat])
        for level in ("easy", "medium", "hard"):
            width = levels[level] / top * bar_w
            if width:
                parts.append(
                    f'<rect x="{x:.1f}" y="{y + 5}" width="{width:.1f}" '
                    f'height="18" fill="{LEVEL_COLORS[level]}"><title>'
                    f"{LEVEL_NAMES[level]} {levels[level]}</title></rect>"
                )
            x += width
        parts.append(
            f'<text x="{x + 6:.1f}" y="{y + 18}" font-size="14">'
            f"{len(rows_by_cat[cat])}</text>"
        )
    height = len(order) * row_h
    return (
        f'<svg viewBox="0 0 {label_w + bar_w + 50} {height}" '
        f'width="{label_w + bar_w + 50}">{"".join(parts)}</svg>'
    )


def level_badge(level: str) -> str:
    return (
        f'<span class="lv" style="background:{LEVEL_COLORS[level]}">'
        f"{LEVEL_NAMES[level]}</span>"
    )


def codes(ids: list[str]) -> str:
    return ", ".join(f"<code>{t}</code>" for t in ids)


def category_cards(rows_by_cat: dict[str, list[dict]], tasks: dict) -> str:
    cards = []
    for cat in sorted(rows_by_cat, key=lambda c: -len(rows_by_cat[c])):
        rows = sorted(rows_by_cat[cat], key=lambda r: r["rearc_verifier_lines"])
        label, plain, judge = CATEGORY_TEXT[cat]
        levels = Counter(r["symbolic"] for r in rows)
        spread = " ".join(
            f"{level_badge(lv)} {levels[lv]}" for lv in ("easy", "medium", "hard")
        )
        reps = [r["task_id"] for r in rows[:3]] + [r["task_id"] for r in rows[-2:]]
        reps = list(dict.fromkeys(reps))
        listing = "".join(
            f"<tr><td><code>{r['task_id']}</code></td><td>"
            f"{level_badge(r['symbolic'])}</td><td>{r['rearc_verifier_lines']}</td>"
            f"<td>{escape(r['detail'])}</td></tr>"
            for r in rows
        )
        cards.append(
            f'<div class="cat" id="cat-{cat}"><h3>{label}（{len(rows)} 題）</h3>'
            f"<div>{spread}</div><p>{plain}</p>{pair_svg(tasks[rows[0]['task_id']])}"
            f'<p class="muted">上圖：<code>{rows[0]["task_id"]}</code> 第一組範例'
            f"（本類 DSL 解答最短的一題）</p><p><b>符號可解性</b>：{judge}</p>"
            f"<p>代表題（DSL 最短）：{codes(reps[:3])}；"
            f"（DSL 最長）：{codes(reps[3:])}</p>"
            f"<details><summary>本類全部 {len(rows)} 題</summary>"
            f'<div class="scroll"><table><tr><th>題號</th><th>估計</th>'
            f"<th>DSL 行數</th><th>細節</th></tr>{listing}</table></div>"
            f"</details></div>"
        )
    return f'<div class="cats">{"".join(cards)}</div>'


def relation_section(rows: list[dict]) -> str:
    names = {
        "same": "同尺寸",
        "shrink_other": "縮小（非整數倍）",
        "upscale": "整數倍放大",
        "downscale": "整數倍縮小",
        "mixed": "各範例不一致",
        "fixed_output": "輸出固定尺寸",
        "grow_other": "放大（非整數倍）",
    }
    counts = Counter(r["size_relation"] for r in rows)
    items = [(names[k], v) for k, v in counts.most_common()]
    return bar_chart(items)


def task_table(rows: list[dict]) -> str:
    head = (
        "題號 類別 估計 範例對 輸入最大 輸出最大 大小關係 輸入色 輸出色 新色 "
        "變動比例 物件數 DSL行數"
    ).split()
    body = "".join(
        f"<tr><td><code>{r['task_id']}</code></td>"
        f"<td>{CATEGORY_TEXT[r['category']][0]}</td>"
        f"<td>{LEVEL_NAMES[r['symbolic']]}</td><td>{r['n_train']}</td>"
        f"<td>{r['in_h_max']}×{r['in_w_max']}</td>"
        f"<td>{r['out_h_max']}×{r['out_w_max']}</td><td>{r['size_relation']}</td>"
        f"<td>{r['in_colors']}</td><td>{r['out_colors']}</td>"
        f"<td>{r['new_out_colors']}</td><td>{r['changed_ratio']}</td>"
        f"<td>{r['objects_mean']}</td><td>{r['rearc_verifier_lines']}</td></tr>"
        for r in rows
    )
    header = "".join(f"<th>{h}</th>" for h in head)
    return f'<div class="scroll"><table><tr>{header}</tr>{body}</table></div>'


def render_html(rows: list[dict], tasks: dict) -> str:
    """Return the full inventory page."""
    total = len(rows)
    by_cat: dict[str, list[dict]] = {}
    for r in rows:
        by_cat.setdefault(r["category"], []).append(r)
    levels = Counter(r["symbolic"] for r in rows)
    same = sum(r["size_relation"] == "same" for r in rows)
    covered = sum(r["rearc_generator_lines"] > 0 for r in rows)
    in_dim = Counter(max(r["in_h_max"], r["in_w_max"]) for r in rows)
    out_dim = Counter(max(r["out_h_max"], r["out_w_max"]) for r in rows)
    in_cols = Counter(r["in_colors"] for r in rows)
    n_train = Counter(r["n_train"] for r in rows)
    vlines = Counter(min(r["rearc_verifier_lines"] // 5 * 5, 80) for r in rows)
    v_sorted = sorted(r["rearc_verifier_lines"] for r in rows)
    median_v = v_sorted[len(v_sorted) // 2]
    one_shot = sum(len(by_cat.get(c, [])) for c in ("geometry", "colormap"))
    one_shot += len(by_cat.get("scale_tile", []))
    n_fill = len(by_cat.get("fill", []))
    dims = sorted(max(r["in_h_max"], r["in_w_max"]) for r in rows)
    dim_med, dim_q3 = dims[total // 2], dims[total * 3 // 4]
    g_sorted = sorted(r["rearc_generator_lines"] for r in rows)
    median_g = g_sorted[total // 2]
    tiles = (
        f'<div class="tile"><b>{total}</b>題 training</div>'
        f'<div class="tile"><b>{same}</b>題輸入輸出同尺寸</div>'
        f'<div class="tile"><b>{len(by_cat)}</b>個粗分題型</div>'
        f'<div class="tile"><b>{covered}/{total}</b>題有 RE-ARC 生成器</div>'
        f'<div class="tile"><b>{levels["easy"]}／{levels["medium"]}／'
        f"{levels['hard']}</b>題 符號估計 易／中／難</div>"
    )
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ARC 訓練集盤點</title>
<style>{CSS}</style>
</head>
<body>
<header>
<div class="muted">ARC-AGI-1 · training 400 題 ·
由 scripts/inventory_training.py 產生</div>
<h1>訓練集題庫盤點</h1>
<p>把 400 題 training 逐題量過一遍：格子多大、輸入輸出怎麼變、用幾種顏色、
給幾組範例，再用程式自動粗分題型，估計每類有多容易寫成一條小規則。
逐題數字在 <a href="training-features.csv">training-features.csv</a>。</p>
<nav><a href="#overview">總覽</a><a href="#types">題型</a><a href="#sizes">格子大小</a>
<a href="#relation">大小關係</a><a href="#colors">顏色與範例</a>
<a href="#rearc">RE-ARC</a><a href="#method">怎麼判定</a><a href="#all">逐題表</a></nav>
</header>
<main>
<section class="card" id="overview"><h2>一眼總覽</h2><div class="tiles">{tiles}</div>
<p>{same} 題（{same * 100 // total}%）輸入輸出一樣大，變化發生在格子內容。
整張圖一個動作就解的（旋轉、換色、放大拼貼）只有 {one_shot} 題。
最大宗是「只在背景上加筆」（{n_fill} 題），這類規則短但種類多。</p></section>

<section class="card" id="types"><h2>題型粗分與符號難易</h2>
<p>每條橫條是一類，顏色是符號難易估計：
{level_badge("easy")} DSL 解答 ≤10 行、{level_badge("medium")} 11–25 行、
{level_badge("hard")} &gt;25 行（行數來源見 <a href="#rearc">RE-ARC</a>）。</p>
{stacked_levels(by_cat)}
<details><summary>這個難易估計怎麼看</summary>
<p>RE-ARC 為每題手寫了一支用 ARC-DSL 寫成的解答程式（verifier），
它本身就是一條符號規則。行數越短，代表用現成積木越快組得出來。
這只是代理指標：DSL 有一百多個積木，換一套積木，長短會變；
但相對排序大致可信。</p></details>
{category_cards(by_cat, tasks)}
</section>

<section class="card" id="sizes"><h2>格子大小</h2>
<p>取每題範例中最長的一邊（1–30）。輸入最長邊中位數 {dim_med} 格、
四分之三的題目在 {dim_q3} 格以內，
輸出則有一大群落在 3 格以下，對應計數、摘要類題目。</p>
<h3>輸入最長邊</h3>{histogram(in_dim, list(range(1, 31)), "最長邊")}
<h3>輸出最長邊</h3>{histogram(out_dim, list(range(1, 31)), "最長邊")}
</section>

<section class="card" id="relation"><h2>輸入／輸出大小關係</h2>
<p>同一題所有範例都成立才算。「輸出固定尺寸」指輸入大小各異、輸出卻總是同一尺寸。</p>
{relation_section(rows)}
<details><summary>判定規則</summary><p>同尺寸：每組長寬相同。整數倍放大／縮小：
長寬都是整數倍。其他放大／縮小：比較面積。各範例不一致：同一題裡混了不同關係。</p>
</details></section>

<section class="card" id="colors"><h2>顏色數與範例對數</h2>
<h3>輸入用到幾種顏色（含背景，全部範例合計）</h3>
{histogram(in_cols, list(range(1, 11)), "顏色數")}
<h3>每題給幾組訓練範例</h3>
{histogram(n_train, list(range(1, 11)), "範例對")}
<p>大部分題目只給 3 組範例。規則必須在 2–4 個例子裡就被唯一確定，
這是符號方法能贏的地方：候選規則少、可以逐一驗證。</p></section>

<section class="card" id="rearc"><h2>RE-ARC 覆蓋</h2>
<p><b>{covered} / {total} 題都有對應生成器</b>，函式名就是題號
（<code>generate_&lt;id&gt;</code>），
也都有 DSL 解答（<code>verify_&lt;id&gt;</code>）。
所以每一題都能無限生成新的練習例子，也都已被證明可用符號程式解出。</p>
<p>DSL 解答長度中位數 {median_v} 行。下圖每格 5 行（80 以上併入最後一格）：</p>
{histogram(vlines, list(range(0, 85, 5)), "DSL 行數")}
<details><summary>注意事項</summary><ul>
<li>生成器重現的是作者對規則的理解，分布可能比原題寬或窄；
用它訓練或測規則前，仍要拿原題範例驗收。</li>
<li>verifier 能解生成的例子，不代表它是唯一或最自然的寫法。</li>
<li>生成器本身的長度（中位數 {median_g} 行）反映的是造題的麻煩，
不是解題難度；逐題數字放在 CSV 的 <code>rearc_generator_lines</code>。</li>
</ul></details></section>

<section class="card" id="method"><h2>怎麼判定題型</h2>
<p>只看訓練範例，依序套下列檢查，第一個「所有範例都成立」的就是該題類別。</p>
<details><summary>判定順序與規則</summary><ol>
<li>幾何變換：輸出等於輸入的某一種旋轉或鏡射。</li>
<li>純顏色映射：同尺寸，且存在一張全題一致的顏色對照表。</li>
<li>放大／平鋪：輸出是輸入的整數倍，且是逐格放大、拼貼（可含翻轉），
或部分區塊留空的拼貼。</li>
<li>裁切：輸出原樣出現在輸入裡。</li>
<li>同尺寸再細分：輸出對稱而輸入不對稱→對稱補全；只改背景格→加筆
（改的格子都在封閉區內時細節標 enclosed）；只把格子抹成背景→刪除；
只把前景換色→依條件上色；顏色總數不變→移動；其餘→綜合。背景＝輸入中最多的顏色。</li>
<li>拆格疊合：輸入剛好是 2–4 塊輸出大小的面板（可含 1 格分隔線）。</li>
<li>小輸出：輸出 9 格以內。其餘依面積分成縮小或放大（其他）。</li>
</ol><p>限制：自動規則只看表面，同一題可能同時屬於好幾類，
這裡只取第一個命中的。「加筆」與「綜合」兩大類裡混了很多不同的機制，
是下一輪值得人工細分的地方。</p></details></section>

<section class="card" id="all"><h2>逐題表</h2>
<details><summary>展開 {total} 題的全部特徵</summary>{task_table(rows)}</details>
</section>
</main>
<footer class="muted">離線頁面，不載入外部資源。資料：data/ARC-AGI/data/training、
vendor/re-arc。重產：<code>uv run python scripts/inventory_training.py</code>。
· <a href="../README.md">所有教學</a></footer>
</body>
</html>
"""
