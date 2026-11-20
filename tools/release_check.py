# -*- coding: utf-8 -*-
"""배포 점검 — 서버 · 모델 없이 파일만 읽어 "빠진 곳" 을 찾는다.

    python tools/release_check.py

새 화면 · 새 파이썬 파일 · 새 모델을 넣을 때 고쳐야 하는 곳이 여러 군데라
한 곳을 빼먹기 쉽다(얼굴 AI 를 넣으며 번들 목록 · 리눅스 설치 스크립트를 빠뜨렸다).
여기서 서로 맞는지 한 번에 본다. 하나라도 어긋나면 FAIL 이고 끝 코드가 1 이다.
tools/make_bundle.bat 와 tools/schema_test/run.py 가 이것을 먼저 돌린다.

보는 것
  1) 서버가 읽는 파이썬 파일(main.py 에서 import 를 따라간 것)이 번들 복사 · 확인 목록에 다 있나
  2) 화면 주소(main.py 의 view_project/*.html)가 PAGE_PATHS · 번들 확인 목록 · 셸(embed.js · shell.js · apps.js)과 맞나
  3) 화면이 부르는 /lib · /assets · /fonts · /blockly 파일이 실제로 있나, 번들 공용 파일 확인 목록이 있나
  4) 서버가 반드시 읽는 모델(tools/check.py NEED)이 설치 스크립트(setup.ps1 · setup.sh)와 배포 받기(setup_deploy.ps1)에 들어가나
  5) 파이썬 코드가 쓰는 바깥 패키지가 requirements.txt · requirements.lock.txt 에 다 있나
  4-1) 코딩 실습 노트북이 부르는 모델(models/... 경로)이 받기 · 번들에서 빠지지 않고, tools/check.py 가 보고,
     00_start 의 모델 점검 목록에 있나 · 한국어/영어 노트북이 같은 모델을 쓰나
     tools/hf/README.md (허깅페이스 저장소 설명) 폴더 표가 그 폴더들을 다 담나
  6) 제품 이름이 brand.json 한 곳에만 있나 — 코드에 이름을 직접 쓰면 FAIL, 문서 · lib/brand.js 가
     brand.json 과 맞는지(tools/rename_brand.py --check), 모든 화면이 lib/brand.js 를 먼저 읽는지
"""
import ast
import fnmatch
import json
import os
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
FAIL = []
WARN = []


def fail(msg):
    FAIL.append(msg)


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8", errors="replace")


# ------------------------------------------------------------------ 1) 파이썬 파일
def local_modules():
    return {p.stem for p in ROOT.glob("*.py")}


def imports_of(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            out.add(node.module.split(".")[0])
    return out


def runtime_closure():
    """main.py 에서 import 를 따라간 저장소 루트의 .py (서버가 실제로 읽는 것)."""
    local = local_modules()
    seen, todo = set(), ["main"]
    while todo:
        m = todo.pop()
        if m in seen:
            continue
        seen.add(m)
        for dep in imports_of(ROOT / (m + ".py")):
            if dep in local and dep not in seen:
                todo.append(dep)
    return seen


def bundle_lists():
    """make_bundle.bat 의 '복사' 목록과 '확인' 목록 (for %%F in (...) 의 첫 두 줄)."""
    bat = read("tools/make_bundle.bat")
    lists = re.findall(r"for %%F in \(([^)]*\bmain\.py\b[^)]*)\) do", bat)
    if len(lists) < 2:
        fail("make_bundle.bat: main.py 가 든 복사 · 확인 목록을 찾지 못했어요")
        return set(), set(), bat
    return set(lists[0].split()), set(lists[1].split()), bat


def check_python():
    copy, verify, bat = bundle_lists()
    mods = runtime_closure()
    for m in sorted(mods):
        f = m + ".py"
        if f not in copy:
            fail("번들 복사 목록(make_bundle.bat [6/8])에 없음: " + f)
        if f not in verify:
            fail("번들 확인 목록(make_bundle.bat [7/8])에 없음: " + f)
    # 패키지 폴더(__init__.py 가 있는 폴더)는 통째로 복사해야 한다
    for d in sorted(p.name for p in ROOT.iterdir() if (p / "__init__.py").exists()):
        used = any(d in imports_of(ROOT / (m + ".py")) for m in mods)
        if used and not re.search(r"xcopy /e /i /q /y %s " % re.escape(d), bat):
            fail("번들에 패키지 폴더 복사가 없음: " + d + "\\")
    # 개발 문서 파일 표에 없는 서버 파일 — 고칠 사람이 못 찾는다
    dev = read("DEVELOP.md")
    for m in sorted(mods):
        if "`%s.py`" % m not in dev:
            WARN.append("DEVELOP.md 파일 구성 표에 없음: %s.py" % m)
    return mods


# ------------------------------------------------------------------ 2) 화면 주소
def page_routes():
    src = read("main.py")
    pairs = re.findall(r'@app\.get\("(/[^"]*)"[^\n]*\n(?:[^\n]*\n){0,4}?\s+with open\("view_project/([\w-]+\.html)"', src)
    return pairs, src


def js_list(text, name):
    m = re.search(name + r"\s*=\s*\[([^\]]*)\]", text)
    return set(re.findall(r'"([^"]+)"', m.group(1))) if m else None


def check_pages():
    pairs, src = page_routes()
    if len(pairs) < 10:
        fail("main.py 에서 화면 주소를 찾지 못했어요 (찾은 것 %d 개)" % len(pairs))
    m = re.search(r"PAGE_PATHS\s*=\s*\(([^)]*)\)", src)
    page_paths = set(re.findall(r'"([^"]+)"', m.group(1))) if m else set()
    _, _, bat = bundle_lists()
    verify_html = set(re.findall(r"view_project\\([\w-]+\.html)", bat))
    embed = js_list(read("view_project/lib/embed.js"), "APP_PATHS") or set()
    shell = read("view_project/lib/shell.js")
    apps = read("view_project/lib/apps.js")
    app_hrefs = set(re.findall(r'href:\s*"(/[^"]*)"', apps))
    routes = {}
    for path, html in pairs:
        routes[path] = html
        if not (ROOT / "view_project" / html).exists():
            fail("%s 이 여는 파일이 없음: view_project/%s" % (path, html))
        if path not in page_paths:
            fail("main.py PAGE_PATHS 에 없음(켜진 직후 1~2분 503): " + path)
        if html not in verify_html:
            fail("번들 화면 확인 목록(make_bundle.bat)에 없음: view_project\\" + html)
    for href in sorted(app_hrefs):
        if href not in routes:
            fail("apps.js 앱 주소에 맞는 화면 경로가 main.py 에 없음: " + href)
        if href not in embed:
            fail("embed.js APP_PATHS 에 없음(셸 창으로 안 열림): " + href)
        if '"%s"' % href not in shell:
            fail("shell.js 창 제목 표에 없음: " + href)
    for p in sorted(page_paths):
        if p not in routes and p not in ("/",):
            WARN.append("PAGE_PATHS 에 있지만 화면 경로가 없음: " + p)
    return routes


# ------------------------------------------------------------------ 3) 화면이 부르는 파일
MOUNTS = {"/lib/": "view_project/lib/", "/assets/": "view_project/assets/",
          "/fonts/": "view_project/fonts/", "/blockly/": "view_project/blockly/"}


def check_assets(routes):
    for html in sorted(set(routes.values())):
        text = read("view_project/" + html)
        for ref in re.findall(r'(?:src|href)\s*=\s*"(/(?:lib|assets|fonts|blockly)/[^"?#]+)', text):
            for pre, d in MOUNTS.items():
                if ref.startswith(pre):
                    if not (ROOT / (d + ref[len(pre):])).exists():
                        fail("%s 이 부르는 파일이 없음: %s" % (html, ref))
    bat = read("tools/make_bundle.bat")
    m = re.search(r"for %%F in \((tokens\.css[^)]*)\) do", bat)
    for f in (m.group(1).split() if m else []):
        if not (ROOT / "view_project/lib" / f).exists():
            fail("번들 공용 파일 확인 목록의 파일이 저장소에 없음: view_project/lib/" + f)


# ------------------------------------------------------------------ 4) 모델
# 설치 스크립트가 이름으로 받지 않는 것 — 다른 단계에서 만들어진다(이유를 적는다)
MODEL_NOT_IN_SETUP = {
    "gan/depth-v2s.xml": "tools/setup.ps1 의 깊이 지도 변환 단계가 만든다(파일 이름이 아니라 변환 결과)",
}


# 서버 코드에 이름이 나오지만 NEED 에 넣지 않는 것 — 폴더째 받고, 없으면 그 기능만 안내한다
MODEL_OPTIONAL = {
    "openvino_model.xml": "대화 자료 찾기(embed/e5-small-int8) 폴더 안의 이름 — 처음 쓸 때 올리고, 없으면 안내",
    "openvino_tokenizer.xml": "같은 폴더의 토크나이저",
}


def need_models():
    src = read("tools/check.py")
    m = re.search(r"^NEED\s*=\s*\[(.*?)\n\]", src, re.S | re.M)
    return re.findall(r'"([^"]+)"', m.group(1)) if m else []


def check_models():
    need = need_models()
    if not need:
        fail("tools/check.py 에서 NEED 목록을 찾지 못했어요")
    ps1, sh = read("tools/setup.ps1"), read("tools/setup.sh")
    fm = read("tools/fetch_models.py")
    ign = re.search(r"IGNORE\s*=\s*\[([^\]]*)\]", fm)
    ignore = re.findall(r'"([^"]+)"', ign.group(1)) if ign else []
    if not ign:
        fail("tools/fetch_models.py 에서 IGNORE 목록을 찾지 못했어요")
    if "tools\\fetch_models.py" not in read("setup_deploy.ps1"):
        fail("setup_deploy.ps1 이 tools\\fetch_models.py 로 모델을 받지 않음")
    for rel in need:
        stem = pathlib.Path(rel).stem
        top = rel.split("/")[0]
        if any(p.rstrip("*").rstrip("/") == top for p in ignore if p.endswith("/*")):
            fail("tools/fetch_models.py 가 받지 않는 폴더의 필수 모델: models/" + rel)
        if rel in MODEL_NOT_IN_SETUP:
            continue
        if stem not in ps1:
            fail("tools/setup.ps1 에 받는 줄이 없음: models/" + rel)
        if stem not in sh:
            fail("tools/setup.sh 에 받는 줄이 없음: models/" + rel)
    # 서버 코드가 부르는 모델 파일 이름이 NEED 에 있나 (없으면 check.py 가 못 잡는다)
    for py in ("engines.py", "mp_routes.py", "speech_routes.py", "face_routes.py"):
        if not (ROOT / py).exists():
            continue
        for lit in re.findall(r'["\']([\w./-]+\.(?:xml|task))["\']', read(py)):
            name = lit.split("/")[-1]
            if name in MODEL_OPTIONAL:
                continue
            if not any(n.endswith(name) for n in need):
                WARN.append("%s 가 부르는 모델이 check.py NEED 에 없음(없어도 되는 것인지 확인): %s" % (py, lit))


# ------------------------------------------------------------------ 4-1) 노트북이 쓰는 모델
NB_ASSIGN = re.compile(r'^\s*([A-Z_][A-Z0-9_]*)\s*=\s*([A-Z_][A-Z0-9_]*)((?:\s*/\s*"[^"]+")+)')
NB_REF = re.compile(r'\b([A-Z_][A-Z0-9_]*)((?:\s*/\s*"[^"]+")+)')


def _nb_code(path):
    nb = json.loads(path.read_text(encoding="utf-8"))
    return "\n".join("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code")


def _nb_join(base, parts):
    return "/".join(([base] if base else []) + re.findall(r'"([^"]+)"', parts))


def nb_models(code):
    """MODELS / "face" / "x.xml" · F = MODELS / "face" 다음 F / "x.xml" 를 따라 models/ 아래 경로를 모은다."""
    var, out = {"MODELS": ""}, set()
    for line in code.splitlines():
        m = NB_ASSIGN.match(line)
        if m and m.group(2) in var:
            var[m.group(1)] = _nb_join(var[m.group(2)], m.group(3))
        for r in NB_REF.finditer(line):
            if r.group(1) in var:
                out.add(_nb_join(var[r.group(1)], r.group(2)))
    return out


def nb_start_list(code):
    """00_start 의 NEED = { "설명": "models 아래 경로", ... } 점검 목록."""
    m = re.search(r"^NEED\s*=\s*\{(.*?)\n\}", code, re.S | re.M)
    return re.findall(r'"[^"]+":\s*"([^"]+)"', m.group(1)) if m else None


def check_notebook_models():
    cp = read("tools/check.py")
    fm = read("tools/fetch_models.py")
    ign = re.search(r"IGNORE\s*=\s*\[([^\]]*)\]", fm)
    ignore_top = {p[:-2] for p in re.findall(r'"([^"]+)"', ign.group(1) if ign else "") if p.endswith("/*")}
    ed = re.search(r"EASYDETECT\s*=\s*\[([^\]]*)\]", fm)
    ed_allow = re.findall(r'"([^"]+)"', ed.group(1)) if ed else []
    removed = set(re.findall(r"rmdir /s /q %BUILD%\\models\\([\w.-]+)", read("tools/make_bundle.bat")))

    def covered_by_check(rel):          # check.py 가 그 경로(또는 그 안의 파일)를 이름으로 보나
        return re.search(r'(?:"|models/)' + re.escape(rel) + r'(?=["/])', cp) is not None

    def fetched(rel):
        top, _, rest = rel.partition("/")
        if top == "easydetect":
            return not rest or any(fnmatch.fnmatch(rest, a) or a.startswith(rest + "/") for a in ed_allow)
        return top not in ignore_top

    used = {}                            # 경로 → 쓰는 노트북들
    starts = {}
    for lang in ("", "en/"):
        books = sorted((ROOT / "notebooks" / lang).glob("*.ipynb"))
        if not books:
            fail("notebooks/%s 에 노트북이 없음" % lang)
        for b in books:
            code = _nb_code(b)
            name = lang + b.name
            if b.name.startswith("00_"):
                lst = nb_start_list(code)
                if lst is None:
                    fail("notebooks/%s 에서 모델 점검 목록(NEED = {...})을 찾지 못함" % name)
                    continue
                starts[lang] = lst
                for rel in lst:
                    used.setdefault(rel, []).append(name + " (점검 목록)")
                continue
            for rel in nb_models(code):
                used.setdefault(rel, []).append(name)
    # 한국어 · 영어가 같은 모델을 쓰나
    by_book = {}
    for rel, books in used.items():
        for b in books:
            by_book.setdefault(b, set()).add(rel)
    for b, rels in by_book.items():
        if b.startswith("en/"):
            ko = by_book.get(b[3:], set())
            if rels != ko:
                fail("notebooks/%s 와 한국어판이 부르는 모델이 다름: %s" % (b, sorted(rels ^ ko)))
    for rel, books in sorted(used.items()):
        who = ", ".join(sorted(set(books)))
        top = rel.split("/")[0]
        if not fetched(rel):
            fail("노트북이 쓰는 모델을 tools/fetch_models.py 가 받지 않음: models/%s (%s)" % (rel, who))
        if top in removed:
            fail("노트북이 쓰는 모델을 make_bundle.bat 이 번들에서 지움: models/%s (%s)" % (rel, who))
        if not covered_by_check(rel):
            fail("노트북이 쓰는 모델을 tools/check.py 가 보지 않음(NEED · NB_NEED): models/%s (%s)" % (rel, who))
    # 00_start 점검 목록이 다른 노트북의 모델을 다 담나
    for lang, lst in starts.items():
        mine = lambda b: b.startswith("en/") == (lang == "en/") and not b.endswith("(점검 목록)")
        for rel, books in sorted(used.items()):
            if not any(mine(b) for b in books):
                continue
            if not any(l == rel or rel.startswith(l + "/") or l.startswith(rel + "/") for l in lst):
                fail("notebooks/%s00_start.ipynb 모델 점검 목록에 없음: models/%s" % (lang, rel))
    # 허깅페이스 저장소 설명(tools/hf/README.md → Actions hf-models)의 폴더 표가 쓰는 폴더를 다 담나
    hf = read("tools/hf/README.md")
    tops = {r.split("/")[0] for r in list(used) + need_models()} | {"stt-sv", "tts-int8"}
    for top in sorted(tops - {"easydetect"}):
        if "`%s/`" % top not in hf:
            fail("tools/hf/README.md 폴더 표에 없음: %s/ (고친 뒤 Actions hf-models → readme)" % top)
    return len(used)


# ------------------------------------------------------------------ 5) 바깥 패키지
IMPORT_TO_PKG = {
    "cv2": "opencv", "PIL": "pillow", "yaml": "pyyaml", "sklearn": "scikit-learn",
    "serial": "pyserial", "multipart": "python-multipart", "huggingface_hub": "huggingface_hub",
    "openvino_genai": "openvino-genai", "openvino_tokenizers": "openvino-tokenizers",
    "sherpa_onnx": "sherpa-onnx", "sounddevice": "sounddevice", "onnxruntime": "onnxruntime",
}


def check_packages(mods):
    std = set(getattr(sys, "stdlib_module_names", ())) | {"__future__"}
    local = local_modules() | {p.name for p in ROOT.iterdir() if (p / "__init__.py").exists()}
    req = (read("requirements.txt") + "\n" + read("requirements.lock.txt")).lower().replace("_", "-")
    used = set()
    for m in mods:
        used |= imports_of(ROOT / (m + ".py"))
    for imp in sorted(used - std - local):
        pkg = IMPORT_TO_PKG.get(imp, imp).lower().replace("_", "-")
        if not re.search(r"(^|\n)\s*" + re.escape(pkg), req):
            # 윈도우 전용 · 선택 기능은 코드에서 try 로 감싸 둔다 — 경고만
            WARN.append("requirements 에 없는 패키지(선택 기능이면 무시): import %s" % imp)


# ------------------------------------------------------------------ 6) 제품 이름
# 이름처럼 보이지만 파일 형식 표시라 그대로 두는 것 (tools/rename_brand.py PROTECT 와 같다)
BRAND_KEEP = ["edge-lab-sound", "edge-lab-drive", "edge-lab-story", 'app: "edge-lab"', "edge-lab.classes"]
BRAND_SKIP = {"brand.py", "brand.json", "tools/rename_brand.py", "tools/release_check.py",
              "view_project/lib/brand.js"}
VENDOR = ("view_project/blockly/", "view_project/lib/swagger/", "view_project/lib/cm/", "models/")


def code_files():
    pats = ["*.py", "*.bat", "*.sh", "*.ps1", "tools/*.py", "tools/*.bat", "tools/*.ps1", "tools/*.sh",
            "view_project/*.html", "view_project/lib/*.js", "view_project/lib/*.css", "view_project/lib/*/*.js"]
    for pat in pats:
        for f in sorted(ROOT.glob(pat)):
            rel = f.relative_to(ROOT).as_posix()
            if rel in BRAND_SKIP or rel.startswith(VENDOR) or ".min." in rel:
                continue
            yield rel


def check_brand():
    sys.path.insert(0, str(ROOT))
    try:
        import brand
        b = brand.load()
    except Exception as ex:
        fail("brand.json 을 읽지 못했어요: %s" % ex)
        return
    import importlib.util
    spec = importlib.util.spec_from_file_location("rename_brand", ROOT / "tools" / "rename_brand.py")
    rb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rb)
    for prob in rb.check():
        fail(prob + "  →  python tools/rename_brand.py")
    words = {b["name"], b["name_ko"], b["slug"], b["work_folder"], b["appdata_folder"], b["tagline"], b["tagline_en"]}
    for rel in code_files():
        text = read(rel)
        for k in BRAND_KEEP + [b["repo_github"], b["repo_hf"]]:
            text = text.replace(k, "")
        for w in sorted(words):
            if w and w in text:
                n = text[:text.index(w)].count("\n") + 1
                fail("코드에 제품 이름을 직접 씀(brand.py · EL_BRAND 로): %s:%d  '%s'" % (rel, n, w))
                break
    for f in sorted((ROOT / "view_project").glob("*.html")):
        t = f.read_text(encoding="utf-8")
        i = t.find("/lib/brand.js")
        first = min([x for x in (t.find("/lib/embed.js"), t.find("/lib/boot.js"), t.find("/lib/shell.js")) if x >= 0] or [len(t)])
        if i < 0 or i > first:
            fail("화면이 lib/brand.js 를 먼저 읽지 않음: view_project/" + f.name)
    bat = read("tools/make_bundle.bat")
    copy, verify, _ = bundle_lists()
    for need in ("brand.json",):
        if need not in copy or need not in verify:
            fail("번들 복사 · 확인 목록에 없음: " + need)


# ------------------------------------------------------------------ 7) 한글 경로
def check_unicode_paths():
    """MediaPipe 에 모델 '경로' 를 넘기지 않는다 — 한글 폴더(바탕 화면)에 풀면 C++ 가 경로를 못 읽고
    프로세스를 끝낸다(배포판 자동 시험이 잡았다). 파이썬으로 읽은 바이트(model_asset_buffer)를 넘긴다."""
    files = [p for p in ROOT.glob("*.py")] + list(ROOT.glob("notebooks/**/*.ipynb"))
    for f in files:
        if "model_asset_path" in f.read_text(encoding="utf-8", errors="replace"):
            fail("MediaPipe 에 경로를 넘김(model_asset_path) — 한글 폴더에서 서버가 죽는다, "
                 "model_asset_buffer=파일.read_bytes() 로: " + f.relative_to(ROOT).as_posix())


def main():
    os.chdir(ROOT)
    mods = check_python()
    routes = check_pages()
    check_assets(routes)
    check_models()
    nbm = check_notebook_models()
    check_packages(mods)
    check_brand()
    check_unicode_paths()
    print("배포 점검 — 서버 파일 %d 개 · 화면 %d 개 · 필수 모델 %d 개 · 노트북 모델 %d 개"
          % (len(mods), len(routes), len(need_models()), nbm))
    for w in dict.fromkeys(WARN):
        print("  WARN  " + w)
    for f in FAIL:
        print("  FAIL  " + f)
    print("  결과: %s (FAIL %d · WARN %d)" % ("통과" if not FAIL else "실패", len(FAIL), len(WARN)))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
