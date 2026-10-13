"""Render validated ARC tasks as a self-contained, offline HTML browser."""

import json
from collections.abc import Iterable
from html import escape
from pathlib import Path

from arcagi.tasks import Task, validate_grid

_COLORS = (
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

_STYLE = """
:root { color-scheme: dark; font-family: system-ui, sans-serif; }
body { margin: 0 auto; padding: 1.5rem; max-width: 100rem; background: #10151d;
       color: #e9edf3; }
h1 { margin-bottom: .4rem; } a { color: #9cd4ff; }
.controls { display: flex; gap: .7rem; flex-wrap: wrap; align-items: center;
            margin: 1.5rem 0; }
button, select, input { font: inherit; padding: .6rem; border: 1px solid #60718b;
                       border-radius: .4rem; background: #1d2939; color: inherit; }
button { cursor: pointer; } button:disabled { opacity: .4; cursor: default; }
select { max-width: 100%; } .muted { color: #b8c3d3; }
.pairs { display: flex; flex-wrap: wrap; gap: 1rem; align-items: flex-start; }
.pair { padding: 1rem; background: #1a2432; border: 1px solid #34445a;
        border-radius: .7rem; max-width: 100%; box-sizing: border-box; }
.grids { display: flex; flex-wrap: wrap; gap: 1.3rem; align-items: flex-start; }
figure { margin: 0; max-width: 100%; overflow-x: auto; }
figcaption { margin-bottom: .5rem; color: #b8c3d3; }
.grid { border-collapse: collapse; table-layout: fixed; }
.grid td { width: 18px; min-width: 18px; height: 18px; padding: 0;
           border: 1px solid #495261; }
.grid td span { position: absolute; width: 1px; height: 1px; overflow: hidden;
                clip-path: inset(50%); }
details { margin-top: 1rem; } summary { cursor: pointer; margin-bottom: .7rem; }
.legend { display: flex; flex-wrap: wrap; gap: .8rem; margin-top: 2rem; }
.swatch { display: inline-block; width: 1rem; height: 1rem; vertical-align: middle;
          border: 1px solid #6d7b90; margin-right: .3rem; }
[hidden] { display: none !important; }
"""
_SCRIPT = """
const tasks = JSON.parse(document.getElementById('task-data').textContent);
const select = document.getElementById('task-select');
const filter = document.getElementById('task-filter');
const options = Array.from(select.options);
const main = document.getElementById('task-view');
function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function grid(values, label) {
  const figure = element('figure');
  figure.append(element('figcaption',
    `${label} · ${values.length} × ${values[0].length}`));
  const table = element('table', undefined, 'grid');
  table.setAttribute('aria-label', label);
  values.forEach((row, rowIndex) => {
    const tr = element('tr');
    row.forEach((color, colIndex) => {
      const td = element('td', undefined, `c${color}`);
      td.title = `row ${rowIndex + 1}, column ${colIndex + 1}: ${color}`;
      td.append(element('span', String(color)));
      tr.append(td);
    });
    table.append(tr);
  });
  figure.append(table);
  return figure;
}
function render(task) {
  const section = element('section', undefined, 'task');
  section.append(element('h2', task.task_id));
  section.append(element('h3', 'Training examples / 示範'));
  const training = element('div', undefined, 'pairs');
  task.train.forEach((example, index) => {
    const pair = element('article', undefined, 'pair');
    pair.append(element('h4', `Example ${index + 1}`));
    const grids = element('div', undefined, 'grids');
    grids.append(grid(example.input, 'Input'), grid(example.output, 'Output'));
    pair.append(grids);
    training.append(pair);
  });
  section.append(training, element('h3', 'Test / 測試'));
  const testing = element('div', undefined, 'pairs');
  task.test.forEach((example, index) => {
    const pair = element('article', undefined, 'pair');
    pair.append(element('h4', `Test ${index + 1}`), grid(example.input, 'Input'));
    if (example.output === null) {
      pair.append(element('p', 'No answer provided / 未提供答案', 'muted'));
    } else {
      const details = element('details');
      details.append(element('summary', 'Reveal answer / 顯示答案'),
        grid(example.output, 'Expected output'));
      pair.append(details);
    }
    testing.append(pair);
  });
  section.append(testing);
  main.replaceChildren(section);
}
function show() {
  const visible = options.filter((option) => !option.hidden);
  const index = visible.findIndex((option) => option.value === select.value);
  document.getElementById('previous').disabled = index <= 0;
  document.getElementById('next').disabled = index < 0 || index >= visible.length - 1;
  document.getElementById('status').textContent = visible.length
    ? `${index + 1} / ${visible.length}` : 'No matching tasks';
  if (index < 0) main.replaceChildren();
  else render(tasks[Number(select.value)]);
}
select.addEventListener('change', show);
filter.addEventListener('input', () => {
  const query = filter.value.toLowerCase().trim();
  options.forEach((option) => {
    option.hidden = !option.textContent.toLowerCase().includes(query);
  });
  const first = options.find((option) => !option.hidden);
  if (!first || !select.value || select.selectedOptions[0]?.hidden) {
    select.value = first?.value || '';
  }
  show();
});
function move(delta) {
  const visible = options.filter((option) => !option.hidden);
  const index = visible.findIndex((option) => option.value === select.value);
  if (visible[index + delta]) select.value = visible[index + delta].value;
  show();
}
document.getElementById('previous').addEventListener('click', () => move(-1));
document.getElementById('next').addEventListener('click', () => move(1));
show();
"""


def _task_data(task: Task) -> dict[str, object]:
    """Validate even directly constructed dataclasses before embedding grids."""
    training = []
    for example in task.train:
        if example.output is None:
            raise ValueError(f"{task.task_id}: training example requires output")
        training.append(
            {
                "input": validate_grid(example.input),
                "output": validate_grid(example.output),
            }
        )
    testing = [
        {
            "input": validate_grid(example.input),
            "output": validate_grid(example.output)
            if example.output is not None
            else None,
        }
        for example in task.test
    ]
    return {"task_id": task.task_id, "train": training, "test": testing}


def render_tasks(tasks: Iterable[Task], *, title: str = "ARC-AGI-1") -> str:
    """Render tasks without external assets; labeled test answers start collapsed.

    Answer collapsing is only a viewing convenience, not a security boundary.
    The returned HTML contains every supplied test output.
    """
    items = tuple(tasks)
    if not items:
        raise ValueError("Cannot visualize an empty task collection")
    palette = "\n".join(
        f".c{index} {{ background: {color}; }}" for index, color in enumerate(_COLORS)
    )
    options = "".join(
        f'<option value="{index}">{escape(task.task_id)}</option>'
        for index, task in enumerate(items)
    )
    # Escape HTML-significant characters so task IDs cannot close the data script.
    data = json.dumps([_task_data(task) for task in items], separators=(",", ":"))
    data = data.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    legend = "".join(
        f'<span><i class="swatch c{index}"></i>{index}</span>' for index in range(10)
    )
    safe_title = escape(title)
    return f"""<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{safe_title}</title><style>{_STYLE}\n{palette}</style></head>
<body><header><h1>{safe_title}</h1>
<p class="muted">Offline task browser · {len(items)} tasks · 離線題目瀏覽器</p>
<p class="muted">Test answers are collapsed, but included in this file.
測試答案預設折疊，仍包含在本檔中。</p></header>
<nav class="controls" aria-label="Task navigation">
<label>搜尋 / Search
<input id="task-filter" type="search" placeholder="Task ID"></label>
<label>題目 / Task <select id="task-select">{options}</select></label>
<button id="previous" type="button">← Previous</button>
<button id="next" type="button">Next →</button>
<span id="status" role="status" aria-live="polite"></span></nav>
<noscript><p>Enable JavaScript to browse tasks /
請啟用 JavaScript 瀏覽題目。</p></noscript>
<main id="task-view"></main>
<footer class="legend" aria-label="ARC color legend">{legend}</footer>
<script type="application/json" id="task-data">{data}</script>
<script>{_SCRIPT}</script></body></html>
"""


def write_html(
    tasks: Iterable[Task], output: str | Path, *, title: str = "ARC-AGI-1"
) -> Path:
    """Write UTF-8 HTML, creating the output's parent directory if necessary."""
    html = render_tasks(tasks, title=title)
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path
