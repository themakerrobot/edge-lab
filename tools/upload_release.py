# -*- coding: utf-8 -*-
"""배포판 올리기 — make_bundle.bat 이 만든 zip 을 허깅페이스 모델 저장소의 release/ 에 올린다.

    tools\\make_bundle.bat 1.0.0                      먼저 배포판을 만든다 → dist\\<slug>-1.0.0.zip
    python tools\\upload_release.py                   dist\\ 의 가장 새 zip 을 올린다
    python tools\\upload_release.py dist\\<slug>-1.0.0.zip
    python tools\\upload_release.py --dry-run         올리지 않고 무엇을 할지만 보인다

올라가는 곳은 brand.json 의 repo_hf (설치가 모델을 받는 그 저장소)의 release/ 폴더다.
  release/<slug>-<버전>.zip          배포판
  release/<slug>-<버전>.zip.sha256   받은 파일이 망가지지 않았는지 확인용
  release/latest.json                가장 최근 배포판 (버전 · 파일 · 크기 · sha256 · 링크)
setup_deploy.ps1 은 release/ 를 받지 않는다(받기 제외 목록) — 설치할 때 zip 까지 받지 않게.

GitHub 릴리즈는 파일 하나가 2GiB 까지라 VLM 이 든 배포판(5GB 남짓)을 못 올린다. 허깅페이스는 그런 제한이 없고,
공개 저장소는 로그인 없이 링크로 받는다(브라우저가 이어받기도 한다).

쓰기 권한: `hf auth login` (또는 huggingface-cli login) 으로 한 번 로그인하거나, 환경변수 HF_TOKEN 에 쓰기 토큰.
큰 파일을 짧은 시간에 여러 번 올리면 허깅페이스가 막을 수 있다 — 시험 빌드는 올리지 말고 배포할 때만 올린다.
"""
import argparse
import glob
import hashlib
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import brand  # noqa: E402


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def newest_zip():
    found = sorted(glob.glob(os.path.join(ROOT, "dist", brand.SLUG + "-*.zip")), key=os.path.getmtime)
    return found[-1] if found else None


def main():
    ap = argparse.ArgumentParser(description="make_bundle 이 만든 배포판 zip 을 허깅페이스 release/ 에 올린다")
    ap.add_argument("zip", nargs="?", help="올릴 zip (생략하면 dist\\ 의 가장 새 것)")
    ap.add_argument("--dry-run", action="store_true", help="올리지 않고 할 일만 보인다")
    ap.add_argument("--notes-out", help="GitHub 릴리즈 노트에 붙일 글을 이 파일에 쓴다 (자동 만들기가 쓴다)")
    a = ap.parse_args()

    path = a.zip or newest_zip()
    if not path or not os.path.isfile(path):
        print("올릴 zip 이 없어요 — 먼저 tools\\make_bundle.bat <버전> 으로 만들어 주세요.")
        return 1
    name = os.path.basename(path)
    m = re.fullmatch(re.escape(brand.SLUG) + r"-(.+)\.zip", name)
    if not m:
        print("파일 이름이 %s-<버전>.zip 모양이 아니에요: %s" % (brand.SLUG, name))
        return 1
    version = m.group(1)
    repo = brand.REPO_HF
    size = os.path.getsize(path)
    print("배포판  %s  (%.2f GB)" % (name, size / 1e9))
    print("sha256 계산 중 ...")
    digest = sha256(path)
    url = "https://huggingface.co/%s/resolve/main/release/%s?download=true" % (repo, name)
    latest = {"name": brand.NAME, "version": version, "file": "release/" + name, "size": size,
              "sha256": digest, "url": url, "uploaded": time.strftime("%Y-%m-%d %H:%M:%S")}
    print("sha256  " + digest)
    print("올릴 곳  https://huggingface.co/%s/tree/main/release" % repo)
    if a.dry_run:
        print("(--dry-run — 올리지 않았어요)")
        return 0

    try:
        from huggingface_hub import CommitOperationAdd, HfApi
    except ImportError:
        print("huggingface_hub 가 없어요 — venv\\Scripts\\pip install huggingface_hub")
        return 1
    api = HfApi()
    try:
        who = api.whoami()
    except Exception:
        print("허깅페이스에 로그인되어 있지 않아요 — `hf auth login` 으로 쓰기 토큰을 넣거나 HF_TOKEN 을 정해 주세요.")
        return 1
    print("로그인  %s" % who.get("name", "?"))

    side = path + ".sha256"
    with open(side, "w", encoding="utf-8", newline="\n") as f:
        f.write("%s  %s\n" % (digest, name))
    msg = "release %s %s" % (brand.NAME, version)
    print("올리는 중 ... (크기에 따라 오래 걸려요 — 끊기면 다시 돌리면 이미 올라간 조각은 건너뛴다)")
    # 셋을 커밋 하나로 — 중간에 끊겨도 zip 없이 latest.json 만 바뀌는 일이 없다
    api.create_commit(repo_id=repo, commit_message=msg, operations=[
        CommitOperationAdd(path_in_repo="release/" + name, path_or_fileobj=path),
        CommitOperationAdd(path_in_repo="release/" + name + ".sha256", path_or_fileobj=side),
        CommitOperationAdd(path_in_repo="release/latest.json",
                           path_or_fileobj=json.dumps(latest, ensure_ascii=False, indent=2).encode("utf-8")),
    ])

    notes = ("**다운로드**: [%s](%s) (%.1f GB)  \n"
             "sha256: `%s`  \n"
             "압축을 풀고 %s.exe(또는 run.bat)를 두 번 누르면 됩니다. 코딩 실습은 lab.bat, 점검은 bundle_check.bat\n"
             ) % (name, url, size / 1e9, digest, brand.SLUG)
    print("\n다 올렸어요.")
    print("받는 링크  " + url)
    print("\nGitHub 릴리즈 노트에 붙일 글:\n\n" + notes)
    if a.notes_out:
        with open(a.notes_out, "w", encoding="utf-8", newline="\n") as f:
            f.write(notes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
