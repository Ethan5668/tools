import asyncio
import ctypes
import os
import re
import sys

import edge_tts

# 数值枚举：用编号选音色
VOICES = (
    "en-US-AriaNeural",     # 0 美式女声（默认）
    "en-US-JennyNeural",    # 1 美式女声
    "en-US-GuyNeural",      # 2 美式男声
    "en-US-ChristopherNeural",  # 3 美式男声
    "en-GB-SoniaNeural",    # 4 英式女声
    "zh-CN-XiaoxiaoNeural", # 5 中文女声
    "zh-CN-YunxiNeural",    # 6 中文男声
)


def resolve_voice(value: str) -> str:
    """接受音色编号（推荐）或完整音色名，返回 edge-tts 音色名。"""
    try:
        index = int(value)
    except ValueError:
        return value
    if not 0 <= index < len(VOICES):
        table = "\n".join(f"  {i}: {name}" for i, name in enumerate(VOICES))
        raise SystemExit(f"音色编号 {index} 超出范围\n可选音色:\n{table}")
    return VOICES[index]


def parse_count(value: str) -> int:
    """解析朗读次数，必须是 >= 1 的整数。"""
    try:
        count = int(value)
    except ValueError:
        raise SystemExit(f"朗读次数必须为整数，收到 {value!r}")
    if count < 1:
        raise SystemExit(f"朗读次数必须 >= 1，收到 {count}")
    return count


def read_file(path: str) -> str:
    """读取文本文件，优先 UTF-8（含 BOM），失败时回退 GBK。"""
    for encoding in ("utf-8-sig", "gbk"):
        try:
            with open(path, "r", encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"无法解码文件（不是 UTF-8 或 GBK）: {path}")


def normalize(text: str) -> str:
    """合并段落内的折行，保留段落分隔，去掉多余空白。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = []
    for block in re.split(r"\n\s*\n", text):
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if lines:
            paragraphs.append(" ".join(lines))
    return "\n".join(paragraphs)


USAGE = (
    '用法: python say.py "文本或文件路径" [音色编号=0] [语速=+0%] [朗读次数=1]\n'
    '      python say.py -f 文件路径 [音色编号=0] [语速=+0%] [朗读次数=1]'
)

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tts_output")

args = sys.argv[1:]
if not args:
    raise SystemExit(USAGE)

# -f/--file 显式指定文件；否则参数是存在的文件路径时按文件读取
if args[0] in ("-f", "--file"):
    if len(args) < 2:
        raise SystemExit(USAGE)
    source, rest = args[1], args[2:]
elif os.path.isfile(args[0]):
    source, rest = args[0], args[1:]
else:
    source, rest = None, args

if source is None:
    TEXT = normalize(args[0])
    rest = args[1:]
else:
    TEXT = normalize(read_file(source))
    print(f"read {len(TEXT)} chars from {source}", flush=True)

if not TEXT:
    raise SystemExit(f"没有可朗读的文本: {source or args[0]!r}")

VOICE = resolve_voice(rest[0] if len(rest) > 0 else "0")
RATE = rest[1] if len(rest) > 1 else "+0%"
COUNT = parse_count(rest[2] if len(rest) > 2 else "1")

# 输出文件名 = 音色名 + .mp3，统一放到 tts_output 目录
OUT = os.path.join(OUT_DIR, f"{VOICE}.mp3")
os.makedirs(OUT_DIR, exist_ok=True)


async def synth() -> None:
    await edge_tts.Communicate(TEXT, VOICE, rate=RATE).save(OUT)


asyncio.run(synth())
print("synthesized:", OUT, flush=True)

winmm = ctypes.windll.winmm
buf = ctypes.create_unicode_buffer(512)


def mci(cmd: str) -> None:
    rc = winmm.mciSendStringW(cmd, buf, 512, 0)
    if rc != 0:
        err = ctypes.create_unicode_buffer(512)
        winmm.mciGetErrorStringW(rc, err, 512)
        raise RuntimeError(f"MCI error {rc}: {err.value} :: {cmd}")


mci(f'open "{OUT}" type mpegvideo alias tts')
try:
    for i in range(1, COUNT + 1):
        print(f"playing {i}/{COUNT} ...", flush=True)
        mci("play tts from 0 wait")
finally:
    mci("close tts")
print("played")
