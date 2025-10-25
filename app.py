# app.py
# 필요 패키지: slack_bolt, slack_sdk, python-dotenv
# Windows PowerShell: py -m pip install slack_bolt slack_sdk python-dotenv
# https://api.slack.com/apps 

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
    last_pat   = re.compile(r"^last\.([A-Za-z]+)(\d+)$")   # last.p4, last.s2

    def add(items: List[str]):
        for it in items:
            if it not in seen:
                seen.add(it)
                result.append(it)

    for t in tokens:
        # Handle 'last.<prefix><n>' tokens (e.g., last.p4, last.s2)
        lm = last_pat.match(t)
        if lm:
            pfx = lm.group(1)
            take_n = int(lm.group(2))
            data = load_data()
            if data is None:
                raise ValueError(f"데이터가 없어 '{t}'을(를) 처리할 수 없습니다.")
            eng_keys = set((data.get("eng") or {}).keys())
            kor_keys = set((data.get("kor") or {}).keys())
            avail = sorted(k for k in (eng_keys | kor_keys) if not k.endswith("#"))

            # collect matching keys for prefix (dot or simple)
            dot_match = re.compile(rf"^{re.escape(pfx)}(\d+)\.(\d+)$")
            simple_match = re.compile(rf"^{re.escape(pfx)}(\d+)$")
            matched: List[Tuple[int, int, str]] = []  # (mid, last or 0, key)
            for k in avail:
                md = dot_match.match(k)
                if md:
                    matched.append((int(md.group(1)), int(md.group(2)), k))
                    continue
                ms = simple_match.match(k)
                if ms:
                    matched.append((int(ms.group(1)), 0, k))

            if not matched:
                raise ValueError(f"'{pfx}' 계열의 챕터를 찾을 수 없습니다: {t}")

            # sort by mid, then last
            matched.sort(key=lambda x: (x[0], x[1]))
            # take last N keys
            sel = [k for _, _, k in matched[-take_n:]]
            add(sel)
            continue

        if "-" not in t:
            add([t])  # '#'(해시) 포함 허용 for explicit single token
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
            if pfx_a != pfx_b:
                raise ValueError(f"같은 계열에서만 범위 가능: {t}")

            # If both parts (mid) are equal, keep original simple expansion.
            if mid_a == mid_b:
                if last_b < last_a:
                    raise ValueError(f"범위 끝값이 시작보다 작음: {t}")
                add([f"{pfx_a}{mid_a}.{i}" for i in range(last_a, last_b + 1)])
                continue

            # If parts differ (예: p1.5-p2.1), try to expand across parts using data.json
            data = load_data()
            if data is None:
                # Without data, we cannot safely expand across different parts.
                raise ValueError(f"데이터가 없어 서로 다른 단원 간 범위({t})를 해석할 수 없습니다.")

            # Collect available chapter keys from eng/kor sections
            eng_keys = set((data.get("eng") or {}).keys())
            kor_keys = set((data.get("kor") or {}).keys())
            # Exclude keys that end with '#' from availability when expanding ranges
            avail = sorted(k for k in (eng_keys | kor_keys) if not k.endswith("#"))

            # Helper: get all last indices for a given prefix+mid present in data
            def available_lasts(pfx: str, mid: int) -> List[int]:
                pat = re.compile(rf"^{re.escape(pfx)}{mid}\.(\d+)$")
                lst: List[int] = []
                for k in avail:
                    m = pat.match(k)
                    if m:
                        lst.append(int(m.group(1)))
                return sorted(lst)

            items_to_add: List[str] = []
            # Ensure start and end tokens exist in available keys
            start_token = f"{pfx_a}{mid_a}.{last_a}"
            end_token = f"{pfx_b}{mid_b}.{last_b}"
            if start_token not in avail:
                raise ValueError(f"범위 시작 챕터가 없습니다: {start_token}")
            if end_token not in avail:
                raise ValueError(f"범위 끝 챕터가 없습니다: {end_token}")

            for mid in range(mid_a, mid_b + 1):
                lasts = available_lasts(pfx_a, mid)
                if not lasts:
                    # 중간 단원에 항목이 전혀 없으면 건너뛰지 않고 오류로 처리
                    raise ValueError(f"단원 {pfx_a}{mid}에 데이터가 없습니다: {t}")
                if mid == mid_a:
                    # include lasts >= last_a
                    for i in [x for x in lasts if x >= last_a]:
                        items_to_add.append(f"{pfx_a}{mid}.{i}")
                elif mid == mid_b:
                    # include lasts <= last_b
                    for i in [x for x in lasts if x <= last_b]:
                        items_to_add.append(f"{pfx_a}{mid}.{i}")
                else:
                    for i in lasts:
                        items_to_add.append(f"{pfx_a}{mid}.{i}")

            if not items_to_add:
                raise ValueError(f"범위로 확장할 수 있는 챕터가 없습니다: {t}")
            add(items_to_add)
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


def collect_items_detailed(section: str, chapters: List[str]) -> Tuple[List[Tuple[str, int, str]], List[str]]:
    """Return detailed items as (chapter, index(1-based), word) and missing chapters list."""
    data = load_data()
    if data is None:
        raise FileNotFoundError("data.json을 찾을 수 없습니다.")
    if section not in data or not isinstance(data[section], dict):
        raise KeyError(f"data.json의 '{section}' 섹션이 올바르지 않습니다.")
    bucket: Dict[str, Any] = data[section]
    items: List[Tuple[str, int, str]] = []
    missing: List[str] = []
    for ch in chapters:
        arr = bucket.get(ch)
        if isinstance(arr, list):
            for i, w in enumerate(arr, 1):
                items.append((ch, i, str(w)))
        else:
            missing.append(ch)
    return items, missing


def _truncate_blocks_for_slack(blocks: List[Dict[str, Any]], max_blocks: int = 50) -> List[Dict[str, Any]]:
    """Slack allows at most 50 blocks per message. If blocks exceed that, truncate and append a notice.
    Returns a new list of blocks safe to send."""
    if len(blocks) <= max_blocks:
        return blocks
    # Keep first (max_blocks-1) blocks and append a context block that indicates truncation
    kept = blocks[: max_blocks - 1]
    kept.append({"type": "context", "elements": [{"type": "mrkdwn", "text": f"... (총 {len(blocks)}블록 중 상위 {max_blocks}개만 표시)"}]})
    return kept

def collect_all_pairs(chapters: List[str] | None) -> List[Tuple[str, str, str, int]]:
    """
    (eng, kor, key, index) 페어 전부 수집. chapters=None이면 가능한 모든 챕터에서 수집.
    길이가 다른 경우 짧은 쪽 길이만큼 페어링. index는 1-based 항목 인덱스입니다.
    """
    data = load_data()
    if data is None:
        raise FileNotFoundError("data.json 없음")
    eng_map: Dict[str, List[str]] = data.get("eng", {}) or {}
    kor_map: Dict[str, List[str]] = data.get("kor", {}) or {}
    keys = chapters if chapters else sorted(set(eng_map.keys()) & set(kor_map.keys()))
    pairs: List[Tuple[str, str, str, int]] = []
    for ch in keys:
        e = eng_map.get(ch)
        k = kor_map.get(ch)
        if isinstance(e, list) and isinstance(k, list) and e and k:
            m = min(len(e), len(k))
            for i in range(m):
                # index is 1-based
                pairs.append((str(e[i]), str(k[i]), ch, i + 1))
    return pairs

def format_lines(items: List[str], max_lines: int = 400) -> List[str]:
    lines = [f"{i}. {w}" for i, w in enumerate(items, 1)]
    if len(lines) > max_lines:
        lines = lines[:max_lines] + [f"... (총 {len(items)}개 중 상위 {max_lines}개 표시)"]
    return lines


def find_matches(query: str) -> List[str]:
    """Find matches for `/find <query>`.
    - If query contains any ASCII letters (a-zA-Z) treat it as English and search the `eng` section keys' values.
    - Otherwise treat it as Korean and search the `kor` section values.
    Returns lines of the form: "source_word : target_word" (one per match)."""
    q = (query or "").strip()
    if not q:
        raise ValueError("검색어를 입력하세요. 예: /find love 또는 /find 사랑")

    data = load_data()
    if data is None:
        raise FileNotFoundError("data.json을 찾을 수 없습니다.")

    eng_map: Dict[str, List[str]] = data.get("eng", {}) or {}
    kor_map: Dict[str, List[str]] = data.get("kor", {}) or {}

    # Decide direction: contains ASCII letter => english query
    is_eng = bool(re.search(r"[A-Za-z]", q))
    results: List[str] = []

    if is_eng:
        # Search all eng values for words that contain q (case-insensitive)
        qlow = q.lower()
        for ch, arr in eng_map.items():
            if not isinstance(arr, list):
                continue
            for i, w in enumerate(arr):
                if qlow in str(w).lower():
                    # Try to get corresponding kor translation at same index if exists
                    kor_arr = kor_map.get(ch)
                    kor_word = None
                    if isinstance(kor_arr, list) and i < len(kor_arr):
                        kor_word = kor_arr[i]
                    results.append(f"{w} : {kor_word or '_(번역없음)_' }")
    else:
        # Korean query: substring match against kor values
        for ch, arr in kor_map.items():
            if not isinstance(arr, list):
                continue
            for i, k in enumerate(arr):
                if q in str(k):
                    eng_arr = eng_map.get(ch)
                    eng_word = None
                    if isinstance(eng_arr, list) and i < len(eng_arr):
                        eng_word = eng_arr[i]
                    results.append(f"{k} : {eng_word or '_(번역없음)_' }")

    return results


BOOKMARK_FILE = os.path.join(os.path.dirname(__file__), "bookmark.json")


def load_bookmarks() -> Dict[str, List[str]]:
    try:
        with open(BOOKMARK_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception:
        return {}


def save_bookmarks(bm: Dict[str, List[str]]):
    with open(BOOKMARK_FILE, "w", encoding="utf-8") as f:
        json.dump(bm, f, ensure_ascii=False, indent=4)


def resolve_bookmark_tokens(tokens: List[str]) -> List[Tuple[str, str, str]]:
    """Given tokens like 'p1.1#3', return list of (token, eng_word, kor_word).
    If any item missing, include placeholder for missing translation."""
    data = load_data()
    if data is None:
        return []
    eng_map: Dict[str, List[str]] = data.get("eng", {}) or {}
    kor_map: Dict[str, List[str]] = data.get("kor", {}) or {}
    out: List[Tuple[str, str, str]] = []
    for t in tokens:
        if not isinstance(t, str) or "#" not in t:
            continue
        chapter, _, idx_s = t.partition("#")
        try:
            idx = int(idx_s)
        except Exception:
            continue
        eng_word = None
        kor_word = None
        e_arr = eng_map.get(chapter)
        k_arr = kor_map.get(chapter)
        if isinstance(e_arr, list) and 1 <= idx <= len(e_arr):
            eng_word = str(e_arr[idx-1])
        if isinstance(k_arr, list) and 1 <= idx <= len(k_arr):
            kor_word = str(k_arr[idx-1])
        out.append((t, eng_word or "_(없음)_", kor_word or "_(없음)_"))
    return out


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
        items_detailed, missing = collect_items_detailed("eng", chapters)
        if not items_detailed:
            respond(response_type="ephemeral", text=f"요청한 범위({text})에 항목이 없습니다.")
            return

        # Load bookmark users to create per-item buttons
        bm = load_bookmarks()
        bm_users = list(bm.keys()) or []

        blocks: List[Dict[str, Any]] = []
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*(챕터 {text})*"}})

        # Add each item as a section + actions (bookmark buttons)
        for i, (ch, idx, word) in enumerate(items_detailed, 1):
            # Build section with accessory overflow to choose bookmark user (keeps layout compact: button beside word)
            section = {"type": "section", "block_id": f"eng_item_{i}", "text": {"type": "mrkdwn", "text": f"{i}. {word}"}}
            if bm_users:
                # Build options (overflow supports up to 5 options). If more users exist, show first 5.
                opts = []
                for u in bm_users[:5]:
                    val = json.dumps({"user_key": u, "chapter": ch, "index": idx, "word": word}, ensure_ascii=False)
                    opts.append({"text": {"type": "plain_text", "text": u}, "value": val})
                action_id = f"bookmark_select_eng_{i}"
                section["accessory"] = {"type": "overflow", "action_id": action_id, "options": opts}
            blocks.append(section)

        # overall action (view kor)
        blocks.append({"type": "actions", "block_id": "eng_actions", "elements": [
            {
                "type": "button",
                "action_id": "show_kor_for_range",
                "text": {"type": "plain_text", "text": "한글로 보기"},
                "style": "primary",
                "value": json.dumps({"chapters_expr": text})
            }
        ]})
        if missing:
            blocks.append({"type": "context", "elements": [
                {"type": "mrkdwn", "text": f"_(데이터 없음: {' '.join(missing)})_"}
            ]})

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
        items_detailed, missing = collect_items_detailed("kor", chapters)
        if not items_detailed:
            respond(response_type="ephemeral", text=f"요청한 범위({text})에 항목이 없습니다.")
            return

        bm = load_bookmarks()
        bm_users = list(bm.keys()) or []

        blocks: List[Dict[str, Any]] = []
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*(챕터 {text})*"}})
        for i, (ch, idx, word) in enumerate(items_detailed, 1):
            section = {"type": "section", "block_id": f"kor_item_{i}", "text": {"type": "mrkdwn", "text": f"{i}. {word}"}}
            if bm_users:
                opts = []
                for u in bm_users[:5]:
                    val = json.dumps({"user_key": u, "chapter": ch, "index": idx, "word": word}, ensure_ascii=False)
                    opts.append({"text": {"type": "plain_text", "text": u}, "value": val})
                action_id = f"bookmark_select_kor_{i}"
                section["accessory"] = {"type": "overflow", "action_id": action_id, "options": opts}
            blocks.append(section)

        blocks.append({"type": "actions", "block_id": "kor_actions", "elements": [
            {
                "type": "button",
                "action_id": "show_eng_for_range",
                "text": {"type": "plain_text", "text": "영어로 보기"},
                "style": "primary",
                "value": json.dumps({"chapters_expr": text})
            }
        ]})
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
    # sample contains tuples (eng, kor, chapter, index)
    s_list = [(e, k, ch, idx) for (e, k, ch, idx) in sample if ch.lower().startswith("s")]
    p_list = [(e, k, ch, idx) for (e, k, ch, idx) in sample if ch.lower().startswith("p")]

    items: List[Dict[str, Any]] = []

    # s → 한글 문제
    for e, k, ch, idx in s_list:
        items.append({"question": k, "answer": e, "chapter": ch, "index": idx, "eng": e, "kor": k})

    remaining_kor_needed = max(0, kor_target - len(s_list))
    random.shuffle(p_list)
    p_kor = p_list[:remaining_kor_needed]
    p_eng = p_list[remaining_kor_needed:]

    for e, k, ch, idx in p_kor:
        items.append({"question": k, "answer": e, "chapter": ch, "index": idx, "eng": e, "kor": k})

    for e, k, ch, idx in p_eng:
        items.append({"question": e, "answer": k, "chapter": ch, "index": idx, "eng": e, "kor": k})

    random.shuffle(items)

    questions = [it["question"] for it in items]
    answers = [it["answer"] for it in items]

    _cleanup_quizzes()
    quiz_id = _new_quiz_id()
    QUIZZES[quiz_id] = {"answers": answers, "created": time.time(), "revealed": False}

    # Build blocks per-item so we can attach bookmark overflow beside each question
    bm = load_bookmarks()
    bm_users = list(bm.keys()) or []

    header = f"*랜덤 테스트* (범위: {chapter_expr or '전체'}) — 총 {len(questions)}문항\n"
    blocks: List[Dict[str, Any]] = []
    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": header}})
    blocks.append({"type": "divider"})

    for i, it in enumerate(items, 1):
        qtext = it["question"]
        ch = it["chapter"]
        idx = it["index"]
        sec = {"type": "section", "block_id": f"quiz_item_{i}", "text": {"type": "mrkdwn", "text": f"{i}. {qtext}"}}
        if bm_users:
            opts = []
            for u in bm_users[:5]:
                val = json.dumps({"user_key": u, "chapter": ch, "index": idx, "word": qtext}, ensure_ascii=False)
                opts.append({"text": {"type": "plain_text", "text": u}, "value": val})
            action_id = f"bookmark_select_test_{i}"
            sec["accessory"] = {"type": "overflow", "action_id": action_id, "options": opts}
        blocks.append(sec)

    # actions block with reveal button
    blocks.append({"type": "actions", "block_id": "quiz_actions", "elements": [
        {"type": "button", "action_id": "reveal_all", "text": {"type": "plain_text", "text": "정답 전체 보기"}, "style": "primary", "value": json.dumps({"quiz_id": quiz_id})}
    ]})

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


# ================== 단어 찾기 (/find) ==================
@app.command("/find")
def handle_find(ack, respond, command, client):
    ack()
    text = (command.get("text") or "").strip()
    if not text:
        respond(response_type="ephemeral", text="사용법: `/find <단어나 뜻>` — 영어 입력 시 eng에서, 한글 입력 시 kor에서 검색합니다.")
        return
    try:
        matches = find_matches(text)
        if not matches:
            respond(response_type="ephemeral", text=f"'{text}'에 대한 결과가 없습니다.")
            return
        body = "\n".join(matches)
        # Post as ephemeral response (private)
        respond(response_type="in_channel", text=f"검색 결과 for '{text}':\n{body}")
    except Exception as e:
        respond(response_type="ephemeral", text=f"오류: {e}")


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
        safe_blocks = _truncate_blocks_for_slack(blocks)
        # If blocks fit under Slack limit, update the original message so it appears as an edit.
        if len(blocks) <= 50:
            try:
                client.chat_update(channel=channel, ts=ts, blocks=safe_blocks, text="한글 뜻 목록")
            except Exception:
                # If update fails, fallback to posting a new message
                client.chat_postMessage(channel=channel, text="한글 뜻 목록", blocks=safe_blocks)
        else:
            # Too many blocks: instead of posting the truncated original blocks (which may leave only
            # the original English content), build a minimal message that contains only the Korean
            # section so the user actually sees the Korean meanings they requested.
            try:
                try:
                    chapters_label = ' '.join(chapters)
                except Exception:
                    chapters_label = expr or "(알수없음)"
                minimal_blocks: List[Dict[str, Any]] = []
                minimal_blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*(챕터 {chapters_label})*"}})
                minimal_blocks.append({"type": "divider"})
                minimal_blocks.append({"type": "section", "block_id": "eng_kor_added", "text": {"type": "mrkdwn", "text": f"*한글 뜻*\n{body_text}"}})
                if missing:
                    minimal_blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": f"_(데이터 없음: {' '.join(missing)})_"}]})
                client.chat_postMessage(channel=channel, text="한글 뜻 목록", blocks=minimal_blocks)
            except Exception:
                # As a last fallback, post the plain text as an ephemeral message to the user
                user_id = body.get("user", {}).get("id")
                plain = body_text if 'body_text' in locals() else "한글 뜻을 불러오는 중 오류가 발생했습니다."
                if channel and user_id:
                    client.chat_postEphemeral(channel=channel, user=user_id, text=plain)
                else:
                    client.chat_postMessage(channel=channel, text=plain)
    except Exception as e:
        logger.exception(e)
        # Fallback: try to send the result as an ephemeral message to the user so they still get the content
        user_id = body.get("user", {}).get("id")
        try:
            plain = body_text if 'body_text' in locals() else "한글 뜻을 불러오는 중 오류가 발생했습니다."
            if channel and user_id:
                client.chat_postEphemeral(channel=channel, user=user_id, text=plain)
                respond(response_type="ephemeral", text="원본 메시지 업데이트에 실패하여 개인 메시지로 결과를 보냈습니다.")
                return
        except Exception:
            logger.exception("ephemeral fallback failed")
        respond(response_type="ephemeral", text=f"메시지 업데이트에 실패했습니다. 오류: {e}")

# ================== 버튼 액션: /kor 메시지에서 '영어 목록 보기' ==================
@app.action("show_eng_for_range")
def on_show_eng_for_range(ack, body, client, respond, logger):
    ack()
    try:
        payload = json.loads(body["actions"][0].get("value", "{}"))
        expr = payload.get("chapters_expr", "")
        chapters = parse_range(expr)
        # To ensure the English list corresponds exactly to the Korean items' order
        # we collect the detailed kor items (chapter,index,word) and map them to
        # English counterparts using collect_all_pairs (which provides indices).
        kor_items_detailed, missing = collect_items_detailed("kor", chapters)
        pairs = collect_all_pairs(chapters)  # returns (eng, kor, chapter, index)
        eng_map = {(ch, idx): e for (e, k, ch, idx) in pairs}
        items = []
        for ch, idx, _kor_word in kor_items_detailed:
            eng_w = eng_map.get((ch, idx))
            items.append(eng_w or "_(번역없음)_")
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
        # show which chapters were resolved (useful for last.<n> tokens)
        try:
            chapters_label = ' '.join(chapters)
        except Exception:
            chapters_label = expr or "(알수없음)"
        blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": f"_(선택된 챕터: {chapters_label})_"}]})
        # truncate long body_text to avoid Slack invalid_blocks due to size
        MAX_BODY = 3000
        if len(body_text) > MAX_BODY:
            body_text = body_text[:MAX_BODY] + "\n... (이하 생략)"
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
        safe_blocks = _truncate_blocks_for_slack(blocks)
        # If blocks fit under Slack limit, update the original message so it appears as an edit.
        if len(blocks) <= 50:
            try:
                client.chat_update(channel=channel, ts=ts, blocks=safe_blocks, text="영어 목록")
            except Exception:
                # If update fails, fallback to posting a new message
                client.chat_postMessage(channel=channel, text="영어 목록", blocks=safe_blocks)
        else:
            # Too many blocks: instead of posting the truncated original blocks (which may leave only
            # the original Korean content), build a minimal message that contains only the English
            # section so the user actually sees the English words they requested.
            try:
                try:
                    chapters_label = ' '.join(chapters)
                except Exception:
                    chapters_label = expr or "(알수없음)"
                minimal_blocks: List[Dict[str, Any]] = []
                minimal_blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*(챕터 {chapters_label})*"}})
                minimal_blocks.append({"type": "divider"})
                minimal_blocks.append({"type": "section", "block_id": "kor_eng_added", "text": {"type": "mrkdwn", "text": f"*영어*\n{body_text}"}})
                if missing:
                    minimal_blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": f"_(데이터 없음: {' '.join(missing)})_"}]})
                client.chat_postMessage(channel=channel, text="영어 목록", blocks=minimal_blocks)
            except Exception:
                # As a last fallback, post the plain text as an ephemeral message to the user
                user_id = body.get("user", {}).get("id")
                plain = body_text if 'body_text' in locals() else "영어 목록을 불러오는 중 오류가 발생했습니다."
                if channel and user_id:
                    client.chat_postEphemeral(channel=channel, user=user_id, text=plain)
                else:
                    client.chat_postMessage(channel=channel, text=plain)
    except Exception as e:
        logger.exception(e)
        # Fallback: try to send the result as an ephemeral message to the user so they still get the content
        user_id = body.get("user", {}).get("id")
        try:
            plain = body_text if 'body_text' in locals() else "영어 목록을 불러오는 중 오류가 발생했습니다."
            if channel and user_id:
                client.chat_postEphemeral(channel=channel, user=user_id, text=plain)
                respond(response_type="ephemeral", text="원본 메시지 업데이트에 실패하여 개인 메시지로 결과를 보냈습니다.")
                return
        except Exception:
            logger.exception("ephemeral fallback failed")
        respond(response_type="ephemeral", text=f"메시지 업데이트에 실패했습니다. 오류: {e}")


@app.command("/mark")
def handle_mark(ack, respond, command, client):
    """Usage:
    /mark <bookmark_user> [eng|kor]           -> list that user's bookmarks (eng/kor or both)
    /mark <bookmark_user> test <n>             -> make a small test from bookmarks (n items)
    Examples: `/mark eunji`, `/mark sm kor`, `/mark sm test 10`
    """
    ack()
    text = (command.get("text") or "").strip()
    if not text:
        respond(response_type="ephemeral", text="사용법: /mark <유저키> [eng|kor] 또는 /mark <유저키> test <n>")
        return
    parts = text.split()
    user_key = parts[0]
    mode = None
    if len(parts) >= 2:
        if parts[1].lower() == "test":
            mode = "test"
        elif parts[1].lower() in ("eng", "kor"):
            mode = parts[1].lower()
    # test count
    n = None
    if mode == "test":
        if len(parts) >= 3:
            try:
                n = int(parts[2])
            except Exception:
                n = None
        if not n or n <= 0:
            respond(response_type="ephemeral", text="테스트 문항 수를 양의 정수로 지정하세요. 예: /mark sm test 10")
            return

    bm = load_bookmarks()
    tokens = bm.get(user_key) or []
    if not tokens:
        respond(response_type="ephemeral", text=f"'{user_key}'의 즐겨찾기가 없습니다.")
        return

    resolved = resolve_bookmark_tokens(tokens)
    if not resolved:
        respond(response_type="ephemeral", text="북마크 항목을 불러오지 못했습니다 (data.json 확인).")
        return

    # test mode
    if mode == "test":
        # build pairs (eng, kor)
        pairs = [(eng, kor, tok) for (tok, eng, kor) in resolved]
        if not pairs:
            respond(response_type="ephemeral", text="출제 가능한 북마크가 없습니다.")
            return
        if n > len(pairs):
            n = len(pairs)
        sample = random.sample(pairs, n)

        kor_target = int(round(n * 0.7))
        random.shuffle(sample)
        # select kor_target items to be Korean questions
        questions = []
        answers = []
        # simple: pick first kor_target as kor questions
        kor_q = sample[:kor_target]
        eng_q = sample[kor_target:]
        for e, k, _ in kor_q:
            questions.append(k)
            answers.append(e)
        for e, k, _ in eng_q:
            questions.append(e)
            answers.append(k)

        combined = list(zip(questions, answers))
        random.shuffle(combined)
        questions, answers = (list(t) for t in zip(*combined)) if combined else ([], [])

        _cleanup_quizzes()
        quiz_id = _new_quiz_id()
        QUIZZES[quiz_id] = {"answers": answers, "created": time.time(), "revealed": False}

        q_lines = "\n".join(f"{i}. {q}" for i, q in enumerate(questions, 1))
        header = f"*북마크 테스트* (사용자: {user_key}) — 총 {len(questions)}문항\n"
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": header}},
            {"type": "divider"},
            {"type": "section", "block_id": "quiz_questions", "text": {"type": "mrkdwn", "text": f"*문제*\n{q_lines}"}},
            {"type": "actions", "block_id": "quiz_actions", "elements": [
                {"type": "button", "action_id": "reveal_all", "text": {"type": "plain_text", "text": "정답 전체 보기"}, "style": "primary", "value": json.dumps({"quiz_id": quiz_id})}
            ]}
        ]
        channel_id = command.get("channel_id")
        res = client.chat_postMessage(channel=channel_id, text="북마크 테스트", blocks=blocks)
        QUIZZES[quiz_id]["channel"] = channel_id
        QUIZZES[quiz_id]["ts"] = res["ts"]
        return

    # list mode: eng / kor / both
    lines: List[str] = []
    if mode == "eng":
        # Build per-item sections so we can attach delete buttons next to each entry
        blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": f"*(북마크: {user_key})*"}}]
        for i, (tok, eng, kor) in enumerate(resolved, 1):
            sec = {"type": "section", "block_id": f"mark_eng_item_{i}", "text": {"type": "mrkdwn", "text": f"{i}. {eng}"}}
            # add delete button as accessory
            del_val = json.dumps({"user_key": user_key, "token": tok}, ensure_ascii=False)
            action_id = f"bookmark_delete_{user_key}_{i}"
            sec["accessory"] = {"type": "button", "action_id": action_id, "text": {"type": "plain_text", "text": "삭제"}, "style": "danger", "value": del_val}
            blocks.append(sec)
        # add toggle button to show kor
        blocks.append({"type": "actions", "block_id": "mark_actions", "elements": [
            {"type": "button", "action_id": "show_kor_for_bookmarks", "text": {"type": "plain_text", "text": "한글로 보기"}, "value": json.dumps({"user_key": user_key})}
        ]})
        channel_id = command.get("channel_id")
        client.chat_postMessage(channel=channel_id, text=f"{user_key} 북마크 (영어)", blocks=blocks)
        return

    if mode == "kor":
        blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": f"*(북마크: {user_key})*"}}]
        for i, (tok, eng, kor) in enumerate(resolved, 1):
            sec = {"type": "section", "block_id": f"mark_kor_item_{i}", "text": {"type": "mrkdwn", "text": f"{i}. {kor}"}}
            del_val = json.dumps({"user_key": user_key, "token": tok}, ensure_ascii=False)
            action_id = f"bookmark_delete_{user_key}_{i}"
            sec["accessory"] = {"type": "button", "action_id": action_id, "text": {"type": "plain_text", "text": "삭제"}, "style": "danger", "value": del_val}
            blocks.append(sec)
        blocks.append({"type": "actions", "block_id": "mark_actions", "elements": [
            {"type": "button", "action_id": "show_eng_for_bookmarks", "text": {"type": "plain_text", "text": "영어로 보기"}, "value": json.dumps({"user_key": user_key})}
        ]})
        channel_id = command.get("channel_id")
        client.chat_postMessage(channel=channel_id, text=f"{user_key} 북마크 (한글)", blocks=blocks)
        return

    # default: show both with delete buttons
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": f"*(북마크: {user_key})*"}}]
    for i, (tok, eng, kor) in enumerate(resolved, 1):
        sec = {"type": "section", "block_id": f"mark_both_item_{i}", "text": {"type": "mrkdwn", "text": f"{i}. {eng} : {kor}"}}
        del_val = json.dumps({"user_key": user_key, "token": tok}, ensure_ascii=False)
        action_id = f"bookmark_delete_{user_key}_{i}"
        sec["accessory"] = {"type": "button", "action_id": action_id, "text": {"type": "plain_text", "text": "삭제"}, "style": "danger", "value": del_val}
        blocks.append(sec)
    channel_id = command.get("channel_id")
    client.chat_postMessage(channel=channel_id, text=f"{user_key} 북마크", blocks=blocks)


@app.action(re.compile(r"^bookmark_select_"))
def on_bookmark_select(ack, body, client, logger):
    ack()
    try:
        action = body["actions"][0]
        selected = action.get("selected_option") or {}
        val = selected.get("value")
        payload = json.loads(val or "{}")
        user_key = payload.get("user_key")
        chapter = payload.get("chapter")
        index = int(payload.get("index")) if payload.get("index") is not None else None
        word = payload.get("word")
    except Exception as e:
        # send ephemeral error
        channel = body.get("container", {}).get("channel_id") or body.get("channel", {}).get("id")
        user_id = body.get("user", {}).get("id")
        if channel and user_id:
            client.chat_postEphemeral(channel=channel, user=user_id, text="버튼 데이터가 올바르지 않습니다.")
        return

    if not (user_key and chapter and index):
        channel = body.get("container", {}).get("channel_id") or body.get("channel", {}).get("id")
        user_id = body.get("user", {}).get("id")
        if channel and user_id:
            client.chat_postEphemeral(channel=channel, user=user_id, text="즐겨찾기 정보가 불완전합니다.")
        return

    token = f"{chapter}#{index}"
    try:
        bm = load_bookmarks()
        if user_key not in bm:
            bm[user_key] = []
        if token in bm[user_key]:
            channel = body.get("container", {}).get("channel_id") or body.get("channel", {}).get("id")
            user_id = body.get("user", {}).get("id")
            if channel and user_id:
                client.chat_postEphemeral(channel=channel, user=user_id, text=f"{user_key}의 즐겨찾기에 이미 있습니다: {word} ({token})")
            return
        bm[user_key].append(token)
        save_bookmarks(bm)
        channel = body.get("container", {}).get("channel_id") or body.get("channel", {}).get("id")
        user_id = body.get("user", {}).get("id")
        if channel and user_id:
            client.chat_postEphemeral(channel=channel, user=user_id, text=f"즐겨찾기 저장됨: {user_key} ← {word} ({token})")
    except Exception as e:
        logger.exception(e)
        channel = body.get("container", {}).get("channel_id") or body.get("channel", {}).get("id")
        user_id = body.get("user", {}).get("id")
        if channel and user_id:
            client.chat_postEphemeral(channel=channel, user=user_id, text=f"즐겨찾기 저장 중 오류: {e}")


@app.action("show_kor_for_bookmarks")
def on_show_kor_for_bookmarks(ack, body, client, respond, logger):
    ack()
    try:
        payload = json.loads(body["actions"][0].get("value", "{}"))
        user_key = payload.get("user_key")
    except Exception:
        respond(response_type="ephemeral", text="요청 정보가 유효하지 않습니다.")
        return

    bm = load_bookmarks()
    tokens = bm.get(user_key) or []
    resolved = resolve_bookmark_tokens(tokens)
    if not resolved:
        respond(response_type="ephemeral", text=f"'{user_key}'의 북마크가 없습니다.")
        return

    lines = [f"{i+1}. {kor}" for i, (_, _, kor) in enumerate(resolved)]
    body_text = "• " + "\n• ".join(lines)
    # update message blocks: append kor section
    blocks = body.get("message", {}).get("blocks", [])[:]
    if not any(b.get("block_id") == "mark_kor_added" for b in blocks):
        blocks.append({"type": "divider"})
    blocks.append({"type": "section", "block_id": "mark_kor_added", "text": {"type": "mrkdwn", "text": f"*한글 뜻*\n{body_text}"}})
    try:
        channel = body.get("container", {}).get("channel_id")
        ts = body.get("container", {}).get("message_ts")
        if not (channel and ts):
            respond(response_type="ephemeral", text="메시지 식별 정보가 없습니다.")
            return
        client.chat_update(channel=channel, ts=ts, blocks=blocks, text="한글 뜻 추가")
    except Exception as e:
        logger.exception(e)
        respond(response_type="ephemeral", text="메시지 업데이트 실패")


@app.action("show_eng_for_bookmarks")
def on_show_eng_for_bookmarks(ack, body, client, respond, logger):
    ack()
    try:
        payload = json.loads(body["actions"][0].get("value", "{}"))
        user_key = payload.get("user_key")
    except Exception:
        respond(response_type="ephemeral", text="요청 정보가 유효하지 않습니다.")
        return

    bm = load_bookmarks()
    tokens = bm.get(user_key) or []
    resolved = resolve_bookmark_tokens(tokens)
    if not resolved:
        respond(response_type="ephemeral", text=f"'{user_key}'의 북마크가 없습니다.")
        return

    lines = [f"{i+1}. {eng}" for i, (_, eng, _) in enumerate(resolved)]
    body_text = "• " + "\n• ".join(lines)
    blocks = body.get("message", {}).get("blocks", [])[:]
    if not any(b.get("block_id") == "mark_eng_added" for b in blocks):
        blocks.append({"type": "divider"})
    blocks.append({"type": "section", "block_id": "mark_eng_added", "text": {"type": "mrkdwn", "text": f"*영어*\n{body_text}"}})
    try:
        channel = body.get("container", {}).get("channel_id")
        ts = body.get("container", {}).get("message_ts")
        if not (channel and ts):
            respond(response_type="ephemeral", text="메시지 식별 정보가 없습니다.")
            return
        client.chat_update(channel=channel, ts=ts, blocks=blocks, text="영어 목록 추가")
    except Exception as e:
        logger.exception(e)
        respond(response_type="ephemeral", text="메시지 업데이트 실패")


@app.action(re.compile(r"^bookmark_delete_"))
def on_bookmark_delete(ack, body, client, logger):
    ack()
    try:
        action = body["actions"][0]
        val = action.get("value")
        payload = json.loads(val or "{}")
        user_key = payload.get("user_key")
        token = payload.get("token")
    except Exception as e:
        channel = body.get("container", {}).get("channel_id") or body.get("channel", {}).get("id")
        user_id = body.get("user", {}).get("id")
        if channel and user_id:
            client.chat_postEphemeral(channel=channel, user=user_id, text="삭제할 항목 정보를 읽지 못했습니다.")
        return

    if not (user_key and token):
        channel = body.get("container", {}).get("channel_id") or body.get("channel", {}).get("id")
        user_id = body.get("user", {}).get("id")
        if channel and user_id:
            client.chat_postEphemeral(channel=channel, user=user_id, text="삭제 정보가 불완전합니다.")
        return

    try:
        bm = load_bookmarks()
        if user_key not in bm or token not in bm[user_key]:
            channel = body.get("container", {}).get("channel_id") or body.get("channel", {}).get("id")
            user_id = body.get("user", {}).get("id")
            if channel and user_id:
                client.chat_postEphemeral(channel=channel, user=user_id, text=f"{user_key}의 북마크에 해당 항목이 없습니다: {token}")
            return
        bm[user_key].remove(token)
        save_bookmarks(bm)
        channel = body.get("container", {}).get("channel_id") or body.get("channel", {}).get("id")
        user_id = body.get("user", {}).get("id")
        if channel and user_id:
            client.chat_postEphemeral(channel=channel, user=user_id, text=f"삭제되었습니다: {token}")
    except Exception as e:
        logger.exception(e)
        channel = body.get("container", {}).get("channel_id") or body.get("channel", {}).get("id")
        user_id = body.get("user", {}).get("id")
        if channel and user_id:
            client.chat_postEphemeral(channel=channel, user=user_id, text=f"삭제 중 오류 발생: {e}")

# ================== 실행 ==================
if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
