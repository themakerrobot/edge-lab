# swagger-ui (vendored)

`/docs` 가 쓰는 Swagger UI 다. **여기 두는 이유가 있다.**

FastAPI 가 기본으로 만들어 주는 `/docs` 는 이 두 파일을
`https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/...` 에서 받아 온다. 그래서
인터넷이 없는 교실 PC 에서는 홈의 [API Docs] 를 눌러도 **흰 화면**만 떴다.
"인터넷 없이 내 컴퓨터에서 돌아요" 라고 적어 둔 프로그램에서 그 한 장만
인터넷이 필요했던 셈이다. 받아서 같이 넣고, `main.py` 가 이 경로를 가리킨다.

| | |
|---|---|
| 출처 | npm `swagger-ui-dist@5.33.0` (FastAPI 기본값이 가리키던 바로 그 묶음) |
| 라이선스 | Apache-2.0 — `LICENSE` 와 `swagger-ui-bundle.js.LICENSE.txt` |
| 올릴 때 | `npm pack swagger-ui-dist@5` 로 받아 `swagger-ui-bundle.js` · `swagger-ui.css` · `LICENSE` 만 덮어쓴다 |

파일은 손대지 않은 원본이다. 고치지 말 것.
