# 보안 정책 / Security policy

보안 취약점을 발견하셨다면 **공개 이슈 대신** 이 레포의 **Security → Report a vulnerability**(비공개 취약점 신고)로 알려 주세요. 확인 후 답변드리고, 고친 버전을 릴리스하면서 함께 안내합니다.

If you find a security issue, please **do not open a public issue**. Use **Security → Report a vulnerability** in this repository to report it privately. We will reply after checking and announce the fix with a release.

cache-autopsy는 네트워크를 쓰지 않는 오프라인 CLI이며 API 키도 필요 없습니다. 다만 입력 로그에 들어 있는 프롬프트·개인정보는 출력에 그대로 찍힐 수 있으니, 결과를 공유할 때는 `--redact` 를 쓰세요. / cache-autopsy is an offline CLI that makes no network calls and needs no API keys. Prompts and personal data inside your input logs can appear in the output, so use `--redact` when sharing results.
