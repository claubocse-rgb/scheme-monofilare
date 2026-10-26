"""Verificări statice ale interfeței: sintaxa JS (node --check) și parserul numeric românesc."""
import pathlib, shutil, subprocess, tempfile
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.mark.skipif(not shutil.which("node"), reason="node nu e instalat")
def test_js_sintaxa():
    s = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    js = s[s.index("<script>") + 8: s.rindex("</script>")]
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js)
    r = subprocess.run(["node", "--check", f.name], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


@pytest.mark.skipif(not shutil.which("node"), reason="node nu e instalat")
@pytest.mark.parametrize("txt,val", [("12,5", 12.5), ("0,12", 0.12), ("1.250", 1250), ("1.250,50", 1250.5), ("1,250.50", 1250.5),
                                     ("0.12", 0.12), ("1 250", 1250), ("abc", None), ("12,5,3", None), ("", None)])
def test_parse_ro(txt, val):
    s = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    i = s.index("function parseRO(t)"); j = s.index("\n}\n", i) + 3
    cod = s[i:j] + f"\nconsole.log(JSON.stringify(parseRO({txt!r})));"
    r = subprocess.run(["node", "-e", cod], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    import json
    assert json.loads(r.stdout) == val


@pytest.mark.parametrize("txt,val", [("1,250.50", 1250.5), ("1.250,50", 1250.5), ("1.250", 1250), ("111,5 lei", 111.5), ("12.5", 12.5)])
def test_num_server(txt, val):
    import sys; sys.path.insert(0, str(ROOT))
    from engine.deviz import _num
    assert _num(txt) == val
