# shopping-reels-host

인스타 릴스 예약 게시 큐. `queue/<이름>/` 에 `video.mp4`, `caption.txt`, `schedule.json` 을 두면
GitHub Actions 가 10분마다 확인해 `publish_at` 이 지난 항목을 게시하고, 영상 파일은 삭제한다.
Secrets: `INSTAGRAM_ACCESS_TOKEN`, `IG_USER_ID`. 실행은 GitHub 이 지연시킬 수 있다(수 분~수십 분).
