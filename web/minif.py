"""Minificare conservatoare pentru build-ul web (fără dependențe): JS (comentarii, spații, rânduri goale), CSS, HTML.
Tokenizatorul JS cunoaște șirurile, șabloanele `...${}...`, expresiile regulate și comentariile; păstrează un rând nou
acolo unde inserarea automată de „;” (ASI) ar putea conta. E o îngreunare a citirii, nu o protecție."""
import re

_ID = re.compile(r"[A-Za-z0-9_$\u0080-￿]")
_KW_INAINTE_DE_REGEX = {"return", "typeof", "instanceof", "in", "of", "new", "delete", "void", "throw", "case", "do", "else", "yield", "await"}


def _id(ch):
    return bool(ch) and bool(_ID.match(ch))


def js(src: str) -> str:
    out = []            # bucăți emise
    i, n = 0, len(src)
    prev = ""           # ultimul caracter semnificativ emis
    prev2 = ""          # penultimul (pentru ++ / --)
    prev_tok = ""       # ultimul cuvânt / semn (pentru regex vs. împărțire)
    ws = False          # au fost spații de la ultimul semn
    nl = False          # a fost rând nou
    stack = []          # adâncimea acoladelor în ${...} din șabloane

    def emit(t, cuvant=None):
        nonlocal prev, prev2, prev_tok, ws, nl
        if out:
            a, b = prev, t[0]
            if nl and not (a in "{([,;:=&|?+*<>!%^~" and not (a in "+-" and prev2 == a)) \
                    and b not in ")]},;.?:":
                out.append("\n")
            elif (ws or nl) and (_id(a) and _id(b) or (a in "+-" and b in "+-") or (a == "/" and b in "/*") or (a == "." and b.isdigit())):
                out.append(" ")
        out.append(t)
        prev2 = t[-2] if len(t) > 1 else prev
        prev = t[-1]
        prev_tok = cuvant if cuvant is not None else t
        ws = nl = False

    def regex_permis():
        if not out:
            return True
        if prev_tok in _KW_INAINTE_DE_REGEX:
            return True
        return not (_id(prev) or prev in ")]}\"'`")

    def citeste_sir(j, q):
        k = j + 1
        while k < n:
            c = src[k]
            if c == "\\":
                k += 2; continue
            if c == q:
                return k + 1
            if c == "\n":
                raise ValueError("șir neterminat la %d" % j)
            k += 1
        raise ValueError("șir neterminat")

    def citeste_sablon(j):
        """de la ` (sau } care închide ${) până la ` sau ${ ; întoarce (sfârșit, se_deschide_expr)"""
        k = j + 1
        while k < n:
            c = src[k]
            if c == "\\":
                k += 2; continue
            if c == "`":
                return k + 1, False
            if c == "$" and src[k + 1:k + 2] == "{":
                return k + 2, True
            k += 1
        raise ValueError("șablon neterminat")

    while i < n:
        c = src[i]
        if c in " \t\r\f\v ﻿":
            ws = True; i += 1; continue
        if c in "\n  ":
            nl = True; i += 1; continue
        if c == "/" and src[i + 1:i + 2] == "/":
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "/" and src[i + 1:i + 2] == "*":
            j = src.find("*/", i + 2)
            if j < 0:
                raise ValueError("comentariu neterminat")
            if "\n" in src[i:j]:
                nl = True
            else:
                ws = True
            i = j + 2; continue
        if c in "'\"":
            j = citeste_sir(i, c); emit(src[i:j], "s"); i = j; continue
        if c == "`":
            j, deschis = citeste_sablon(i); emit(src[i:j], "s"); i = j
            if deschis:
                stack.append(0)
            continue
        if c == "}" and stack and stack[-1] == 0:
            stack.pop()
            j, deschis = citeste_sablon(i)
            out.append(src[i:j]); prev2 = src[j - 2]; prev = src[j - 1]; prev_tok = "s"; ws = nl = False; i = j
            if deschis:
                stack.append(0)
            continue
        if c == "/" and regex_permis():
            k, cls = i + 1, False
            while k < n:
                ch = src[k]
                if ch == "\\":
                    k += 2; continue
                if ch == "[":
                    cls = True
                elif ch == "]":
                    cls = False
                elif ch == "/" and not cls:
                    break
                elif ch == "\n":
                    raise ValueError("regex neterminat la %d" % i)
                k += 1
            k += 1
            while k < n and _id(src[k]):
                k += 1
            emit(src[i:k], "r"); i = k; continue
        if _id(c):
            j = i
            while j < n and (_id(src[j]) or (src[j] == "." and src[i].isdigit() and j + 1 < n and src[j + 1].isdigit())):
                j += 1
            emit(src[i:j]); i = j; continue
        if stack:
            if c == "{":
                stack[-1] += 1
            elif c == "}":
                stack[-1] -= 1
        emit(c); i += 1
    return "".join(out).strip() + "\n"


def css(src: str) -> str:
    s = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s*([{};,>])\s*", r"\1", s)
    s = s.replace(";}", "}")
    return s.strip()


def html(src: str) -> str:
    """minifică <style> și <script> (fără src) din pagină; în afara lor scoate comentariile HTML și indentarea"""
    parti = re.split(r"(<(?:script|style)[^>]*>.*?</(?:script|style)>)", src, flags=re.S | re.I)
    out = []
    for k, p in enumerate(parti):
        if k % 2:
            m = re.match(r"(<(script|style)[^>]*>)(.*)(</\2>)$", p, flags=re.S | re.I)
            if m.group(2).lower() == "style":
                p = m.group(1) + css(m.group(3)) + m.group(4)
            elif "src=" not in m.group(1) and m.group(3).strip():
                p = m.group(1) + "\n" + js(m.group(3)) + m.group(4)
        else:
            p = re.sub(r"<!--(?!\[if).*?-->", "", p, flags=re.S)
            p = re.sub(r"\n[ \t]+", "\n", p)
            p = re.sub(r"\n{2,}", "\n", p)
        out.append(p)
    return "".join(out)
