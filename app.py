# app.py
# Windows / Socket Mode / 가상환경 없이 실행 가능
# 필요 패키지: slack_bolt, slack_sdk, python-dotenv
#   PowerShell: py -m pip install slack_bolt slack_sdk python-dotenv

import os
import re
import json
from typing import List, Tuple, Dict, Any

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

# ================== 기본 설정 ==================
load_dotenv()
DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")

app = App(token=os.environ["SLACK_BOT_TOKEN"])

_json_cache: Dict[str, Any] | None = None
_json_mtime: float = 0.0

# ================== 데이터 로딩/캐시 ==================
def load_data(force: bool = False) -> Dict[str, Any] | None:
    # """data.json 로드 + 변경 감지 캐시."""
    global _json_cache, _json_mtime
    try:
        mtime = os.path.getmtime(DATA_FILE)
    except FileNotFoundError:
        return None
    if force or _json_cache is None or mtime != _json_mtime:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            _json_cache = json.load(f)
        _json_mtime = mtime
    return _json_cache

# ================== 범위/토큰 파서 ==================
def parse_range(arg: str) -> List[str]:
    # """
    # 규칙(순수 숫자 챕터 없음 가정):
    #   - 범위: '같은 계열'에서 끝자리 숫자만 증가
    #     예) p1.1-p1.4 -> p1.1, p1.2, p1.3, p1.4
    #         s1-s4     -> s1, s2, s3, s4
    #   - 범위 확장 시 끝에 '#' 붙은 변형은 자동 제외 (range로는 생성하지 않음)
    #   - 단일 챕터는 무엇이든 허용: p1.1, p1.1#, s1, s2 ...
    #   - 콤마 혼합 허용: 'p1.1-p1.4,s2,p1.2#'
    #   - 금지: 서로 다른 계열/형식 범위 (p1.1-s4, p1.1-p2.1, p1.1#-p1.4 등)
    # """
    s = (arg or "").strip()
    if not s:
        raise ValueError("챕터를 입력하세요. 예: p1.1-p1.4, s1-s4, p1.1, p1.1#, s2")

    tokens = [t.strip() for t in s.split(",") if t.strip()]
    if not tokens:
        raise ValueError("유효한 챕터 형식이 없습니다.")

    result: List[str] = []
    seen = set()

    dot_pat    = re.compile(r"^([A-Za-z]+)(\d+)\.(\d+)$")  # p1.1 → (p,1,1)
    simple_pat = re.compile(r"^([A-Za-z]+)(\d+)$")         # s1   → (s,1)

    def add(items: List[str]):
        for it in items:
            if it not in seen:
                seen.add(it)
                result.append(it)

    for t in tokens:
        if "-" not in t:
            # 단일 챕터는 '#' 포함도 허용
            add([t])
            continue

        a, b = [x.strip() for x in t.split("-", 1)]
        if not a or not b:
            raise ValueError(f"범위 표기가 올바르지 않습니다: {t}")

        # 범위에는 '#' 금지 (해시 변형은 단독 지정만)
        if a.endswith("#") or b.endswith("#"):
            raise ValueError(f"'#'가 붙은 챕터는 범위로 지정할 수 없습니다: {t}")

        ma, mb = dot_pat.match(a), dot_pat.match(b)
        if ma and mb:
            pfx_a, mid_a, last_a = ma.group(1), int(ma.group(2)), int(ma.group(3))
            pfx_b, mid_b, last_b = mb.group(1), int(mb.group(2)), int(mb.group(3))
            if pfx_a != pfx_b or mid_a != mid_b:
                raise ValueError(f"같은 계열에서만 범위가 가능합니다: {t}")
            if last_b < last_a:
                raise ValueError(f"범위의 끝값이 시작값보다 작습니다: {t}")
            add([f"{pfx_a}{mid_a}.{i}" for i in range(last_a, last_b + 1)])
            continue

        sa, sb = simple_pat.match(a), simple_pat.match(b)
        if sa and sb:
            pfx_a, last_a = sa.group(1), int(sa.group(2))
            pfx_b, last_b = sb.group(1), int(sb.group(2))
            if pfx_a != pfx_b:
                raise ValueError(f"같은 접두어에서만 범위가 가능합니다: {t}")
            if last_b < last_a:
                raise ValueError(f"범위의 끝값이 시작값보다 작습니다: {t}")
            add([f"{pfx_a}{i}" for i in range(last_a, last_b + 1)])
            continue

        raise ValueError(f"지원하지 않는 범위 형식입니다: {t}")

    return result

# ================== 공통 헬퍼 ==================
def collect_items(section: str, chapters: List[str]) -> Tuple[List[str], List[str]]:
    # """
    # section: 'eng' 또는 'kor'
    # 반환: (존재하는 챕터에서 모은 아이템, 누락된 챕터 목록)
    # - 범위 확장으로 생성된 목록에는 '#'(해시) 변형이 애초에 포함되지 않지만,
    #   단일 토큰으로 들어온 '...#'는 그대로 허용됩니다.
    # """
    data = load_data()
    if data is None:
        raise FileNotFoundError("data.json 파일을 찾을 수 없습니다.")
    if section not in data or not isinstance(data[section], dict):
        raise KeyError(f"data.json의 '{section}' 섹션이 올바르지 않습니다.")

    result: List[str] = []
    missing: List[str] = []
    bucket: Dict[str, Any] = data[section]

    for ch in chapters:
        arr = bucket.get(ch)
        if not isinstance(arr, list):
            # 범위에서 자동 생성된 후보 중, 실제 파일에 없으면 missing 안내
            # (예: p1.2가 파일에 없을 때)
            missing.append(ch)
            continue
        for item in arr:
            result.append(str(item))

    return result, missing

def format_lines(items: List[str], max_lines: int = 300) -> List[str]:
    # """슬랙 메시지 길이 제한 대비 줄 수 제한."""
    lines = [f"{i}. {w}" for i, w in enumerate(items, 1)]
    if len(lines) > max_lines:
        lines = lines[:max_lines] + [f"... (총 {len(items)}개 중 상위 {max_lines}개 표시)"]
    return lines

<<<<<<< HEAD
USAGE_ENG = "사용법: /eng p1.1-p1.4 / /eng p1.1,p1.2# / /eng s1-s4"
USAGE_KOR   = "사용법: /kor p1.1-p1.4 / /kor p1.1,p1.2# / /kor s1-s4"
=======
USAGE_ENG = "사용법: `/eng p1.1-p1.4` / `/eng p1.1,p1.2#` / `/eng s1-s4`"
USAGE_KOR   = "사용법: `/kor p1.1-p1.4` / `/kor p1.1,p1.2#` / `/kor s1-s4`"
>>>>>>> d365b68 (commit)

# ================== /eng : 영어 단어만 ==================
@app.command("/eng")
def handle_eng(ack, respond, command):
    ack()
    text = (command.get("text") or "").strip()
    if not text:
        respond(response_type="ephemeral", text=USAGE_ENG)
        return
    try:
        chapters = parse_range(text)
        # 범위로 생성된 리스트엔 '#'(해시) 변형 없음. 단일 지정된 '...#'는 포함됨.
        items, missing = collect_items("eng", chapters)
    except Exception as e:
        respond(response_type="ephemeral", text=f"오류: {e}\n{USAGE_ENG}")
        return

    if not items:
        respond(response_type="ephemeral", text=f"요청한 범위({text})에 표시할 항목이 없습니다.")
        return

    lines = format_lines(items, max_lines=400)
    msg = f"*영어 단어 목록 (챕터 {text})*\n• " + "\n• ".join(lines)
    if missing:
        msg += f"\n_(다음 챕터는 데이터가 없어 건너뜀: {' '.join(missing)})_"
    respond(response_type="in_channel", text=msg)

# ================== /kor : 한글 뜻만 ==================
@app.command("/kor")
def handle_kor(ack, respond, command):
    ack()
    text = (command.get("text") or "").strip()
    if not text:
        respond(response_type="ephemeral", text=USAGE_KOR)
        return
    try:
        chapters = parse_range(text)
        items, missing = collect_items("kor", chapters)
    except Exception as e:
        respond(response_type="ephemeral", text=f"오류: {e}\n{USAGE_KOR}")
        return

    if not items:
        respond(response_type="ephemeral", text=f"요청한 범위({text})에 표시할 항목이 없습니다.")
        return

    lines = format_lines(items, max_lines=400)
<<<<<<< HEAD
    msg = f"한글 뜻 목록 (챕터 {text})\n• " + "\n• ".join(lines)
=======
    msg = f"*한글 뜻 목록 (챕터 {text})*\n• " + "\n• ".join(lines)
>>>>>>> d365b68 (commit)
    if missing:
        msg += f"\n_(다음 챕터는 데이터가 없어 건너뜀: {' '.join(missing)})_"
    respond(response_type="in_channel", text=msg)

# ================== 실행 ==================
if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
