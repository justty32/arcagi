"""Checks for lazy offline rendering, answer disclosure, and escaping."""

import json
import shutil
import subprocess
from html.parser import HTMLParser

import pytest

from arcagi.tasks import Example, Task
from arcagi.visualization import _SCRIPT, render_tasks, write_html


class _Document(HTMLParser):
    def __init__(self, html: str) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str | None]]] = []
        self.data_text = ""
        self.in_data = False
        self.feed(html)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append((tag, dict(attrs)))
        if tag == "script" and dict(attrs).get("id") == "task-data":
            self.in_data = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self.in_data = False

    def handle_data(self, data: str) -> None:
        if self.in_data:
            self.data_text += data

    @property
    def tasks(self) -> list[dict]:
        return json.loads(self.data_text)


def _task(task_id: str = "demo", *, labeled: bool = True) -> Task:
    return Task(
        task_id=task_id,
        train=(Example(input=((1, 2),), output=((3,), (4,))),),
        test=(Example(input=((5,),), output=((6,),) if labeled else None),),
    )


def test_embedded_data_preserves_all_grids_without_eager_grid_dom() -> None:
    parsed = _Document(render_tasks([_task()]))
    assert parsed.tasks == [
        {
            "task_id": "demo",
            "train": [{"input": [[1, 2]], "output": [[3], [4]]}],
            "test": [{"input": [[5]], "output": [[6]]}],
        }
    ]
    assert not any(tag == "td" for tag, _ in parsed.tags)
    assert any(attrs.get("id") == "task-view" for _, attrs in parsed.tags)


def test_unlabeled_and_duplicate_ids_have_unambiguous_navigation() -> None:
    parsed = _Document(render_tasks([_task("same", labeled=False), _task("same")]))
    assert [attrs["value"] for tag, attrs in parsed.tags if tag == "option"] == [
        "0",
        "1",
    ]
    assert parsed.tasks[0]["test"][0]["output"] is None
    assert parsed.tasks[1]["test"][0]["output"] == [[6]]


def test_user_strings_cannot_escape_data_script_or_inject_resources() -> None:
    task_id = '</script><img src=x onerror="alert(1)">&\u2028\u2029'
    html = render_tasks([_task(task_id)], title="</title><script>x</script>")
    parsed = _Document(html)
    assert not any(tag == "img" for tag, _ in parsed.tags)
    assert len([tag for tag, _ in parsed.tags if tag == "script"]) == 2
    assert not any("src" in attrs or "href" in attrs for _, attrs in parsed.tags)
    assert parsed.tasks[0]["task_id"] == task_id
    assert "<" not in parsed.data_text
    assert "&lt;/title&gt;&lt;script&gt;x&lt;/script&gt;" in html


def test_output_is_deterministic_and_accepts_an_iterator(tmp_path) -> None:
    tasks = [_task()]
    expected = render_tasks(tasks)
    path = write_html(iter(tasks), tmp_path / "nested" / "tasks.html")
    assert path.read_text(encoding="utf-8") == expected
    assert render_tasks(tasks) == expected


def test_empty_input_and_invalid_grid_fail_before_writing(tmp_path) -> None:
    target = tmp_path / "invalid.html"
    with pytest.raises(ValueError, match="empty"):
        write_html([], target)
    assert not target.exists()
    bad = Task("invalid", (Example(((10,),), ((1,),)),), (Example(((1,),), None),))
    with pytest.raises(ValueError):
        write_html([bad], target)
    assert not target.exists()


@pytest.mark.skipif(shutil.which("node") is None, reason="Optional Node DOM smoke test")
def test_browser_render_navigation_and_filter_recovery() -> None:
    """Exercise the real script with a small DOM fixture, without a browser package."""
    data = _Document(render_tasks([_task("alpha"), _task("beta", labeled=False)]))
    fixture = r"""
const assert = require('node:assert/strict');
class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.attributes = {};
    this.listeners = {}; this.value = ''; this.textContent = ''; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; }
  setAttribute(name, value) { this.attributes[name] = value; }
  addEventListener(name, handler) { this.listeners[name] = handler; }
}
const elements = {};
for (const id of ['task-data', 'task-select', 'task-filter', 'task-view',
                  'previous', 'next', 'status']) elements[id] = new Element('div');
elements['task-data'].textContent = JSON.stringify(DATA);
elements['task-select'].options = DATA.map((task, index) => ({
  value: String(index), textContent: task.task_id, hidden: false }));
elements['task-select'].value = '0';
Object.defineProperty(elements['task-select'], 'selectedOptions', { get() {
  return this.options.filter(option => option.value === this.value); } });
global.document = { getElementById: id => elements[id],
                    createElement: tag => new Element(tag) };
function descendants(node) {
  return [node, ...node.children.flatMap(descendants)];
}
"""
    checks = r"""
let nodes = descendants(elements['task-view']);
assert.deepEqual(nodes.filter(n => n.tag === 'td').map(n => n.className),
                 ['c1','c2','c3','c4','c5','c6']);
assert.equal(nodes.filter(n => n.tag === 'details').length, 1);
assert.equal(nodes.find(n => n.tag === 'details').attributes.open, undefined);
assert.equal(nodes.find(n => n.tag === 'h2').textContent, 'alpha');
elements.next.listeners.click();
nodes = descendants(elements['task-view']);
assert.equal(nodes.find(n => n.tag === 'h2').textContent, 'beta');
assert.equal(nodes.filter(n => n.tag === 'details').length, 0);
assert.ok(nodes.some(n => n.textContent.includes('No answer provided')));
assert.equal(nodes.filter(n => n.tag === 'section').length, 1);
elements['task-filter'].value = 'missing';
elements['task-filter'].listeners.input();
assert.equal(elements['task-view'].children.length, 0);
assert.equal(elements.status.textContent, 'No matching tasks');
elements['task-filter'].value = 'alpha';
elements['task-filter'].listeners.input();
assert.equal(elements['task-select'].value, '0');
assert.equal(elements.previous.disabled, true);
assert.equal(elements.next.disabled, true);
assert.equal(descendants(elements['task-view']).find(n => n.tag === 'h2')
  .textContent, 'alpha');
"""
    program = (
        f"const DATA = {json.dumps(data.tasks)};\n"
        f"{fixture}\n{{\n{_SCRIPT}\n}}\n{checks}"
    )
    subprocess.run([shutil.which("node"), "-e", program], check=True, timeout=10)
