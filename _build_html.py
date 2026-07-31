# -*- coding: utf-8 -*-
import json
from pathlib import Path

p = Path(__file__).resolve().parent
data = json.loads((p / "data.json").read_text(encoding="utf-8"))
embedded = json.dumps(data, ensure_ascii=False)

html = r"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>영어 테스트</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;500;600;700&family=Literata:opsz,wght@7..72,500;7..72,600&display=swap" rel="stylesheet" />
  <style>
    :root {
      --bg: #f0f3f1;
      --ink: #1c2620;
      --muted: #5f6f66;
      --line: #c9d4cc;
      --card: #ffffff;
      --teal: #1f6f5b;
      --teal-soft: #dff0ea;
      --good: #1b6b3a;
      --bad: #a12828;
      --shadow: 0 16px 40px rgba(28, 38, 32, 0.08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: "IBM Plex Sans KR", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(900px 420px at 0% 0%, #d7e8df 0%, transparent 55%),
        radial-gradient(700px 380px at 100% 10%, #e4ebe4 0%, transparent 50%),
        var(--bg);
    }
    .app { width: min(860px, calc(100% - 28px)); margin: 0 auto; padding: 32px 0 72px; }
    h1 {
      font-family: "Literata", serif;
      font-size: clamp(1.8rem, 4vw, 2.4rem);
      font-weight: 600;
      margin: 0 0 6px;
      letter-spacing: -0.03em;
    }
    .lead { margin: 0 0 24px; color: var(--muted); }
    .card {
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 18px;
      box-shadow: var(--shadow);
      padding: 22px;
      margin-bottom: 14px;
    }
    .card h2 { margin: 0 0 14px; font-size: 1rem; font-weight: 600; }
    .modes { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
    @media (max-width: 900px) { .modes { grid-template-columns: 1fr; } }
    .check-row {
      display: flex;
      align-items: center;
      gap: 8px;
      margin: 14px 0 0;
      cursor: pointer;
      user-select: none;
      font-weight: 500;
    }
    .check-row input {
      width: auto;
      accent-color: var(--teal);
      margin: 0;
    }
    .mode {
      border: 1px solid var(--line);
      background: #fff;
      border-radius: 14px;
      padding: 16px;
      text-align: left;
      cursor: pointer;
      font: inherit;
      transition: border-color .15s, transform .15s;
    }
    .mode:hover { border-color: var(--teal); transform: translateY(-2px); }
    .mode strong { display: block; margin-bottom: 4px; }
    .mode span { color: var(--muted); font-size: 0.86rem; line-height: 1.4; }
    label { display: block; margin-bottom: 12px; }
    label > em, .field-label {
      display: block;
      font-style: normal;
      font-size: 0.84rem;
      color: var(--muted);
      margin-bottom: 6px;
    }
    input[type="text"], input[type="number"] {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 12px 14px;
      font: inherit;
      background: #fff;
    }
    input:focus { outline: 2px solid rgba(31, 111, 91, 0.25); border-color: var(--teal); }
    .chapters {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      max-height: 180px;
      overflow: auto;
      padding: 4px 2px 8px;
    }
    .chapters label {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      margin: 0;
      padding: 7px 11px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #fff;
      font-size: 0.86rem;
      cursor: pointer;
      user-select: none;
    }
    .chapters label:has(input:checked) {
      background: var(--teal-soft);
      border-color: var(--teal);
      color: var(--teal);
      font-weight: 600;
    }
    .chapters input { accent-color: var(--teal); }
    .row { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
    .btn {
      border: none;
      border-radius: 999px;
      padding: 11px 18px;
      font: inherit;
      font-weight: 600;
      cursor: pointer;
    }
    .btn:disabled { opacity: 0.45; cursor: not-allowed; }
    .btn-main { background: var(--teal); color: #fff; }
    .btn-sub { background: transparent; border: 1px solid var(--line); color: var(--ink); }
    .btn-soft { background: var(--teal-soft); color: var(--teal); }
    .btn-danger { background: #f8e4e4; color: var(--bad); }
    .btn-sm { padding: 8px 12px; font-size: 0.86rem; }
    .hide { display: none !important; }
    .bar { height: 8px; background: #e2e9e4; border-radius: 999px; overflow: hidden; margin-bottom: 16px; }
    .bar > i { display: block; height: 100%; width: 0; background: linear-gradient(90deg, #1f6f5b, #2f9a7f); transition: width .2s; }
    .meta { display: flex; justify-content: space-between; color: var(--muted); font-size: 0.9rem; margin-bottom: 8px; }
    .q {
      font-family: "Literata", serif;
      font-size: clamp(1.4rem, 3.8vw, 1.95rem);
      font-weight: 600;
      line-height: 1.35;
      margin: 8px 0 18px;
      word-break: keep-all;
    }
    .review {
      display: grid;
      gap: 10px;
      margin: 8px 0 18px;
      padding: 14px 16px;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: #f7faf8;
    }
    .review dt {
      font-size: 0.84rem;
      color: var(--muted);
      margin: 0;
    }
    .review dd {
      margin: 2px 0 0;
      font-size: 1.05rem;
      font-weight: 600;
      word-break: keep-all;
    }
    .marks { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 4px; }
    .mark {
      border: 2px solid var(--line);
      border-radius: 16px;
      padding: 18px 12px;
      font: inherit;
      font-size: 2rem;
      font-weight: 700;
      line-height: 1;
      cursor: pointer;
      background: #fff;
      transition: border-color .15s, background .15s, transform .15s;
    }
    .mark:hover { transform: translateY(-2px); }
    .mark-ok { color: var(--good); }
    .mark-ok:hover { border-color: var(--good); background: #e7f6ec; }
    .mark-no { color: var(--bad); }
    .mark-no:hover { border-color: var(--bad); background: #f8e8e8; }
    .list { display: grid; gap: 8px; }
    .item {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: start;
      padding: 12px 14px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: #fff;
    }
    .item small { display: block; margin-top: 4px; color: var(--muted); }
    .item-result {
      display: grid;
      grid-template-columns: auto 1fr auto;
      align-items: start;
    }
    .result-mark {
      width: 44px;
      height: 44px;
      border: 2px solid var(--line);
      border-radius: 12px;
      font: inherit;
      font-size: 1.35rem;
      font-weight: 700;
      line-height: 1;
      cursor: pointer;
      background: #fff;
      padding: 0;
      flex-shrink: 0;
      transition: border-color .15s, background .15s, color .15s;
    }
    .result-mark.is-ok {
      color: var(--good);
      border-color: var(--good);
      background: #e7f6ec;
    }
    .result-mark.is-no {
      color: var(--bad);
      border-color: var(--bad);
      background: #f8e8e8;
    }
    .toast {
      position: fixed;
      left: 50%;
      bottom: 22px;
      transform: translateX(-50%) translateY(16px);
      background: var(--ink);
      color: #fff;
      padding: 11px 16px;
      border-radius: 999px;
      font-size: 0.9rem;
      opacity: 0;
      transition: .2s;
      pointer-events: none;
      z-index: 20;
    }
    .toast.show { opacity: 1; transform: translateX(-50%) translateY(0); }
    .note { margin: 0; color: var(--muted); font-size: 0.88rem; line-height: 1.5; }
    .open-hint {
      margin: 0 0 16px;
      padding: 14px 16px;
      border: 1px solid #e2b86b;
      border-radius: 14px;
      background: #fff7e8;
      color: #6a4b12;
      font-size: 0.92rem;
      line-height: 1.55;
    }
    .open-hint strong { display: block; margin-bottom: 6px; }
    .open-hint ol { margin: 8px 0 0; padding-left: 1.2em; }
    .study-sticky {
      position: sticky;
      top: 0;
      z-index: 15;
      display: flex;
      flex-wrap: wrap;
      gap: 12px 18px;
      align-items: center;
      justify-content: space-between;
      padding: 12px 14px;
      margin-bottom: 12px;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: rgba(255, 255, 255, 0.96);
      box-shadow: var(--shadow);
      backdrop-filter: blur(8px);
    }
    .study-sticky .check-row { margin: 0; }
    .study-checks { display: flex; flex-wrap: wrap; gap: 14px; }
    .study-meta { color: var(--muted); font-size: 0.88rem; }
    .study-chapter {
      margin: 18px 0 8px;
      font-size: 0.92rem;
      font-weight: 700;
      color: var(--teal);
    }
    .study-chapter:first-child { margin-top: 0; }
    .study-row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      padding: 12px 14px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: #fff;
      margin-bottom: 8px;
    }
    @media (max-width: 600px) {
      .study-row { grid-template-columns: 1fr; }
    }
    .study-eng, .study-kor {
      word-break: keep-all;
      line-height: 1.45;
      min-height: 1.45em;
    }
    .study-eng {
      font-family: "Literata", serif;
      font-weight: 600;
      font-size: 1.05rem;
    }
    .study-kor { color: var(--ink); }
    .study-list.hide-eng .study-eng,
    .study-list.hide-kor .study-kor {
      visibility: hidden;
    }
  </style>
</head>
<body>
  <div class="app">
    <h1>영어 테스트</h1>
    <div class="open-hint" id="openHint">
      <strong>버튼이 안 눌리면 Safari로 열어 주세요</strong>
      카톡·미리보기에서는 시험이 동작하지 않습니다.
      <ol>
        <li>파일을 길게 눌러 <b>저장</b> / <b>파일에 저장</b></li>
        <li><b>파일</b> 앱에서 해당 HTML 열기</li>
        <li>하단 공유 → <b>Safari로 열기</b></li>
      </ol>
    </div>
    <p class="lead">HTML 파일만 열어서 바로 시험 보세요.</p>

    <section id="home">
      <div class="card">
        <h2>테스트 종류</h2>
        <div class="modes">
          <button class="mode" data-type="study">
            <strong>공부하기</strong>
            <span>단원 단어를 목록으로 보며 가리기 공부</span>
          </button>
          <button class="mode" data-type="eng2kor">
            <strong>영어 → 한글</strong>
            <span>영어를 보고 한글 뜻을 입력 · 랜덤 추가 가능</span>
          </button>
          <button class="mode" data-type="kor2eng">
            <strong>한글 → 영어</strong>
            <span>한글을 보고 영어를 입력 · 랜덤 추가 가능</span>
          </button>
        </div>
      </div>

      <div class="card">
        <h2>즐겨찾기</h2>
        <p class="note" id="favSummary"></p>
        <div class="row" style="margin-top:12px;">
          <button class="btn btn-soft" id="btnFavView">즐겨찾기 보기 / 복습</button>
          <button class="btn btn-sub btn-sm" id="btnExport">내보내기</button>
          <button class="btn btn-sub btn-sm" id="btnImport">가져오기</button>
          <input type="file" id="importFile" accept=".json,application/json" class="hide" />
        </div>
      </div>
    </section>

    <section id="setup" class="hide">
      <div class="card">
        <h2 id="setupTitle">설정</h2>
        <div id="chapterBlock">
          <div class="field-label" id="rangeLabel">출제 범위 선택</div>
          <div class="row" style="margin-bottom:10px;">
            <button class="btn btn-sub btn-sm" id="selWords">단어만</button>
            <button class="btn btn-sub btn-sm" id="selTalk">회화만</button>
            <button class="btn btn-sub btn-sm" id="selAll">전체 선택</button>
            <button class="btn btn-sub btn-sm" id="selNone">선택 해제</button>
          </div>
          <div class="chapters" id="chapterList"></div>
        </div>
        <div id="testOptions">
          <label class="check-row">
            <input type="checkbox" id="includeRandom" />
            <span>랜덤 테스트 포함 (전체에서 출제 · 영/한 방향 랜덤)</span>
          </label>
          <label id="randomCountBlock" class="hide" style="margin-top:12px;">
            <em>랜덤 문항 수</em>
            <input type="number" id="randomCount" min="1" max="300" value="10" />
          </label>
        </div>
        <div class="row" style="margin-top:14px;">
          <button class="btn btn-main" id="btnStart">시작</button>
          <button class="btn btn-sub" data-home>홈</button>
        </div>
      </div>
    </section>

    <section id="study" class="hide">
      <div class="study-sticky">
        <div class="study-checks">
          <label class="check-row">
            <input type="checkbox" id="hideKor" />
            <span>한글 가리기</span>
          </label>
          <label class="check-row">
            <input type="checkbox" id="hideEng" />
            <span>영단어 가리기</span>
          </label>
        </div>
        <span class="study-meta" id="studyMeta"></span>
        <button class="btn btn-sub btn-sm" data-home>홈</button>
      </div>
      <div class="card">
        <div class="study-list" id="studyList"></div>
      </div>
    </section>

    <section id="quiz" class="hide">
      <div class="card">
        <div class="bar"><i id="progress"></i></div>
        <div class="meta">
          <span id="qNum">1 / 10</span>
          <span id="qDir"></span>
        </div>
        <div class="q" id="qText"></div>
        <label>
          <em id="qHint">정답 입력</em>
          <input type="text" id="answer" autocomplete="off" spellcheck="false" />
        </label>
        <div class="row" style="margin-top:14px;">
          <button class="btn btn-main" id="btnNext">다음</button>
          <button class="btn btn-sub" data-home>그만두기</button>
        </div>
      </div>
    </section>

    <section id="grade" class="hide">
      <div class="card">
        <div class="bar"><i id="gProgress"></i></div>
        <div class="meta">
          <span id="gNum">채점 1 / 10</span>
          <span id="gDir"></span>
        </div>
        <div class="q" id="gText"></div>
        <dl class="review">
          <div>
            <dt>내 답</dt>
            <dd id="gUser"></dd>
          </div>
          <div>
            <dt>정답</dt>
            <dd id="gAnswer"></dd>
          </div>
        </dl>
        <p class="note">맞으면 ○, 틀리면 ✕를 누르세요.</p>
        <div class="marks">
          <button type="button" class="mark mark-ok" id="btnOk" aria-label="맞음">○</button>
          <button type="button" class="mark mark-no" id="btnNg" aria-label="틀림">✕</button>
        </div>
        <div class="row" style="margin-top:14px;">
          <button class="btn btn-sub" data-home>그만두기</button>
        </div>
      </div>
    </section>

    <section id="result" class="hide">
      <div class="card">
        <h2>결과</h2>
        <div class="q" id="score" style="margin-top:0;"></div>
        <p class="note" style="margin-bottom:12px;">○ / ✕를 누르면 채점을 수정할 수 있습니다.</p>
        <div class="list" id="resultList"></div>
        <div class="row" style="margin-top:16px;">
          <button class="btn btn-main" id="btnAgain">다시 풀기</button>
          <button class="btn btn-sub" data-home>홈</button>
        </div>
      </div>
    </section>

    <section id="favs" class="hide">
      <div class="card">
        <h2>즐겨찾기</h2>
        <p class="note" id="favNote"></p>
        <div class="list" id="favList" style="margin-top:12px;"></div>
        <div class="row" style="margin-top:16px;">
          <button class="btn btn-main" id="btnFavQuiz">즐겨찾기로 테스트</button>
          <button class="btn btn-sub" data-home>홈</button>
        </div>
      </div>
    </section>
  </div>

  <div class="toast" id="toast"></div>

  <script>
    // data.json 내용이 이 파일 안에 들어 있음 — 서버 없이 더블클릭으로 실행
    const DATA = __EMBEDDED_DATA__;
    const FAV_KEY = "eng-test-favorites";

    const state = {
      type: "eng2kor",
      quiz: [],
      i: 0,
      score: 0,
      answers: [],
      marks: [],
      favs: new Set(),
    };

    const $ = (s) => document.querySelector(s);
    const $$ = (s) => [...document.querySelectorAll(s)];

    function toast(msg) {
      const el = $("#toast");
      el.textContent = msg;
      el.classList.add("show");
      clearTimeout(toast.t);
      toast.t = setTimeout(() => el.classList.remove("show"), 2000);
    }

    function view(name) {
      ["home", "setup", "study", "quiz", "grade", "result", "favs"].forEach((id) => {
        document.getElementById(id).classList.toggle("hide", id !== name);
      });
    }

    function stripSound(eng) {
      return String(eng).replace(/\[[^\]]*\]/g, "").trim();
    }

    function expectedOf(q) {
      return q.kind === "eng" ? stripSound(q.eng) : q.kor;
    }

    function idOf(chapter, index) {
      return chapter + "::" + index;
    }

    function allPairs() {
      const eng = DATA.eng || {};
      const kor = DATA.kor || {};
      const keys = Object.keys(eng)
        .filter((k) => Array.isArray(eng[k]) && Array.isArray(kor[k]))
        .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
      const out = [];
      for (const ch of keys) {
        const n = Math.min(eng[ch].length, kor[ch].length);
        for (let i = 0; i < n; i++) {
          out.push({
            id: idOf(ch, i),
            chapter: ch,
            eng: String(eng[ch][i]),
            kor: String(kor[ch][i]),
          });
        }
      }
      return out;
    }

    function chapterNames() {
      const eng = DATA.eng || {};
      const kor = DATA.kor || {};
      return Object.keys(eng)
        .filter((k) => Array.isArray(eng[k]) && Array.isArray(kor[k]))
        .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
    }

    function shuffle(arr) {
      const a = arr.slice();
      for (let i = a.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [a[i], a[j]] = [a[j], a[i]];
      }
      return a;
    }

    function loadFavs() {
      try {
        const arr = JSON.parse(localStorage.getItem(FAV_KEY) || "[]");
        state.favs = new Set(Array.isArray(arr) ? arr : []);
      } catch (e) {
        state.favs = new Set();
      }
      updateFavSummary();
    }

    function saveFavs() {
      localStorage.setItem(FAV_KEY, JSON.stringify([...state.favs]));
      updateFavSummary();
    }

    function updateFavSummary() {
      $("#favSummary").textContent = "저장된 단어 " + state.favs.size + "개 · 이 브라우저에 자동 저장됩니다.";
    }

    function renderChapters() {
      const box = $("#chapterList");
      box.innerHTML = "";
      for (const ch of chapterNames()) {
        const lab = document.createElement("label");
        lab.innerHTML = '<input type="checkbox" value="' + ch + '" /> ' + ch;
        box.appendChild(lab);
      }
    }

    function selectedChapters() {
      return $$("#chapterList input:checked").map((el) => el.value);
    }

    function setChecks(pred) {
      $$("#chapterList input").forEach((el) => {
        el.checked = pred(el.value);
      });
    }

    function makeQuiz(pool, type, count) {
      // 일반 테스트는 단원·단어 순서 유지, 랜덤만 섞음
      let pick = type === "random" ? shuffle(pool) : pool.slice();
      if (count < pick.length) pick = pick.slice(0, count);

      if (type === "eng2kor") {
        return pick.map((p) => ({
          ...p,
          question: stripSound(p.eng),
          answer: p.kor,
          kind: "kor",
          hint: "한글 뜻",
          isRandom: false,
        }));
      }
      if (type === "kor2eng") {
        return pick.map((p) => ({
          ...p,
          question: p.kor,
          answer: stripSound(p.eng),
          kind: "eng",
          hint: "영어",
          isRandom: false,
        }));
      }

      return pick.map((p) => {
        const talk = String(p.chapter).toLowerCase().startsWith("s");
        if (talk || Math.random() < 0.5) {
          return { ...p, question: p.kor, answer: stripSound(p.eng), kind: "eng", hint: "영어", isRandom: true };
        }
        return { ...p, question: stripSound(p.eng), answer: p.kor, kind: "kor", hint: "한글 뜻", isRandom: true };
      });
    }

    function dirLabel(q) {
      const dir = q.kind === "eng" ? "한글 → 영어" : "영어 → 한글";
      return q.isRandom ? "랜덤 · " + dir : dir;
    }

    function openSetup(type) {
      state.type = type;
      const titles = { eng2kor: "영어 → 한글", kor2eng: "한글 → 영어", study: "공부하기" };
      $("#setupTitle").textContent = titles[type] || "설정";
      $("#includeRandom").checked = false;
      $("#randomCount").value = 10;
      $("#randomCountBlock").classList.add("hide");
      const isStudy = type === "study";
      const testOptions = $("#testOptions");
      if (testOptions) testOptions.classList.toggle("hide", isStudy);
      const rangeLabel = $("#rangeLabel");
      if (rangeLabel) rangeLabel.textContent = isStudy ? "공부 범위 선택" : "출제 범위 선택";
      $("#btnStart").textContent = isStudy ? "공부 시작" : "시작";
      view("setup");
    }

    function startFromSetup() {
      if (state.type === "study") {
        startStudy();
        return;
      }

      let pool = allPairs();
      const sel = selectedChapters();
      if (sel.length) pool = pool.filter((p) => sel.includes(p.chapter));
      if (!pool.length) {
        toast("선택한 범위에 문제가 없습니다");
        return;
      }

      const main = makeQuiz(pool, state.type, pool.length);
      let quiz = main;

      if ($("#includeRandom").checked) {
        const n = Math.max(1, Math.min(300, Number($("#randomCount").value) || 10));
        const used = new Set(main.map((q) => q.id));
        let rpool = allPairs().filter((p) => !used.has(p.id));
        if (rpool.length < n) rpool = allPairs();
        quiz = main.concat(makeQuiz(rpool, "random", n));
      }

      beginQuiz(quiz);
    }

    function startStudy() {
      let pool = allPairs();
      const sel = selectedChapters();
      if (sel.length) pool = pool.filter((p) => sel.includes(p.chapter));
      if (!pool.length) {
        toast("선택한 범위에 단어가 없습니다");
        return;
      }

      const box = $("#studyList");
      box.innerHTML = "";
      box.classList.remove("hide-eng", "hide-kor");
      $("#hideEng").checked = false;
      $("#hideKor").checked = false;

      let lastCh = "";
      for (const p of pool) {
        if (p.chapter !== lastCh) {
          lastCh = p.chapter;
          const h = document.createElement("div");
          h.className = "study-chapter";
          h.textContent = p.chapter;
          box.appendChild(h);
        }
        const row = document.createElement("div");
        row.className = "study-row";
        row.innerHTML =
          '<div class="study-eng">' + esc(stripSound(p.eng)) + "</div>" +
          '<div class="study-kor">' + esc(p.kor) + "</div>";
        box.appendChild(row);
      }

      $("#studyMeta").textContent = pool.length + "개 · " +
        (sel.length ? sel.length + "개 단원" : "전체");
      view("study");
      window.scrollTo(0, 0);
    }

    function applyStudyHide() {
      const box = $("#studyList");
      box.classList.toggle("hide-eng", $("#hideEng").checked);
      box.classList.toggle("hide-kor", $("#hideKor").checked);
    }

    function beginQuiz(quiz) {
      state.quiz = quiz;
      state.i = 0;
      state.score = 0;
      state.answers = new Array(quiz.length).fill("");
      state.marks = new Array(quiz.length).fill(null);
      view("quiz");
      showQ();
      $("#answer").focus();
    }

    function showQ() {
      const q = state.quiz[state.i];
      const total = state.quiz.length;
      const last = state.i + 1 >= total;
      $("#qNum").textContent = (state.i + 1) + " / " + total;
      $("#progress").style.width = ((state.i / total) * 100) + "%";
      $("#qDir").textContent = dirLabel(q);
      $("#qText").textContent = q.question;
      $("#qHint").textContent = q.hint + " 입력";
      $("#answer").value = state.answers[state.i] || "";
      $("#answer").disabled = false;
      $("#btnNext").textContent = last ? "채점하기" : "다음";
    }

    function esc(s) {
      return String(s)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
    }

    function next() {
      state.answers[state.i] = $("#answer").value;
      if (state.i + 1 >= state.quiz.length) {
        beginGrade();
        return;
      }
      state.i += 1;
      showQ();
      $("#answer").focus();
    }

    function beginGrade() {
      state.i = 0;
      view("grade");
      showGrade();
    }

    function showGrade() {
      const q = state.quiz[state.i];
      const total = state.quiz.length;
      $("#gNum").textContent = "채점 " + (state.i + 1) + " / " + total;
      $("#gProgress").style.width = ((state.i / total) * 100) + "%";
      $("#gDir").textContent = dirLabel(q);
      $("#gText").textContent = q.question;
      $("#gUser").textContent = (state.answers[state.i] || "").trim() || "(미입력)";
      $("#gAnswer").textContent = expectedOf(q);
    }

    function mark(ok) {
      state.marks[state.i] = ok;
      if (state.i + 1 >= state.quiz.length) {
        finishGrade();
        return;
      }
      state.i += 1;
      showGrade();
    }

    function finishGrade() {
      updateScore();
      showResult();
    }

    function updateScore() {
      state.score = state.marks.filter((m) => m === true).length;
      $("#score").textContent = state.score + " / " + state.quiz.length + " 정답";
    }

    function showResult() {
      updateScore();
      const box = $("#resultList");
      box.innerHTML = "";
      state.quiz.forEach((q, i) => {
        const user = (state.answers[i] || "").trim() || "(미입력)";
        const expected = expectedOf(q);
        const ok = state.marks[i] === true;
        const saved = state.favs.has(q.id);
        const div = document.createElement("div");
        div.className = "item item-result";
        div.innerHTML =
          '<button type="button" class="result-mark ' + (ok ? "is-ok" : "is-no") +
          '" aria-label="채점 수정">' + (ok ? "○" : "✕") + "</button>" +
          "<div><div><b>" + esc(q.question) + "</b></div>" +
          "<small>" + esc(dirLabel(q)) + " · " + esc(q.chapter) + "</small>" +
          "<small>내 답: " + esc(user) + "</small>" +
          "<small>정답: " + esc(expected) + "</small></div>" +
          '<button type="button" class="btn btn-soft btn-sm"' + (saved ? " disabled" : "") + ">" +
          (saved ? "저장됨" : "★ 저장") + "</button>";

        const markBtn = div.querySelector(".result-mark");
        markBtn.addEventListener("click", () => {
          state.marks[i] = state.marks[i] !== true;
          const nowOk = state.marks[i] === true;
          markBtn.textContent = nowOk ? "○" : "✕";
          markBtn.classList.toggle("is-ok", nowOk);
          markBtn.classList.toggle("is-no", !nowOk);
          updateScore();
        });

        const favBtn = div.querySelector(".btn");
        favBtn.addEventListener("click", () => {
          state.favs.add(q.id);
          saveFavs();
          favBtn.textContent = "저장됨";
          favBtn.disabled = true;
          toast("저장됨");
        });
        box.appendChild(div);
      });
      view("result");
    }

    function renderFavs() {
      const map = new Map(allPairs().map((p) => [p.id, p]));
      const list = [...state.favs].map((id) => map.get(id)).filter(Boolean);
      $("#favNote").textContent = list.length + "개 (브라우저 저장)";
      const box = $("#favList");
      box.innerHTML = "";
      if (!list.length) {
        box.innerHTML = '<p class="note">아직 없습니다. 결과 화면에서 ★로 추가하세요.</p>';
        return;
      }
      for (const p of list) {
        const div = document.createElement("div");
        div.className = "item";
        div.innerHTML =
          "<div><div><b>" + esc(stripSound(p.eng)) + "</b> — " + esc(p.kor) +
          "</div><small>" + esc(p.chapter) + "</small></div>" +
          '<button class="btn btn-danger btn-sm">삭제</button>';
        div.querySelector("button").addEventListener("click", () => {
          state.favs.delete(p.id);
          saveFavs();
          renderFavs();
        });
        box.appendChild(div);
      }
    }

    function startFavQuiz() {
      const map = new Map(allPairs().map((p) => [p.id, p]));
      const pool = [...state.favs].map((id) => map.get(id)).filter(Boolean);
      if (!pool.length) {
        toast("즐겨찾기가 비어 있습니다");
        return;
      }
      state.type = "fav";
      beginQuiz(makeQuiz(pool, "random", pool.length));
    }

    $$(".mode").forEach((btn) => {
      btn.addEventListener("click", () => openSetup(btn.dataset.type));
    });
    $$("[data-home]").forEach((btn) => {
      btn.addEventListener("click", () => {
        updateFavSummary();
        view("home");
      });
    });

    $("#selWords").onclick = () => setChecks((v) => v.toLowerCase().startsWith("p"));
    $("#selTalk").onclick = () => setChecks((v) => v.toLowerCase().startsWith("s"));
    $("#selAll").onclick = () => setChecks(() => true);
    $("#selNone").onclick = () => setChecks(() => false);

    $("#includeRandom").onchange = () => {
      $("#randomCountBlock").classList.toggle("hide", !$("#includeRandom").checked);
    };
    $("#hideEng").onchange = applyStudyHide;
    $("#hideKor").onchange = applyStudyHide;
    $("#btnStart").onclick = startFromSetup;
    $("#btnNext").onclick = next;
    $("#btnOk").onclick = () => mark(true);
    $("#btnNg").onclick = () => mark(false);
    $("#btnAgain").onclick = () => {
      if (state.type === "fav") startFavQuiz();
      else openSetup(state.type);
    };

    $("#answer").addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        next();
      }
    });

    document.addEventListener("keydown", (e) => {
      if ($("#grade").classList.contains("hide")) return;
      if (e.key === "o" || e.key === "O" || e.key === "ㅇ") {
        e.preventDefault();
        mark(true);
      } else if (e.key === "x" || e.key === "X" || e.key === "ㅌ") {
        e.preventDefault();
        mark(false);
      }
    });

    $("#btnFavView").onclick = () => {
      renderFavs();
      view("favs");
    };
    $("#btnFavQuiz").onclick = startFavQuiz;

    $("#btnExport").onclick = () => {
      const blob = new Blob([JSON.stringify([...state.favs], null, 2)], { type: "application/json" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "favorites.json";
      a.click();
      URL.revokeObjectURL(a.href);
      toast("favorites.json 다운로드");
    };
    $("#btnImport").onclick = () => $("#importFile").click();
    $("#importFile").onchange = async (e) => {
      const f = e.target.files && e.target.files[0];
      if (!f) return;
      try {
        const arr = JSON.parse(await f.text());
        state.favs = new Set(Array.isArray(arr) ? arr : []);
        saveFavs();
        toast("가져오기 완료");
      } catch (err) {
        toast("파일 형식이 올바르지 않습니다");
      }
      e.target.value = "";
    };

    renderChapters();
    loadFavs();
    const hint = $("#openHint");
    if (hint) hint.classList.add("hide");
  </script>
</body>
</html>
"""

out = html.replace("__EMBEDDED_DATA__", embedded)
(p / "index.html").write_text(out, encoding="utf-8")
print("ok", (p / "index.html").stat().st_size)
