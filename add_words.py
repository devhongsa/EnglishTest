# -*- coding: utf-8 -*-
"""data.json 단어 빠른 추가/수정 UI — Tab으로 이동, Enter로 저장."""

import json
import re
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data.json"

# Windows 입력기: 영어칸=영문, 한글칸=한글
LANG_EN = "00000409"
LANG_KO = "00000412"
IME_CMODE_NATIVE = 0x0001  # Hangul
IME_CMODE_FULLSHAPE = 0x0008
WM_INPUTLANGCHANGEREQUEST = 0x0050


def set_input_lang(lang_id: str, hangul: bool | None = None) -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.LoadKeyboardLayoutW.argtypes = (wintypes.LPCWSTR, wintypes.UINT)
        user32.LoadKeyboardLayoutW.restype = wintypes.HKL
        user32.ActivateKeyboardLayout.argtypes = (wintypes.HKL, wintypes.UINT)
        user32.ActivateKeyboardLayout.restype = wintypes.HKL
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        user32.PostMessageW.restype = wintypes.BOOL

        hkl = user32.LoadKeyboardLayoutW(lang_id, 1)
        if hkl:
            user32.ActivateKeyboardLayout(hkl, 0)
            hwnd = user32.GetForegroundWindow()
            if hwnd:
                user32.PostMessageW(hwnd, WM_INPUTLANGCHANGEREQUEST, 0, hkl)

        if hangul is not None:
            imm32 = ctypes.WinDLL("imm32", use_last_error=True)
            imm32.ImmGetContext.argtypes = (wintypes.HWND,)
            imm32.ImmGetContext.restype = wintypes.HANDLE
            imm32.ImmReleaseContext.argtypes = (wintypes.HWND, wintypes.HANDLE)
            imm32.ImmReleaseContext.restype = wintypes.BOOL
            imm32.ImmGetConversionStatus.argtypes = (
                wintypes.HANDLE,
                ctypes.POINTER(wintypes.DWORD),
                ctypes.POINTER(wintypes.DWORD),
            )
            imm32.ImmGetConversionStatus.restype = wintypes.BOOL
            imm32.ImmSetConversionStatus.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD)
            imm32.ImmSetConversionStatus.restype = wintypes.BOOL

            hwnd = user32.GetForegroundWindow()
            himc = imm32.ImmGetContext(hwnd) if hwnd else None
            if himc:
                conv = wintypes.DWORD()
                sent = wintypes.DWORD()
                if imm32.ImmGetConversionStatus(himc, ctypes.byref(conv), ctypes.byref(sent)):
                    mode = int(conv.value)
                    if hangul:
                        mode |= IME_CMODE_NATIVE
                        mode &= ~IME_CMODE_FULLSHAPE
                    else:
                        mode &= ~IME_CMODE_NATIVE
                    imm32.ImmSetConversionStatus(himc, mode, sent.value)
                imm32.ImmReleaseContext(hwnd, himc)
    except Exception:
        pass


def set_english_input() -> None:
    set_input_lang(LANG_EN, hangul=False)


def set_korean_input() -> None:
    set_input_lang(LANG_KO, hangul=True)


def normalize_chapter(raw: str) -> str:
    s = raw.strip().replace(" ", "")
    if not s:
        return ""
    s = re.sub(r"^([pPsS])\.", r"\1", s)
    return s[0].lower() + s[1:]


def chapter_sort_key(k: str):
    return [int(x) if x.isdigit() else x for x in re.findall(r"\d+|[^\d]+", k)]


def load_data() -> dict:
    with DATA_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("eng", {})
    data.setdefault("kor", {})
    return data


def save_data(data: dict) -> None:
    eng = data["eng"]
    kor = data["kor"]
    keys = sorted(set(eng) | set(kor), key=chapter_sort_key)
    out = {"eng": {}, "kor": {}}
    for k in keys:
        out["eng"][k] = list(eng.get(k, []))
        out["kor"][k] = list(kor.get(k, []))
    with DATA_PATH.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=4)
        f.write("\n")


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("영어 단어 추가/수정 — data.json")
        self.geometry("920x600")
        self.minsize(760, 480)

        self.data = load_data()
        self.edit_index = None  # None=추가, int=수정
        self._build()
        self.refresh_chapters()
        self.chapter_entry.focus_set()

    def _build(self) -> None:
        root = ttk.Frame(self, padding=10)
        root.pack(fill="both", expand=True)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(0, weight=1)

        # 왼쪽: 단원 목록
        left = ttk.Frame(root)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left.rowconfigure(2, weight=1)

        ttk.Label(left, text="단원 목록").grid(row=0, column=0, sticky="w")
        self.ch_filter = tk.StringVar()
        filt = ttk.Entry(left, textvariable=self.ch_filter, width=18)
        filt.grid(row=1, column=0, sticky="we", pady=(4, 6))
        filt.bind("<KeyRelease>", lambda e: self.refresh_chapters())

        self.chapter_list = tk.Listbox(left, width=18, activestyle="dotbox", exportselection=False)
        self.chapter_list.grid(row=2, column=0, sticky="nsew")
        ch_scroll = ttk.Scrollbar(left, orient="vertical", command=self.chapter_list.yview)
        ch_scroll.grid(row=2, column=1, sticky="ns")
        self.chapter_list.configure(yscrollcommand=ch_scroll.set)
        self.chapter_list.bind("<<ListboxSelect>>", self.on_chapter_select)

        ttk.Button(left, text="새로고침", command=self.reload_all).grid(row=3, column=0, sticky="we", pady=(8, 0))

        # 오른쪽
        right = ttk.Frame(root)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(1, weight=1)

        pad = {"padx": 6, "pady": 4}

        ttk.Label(right, text="단원").grid(row=0, column=0, sticky="w", **pad)
        self.chapter_var = tk.StringVar()
        self.chapter_entry = ttk.Entry(right, textvariable=self.chapter_var)
        self.chapter_entry.grid(row=0, column=1, sticky="we", **pad)
        self.chapter_entry.bind("<Return>", lambda e: self.load_chapter_from_entry())
        self.chapter_entry.bind("<FocusOut>", lambda e: self.load_chapter_from_entry())
        ttk.Button(right, text="불러오기", command=self.load_chapter_from_entry).grid(row=0, column=2, **pad)

        ttk.Label(right, text="영어").grid(row=1, column=0, sticky="w", **pad)
        self.eng_var = tk.StringVar()
        self.eng_entry = ttk.Entry(right, textvariable=self.eng_var)
        self.eng_entry.grid(row=1, column=1, columnspan=2, sticky="we", **pad)
        self.eng_entry.bind("<FocusIn>", lambda e: set_english_input())

        ttk.Label(right, text="한글").grid(row=2, column=0, sticky="w", **pad)
        self.kor_var = tk.StringVar()
        self.kor_entry = ttk.Entry(right, textvariable=self.kor_var)
        self.kor_entry.grid(row=2, column=1, columnspan=2, sticky="we", **pad)
        self.kor_entry.bind("<Return>", lambda e: self.save_pair())
        self.kor_entry.bind("<FocusIn>", lambda e: set_korean_input())

        self.mode_var = tk.StringVar(value="모드: 추가")
        ttk.Label(right, textvariable=self.mode_var, foreground="#1f6f5b").grid(
            row=3, column=0, columnspan=3, sticky="w", **pad
        )

        btns = ttk.Frame(right)
        btns.grid(row=4, column=0, columnspan=3, sticky="we", **pad)
        ttk.Button(btns, text="저장 (Enter)", command=self.save_pair).pack(side="left", padx=(0, 6))
        ttk.Button(btns, text="새 항목 모드", command=self.clear_edit_mode).pack(side="left", padx=(0, 6))
        ttk.Button(btns, text="선택 삭제", command=self.delete_selected).pack(side="left", padx=(0, 6))
        ttk.Button(btns, text="HTML 빌드", command=self.rebuild_html).pack(side="left", padx=(0, 6))
        self.auto_build = tk.BooleanVar(value=False)
        ttk.Checkbutton(btns, text="저장 후 HTML 빌드", variable=self.auto_build).pack(side="left")

        self.status = tk.StringVar(value=str(DATA_PATH))
        ttk.Label(right, textvariable=self.status, foreground="#444").grid(
            row=5, column=0, columnspan=3, sticky="w", **pad
        )

        ttk.Label(right, text="단어 목록 (클릭/더블클릭 = 수정)").grid(row=6, column=0, columnspan=3, sticky="w", **pad)
        list_frame = ttk.Frame(right)
        list_frame.grid(row=7, column=0, columnspan=3, sticky="nsew", **pad)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        right.rowconfigure(7, weight=1)

        self.word_list = tk.Listbox(list_frame, activestyle="dotbox", exportselection=False)
        self.word_list.grid(row=0, column=0, sticky="nsew")
        w_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.word_list.yview)
        w_scroll.grid(row=0, column=1, sticky="ns")
        self.word_list.configure(yscrollcommand=w_scroll.set)
        self.word_list.bind("<<ListboxSelect>>", self.on_word_select)
        self.word_list.bind("<Double-Button-1>", self.on_word_select)
        self.word_list.bind("<Delete>", lambda e: self.delete_selected())

        tip = (
            "왼쪽에서 단원을 고르면 단어를 볼 수 있습니다. 단어를 클릭하면 수정 모드로 바뀝니다.\n"
            "빠른 추가: 단원 입력 → Tab → 영어 → Tab → 한글 → Enter"
        )
        ttk.Label(right, text=tip, foreground="#555").grid(row=8, column=0, columnspan=3, sticky="w", **pad)

        self.chapter_entry.bind("<Tab>", self._tab_to_eng)
        self.eng_entry.bind("<Tab>", self._tab_to_kor)
        self.kor_entry.bind("<Tab>", self._tab_save)

    def _tab_to_eng(self, _e=None):
        self.load_chapter_from_entry()
        set_english_input()
        self.eng_entry.focus_set()
        self.eng_entry.selection_range(0, "end")
        return "break"

    def _tab_to_kor(self, _e=None):
        set_korean_input()
        self.kor_entry.focus_set()
        self.kor_entry.selection_range(0, "end")
        return "break"

    def _tab_save(self, _e=None):
        self.save_pair()
        return "break"

    def current_chapter(self) -> str:
        return normalize_chapter(self.chapter_var.get())

    def reload_all(self) -> None:
        self.data = load_data()
        self.refresh_chapters()
        self.refresh_words()
        self.status.set(f"다시 불러옴 · {DATA_PATH}")

    def all_chapters(self):
        return sorted(set(self.data["eng"]) | set(self.data["kor"]), key=chapter_sort_key)

    def refresh_chapters(self) -> None:
        q = self.ch_filter.get().strip().lower()
        cur = self.current_chapter()
        self.chapter_list.delete(0, "end")
        for ch in self.all_chapters():
            if q and q not in ch.lower():
                continue
            n = max(len(self.data["eng"].get(ch, [])), len(self.data["kor"].get(ch, [])))
            self.chapter_list.insert("end", f"{ch}  ({n})")
            if ch == cur:
                self.chapter_list.selection_set("end")
                self.chapter_list.see("end")

    def on_chapter_select(self, _e=None) -> None:
        sel = self.chapter_list.curselection()
        if not sel:
            return
        text = self.chapter_list.get(sel[0])
        ch = text.split()[0]
        self.chapter_var.set(ch)
        self.clear_edit_mode(focus=False)
        self.refresh_words()

    def load_chapter_from_entry(self) -> None:
        ch = self.current_chapter()
        if ch:
            self.chapter_var.set(ch)
        self.clear_edit_mode(focus=False)
        self.refresh_chapters()
        self.refresh_words()

    def refresh_words(self) -> None:
        ch = self.current_chapter()
        self.word_list.delete(0, "end")
        if not ch:
            self.status.set(f"{DATA_PATH}  ·  단원을 선택하거나 입력하세요")
            return
        eng = self.data["eng"].get(ch, [])
        kor = self.data["kor"].get(ch, [])
        n = max(len(eng), len(kor))
        for i in range(n):
            e = eng[i] if i < len(eng) else ""
            k = kor[i] if i < len(kor) else ""
            self.word_list.insert("end", f"{i + 1:3d}.  {e}  —  {k}")
        kind = "있음" if ch in self.data["eng"] or ch in self.data["kor"] else "새 단원"
        mode = f"수정 #{self.edit_index + 1}" if self.edit_index is not None else "추가"
        self.status.set(f"{DATA_PATH}  ·  [{ch}] {n}개 ({kind})  ·  모드: {mode}")
        self.mode_var.set(f"모드: {mode}")

    def on_word_select(self, _e=None) -> None:
        ch = self.current_chapter()
        sel = self.word_list.curselection()
        if not ch or not sel:
            return
        i = sel[0]
        eng = self.data["eng"].get(ch, [])
        kor = self.data["kor"].get(ch, [])
        self.edit_index = i
        self.eng_var.set(eng[i] if i < len(eng) else "")
        self.kor_var.set(kor[i] if i < len(kor) else "")
        self.mode_var.set(f"모드: 수정 #{i + 1}")
        self.status.set(f"[{ch}] {i + 1}번 수정 중 — 저장하면 해당 항목이 바뀝니다")

    def clear_edit_mode(self, focus: bool = True) -> None:
        self.edit_index = None
        self.eng_var.set("")
        self.kor_var.set("")
        self.mode_var.set("모드: 추가")
        self.word_list.selection_clear(0, "end")
        if focus:
            self.eng_entry.focus_set()
        ch = self.current_chapter()
        if ch:
            n = max(len(self.data["eng"].get(ch, [])), len(self.data["kor"].get(ch, [])))
            self.status.set(f"[{ch}] {n}개  ·  모드: 추가")

    def save_pair(self) -> None:
        ch = self.current_chapter()
        eng = self.eng_var.get().strip()
        kor = self.kor_var.get().strip()
        if not ch:
            messagebox.showwarning("입력", "단원을 입력하세요. 예: p7.4 / s12")
            self.chapter_entry.focus_set()
            return
        if not eng or not kor:
            messagebox.showwarning("입력", "영어와 한글을 모두 입력하세요.")
            (self.eng_entry if not eng else self.kor_entry).focus_set()
            return

        self.data["eng"].setdefault(ch, [])
        self.data["kor"].setdefault(ch, [])
        while len(self.data["kor"][ch]) < len(self.data["eng"][ch]):
            self.data["kor"][ch].append("")
        while len(self.data["eng"][ch]) < len(self.data["kor"][ch]):
            self.data["eng"][ch].append("")

        if self.edit_index is not None:
            i = self.edit_index
            if i >= len(self.data["eng"][ch]):
                messagebox.showerror("수정", "선택한 항목을 찾을 수 없습니다.")
                self.clear_edit_mode()
                return
            self.data["eng"][ch][i] = eng
            self.data["kor"][ch][i] = kor
        else:
            self.data["eng"][ch].append(eng)
            self.data["kor"][ch].append(kor)

        try:
            save_data(self.data)
            self.data = load_data()
        except Exception as e:
            messagebox.showerror("저장 실패", str(e))
            return

        was_edit = self.edit_index
        self.clear_edit_mode(focus=False)
        self.refresh_chapters()
        self.refresh_words()
        if was_edit is None:
            self.word_list.see("end")
        self.eng_entry.focus_set()

        if self.auto_build.get():
            self.rebuild_html(silent=True)

    def delete_selected(self) -> None:
        ch = self.current_chapter()
        sel = self.word_list.curselection()
        if not ch or not sel:
            messagebox.showinfo("삭제", "삭제할 단어를 목록에서 선택하세요.")
            return
        i = sel[0]
        if not messagebox.askyesno("삭제", f"[{ch}] {i + 1}번 항목을 삭제할까요?"):
            return
        eng = self.data["eng"].get(ch, [])
        kor = self.data["kor"].get(ch, [])
        if i < len(eng):
            eng.pop(i)
        if i < len(kor):
            kor.pop(i)
        self.data["eng"][ch] = eng
        self.data["kor"][ch] = kor
        if not eng and not kor:
            self.data["eng"].pop(ch, None)
            self.data["kor"].pop(ch, None)
        save_data(self.data)
        self.data = load_data()
        self.clear_edit_mode(focus=False)
        self.refresh_chapters()
        self.refresh_words()

    def rebuild_html(self, silent: bool = False) -> None:
        """현재 index.html 폼은 유지하고 data.json 단어만 주입."""
        script = ROOT / "_build_html.py"
        if not script.exists():
            if not silent:
                messagebox.showerror("빌드", "_build_html.py 가 없습니다.")
            return
        try:
            r = subprocess.run(
                [sys.executable, str(script)],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
            )
            msg = (r.stdout or r.stderr or "").strip() or "완료"
            if r.returncode != 0:
                messagebox.showerror("빌드 실패", msg)
            elif not silent:
                messagebox.showinfo("빌드", "index.html 폼은 그대로 두고 단어 데이터만 갱신했습니다.\n" + msg)
            else:
                self.status.set(f"저장 + HTML 데이터 갱신 완료 · {msg}")
        except Exception as e:
            messagebox.showerror("빌드 실패", str(e))


if __name__ == "__main__":
    App().mainloop()
