# Aspen Co-pilot

[English](README.md) · [繁體中文](README.zh-TW.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · **한국어** · [Español](README.es.md) · [Português](README.pt-BR.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Русский](README.ru.md)

이 문서는 번역본입니다. 내용이 다를 경우 [영문판](README.md)이 우선합니다.

**AI 에이전트가 여러분의 Aspen Plus에서 화학 공정을 설계하고, 시뮬레이션하고, 최적화합니다.
모든 단계는 여러분에게 보이며, 결정은 언제나 여러분이 내립니다.**

Aspen Co-pilot은 Model Context Protocol(MCP)을 통해 Aspen Plus를 Claude Code, Codex 같은
AI 에이전트와 연결합니다. 공정을 평소 쓰는 말로 설명하면 에이전트가 Aspen에서 작업을 수행하고,
여러분은 그 결과를 검토합니다.

Windows 전용입니다. 라이선스가 있는 Aspen Plus를 직접 준비해야 하며, 이 프로젝트에는 포함되어 있지 않습니다.
개발: NCKU GESE Lab.

## 할 수 있는 일

**공정을 구축하고 변경합니다.** 설명만으로 공정 흐름도를 만듭니다. 성분, 물성 모델, 반응,
단위 조작, 스트림을 구성하고, 모든 파라미터를 설정·조정하며, 시뮬레이션을 실행하고 결과를
읽어 옵니다. Aspen Plus 기능 대부분을 사용할 수 있습니다.

**문헌에서 작동하는 모델까지.** AI 클라이언트의 조사 도구를 활용하면 에이전트가 논문과 특허에서
반응 속도론, 운전 조건, 공정 경로를 수집하고, 출처와 대조해 확인할 수 있는 Aspen 모델로 구축합니다.

**실행이 실패하는 이유를 찾아냅니다.** 실행 전에 Aspen에 아직 부족한 입력을 확인하고, 실패한 실행과
경고를 설명하며 이를 수정합니다. 효과가 있었던 수정은 여러분의 컴퓨터에 저장되어 다음에 활용됩니다.

**공정을 최적화합니다.** 하나의 도구에 9가지 알고리즘을 담았습니다. NSGA-II, NSGA-III, PSO,
DE/GDE3, 경사법(SLSQP), 그리드 탐색, 그리고 3가지 베이지안 방법(BO, CBO, AFM-CBO)으로 제약 조건이
있는 단일 목적 및 다목적 최적화 문제를 다룹니다. 또한 열 통합을 위한 핀치 분석과 열교환기 매칭
제안도 제공합니다.

**추측하지 않고 찾아봅니다.** 모든 블록, 스트림, 설정 항목에 대한 참고 문서
([aspen-mcp/docs](aspen-mcp/docs/aspen.md))가 있으며, 에이전트는 항목을 변경하기 전에 이를 참조합니다.

## 사람과 함께 일하도록 설계

소프트웨어를 혼자 조작하는 LLM 에이전트는 신뢰하기 어렵습니다. 무엇을 왜 바꿨는지 볼 수 없고,
실수가 모델에 반영되기 전에 막을 수도 없습니다. Aspen Co-pilot은 Aspen Plus 옆에 띄우는 데스크톱
창인 **Aspen Workbench**로 이 문제를 해결합니다.

- **AI가 하는 일을 봅니다.** 공정 흐름도, 계산 결과, 그리고 AI가 만든 모든 변경 사항과 그 이유가
  실시간으로 갱신됩니다. 어떤 변경이든 되돌릴 수 있고, 복원 지점으로 돌아갈 수도 있습니다.
- **주도권은 여러분에게 있습니다.** 검토 모드에서는 AI의 변경이 여러분의 승인을 기다립니다. 큰 변경은
  제안으로 도착하며, 실행할 수 있는 사람은 여러분뿐입니다.
- **블록 프로그램으로 작업을 직접 정의합니다.** 파라미터 스윕, 계산, 표, 차트, 최적화 연구를
  여러분만의 변수·목적 함수·제약 조건과 함께 드래그 앤 드롭 블록으로 코드 없이 조립할 수 있습니다.
  AI가 프로그램을 작성하면 여러분이 편집할 수도 있고, 여러분이 만든 프로그램을 AI가 실행할 수도 있습니다.
- **함께 작업합니다.** 아무 스트림이나 블록을 클릭해 **Ask AI**로 질문할 수 있습니다. 학습 모드에서는
  AI가 각 변경의 바탕이 되는 공정 원리를 설명합니다.

워크벤치 화면은 영어와 중국어만 지원합니다(한국어는 지원하지 않습니다). AI 클라이언트 없이도
실행됩니다(`%USERPROFILE%\.aspen-mcp\aspen-workbench.cmd`: 네트워크 불필요, 토큰 불필요).

## 설치

필요한 것은 **Windows**, 라이선스가 있는 **Aspen Plus**, 그리고 **[uv](https://docs.astral.sh/uv/)**
입니다(`winget install --id=astral-sh.uv -e`. Python은 uv가 함께 설치합니다).

**Claude Code:**

```bash
claude plugin marketplace add nckugese/Aspen_Co-pilot
claude plugin install aspen-plus@aspen-mcp
```

**Codex:** `codex plugin marketplace add nckugese/Aspen_Co-pilot`을 실행한 뒤, `/plugins`에서
**Aspen Plus**를 활성화하고 `/hooks`에서 해당 훅을 신뢰하도록 설정합니다.

그런 다음 클라이언트를 다시 시작합니다. 첫 세션에서 설치 마무리를 제안합니다(약 200 MB: Python,
서버, 최적화 라이브러리). 수락한 뒤 한 번 더 다시 시작합니다. `/aspen-doctor`로
결과를 확인할 수 있습니다.

플러그인은 하나의 릴리스에 고정되어 있으므로, 업데이트하기 전에는 아무것도 바뀌지 않습니다
(`claude plugin update aspen-plus@aspen-mcp`). 새 릴리스가 나오면 플러그인이 알려 줍니다.

다른 MCP 클라이언트(Claude Desktop, Gemini CLI, 플러그인 없는 Codex), 확인 절차를 포함한 단계별
안내, 문제 해결은 **[INSTALL.md](INSTALL.md)**(영문)를 참고하십시오.

## 개인정보

서버가 보관하는 모든 것은 여러분의 컴퓨터 `~/.aspen-mcp/` 아래에 남습니다. 로그, 변경 기록,
복원 지점(모델 사본), 오류 기록이 여기에 해당합니다. 이 프로젝트는 여러분의 모델, 결과, 대화를
어디에도 전송하지 않습니다. 네트워크 접근은 다음뿐입니다.

- 플러그인 업데이트 확인(하루 최대 한 번, 이 저장소에 대한 `git ls-remote`)
- 최초의 `pinch_analysis` 호출(uv를 통해 Python 3.14와 OpenPinch 다운로드)
- 설치 및 업데이트(uv를 통해 서버와 의존 패키지를 가져옴)

AI 클라이언트가 자체 제공업체로 보내는 내용은 해당 클라이언트의 정책을 따릅니다.

## 피드백

질문 및 버그 신고: [GitHub Issues](https://github.com/nckugese/Aspen_Co-pilot/issues). 보안 신고: [SECURITY.md](SECURITY.md)(영문).

## 라이선스

MIT — [LICENSE](LICENSE)를 참고하십시오. Copyright (c) 2026 NCKU GESE Lab.

학술 연구에 이 소프트웨어를 사용하는 경우 이 저장소를 인용해 주십시오.

## 면책 조항

Aspen Plus® 및 AspenTech®는 Aspen Technology, Inc.의 상표입니다. 이 프로젝트는 독립적인
비공식 연동 도구이며, Aspen Technology, Inc.와 제휴 관계가 없고 그로부터 승인이나 후원을 받지
않았습니다. 이 프로젝트는 Aspen Plus를 포함하거나 배포하지 않습니다. 사용자가 별도로 마련한
설치본을 제어할 뿐이며, 유효한 Aspen Plus 라이선스를 직접 보유해야 합니다.
