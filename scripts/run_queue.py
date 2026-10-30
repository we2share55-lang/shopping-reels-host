#!/usr/bin/env python
"""queue/<이름>/ 에서 게시 시각이 지난 pending 항목을 인스타 릴스로 게시한다.

queue/<이름>/video.mp4, caption.txt, schedule.json (+ cover.jpg 선택: 릴스 커버) {"publish_at": ISO8601, "status": "pending"}
성공하면 status=done + permalink 기록 후 video.mp4 삭제. 실패하면 status=failed (중복 게시 방지, 수동 확인 후 pending 으로 되돌린다).
DRY_RUN=1 이면 시각과 상관없이 점검만 하고 상태를 바꾸지 않는다.
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = os.environ.get("GITHUB_REPOSITORY", "we2share55-lang/shopping-reels-host")
DRY = os.environ.get("DRY_RUN") == "1"
now = datetime.now(timezone.utc)

for sched in sorted((ROOT / "queue").glob("*/schedule.json")):
    d = sched.parent
    meta = json.loads(sched.read_text(encoding="utf-8"))
    if meta.get("status") != "pending":
        continue
    due = datetime.fromisoformat(meta["publish_at"])
    if not DRY and now < due:
        print(f"[{d.name}] 대기 중 (예정 {meta['publish_at']})")
        continue
    url = f"https://raw.githubusercontent.com/{REPO}/main/queue/{d.name}/video.mp4"
    cmd = [sys.executable, str(ROOT / "scripts/publish_instagram_reel.py"),
           "--video-url", url, "--caption-file", str(d / "caption.txt")]
    cover = d / "cover.jpg"
    if cover.exists():
        cmd += ["--cover-url", f"https://raw.githubusercontent.com/{REPO}/main/queue/{d.name}/cover.jpg"]
    if not DRY:
        cmd.append("--publish")
    print(f"[{d.name}] {'점검' if DRY else '게시'} 시작")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    print(r.stdout)
    print(r.stderr, file=sys.stderr)
    if DRY:
        continue
    if r.returncode == 0:
        m = re.search(r"https://www\.instagram\.com/\S+", r.stdout)
        meta.update(status="done", published_at=now.isoformat(), permalink=m.group(0) if m else "")
        (d / "video.mp4").unlink(missing_ok=True)
        cover.unlink(missing_ok=True)
    else:
        meta.update(status="failed", failed_at=now.isoformat())
    sched.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
