# -*- coding: utf-8 -*-
# edge-lab : Google Fonts 로컬화 (셋업 시 1회, 인터넷 필요)
# css2 스타일시트를 받아 모든 woff2 서브셋을 view_project/fonts/ 에 저장하고
# url()을 로컬 경로(/fonts/...)로 재작성한 fonts.css 를 생성한다.
import re
import urllib.request
from pathlib import Path

CSS_URL = ("https://fonts.googleapis.com/css2"
           "?family=Gowun+Batang:wght@400;700&family=Gowun+Dodum&display=swap")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")  # woff2 응답 유도
OUT = Path("view_project/fonts")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    css = fetch(CSS_URL).decode("utf-8")
    urls = sorted(set(re.findall(r"url\((https://[^)]+\.woff2)\)", css)))
    print(f"woff2 {len(urls)}개 다운로드")
    for i, url in enumerate(urls):
        name = url.rsplit("/", 2)[-2] + "-" + url.rsplit("/", 1)[-1]  # 고유 파일명
        path = OUT / name
        if not path.exists():
            path.write_bytes(fetch(url))
        css = css.replace(url, f"/fonts/{name}")
        if (i + 1) % 40 == 0:
            print(f"  {i + 1}/{len(urls)}")
    (OUT / "fonts.css").write_text(css, encoding="utf-8")
    total = sum(f.stat().st_size for f in OUT.glob("*.woff2")) / 1e6
    print(f"완료: view_project/fonts/ ({len(urls)}개, {total:.1f}MB) + fonts.css")


if __name__ == "__main__":
    main()
