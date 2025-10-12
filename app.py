# app.py
# 필요 패키지: slack_bolt, slack_sdk, python-dotenv
# Windows PowerShell: py -m pip install slack_bolt slack_sdk python-dotenv

import os
import re
import json
import time
import random
import string
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

# 정답 임시 저장(메모리) - 서버 재시작 시 초기화됨
# {quiz_id: {"answers":[...], "created":ts, "revealed":False, "channel":str, "ts":str}}
QUIZZES: Dict[str, Any] = {}
QUIZ_TTL_SEC = 3600  # 1시간

def _new_quiz_id() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

def _cleanup_quizzes():
    now = time.time()
    for qid in list(QUIZZES.keys()):
        if now - QUIZZES[qid]["created"] > QUIZ_TTL_SEC:
            QUIZZES.pop(qid, None)

# ================== 데이터 로딩/캐시 ==================
def load_data(force: bool = False) -> Dict[str, Any] | None:
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
    """
    예) p1.1-p1.4 -> p1.1, p1.2, p1.3, p1.4
        s1-s4     -> s1, s2, s3, s4
        p1.1,p1.1#,s2 -> 단일/혼합 OK
    '#' 토큰은 범위에 사용 불가(단독 지정만 허용).
    서로 다른 계열/형식의 범위는 불가(예: p1.1-s4, p1.1-p2.1).
    """
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
            add([t])  # '#'(해시) 포함 허용
            continue

        a, b = [x.strip() for x in t.split("-", 1)]
        if not a or not b:
            raise ValueError(f"범위 표기가 올바르지 않습니다: {t}")
        if a.endswith("#") or b.endswith("#"):
            raise ValueError(f"'#' 챕터는 범위로 지정 불가: {t}")

        ma, mb = dot_pat.match(a), dot_pat.match(b)
        if ma and mb:
            pfx_a, mid_a, last_a = ma.group(1), int(ma.group(2)), int(ma.group(3))
            pfx_b, mid_b, last_b = mb.group(1), int(mb.group(2)), int(mb.group(3))
            if pfx_a != pfx_b or mid_a != mid_b:
                raise ValueError(f"같은 계열에서만 범위 가능: {t}")
            if last_b < last_a:
                raise ValueError(f"범위 끝값이 시작보다 작음: {t}")
            add([f"{pfx_a}{mid_a}.{i}" for i in range(last_a, last_b + 1)])
            continue

        sa, sb = simple_pat.match(a), simple_pat.match(b)
        if sa and sb:
            pfx_a, last_a = sa.group(1), int(sa.group(2))
            pfx_b, last_b = sb.group(1), int(sb.group(2))
            if pfx_a != pfx_b:
                raise ValueError(f"같은 접두어에서만 범위 가능: {t}")
            if last_b < last_a:
                raise ValueError(f"범위 끝값이 시작보다 작음: {t}")
            add([f"{pfx_a}{i}" for i in range(last_a, last_b + 1)])
            continue

        raise ValueError(f"지원하지 않는 범위 형식: {t}")

    return result

# ================== 공통 헬퍼 ==================
def collect_items(section: str, chapters: List[str]) -> Tuple[List[str], List[str]]:
    data = load_data()
    if data is None:
        raise FileNotFoundError("data.json을 찾을 수 없습니다.")
    if section not in data or not isinstance(data[section], dict):
        raise KeyError(f"data.json의 '{section}' 섹션이 올바르지 않습니다.")
    bucket: Dict[str, Any] = data[section]
    items, missing = [], []
    for ch in chapters:
        arr = bucket.get(ch)
        if isinstance(arr, list):
            items.extend(str(x) for x in arr)
        else:
            missing.append(ch)
    return items, missing

def collect_all_pairs(chapters: List[str] | None) -> List[Tuple[str, str, str]]:
    """
    (eng, kor, key) 페어 전부 수집. chapters=None이면 가능한 모든 챕터에서 수집.
    길이가 다른 경우 짧은 쪽 길이만큼 페어링.
    """
    data = load_data()
    if data is None:
        raise FileNotFoundError("data.json 없음")
    eng_map: Dict[str, List[str]] = data.get("eng", {}) or {}
    kor_map: Dict[str, List[str]] = data.get("kor", {}) or {}
    keys = chapters if chapters else sorted(set(eng_map.keys()) & set(kor_map.keys()))
    pairs: List[Tuple[str, str, str]] = []
    for ch in keys:
        e = eng_map.get(ch)
        k = kor_map.get(ch)
        if isinstance(e, list) and isinstance(k, list) and e and k:
            m = min(len(e), len(k))
            for i in range(m):
                pairs.append((str(e[i]), str(k[i]), ch))
    return pairs

def format_lines(items: List[str], max_lines: int = 400) -> List[str]:
    lines = [f"{i}. {w}" for i, w in enumerate(items, 1)]
    if len(lines) > max_lines:
        lines = lines[:max_lines] + [f"... (총 {len(items)}개 중 상위 {max_lines}개 표시)"]
    return lines

USAGE_ENG = "사용법: `/eng p1.1-p1.4` / `/eng p1.1,p1.2#` / `/eng s1-s4`"
USAGE_KOR = "사용법: `/kor p1.1-p1.4` / `/kor p1.1,p1.2#` / `/kor s1-s4`"

# ================== 리스트업 명령 (/eng) ==================
@app.command("/eng")
def handle_eng(ack, respond, command, client):
    ack()
    text = (command.get("text") or "").strip()
    if not text:
        respond(response_type="ephemeral", text=USAGE_ENG)
        return
    try:
        chapters = parse_range(text)
        items, missing = collect_items("eng", chapters)
        if not items:
            respond(response_type="ephemeral", text=f"요청한 범위({text})에 항목이 없습니다.")
            return
        lines = format_lines(items)
        body = "• " + "\n• ".join(lines)

        # 블록 + 액션 버튼(한글 뜻 보기)
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*(챕터 {text})*"}},
            {"type": "section", "block_id": "eng_list", "text": {"type": "mrkdwn", "text": body}},
            {"type": "actions", "block_id": "eng_actions", "elements": [
                {
                    "type": "button",
                    "action_id": "show_kor_for_range",
                    "text": {"type": "plain_text", "text": "한글로 보기"},
                    "style": "primary",
                    "value": json.dumps({"chapters_expr": text})
                }
            ]}
        ]
        if missing:
            blocks.append({"type": "context", "elements": [
                {"type": "mrkdwn", "text": f"_(데이터 없음: {' '.join(missing)})_"}
            ]})

        # 봇이 직접 채널에 올림 (chat.update 가능)
        channel_id = command.get("channel_id")
        res = client.chat_postMessage(channel=channel_id, text="영어 목록", blocks=blocks)
        # 안내 (선택)
    except Exception as e:
        respond(response_type="ephemeral", text=f"오류: {e}\n{USAGE_ENG}")

# ================== 리스트업 명령 (/kor) ==================
@app.command("/kor")
def handle_kor(ack, respond, command, client):
    ack()
    text = (command.get("text") or "").strip()
    if not text:
        respond(response_type="ephemeral", text=USAGE_KOR)
        return
    try:
        chapters = parse_range(text)
        items, missing = collect_items("kor", chapters)
        if not items:
            respond(response_type="ephemeral", text=f"요청한 범위({text})에 항목이 없습니다.")
            return
        lines = format_lines(items)
        body = "• " + "\n• ".join(lines)

        # 블록 + 액션 버튼(영어 목록 보기)
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*(챕터 {text})*"}},
            {"type": "section", "block_id": "kor_list", "text": {"type": "mrkdwn", "text": body}},
            {"type": "actions", "block_id": "kor_actions", "elements": [
                {
                    "type": "button",
                    "action_id": "show_eng_for_range",
                    "text": {"type": "plain_text", "text": "영어로 보기"},
                    "style": "primary",
                    "value": json.dumps({"chapters_expr": text})
                }
            ]}
        ]
        if missing:
            blocks.append({"type": "context", "elements": [
                {"type": "mrkdwn", "text": f"_(데이터 없음: {' '.join(missing)})_"}
            ]})

        channel_id = command.get("channel_id")
        res = client.chat_postMessage(channel=channel_id, text="한글 뜻 목록", blocks=blocks)
    except Exception as e:
        respond(response_type="ephemeral", text=f"오류: {e}\n{USAGE_KOR}")

# ================== 랜덤 테스트 (/test) ==================
@app.command("/test")
def handle_test(ack, respond, command, client):
    ack()
    text = (command.get("text") or "").strip()
    parts = text.split() if text else []

    if not parts:
        respond(response_type="ephemeral", text="형식: `/test <문항수> [범위]` (범위 생략 시 전체에서 랜덤)")
        return

    # 문항 수
    try:
        n = int(parts[0]); assert n > 0
    except Exception:
        respond(response_type="ephemeral", text="문항 수는 양의 정수. 예) `/test 10 p1.1-p1.4`")
        return

    # 범위(선택)
    chapters = None
    chapter_expr = " ".join(parts[1:]).strip() if len(parts) > 1 else ""
    if chapter_expr:
        try:
            chapters = parse_range(chapter_expr)
        except Exception as e:
            respond(response_type="ephemeral", text=f"챕터 해석 오류: {e}")
            return

    # 페어 수집 → 랜덤 n개
    pairs = collect_all_pairs(chapters)  # [(eng, kor, key), ...]
    if not pairs:
        respond(response_type="ephemeral", text=f"{chapter_expr or '전체'}에서 출제할 항목이 없습니다.")
        return
    if n > len(pairs):
        n = len(pairs)

    sample = random.sample(pairs, n)

    # 규칙: s는 항상 '한글 문제', p는 혼합(총 6:4 목표)
    kor_target = int(round(n * 0.6))  # 목표 한글문항 수
    s_list = [(e, k, key) for (e, k, key) in sample if key.lower().startswith("s")]
    p_list = [(e, k, key) for (e, k, key) in sample if key.lower().startswith("p")]

    questions: List[str] = []
    answers:   List[str] = []

    # s → 한글 문제
    for e, k, _ in s_list:
        questions.append(k)
        answers.append(e)

    remaining_kor_needed = max(0, kor_target - len(s_list))
    random.shuffle(p_list)
    p_kor = p_list[:remaining_kor_needed]
    p_eng = p_list[remaining_kor_needed:]

    for e, k, _ in p_kor:
        questions.append(k); answers.append(e)  # 한글 문제

    for e, k, _ in p_eng:
        questions.append(e); answers.append(k)  # 영어 문제

    combined = list(zip(questions, answers))
    random.shuffle(combined)
    questions, answers = (list(t) for t in zip(*combined)) if combined else ([], [])

    _cleanup_quizzes()
    quiz_id = _new_quiz_id()
    QUIZZES[quiz_id] = {
        "answers": answers,
        "created": time.time(),
        "revealed": False,
    }

    q_lines = "\n".join(f"{i}. {q}" for i, q in enumerate(questions, 1))
    header = (
        f"*랜덤 테스트* (범위: {chapter_expr or '전체'}) — 총 {len(questions)}문항\n"
    )
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": header}},
        {"type": "divider"},
        {"type": "section", "block_id": "quiz_questions", "text": {"type": "mrkdwn", "text": f"*문제*\n{q_lines}"}},
        {"type": "actions", "block_id": "quiz_actions", "elements": [
            {
                "type": "button",
                "action_id": "reveal_all",
                "text": {"type": "plain_text", "text": "정답 전체 보기"},
                "style": "primary",
                "value": json.dumps({"quiz_id": quiz_id})
            }
        ]}
    ]

    channel_id = command.get("channel_id")
    res = client.chat_postMessage(channel=channel_id, text="랜덤 테스트", blocks=blocks)
    # 정답 공개에 필요한 ts/channel 저장
    QUIZZES[quiz_id]["channel"] = channel_id
    QUIZZES[quiz_id]["ts"] = res["ts"]

# ================== 버튼 액션: 정답 전체 공개 ==================
@app.action("reveal_all")
def on_reveal_all(ack, body, client, respond, logger):
    ack()
    try:
        payload = json.loads(body["actions"][0].get("value", "{}"))
        quiz_id = payload.get("quiz_id")
    except Exception:
        respond(response_type="ephemeral", text="정답 정보를 찾지 못했습니다. 다시 시도하세요.")
        return

    _cleanup_quizzes()
    quiz = QUIZZES.get(quiz_id)
    if not quiz:
        respond(response_type="ephemeral", text="퀴즈가 만료되었거나 없습니다. `/test`로 다시 시작하세요.")
        return
    if quiz.get("revealed"):
        respond(response_type="ephemeral", text="정답은 이미 공개되었습니다.")
        return

    answers = quiz["answers"]
    a_lines = "\n".join(f"{i}. {a}" for i, a in enumerate(answers, 1))

    channel = quiz.get("channel")
    ts = quiz.get("ts")
    if not (channel and ts):
        respond(response_type="ephemeral", text="메시지 식별 정보가 없습니다.")
        return

    blocks = body.get("message", {}).get("blocks", [])[:]

    # 버튼 블록을 안내 context로 교체
    for i, b in enumerate(blocks):
        if b.get("block_id") == "quiz_actions":
            blocks[i] = {
                "type": "context",
                "block_id": "quiz_actions",
                "elements": [{"type": "mrkdwn", "text": "*정답이 공개되었습니다.*"}]
            }
            break

    # 정답 섹션 추가
    if not any(b.get("block_id") == "quiz_answers" for b in blocks):
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "block_id": "quiz_answers",
            "text": {"type": "mrkdwn", "text": f"*정답표*\n{a_lines or '_정답이 없습니다_'}"}
        })

    try:
        client.chat_update(channel=channel, ts=ts, blocks=blocks, text="정답 공개")
        quiz["revealed"] = True
    except Exception as e:
        logger.exception(e)
        respond(response_type="ephemeral", text="메시지 업데이트에 실패했습니다.")

# ================== 버튼 액션: /eng 메시지에서 '한글 뜻 보기' ==================
@app.action("show_kor_for_range")
def on_show_kor_for_range(ack, body, client, respond, logger):
    ack()
    try:
        payload = json.loads(body["actions"][0].get("value", "{}"))
        expr = payload.get("chapters_expr", "")
        chapters = parse_range(expr)
        items, missing = collect_items("kor", chapters)
    except Exception as e:
        respond(response_type="ephemeral", text=f"한글 뜻 로드 실패: {e}")
        return

    if not items:
        respond(response_type="ephemeral", text="해당 범위의 한글 뜻이 없습니다.")
        return

    lines = format_lines(items)
    body_text = "• " + "\n• ".join(lines)

    # 기존 블록 가져오기
    blocks = body.get("message", {}).get("blocks", [])[:]

    # actions 블록을 안내 context로 교체
    for i, b in enumerate(blocks):
        if b.get("block_id") == "eng_actions":
            blocks[i] = {
                "type": "context",
                "block_id": "eng_actions",
                "elements": [{"type": "mrkdwn", "text": "_한글로 보기_"}]
            }
            break

    # 이미 추가되어 있지 않다면, 한글 뜻 섹션 추가
    if not any(b.get("block_id") == "eng_kor_added" for b in blocks):
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "block_id": "eng_kor_added",
            "text": {"type": "mrkdwn", "text": f"*한글 뜻*\n{body_text}"}
        })
        if missing:
            blocks.append({"type": "context", "elements": [
                {"type": "mrkdwn", "text": f"_(데이터 없음: {' '.join(missing)})_"}
            ]})

    # 원본 메시지 식별
    channel = body.get("container", {}).get("channel_id")
    ts = body.get("container", {}).get("message_ts")
    if not (channel and ts):
        respond(response_type="ephemeral", text="메시지 식별 정보가 없습니다.")
        return

    try:
        client.chat_update(channel=channel, ts=ts, blocks=blocks, text="한글 뜻 추가")
    except Exception as e:
        logger.exception(e)
        respond(response_type="ephemeral", text="메시지 업데이트에 실패했습니다.")

# ================== 버튼 액션: /kor 메시지에서 '영어 목록 보기' ==================
@app.action("show_eng_for_range")
def on_show_eng_for_range(ack, body, client, respond, logger):
    ack()
    try:
        payload = json.loads(body["actions"][0].get("value", "{}"))
        expr = payload.get("chapters_expr", "")
        chapters = parse_range(expr)
        items, missing = collect_items("eng", chapters)
    except Exception as e:
        respond(response_type="ephemeral", text=f"영어 목록 로드 실패: {e}")
        return

    if not items:
        respond(response_type="ephemeral", text="해당 범위의 영어 목록이 없습니다.")
        return

    lines = format_lines(items)
    body_text = "• " + "\n• ".join(lines)

    blocks = body.get("message", {}).get("blocks", [])[:]

    # actions 블록을 안내 context로 교체
    for i, b in enumerate(blocks):
        if b.get("block_id") == "kor_actions":
            blocks[i] = {
                "type": "context",
                "block_id": "kor_actions",
                "elements": [{"type": "mrkdwn", "text": "_영어로 보기_"}]
            }
            break

    # 이미 추가되어 있지 않다면, 영어 목록 섹션 추가
    if not any(b.get("block_id") == "kor_eng_added" for b in blocks):
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "block_id": "kor_eng_added",
            "text": {"type": "mrkdwn", "text": f"*영어*\n{body_text}"}
        })
        if missing:
            blocks.append({"type": "context", "elements": [
                {"type": "mrkdwn", "text": f"_(데이터 없음: {' '.join(missing)})_"}
            ]})

    channel = body.get("container", {}).get("channel_id")
    ts = body.get("container", {}).get("message_ts")
    if not (channel and ts):
        respond(response_type="ephemeral", text="메시지 식별 정보가 없습니다.")
        return

    try:
        client.chat_update(channel=channel, ts=ts, blocks=blocks, text="영어 목록 추가")
    except Exception as e:
        logger.exception(e)
        respond(response_type="ephemeral", text="메시지 업데이트에 실패했습니다.")

# ================== 실행 ==================
if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
