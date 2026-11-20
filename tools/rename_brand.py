# -*- coding: utf-8 -*-
"""제품 이름 맞추기 — brand.json 을 고친 뒤 한 번 돌린다.

    python tools/rename_brand.py           brand.json 대로 맞춘다
    python tools/rename_brand.py --check   맞는지만 본다 (틀리면 끝 코드 1, release_check 가 부른다)

코드(서버 · 화면)는 실행할 때 brand.json 에서 이름을 읽는다 — 서버는 brand.py, 화면은 lib/brand.js.
이 도구가 하는 일은 셋이다.
  1) view_project/lib/brand.js 를 brand.json 에서 다시 만든다 (화면이 읽는 사본)
  2) 실행하면서 읽을 수 없는 글(README · INSTALL · 매뉴얼 · 노트북 · 설치 스크립트의 주소)에서
     지난번 이름 · 부제(tools/brand_applied.json)를 새 것으로 바꾼다
  3) 아이콘 파일(<slug>.ico) 이름을 바꾸고, 이번 이름을 tools/brand_applied.json 에 적는다

바꾸지 않는 것 — 이름처럼 보이지만 파일 형식 표시라 바꾸면 저장해 둔 파일 · 모델과 어긋난다:
  edge-lab-sound · edge-lab-drive · edge-lab-story (저장 파일 형식), app: "edge-lab" (가르친 AI),
  edge-lab.classes (마스크 모델 안의 메타데이터), tools/score_check.py (로봇과 같은 파일)
"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import brand as BR  # noqa: E402

APPLIED = os.path.join(ROOT, "tools", "brand_applied.json")
JS = os.path.join(ROOT, "view_project", "lib", "brand.js")

PROTECT = ["edge-lab-sound", "edge-lab-drive", "edge-lab-story", 'app: "edge-lab"', "edge-lab.classes",
           "----edgelab"]
SKIP_FILES = {"tools/score_check.py", "tools/brand_applied.json", "brand.json", "tools/rename_brand.py",
              "brand.py", "view_project/lib/brand.js"}
SKIP_DIRS = ("models/", "view_project/blockly/", "view_project/lib/swagger/", "view_project/lib/cm/",
             "view_project/fonts/", "view_project/assets/")
TEXT_EXT = (".md", ".py", ".js", ".html", ".css", ".bat", ".ps1", ".sh", ".ipynb", ".txt", ".json", ".spec")
HANGUL = re.compile(r"[가-힣]")


def js_text(b):
    data = json.dumps(b, ensure_ascii=False, indent=1)
    return (
        "/* 제품 이름 — brand.json 에서 tools/rename_brand.py 가 만든다. 손으로 고치지 않는다.\n"
        " *   EL_BRAND.label()  화면에 보이는 이름 (한국어 화면은 name_ko, 영어 화면은 name)\n"
        " *   EL_BRAND.tag()    부제\n"
        " *   EL_BRAND.ko(\"을\") 한국어 이름 + 맞는 조사 */\n"
        "window.EL_BRAND = " + data + ";\n"
        "(function (B) {\n"
        "  function lang() { try { return localStorage.getItem(\"vapiLang\") === \"en\" ? \"en\" : \"ko\"; } catch (e) { return \"ko\"; } }\n"
        "  B.label = function (L) { return (L || lang()) === \"en\" ? B.name : B.name_ko; };\n"
        "  B.tag = function (L) { return (L || lang()) === \"en\" ? B.tagline_en : B.tagline; };\n"
        "  function batchim(w) {\n"
        "    var c = String(w).replace(/\\s+$/, \"\").slice(-1);\n"
        "    if (c >= \"가\" && c <= \"힣\") return (c.charCodeAt(0) - 0xAC00) % 28 !== 0;\n"
        "    return \"bklmnpt\".indexOf(c.toLowerCase()) >= 0;\n"
        "  }\n"
        "  var PAIRS = { \"을\": [\"을\", \"를\"], \"를\": [\"을\", \"를\"], \"은\": [\"은\", \"는\"], \"는\": [\"은\", \"는\"],\n"
        "               \"이\": [\"이\", \"가\"], \"가\": [\"이\", \"가\"], \"과\": [\"과\", \"와\"], \"와\": [\"과\", \"와\"] };\n"
        "  B.ko = function (p) {\n"
        "    var pr = PAIRS[p || \"을\"] || [p, p], n = B.name_ko, last = n.slice(-1);\n"
        "    return n + (last >= \"가\" && last <= \"힣\" ? \"\" : \" \") + (batchim(n) ? pr[0] : pr[1]);\n"
        "  };\n"
        "})(window.EL_BRAND);\n"
    )


def gh_anchor(title):
    """GitHub 제목 앵커 — 소문자, 공백은 -, 글자 · 숫자 · - 말고는 뺀다."""
    t = title.strip().lower()
    t = re.sub(r"[^\w\- 가-힣]", "", t)
    return t.replace(" ", "-")


def tracked_files():
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split("\n")
    for rel in out:
        if not rel or rel in SKIP_FILES or rel.startswith(SKIP_DIRS) or not (rel.endswith(TEXT_EXT) or rel == "NOTICE"):
            continue
        if rel.endswith((".min.js",)) or "tf.min" in rel:
            continue
        yield rel


def _josa(new_ko, particle):
    if particle in ("으로", "로"):                      # 받침이 없거나 ㄹ 받침이면 '로'
        c = new_ko.rstrip()[-1]
        rieul = ("가" <= c <= "힣" and (ord(c) - 0xAC00) % 28 == 8) or c.lower() == "l"
        return "으로" if BR._has_batchim(new_ko) and not rieul else "로"
    pairs = {"을": ("을", "를"), "를": ("을", "를"), "은": ("은", "는"), "는": ("은", "는"),
             "이": ("이", "가"), "가": ("이", "가"), "과": ("과", "와"), "와": ("과", "와")}
    if particle not in pairs:
        return particle
    a, b = pairs[particle]
    return a if BR._has_batchim(new_ko) else b


def rewrite(text, old, new):
    """지난 이름(old) → 새 이름(new). 특정한 모양부터 바꾸고, 남은 이름은 줄 언어로 고른다."""
    keep = {}
    for i, p in enumerate(PROTECT):
        tok = "\x00P%d\x00" % i
        keep[tok] = p
        text = text.replace(p, tok)
    rep = []
    # 부제 (README 첫머리 등) — 글 그대로 바꾼다
    rep.append((re.escape(old["tagline"]), new["tagline"].replace("\\", "\\\\")))
    rep.append((re.escape(old["tagline_en"]), new["tagline_en"].replace("\\", "\\\\")))
    # 저장소 주소 · 폴더
    rep.append((re.escape(old["repo_github"]), new["repo_github"]))
    rep.append((re.escape(old["repo_hf"]), new["repo_hf"]))
    old_repo, new_repo = old["repo_github"].split("/")[-1], new["repo_github"].split("/")[-1]
    rep.append((r"(?<=\bcd )" + re.escape(old_repo) + r"\b", new_repo))
    rep.append((re.escape(old["work_folder"]), new["work_folder"]))
    rep.append((r"\b" + re.escape(old["appdata_folder"]) + r"\b", new["appdata_folder"]))
    rep.append((r"\b" + re.escape(old["appdata_folder"].lower()) + r"\b", new["appdata_folder"].lower()))
    # 파일 이름(slug)
    s_old, s_new = re.escape(old["slug"]), new["slug"]
    for pat in (s_old + r"(?=\.exe|\.ico|\*\.exe|-%VERSION%|-<VERSION>|-\d)",
                r"(?<=build\\)" + s_old, r"(?<=-C build )" + s_old, r"(?<=--name )" + s_old):
        rep.append((pat, s_new))
    # 문서 앵커 (README · 매뉴얼)
    rep.append((r"(?<=#)" + re.escape(gh_anchor(old["name"])) + r"-(english|user-guide)",
                gh_anchor(new["name"]) + r"-\1"))
    rep.append((r'(?<=name=")' + re.escape(gh_anchor(old["name"])) + r"-(english|user-guide)",
                gh_anchor(new["name"]) + r"-\1"))
    rep.append((r"\(#" + re.escape(gh_anchor(old["name_ko"])) + r"-사용-설명서\)",
                "(#" + gh_anchor(new["name_ko"]) + "-사용-설명서)"))
    rep.append((r"\(#" + re.escape(gh_anchor(old["name"])) + r"\)", "(#" + gh_anchor(new["name"]) + ")"))   # README 첫 제목(# <name>)
    for pat, sub in rep:
        text = re.sub(pat, sub, text)
    # 남은 이름 — 한글이 있는 줄은 한국어 이름(조사까지), 아니면 영어 이름
    ko_rx = re.compile(re.escape(old["name_ko"]) + r"(`?)( ?)(으로|로|을|를|은|는|이|가|과|와)?(?![\w-])")
    en_rx = re.compile(re.escape(old["name"]) + r"(?![\w-])")
    lines = text.split("\n")
    for i, ln in enumerate(lines):
        if HANGUL.search(ln):
            def ko_sub(m):
                tick, sp, part = m.group(1), m.group(2), m.group(3)
                if not part:
                    return new["name_ko"] + tick + sp            # 뒤 공백 · 백틱은 그대로
                if tick:
                    return new["name_ko"] + tick + sp + _josa(new["name_ko"], part)
                sep = "" if HANGUL.match(new["name_ko"][-1]) else " "
                return new["name_ko"] + sep + _josa(new["name_ko"], part)
            ln = ko_rx.sub(ko_sub, ln)
        ln = en_rx.sub(new["name"].replace("\\", "\\\\"), ln)
        lines[i] = ln
    text = "\n".join(lines)
    for tok, p in keep.items():
        text = text.replace(tok, p)
    return text


def load_applied():
    if not os.path.isfile(APPLIED):
        return None
    with open(APPLIED, encoding="utf-8") as f:
        return json.load(f)


def check():
    b, problems = BR.load(), []
    if not os.path.isfile(JS) or open(JS, encoding="utf-8").read() != js_text(b):
        problems.append("view_project/lib/brand.js 가 brand.json 과 다름")
    if load_applied() != b:
        problems.append("tools/brand_applied.json 이 brand.json 과 다름 (문서 · 노트북에 아직 지난 이름)")
    for k, v in b.items():
        if any(ch in v for ch in '"\\<>&|^%'):
            problems.append("brand.json %s 에 쓸 수 없는 글자(\" \\ < > & | ^ %%)" % k)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", b["slug"]):
        problems.append("brand.json slug 는 소문자 · 숫자 · - 만 (파일 이름 · 번들 이름에 쓴다)")
    for k in ("work_folder", "appdata_folder"):
        if re.search(r'[/\\:*?]', b[k]):
            problems.append("brand.json %s 에 폴더 구분 글자(/ \\ : * ?)를 쓸 수 없어요" % k)
    for k in ("repo_github", "repo_hf"):
        if not re.fullmatch(r"[\w.-]+/[\w.-]+", b[k]):
            problems.append("brand.json %s 는 '주인/이름' 모양이어야 해요" % k)
    return problems


def main():
    if "--check" in sys.argv:
        p = check()
        for x in p:
            print("  FAIL  " + x + "  →  python tools/rename_brand.py")
        return 1 if p else 0
    bad = [x for x in check() if "brand.js" not in x and "brand_applied" not in x]
    if bad:                                             # 값이 틀리면 아무것도 바꾸지 않는다
        for x in bad:
            print("  FAIL  " + x)
        return 1
    new = BR.load()
    old = load_applied() or new
    changed = []
    if old != new:
        for rel in tracked_files():
            path = os.path.join(ROOT, rel)
            try:
                with open(path, encoding="utf-8", newline="") as f:
                    src = f.read()
            except (UnicodeDecodeError, OSError):
                continue
            out = rewrite(src, old, new)
            if out != src:
                with open(path, "w", encoding="utf-8", newline="") as f:
                    f.write(out)
                changed.append(rel)
        if old["slug"] != new["slug"] and os.path.isfile(os.path.join(ROOT, old["slug"] + ".ico")):
            subprocess.run(["git", "mv", old["slug"] + ".ico", new["slug"] + ".ico"], cwd=ROOT, check=True)
            changed.append(new["slug"] + ".ico")
    with open(JS, "w", encoding="utf-8", newline="\n") as f:
        f.write(js_text(new))
    with open(APPLIED, "w", encoding="utf-8", newline="\n") as f:
        json.dump(new, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("이름: %s / %s  (파일 %s)" % (new["name"], new["name_ko"], new["slug"]))
    print("바꾼 파일 %d 개" % len(changed) + ("" if not changed else ":\n  " + "\n  ".join(changed)))
    if old["repo_github"] != new["repo_github"] or old["repo_hf"] != new["repo_hf"]:
        print("저장소 주소가 바뀌었어요 — GitHub 저장소 이름 바꾸기 · HF 새 저장소 올리기는 직접 해 주세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
