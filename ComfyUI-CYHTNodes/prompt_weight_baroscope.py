import os
import re
import math
from typing import List, Dict, Any, Optional

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont


NODE_PREFIX = "KZ_PWB"
NODE_DISPLAY_NAME = "提示词权重可视化 (Prompt Weight Baroscope)"


_FONT_CACHE: Dict[int, ImageFont.ImageFont] = {}


def _get_font(size: int = 14):
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]

    candidates = [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/msyhbd.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]

    for path in candidates:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size)
                _FONT_CACHE[size] = font
                return font
            except Exception:
                continue

    font = ImageFont.load_default()
    _FONT_CACHE[size] = font
    return font


_BRACKET_PAIRS = {"(": ")", "[": "]", "{": "}"}
_BRACKET_DEFAULT = {"(": 1.1, "[": 0.9, "{": 1.05}
_WEIGHT_TAIL_RE = re.compile(r":\s*([-+]?\d*\.?\d+)\s*$")


def _find_matching(text, start, open_ch, close_ch):
    depth = 0
    i = start
    n = len(text)
    while i < n:
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _split_weight(inner):
    m = _WEIGHT_TAIL_RE.search(inner)
    if m:
        try:
            return inner[: m.start()], float(m.group(1))
        except ValueError:
            return inner, None
    return inner, None


def _flush_segments(buf, weight, depth, out):
    plain = "".join(buf)
    for seg in re.split(r"[,\n;]+", plain):
        seg = seg.strip()
        if seg:
            out.append({"text": seg, "weight": weight, "depth": depth})


def _parse(text, base_weight, depth, out, a1111):
    i = 0
    n = len(text)
    buf = []

    while i < n:
        c = text[i]

        if c == "\\" and i + 1 < n:
            buf.append(text[i + 1])
            i += 2
            continue

        if c in _BRACKET_PAIRS:
            close_ch = _BRACKET_PAIRS[c]
            j = _find_matching(text, i, c, close_ch)
            if j == -1:
                buf.append(c)
                i += 1
                continue

            if buf:
                _flush_segments(buf, base_weight, depth, out)
                buf = []

            inner = text[i + 1:j]
            inner_text, explicit_w = _split_weight(inner)

            if explicit_w is not None:
                factor = explicit_w
            else:
                factor = _BRACKET_DEFAULT[c] if a1111 else 1.0
                inner_text = inner

            _parse(inner_text, base_weight * factor, depth + 1, out, a1111)
            i = j + 1
            continue

        if c in ")]}":
            buf.append(c)
            i += 1
            continue

        buf.append(c)
        i += 1

    if buf:
        _flush_segments(buf, base_weight, depth, out)


def parse_prompt(text, a1111=True):
    out = []
    _parse(text or "", 1.0, 0, out, a1111)
    return out


def _approx_token_count(text):
    total = 0.0
    for ch in text:
        cp = ord(ch)
        if 0x4E00 <= cp <= 0x9FFF or 0x3040 <= cp <= 0x30FF or 0xAC00 <= cp <= 0xD7AF:
            total += 1.5
        elif ch.isalpha():
            total += 0.3
        elif ch.isdigit():
            total += 0.3
        elif ch.isspace():
            total += 0.1
        else:
            total += 0.4
    return max(1, int(math.ceil(total)))


def _clip_token_count(clip, text):
    if clip is None:
        return None
    try:
        chunks = clip.tokenize(text)
    except Exception:
        return None

    total = 0
    try:
        for chunk in chunks:
            if isinstance(chunk, dict):
                toks = chunk.get("tokens", [])
                total += len(toks)
            elif isinstance(chunk, (list, tuple)):
                total += len(chunk)
    except Exception:
        return None

    return total if total > 0 else None


def _check_balance(text):
    stack = []
    pairs = {")": "(", "]": "[", "}": "{"}
    opens = set("([{")
    i = 0
    n = len(text or "")
    while i < n:
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c in opens:
            stack.append((c, i))
        elif c in pairs:
            if not stack or stack[-1][0] != pairs[c]:
                return {"balanced": False, "msg": "多余的 '" + c + "' 出现在位置 " + str(i)}
            stack.pop()
        i += 1
    if stack:
        ch, pos = stack[-1]
        return {"balanced": False, "msg": "位置 " + str(pos) + " 的 '" + ch + "' 没有闭合"}
    return {"balanced": True, "msg": ""}


def _normalize(rows):
    parts = []
    for r in rows:
        t = r["text"]
        w = r["weight"]
        if abs(w - 1.0) < 1e-6:
            parts.append(t)
        else:
            parts.append("(" + t + ":" + ("%.3f" % w) + ")")
    return ", ".join(parts)


def _weight_color(w):
    if w > 1.0:
        t = min((w - 1.0) / 0.8, 1.0)
        r = int(220 + 35 * t)
        g = int(170 - 120 * t)
        b = int(90 - 60 * t)
        return (r, g, b)
    if w < 1.0:
        t = min((1.0 - w) / 0.5, 1.0)
        r = int(110 - 40 * t)
        g = int(170 + 20 * t)
        b = int(225 + 30 * t)
        return (r, g, b)
    return (150, 150, 150)


def _truncate_label(s, max_units=40):
    units = 0
    out = []
    for ch in s:
        w = 2 if ord(ch) > 0x2E80 else 1
        if units + w > max_units:
            out.append("...")
            break
        units += w
        out.append(ch)
    return "".join(out)


def render_xray(rows, stats, width=1000):
    row_h = 30
    pad = 20
    header_h = 80
    footer_h = 140

    n = max(1, len(rows))
    height = header_h + row_h * n + footer_h

    bg = (22, 22, 28)
    fg = (235, 235, 235)
    dim = (150, 150, 160)
    accent = (200, 180, 255)

    img = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(img)

    font_title = _get_font(20)
    font_sub = _get_font(13)
    font = _get_font(14)
    font_small = _get_font(12)

    draw.text((pad, 18), "提示词权重可视化", fill=fg, font=font_title)
    draw.text((pad, 48), "Prompt Weight Baroscope", fill=accent, font=font_sub)

    label_x = pad
    label_w = 320
    bar_x = pad + label_w
    bar_max_w = 280
    value_x = bar_x + bar_max_w + 20
    tok_x = value_x + 90

    scale_ref = 2.0

    if not rows:
        draw.text((pad, header_h + 8), "（空提示词）", fill=dim, font=font)
    else:
        y = header_h
        for row in rows:
            text = row["text"]
            w = row["weight"]
            depth = row.get("depth", 0)

            indent = "  " * min(depth, 4)
            label = _truncate_label(indent + text, 40)
            color = _weight_color(w)

            draw.text((label_x, y + 6), label, fill=fg, font=font)

            draw.rectangle(
                [bar_x, y + 5, bar_x + bar_max_w, y + 21],
                outline=(60, 60, 70),
                fill=(35, 35, 42),
            )
            bar_len = int(min(w / scale_ref, 1.0) * bar_max_w)
            if bar_len > 0:
                draw.rectangle(
                    [bar_x, y + 5, bar_x + bar_len, y + 21],
                    fill=color,
                )

            draw.text((value_x, y + 7), "%.2f" % w, fill=color, font=font)

            tok = row.get("tokens", 0)
            draw.text((tok_x, y + 7), str(tok) + " token", fill=dim, font=font_small)

            y += row_h

    sep_y = header_h + row_h * n + 6
    draw.line([pad, sep_y, width - pad, sep_y], fill=(70, 70, 80), width=1)

    fy = sep_y + 14
    line_h = 22
    for i, line in enumerate(stats.get("footer_lines", [])):
        color = (240, 130, 130) if line.startswith("警告") else dim
        draw.text((pad, fy + i * line_h), line, fill=color, font=font_small)

    return img


class PromptWeightBaroscope:
    CATEGORY = "utils/prompt"
    FUNCTION = "run"
    RETURN_TYPES = ("IMAGE", "STRING", "STRING", "INT")
    RETURN_NAMES = ("权重图", "报告", "规范化提示词", "token数")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "提示词": ("STRING", {
                    "multiline": True,
                    "default": "(masterpiece:1.2), (best quality:1.3), [cat:0.8], (rainy city:1.1), (cinematic lighting:1.4), ultra detailed",
                }),
                "最大token数": ("INT", {
                    "default": 77, "min": 1, "max": 4096,
                }),
                "使用A1111语法": ("BOOLEAN", {
                    "default": True,
                }),
                "显示全部": ("BOOLEAN", {
                    "default": True,
                }),
                "高亮阈值": ("FLOAT", {
                    "default": 0.2, "min": 0.0, "max": 1.0, "step": 0.05,
                }),
            },
            "optional": {
                "clip": ("CLIP",),
            },
        }

    def run(self, 提示词, 最大token数, 使用A1111语法, 显示全部, 高亮阈值, clip=None):

        rows = parse_prompt(提示词, a1111=使用A1111语法)

        for r in rows:
            r["tokens"] = _approx_token_count(r["text"])

        total_approx = sum(r["tokens"] for r in rows) if rows else 0
        clip_tokens = _clip_token_count(clip, 提示词) if clip is not None else None

        display_rows = rows
        if not 显示全部 and rows:
            filtered = [r for r in rows if abs(r["weight"] - 1.0) >= 高亮阈值]
            display_rows = filtered if filtered else rows

        weights = [r["weight"] for r in rows] or [1.0]
        max_w = max(weights)
        min_w = min(weights)
        avg_w = sum(weights) / len(weights)

        balance = _check_balance(提示词)

        report_lines = []
        report_lines.append("词条数：" + str(len(rows)))
        report_lines.append("token数（近似）：" + str(total_approx))
        if clip_tokens is not None:
            report_lines.append("token数（CLIP）：" + str(clip_tokens))
        report_lines.append("最大权重：" + ("%.2f" % max_w))
        report_lines.append("最小权重：" + ("%.2f" % min_w))
        report_lines.append("平均权重：" + ("%.2f" % avg_w))
        if balance["balanced"]:
            report_lines.append("括号：平衡")
        else:
            report_lines.append("括号：不平衡（" + balance["msg"] + "）")

        footer_lines = [
            "词条数 " + str(len(rows)) + "    最大 " + ("%.2f" % max_w) + "    最小 " + ("%.2f" % min_w) + "    平均 " + ("%.2f" % avg_w),
            "token数（近似） " + str(total_approx) + " / " + str(最大token数)
            + (("    token数（CLIP） " + str(clip_tokens)) if clip_tokens is not None else ""),
        ]
        if not balance["balanced"]:
            footer_lines.append("警告：括号 " + balance["msg"])
        if total_approx > 最大token数:
            footer_lines.append("注意：token数超过 " + str(最大token数) + "，文本可能被 CLIP 分块或截断")

        img = render_xray(display_rows, {
            "max_weight": max_w,
            "footer_lines": footer_lines,
        })

        arr = np.array(img).astype(np.float32) / 255.0
        tensor = torch.from_numpy(arr).unsqueeze(0)

        report = "\n".join(report_lines)
        normalized = _normalize(rows)

        return (tensor, report, normalized, int(total_approx))


NODE_CLASS_MAPPINGS = {
    "KZ_PWB_PromptWeightBaroscope": PromptWeightBaroscope,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KZ_PWB_PromptWeightBaroscope": NODE_DISPLAY_NAME,
}