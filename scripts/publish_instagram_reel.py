#!/usr/bin/env python
"""인스타그램 릴스 게시 (Instagram Graph API: 컨테이너 생성 -> 처리 대기 -> 게시).

  # 점검만 (기본): 토큰/영상 URL/캡션을 확인하고 아무것도 올리지 않는다
  python scripts/publish_instagram_reel.py --video-url https://.../reel.mp4 --caption-file projects/battlerope/caption.txt
  # 실제 게시
  python scripts/publish_instagram_reel.py --video-url ... --caption-file ... --publish

Graph API 는 **로컬 파일이 아니라 공개 mp4 URL** 만 받는다. 영상을 어디에 올릴지는 docs/upload.md 참고.
`.env` 에 INSTAGRAM_ACCESS_TOKEN, IG_USER_ID 가 필요하다 (.env.example).

출처: myparang_marketing_instagram @ scripts/render-and-publish-reel.sh 의 [4/4] 단계를 파이썬으로 옮김
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GRAPH = "https://graph.instagram.com/v21.0"

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


def load_env(path: Path) -> None:
    """.env 를 읽어 os.environ 에 채운다 (이미 있는 값은 건드리지 않는다)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def call(method: str, url: str, params: dict) -> dict:
    data = urllib.parse.urlencode(params).encode("utf-8") if method == "POST" else None
    if method == "GET":
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = json.loads(e.read().decode("utf-8", "replace") or "{}")
    if "error" in body:
        raise SystemExit(f"Graph API 오류: {json.dumps(body['error'], ensure_ascii=False)}")
    return body


def main() -> None:
    ap = argparse.ArgumentParser(description="인스타그램 릴스 게시")
    ap.add_argument("--video-url", required=True, help="공개 접근 가능한 mp4 URL")
    ap.add_argument("--caption-file", required=True, help="UTF-8 캡션 txt")
    ap.add_argument("--thumb-offset-ms", type=int, default=3200, help="커버로 쓸 프레임 시각(ms)")
    ap.add_argument("--publish", action="store_true", help="실제로 게시한다 (없으면 점검만)")
    ap.add_argument("--no-ai-label", action="store_true", help="AI 라벨(is_ai_generated)을 켜지 않는다")
    args = ap.parse_args()

    load_env(REPO / ".env")
    token, user = os.environ.get("INSTAGRAM_ACCESS_TOKEN"), os.environ.get("IG_USER_ID")
    if not token or not user:
        raise SystemExit("INSTAGRAM_ACCESS_TOKEN / IG_USER_ID 가 .env 에 없습니다")
    caption = Path(args.caption_file).read_text(encoding="utf-8").strip()
    if not caption:
        raise SystemExit("캡션이 비어 있습니다")

    # 영상 URL 이 실제로 열리는지 먼저 확인한다 (Graph API 는 실패 사유를 잘 알려주지 않는다)
    try:
        head = urllib.request.Request(args.video_url, method="HEAD")
        with urllib.request.urlopen(head, timeout=30) as r:
            print(f"영상 URL 확인: HTTP {r.status}, {r.headers.get('Content-Type')}, "
                  f"{r.headers.get('Content-Length')} bytes")
    except Exception as e:  # noqa: BLE001
        raise SystemExit(f"영상 URL 에 접근할 수 없습니다: {e}")

    print(f"캡션 {len(caption)}자:\n---\n{caption}\n---")
    if not args.publish:
        print("--publish 없이 실행됨 — 여기서 멈춤 (아무것도 게시하지 않았습니다)")
        return

    params = {
        "media_type": "REELS", "video_url": args.video_url, "caption": caption,
        "thumb_offset": args.thumb_offset_ms, "access_token": token,
    }
    # 기본으로 AI 라벨을 건다. 협찬 광고(유료 파트너십) 라벨은 Content Publishing API 가 지원하지 않는다
    # (is_paid_partnership -> "Unsupported Param", 2026-10-27 확인). 게시 후 앱에서 직접 켠다.
    if not args.no_ai_label:
        params["is_ai_generated"] = "true"
    print(f"라벨: AI={'is_ai_generated' in params} (협찬 광고 라벨은 API 미지원 -> 게시 후 앱에서 직접 켜기)")
    container = call("POST", f"{GRAPH}/{user}/media", params)["id"]
    print(f"컨테이너 생성: {container}")

    status = "UNKNOWN"
    for i in range(1, 21):
        status = call("GET", f"{GRAPH}/{container}",
                      {"fields": "status_code", "access_token": token}).get("status_code", "UNKNOWN")
        print(f"  status ({i}): {status}")
        if status == "FINISHED":
            break
        if status == "ERROR":
            raise SystemExit("컨테이너 처리 실패")
        time.sleep(8)
    if status != "FINISHED":
        raise SystemExit("처리 시간 초과")

    media_id = call("POST", f"{GRAPH}/{user}/media_publish",
                    {"creation_id": container, "access_token": token})["id"]
    link = call("GET", f"{GRAPH}/{media_id}",
                {"fields": "permalink", "access_token": token}).get("permalink")
    print(f"게시 완료: media id {media_id}\n{link}")


if __name__ == "__main__":
    main()
