"""
AlgoTrade PRO - Promotional Video Generator for Fiverr & Upwork
Generates a complete 1080p 60fps/30fps MP4 video with:
- Studio-quality neural AI voiceover (edge-tts Christopher Neural)
- Ambient cyber synthwave background music (synthesized in-place)
- 5 high-tech scenes (Hook, Code Architecture, Terminal Logs, Web Dashboard, Call to Action)
- Auto-synced dynamic captions/subtitles on every frame
- Direct export to the user's Desktop
"""
import os
import sys
import math
import time
import asyncio
import subprocess
from pathlib import Path
import numpy as np
import scipy.io.wavfile as wavfile
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg
import edge_tts

# Paths
DESKTOP_DIR = Path(os.environ.get("USERPROFILE", "C:/Users/666de")) / "Desktop"
OUTPUT_MP4 = DESKTOP_DIR / "AlgoTrade_PRO_Promo.mp4"
TEMP_DIR = Path(__file__).resolve().parent / "temp_video_build"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

VOICE_MP3 = TEMP_DIR / "voiceover.mp3"
MUSIC_WAV = TEMP_DIR / "synth_music.wav"

# Video specs
WIDTH = 1920
HEIGHT = 1080
FPS = 30

# Colors (RGB)
BG_DARK_1 = (11, 15, 23)
BG_DARK_2 = (18, 24, 38)
ACCENT_CYAN = (0, 229, 255)
ACCENT_GREEN = (16, 185, 129)
ACCENT_YELLOW = (245, 158, 11)
ACCENT_PURPLE = (168, 85, 247)
ACCENT_ORANGE = (249, 115, 22)
ACCENT_RED = (239, 68, 68)
TEXT_WHITE = (248, 250, 252)
TEXT_GRAY = (148, 163, 184)
TEXT_DIM = (100, 116, 139)
CARD_BG = (23, 31, 48)
CARD_BORDER = (40, 52, 78)

# Load fonts with fallbacks
def get_font(size: int, bold: bool = False):
    font_paths = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                pass
    return ImageFont.load_default()

def get_code_font(size: int):
    font_paths = [
        "C:/Windows/Fonts/consola.ttf",
        "C:/Windows/Fonts/cour.ttf",
        "C:/Windows/Fonts/lucon.ttf",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                pass
    return ImageFont.load_default()

# Script Text & Sentence Timings
VOICEOVER_TEXT = (
    "Looking for a battle-tested crypto algorithmic trading system? "
    "Stop risking your capital with basic, lagging scripts. "
    "I engineer custom quantitative trading bots in Python powered by Dual Ensemble AI and sub-20-millisecond WebSocket feeds. "
    "Featuring automated Maker-order fee optimization, cross-exchange arbitrage between Binance and Bybit, dynamic stop-loss protection, and a sleek real-time web dashboard. "
    "Fully containerized, cloud-deployed, and built for maximum profitability. "
    "Do not settle for amateur bots. "
    "Send me a message, and let us launch your institutional-grade trading system today."
)

SCENE_SUBTITLES = [
    (0.0, 4.3, "Looking for a battle-tested crypto algorithmic trading system?"),
    (4.3, 8.5, "Stop risking your capital with basic, lagging scripts."),
    (8.5, 12.8, "I engineer custom quantitative trading bots in Python..."),
    (12.8, 16.8, "...powered by Dual Ensemble AI and sub-20ms WebSocket feeds."),
    (16.8, 21.5, "Featuring automated Maker fee optimization and Binance ↔ Bybit arbitrage..."),
    (21.5, 26.5, "...with dynamic stop-loss protection and a sleek real-time web dashboard."),
    (26.5, 30.5, "Fully containerized, cloud-deployed on 24/7 Oracle VPS..."),
    (30.5, 34.0, "...and engineered for maximum quantitative profitability."),
    (34.0, 36.8, "Do not settle for amateur bots."),
    (36.8, 41.5, "Send me a message, and let's launch your institutional system today!")
]

async def generate_voiceover(output_path: Path):
    print("🎙️ Generating neural AI voiceover (Christopher Neural)...")
    comm = edge_tts.Communicate(VOICEOVER_TEXT, "en-US-ChristopherNeural", rate="+4%")
    await comm.save(str(output_path))
    print("✅ Voiceover generated.")

def generate_synth_music(output_path: Path, duration: float):
    print(f"🎵 Synthesizing ambient cyber backing track ({duration:.1f}s)...")
    sr = 44100
    total_samples = int(sr * duration)
    t = np.linspace(0, duration, total_samples, False)

    # 120 BPM: beat every 0.5s
    bpm = 120
    beat_dur = 60.0 / bpm
    sub_kick = np.zeros(total_samples)
    for b in range(int(duration / beat_dur)):
        start = int(b * beat_dur * sr)
        kick_len = int(0.12 * sr)
        if start + kick_len < total_samples:
            kt = np.linspace(0, 0.12, kick_len, False)
            freq = 65.0 * np.exp(-kt * 25.0)
            env = np.exp(-kt * 30.0)
            sub_kick[start:start+kick_len] += 0.35 * np.sin(2 * np.pi * freq * kt) * env

    # Bassline (Pulsing synth 16th notes: A1 -> F1 -> C2 -> G1)
    chords = [55.0, 43.65, 65.41, 48.99]  # A, F, C, G
    bass = np.zeros(total_samples)
    step = beat_dur / 4.0
    for s in range(int(duration / step)):
        chord_idx = int((s * step / 4.0) % 4)
        base_f = chords[chord_idx]
        start = int(s * step * sr)
        slen = int(step * 0.75 * sr)
        if start + slen < total_samples:
            st = np.linspace(0, step * 0.75, slen, False)
            env = np.exp(-st * 15.0)
            # Filtered saw
            wave = 0.5 * np.sin(2 * np.pi * base_f * st) + 0.25 * np.sin(2 * np.pi * base_f * 2 * st)
            bass[start:start+slen] += 0.22 * wave * env

    # Ambient cyber arpeggio (sine plucks)
    arp = np.zeros(total_samples)
    arp_notes = [440.0, 523.25, 659.25, 783.99, 880.0]
    for s in range(int(duration / (step * 2))):
        note = arp_notes[s % len(arp_notes)]
        start = int(s * step * 2 * sr)
        alen = int(0.3 * sr)
        if start + alen < total_samples:
            at = np.linspace(0, 0.3, alen, False)
            env = np.exp(-at * 8.0)
            arp[start:start+alen] += 0.12 * np.sin(2 * np.pi * note * at) * env

    mix = sub_kick + bass + arp
    # Master compression / normalization
    max_val = np.max(np.abs(mix))
    if max_val > 0:
        mix = mix / max_val * 0.75
    # Fade in & fade out
    fade_len = int(1.5 * sr)
    mix[:fade_len] *= np.linspace(0, 1, fade_len)
    mix[-fade_len:] *= np.linspace(1, 0, fade_len)

    wavfile.write(str(output_path), sr, (mix * 32767).astype(np.int16))
    print("✅ Music synthesized.")

def get_audio_duration(audio_path: Path) -> float:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    res = subprocess.run([ffmpeg, "-i", str(audio_path)], capture_output=True, text=True)
    import re
    match = re.search(r"Duration: (\d{2}):(\d{2}):(\d{2}\.\d+)", res.stderr)
    if match:
        h, m, s = match.groups()
        return int(h) * 3600 + int(m) * 60 + float(s)
    return 40.0

# Drawing Utilities
def draw_gradient_background(draw: ImageDraw.ImageDraw, frame_idx: int):
    # Futuristic deep background
    shift = int(math.sin(frame_idx * 0.03) * 15)
    for y in range(0, HEIGHT, 4):
        ratio = y / HEIGHT
        r = int(BG_DARK_1[0] * (1 - ratio) + (BG_DARK_2[0] + shift // 2) * ratio)
        g = int(BG_DARK_1[1] * (1 - ratio) + (BG_DARK_2[1] + shift // 2) * ratio)
        b = int(BG_DARK_1[2] * (1 - ratio) + (BG_DARK_2[2] + shift) * ratio)
        draw.rectangle([0, y, WIDTH, y + 4], fill=(r, g, b))

    # Perspective Grid lines
    grid_alpha = 25
    center_x = WIDTH // 2
    horizon_y = 650
    # Moving vertical perspective lines
    t_offset = (frame_idx * 2) % 60
    for i in range(-15, 16):
        x_base = center_x + i * 80 + t_offset
        draw.line([(center_x, horizon_y), (x_base * 2.2 - center_x * 0.8, HEIGHT)], fill=(20, 35, 55), width=1)
    for y in range(horizon_y + 10, HEIGHT, 30):
        draw.line([(0, y), (WIDTH, y)], fill=(16, 28, 45), width=1)

def draw_header_badge(draw: ImageDraw.ImageDraw, title: str = "AlgoTrade PRO v4.2"):
    font_bold = get_font(18, bold=True)
    font_reg = get_font(15, bold=False)
    # Top status bar
    draw.rectangle([0, 0, WIDTH, 48], fill=(15, 23, 42))
    draw.line([(0, 48), (WIDTH, 48)], fill=(30, 41, 59), width=1)

    # Logo pill
    draw.rectangle([40, 10, 220, 38], fill=(30, 41, 59), outline=ACCENT_CYAN, width=1)
    draw.ellipse([50, 20, 58, 28], fill=ACCENT_GREEN)
    draw.text((68, 14), title, font=font_bold, fill=TEXT_WHITE)

    # Live indicators
    draw.text((WIDTH - 550, 15), "● BTC: $74,850  │  ETH: $2,125  │  SOL: $86.40", font=font_reg, fill=TEXT_GRAY)
    draw.rectangle([WIDTH - 180, 10, WIDTH - 40, 38], fill=(34, 197, 94, 40), outline=ACCENT_GREEN, width=1)
    draw.text((WIDTH - 165, 14), "⚡ WS: <18ms", font=font_bold, fill=ACCENT_GREEN)

def draw_subtitle_banner(draw: ImageDraw.ImageDraw, current_time: float):
    active_text = ""
    for start, end, text in SCENE_SUBTITLES:
        if start <= current_time <= end:
            active_text = text
            break
    if not active_text:
        return

    font_sub = get_font(30, bold=True)
    bbox = font_sub.getbbox(active_text)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]

    cx = WIDTH // 2
    cy = HEIGHT - 80
    pad_x = 28
    pad_y = 14

    # Rounded pill box
    draw.rounded_rectangle(
        [cx - w // 2 - pad_x, cy - pad_y, cx + w // 2 + pad_x, cy + h + pad_y],
        radius=14,
        fill=(10, 14, 23, 230),
        outline=(245, 158, 11, 200),
        width=2
    )
    # Highlight keywords in yellow
    draw.text((cx - w // 2, cy - 2), active_text, font=font_sub, fill=(255, 255, 255))

# --- SCENE RENDERERS ---

def render_scene_intro(draw: ImageDraw.ImageDraw, frame: int, t: float):
    # Scene 1: Hero presentation & 3D Bitcoin
    pulse = math.sin(t * 3.5) * 8
    glow_r = int(140 + pulse)
    center_x = WIDTH // 2
    center_y = 360

    # Glow rings
    draw.ellipse([center_x - glow_r - 20, center_y - glow_r - 20, center_x + glow_r + 20, center_y + glow_r + 20], outline=(0, 229, 255, 50), width=3)
    draw.ellipse([center_x - glow_r, center_y - glow_r, center_x + glow_r, center_y + glow_r], fill=(15, 25, 45), outline=ACCENT_YELLOW, width=6)

    # Bitcoin Symbol ₿
    font_btc = get_font(140, bold=True)
    draw.text((center_x - 45, center_y - 95), "₿", font=font_btc, fill=ACCENT_YELLOW)

    # Big Titles
    font_title = get_font(56, bold=True)
    font_sub = get_font(26, bold=True)
    font_tag = get_font(20, bold=False)

    title_text = "AlgoTrade PRO v4.2"
    bbox = font_title.getbbox(title_text)
    draw.text((center_x - (bbox[2] - bbox[0]) // 2, 530), title_text, font=font_title, fill=TEXT_WHITE)

    sub_text = "INSTITUTIONAL QUANTITATIVE SCALPER & ARBITRAGE CORE"
    bbox_s = font_sub.getbbox(sub_text)
    draw.text((center_x - (bbox_s[2] - bbox_s[0]) // 2, 605), sub_text, font=font_sub, fill=ACCENT_CYAN)

    # 3 Badges
    badges = [
        ("⚡ Sub-20ms WebSocket Stream", ACCENT_GREEN),
        ("🧠 Dual Ensemble AI (RF + LightGBM)", ACCENT_PURPLE),
        ("💎 Maker Limit Fee Saver (-73.3%)", ACCENT_YELLOW)
    ]
    total_w = len(badges) * 360 + (len(badges) - 1) * 30
    bx = (WIDTH - total_w) // 2
    for b_text, col in badges:
        draw.rounded_rectangle([bx, 675, bx + 360, 735], radius=10, fill=CARD_BG, outline=col, width=2)
        font_b = get_font(18, bold=True)
        draw.text((bx + 20, 693), b_text, font=font_b, fill=TEXT_WHITE)
        bx += 390

def render_scene_code(draw: ImageDraw.ImageDraw, frame: int, t: float):
    # Scene 2: VS Code Window Mockup
    font_bold = get_font(20, bold=True)
    font_code = get_code_font(19)

    # Window Container
    wx1, wy1, wx2, wy2 = 180, 100, WIDTH - 180, HEIGHT - 180
    draw.rounded_rectangle([wx1, wy1, wx2, wy2], radius=14, fill=(15, 23, 42), outline=(51, 65, 85), width=2)

    # Window Title Bar
    draw.rectangle([wx1, wy1, wx2, wy1 + 42], fill=(30, 41, 59))
    draw.ellipse([wx1 + 16, wy1 + 14, wx1 + 28, wy1 + 26], fill=(239, 68, 68))
    draw.ellipse([wx1 + 36, wy1 + 14, wx1 + 48, wy1 + 26], fill=(245, 158, 11))
    draw.ellipse([wx1 + 56, wy1 + 14, wx1 + 68, wy1 + 26], fill=(34, 197, 94))
    draw.text((wx1 + 90, wy1 + 10), "Visual Studio Code  —  algo-trade-core/src/engine/infrastructure/websocket_feed.py", font=get_font(15), fill=TEXT_GRAY)

    # Left File Tree (Sidebar)
    draw.rectangle([wx1, wy1 + 42, wx1 + 280, wy2], fill=(20, 29, 47))
    draw.line([(wx1 + 280, wy1 + 42), (wx1 + 280, wy2)], fill=(40, 53, 76), width=1)
    draw.text((wx1 + 20, wy1 + 58), "EXPLORER", font=get_font(14, bold=True), fill=TEXT_DIM)

    files = [
        ("📁 src/engine/domain", False),
        ("   📄 models.py", False),
        ("📁 src/engine/infrastructure", True),
        ("   ⚡ websocket_feed.py", True),
        ("   📄 exchange_manager.py", False),
        ("   📄 cache_manager.py", False),
        ("📁 src/engine/application", False),
        ("   📄 arbitrage.py", False),
        ("   📄 paper_trader.py", False),
        ("📄 main.py", False)
    ]
    fy = wy1 + 95
    for fn, active in files:
        if active and "websocket" in fn:
            draw.rectangle([wx1 + 5, fy - 4, wx1 + 275, fy + 24], fill=(30, 41, 59))
            draw.text((wx1 + 18, fy), fn, font=get_font(15, bold=True), fill=ACCENT_CYAN)
        else:
            draw.text((wx1 + 18, fy), fn, font=get_font(15), fill=TEXT_GRAY)
        fy += 32

    # Right Code Editor
    cx = wx1 + 310
    cy = wy1 + 65

    # Active Tab
    draw.rectangle([cx - 20, wy1 + 42, cx + 220, wy1 + 75], fill=(15, 23, 42))
    draw.line([(cx - 20, wy1 + 42), (cx + 220, wy1 + 42)], fill=ACCENT_CYAN, width=2)
    draw.text((cx, wy1 + 49), "⚡ websocket_feed.py", font=get_font(15, bold=True), fill=TEXT_WHITE)

    code_lines = [
        ("class WebSocketFeed:", ACCENT_CYAN, False),
        ("    '''Ultra-low latency public BBO stream for Binance & Bybit (<20ms).'''", TEXT_DIM, False),
        ("    def __init__(self, symbols: List[str] = TOP_20_PAIRS):", TEXT_WHITE, False),
        ("        self.prices = {'binance': {}, 'bybit': {}}", ACCENT_YELLOW, False),
        ("        self.order_mode = 'MAKER_LIMIT'  # -73.3% fee savings", ACCENT_GREEN, False),
        ("", TEXT_WHITE, False),
        ("    async def start(self) -> None:", ACCENT_CYAN, False),
        ("        # Connect concurrent WebSocket streams (No rate-limits)", TEXT_DIM, False),
        ("        await asyncio.gather(self._binance_stream(), self._bybit_stream())", ACCENT_PURPLE, False),
        ("", TEXT_WHITE, False),
        ("    def get_bbo(self, symbol: str, exchange: str = 'binance') -> Dict:", ACCENT_CYAN, True),
        ("        '''Sub-millisecond Best Bid / Best Ask in-memory retrieval.'''", TEXT_DIM, True),
        ("        return self.prices[exchange].get(symbol)", ACCENT_GREEN, True),
        ("", TEXT_WHITE, False),
        ("    def get_execution_params(self) -> Dict:", ACCENT_CYAN, False),
        ("        return {'fee_pct': 0.0002, 'post_only': True, 'type': 'MAKER'}", ACCENT_YELLOW, False)
    ]

    for line, color, is_hl in code_lines:
        if is_hl:
            draw.rectangle([cx - 15, cy - 2, wx2 - 20, cy + 24], fill=(30, 48, 80))
        draw.text((cx, cy), line, font=font_code, fill=color)
        cy += 28

    # Floating Feature Callout
    draw.rounded_rectangle([wx2 - 380, wy2 - 120, wx2 - 20, wy2 - 20], radius=10, fill=(15, 23, 42, 240), outline=ACCENT_GREEN, width=2)
    draw.text((wx2 - 360, wy2 - 105), "⚡ 100% ASYNCIO ARCHITECTURE", font=get_font(16, bold=True), fill=ACCENT_GREEN)
    draw.text((wx2 - 360, wy2 - 75), "• Sub-20ms WebSocket Latency\n• Zero REST 429 Rate Limits\n• Hexagonal Python 3.12 Engine", font=get_font(14), fill=TEXT_WHITE)

def render_scene_terminal(draw: ImageDraw.ImageDraw, frame: int, t: float):
    # Scene 3: High-Frequency Terminal Logs
    font_code = get_code_font(18)
    font_bold = get_font(18, bold=True)

    wx1, wy1, wx2, wy2 = 140, 80, WIDTH - 140, HEIGHT - 160
    draw.rounded_rectangle([wx1, wy1, wx2, wy2], radius=14, fill=(8, 12, 20), outline=(30, 41, 59), width=2)

    # Terminal Title Bar
    draw.rectangle([wx1, wy1, wx2, wy1 + 42], fill=(18, 24, 38))
    draw.ellipse([wx1 + 16, wy1 + 14, wx1 + 28, wy1 + 26], fill=(239, 68, 68))
    draw.ellipse([wx1 + 36, wy1 + 14, wx1 + 48, wy1 + 26], fill=(245, 158, 11))
    draw.ellipse([wx1 + 56, wy1 + 14, wx1 + 68, wy1 + 26], fill=(34, 197, 94))
    draw.text((wx1 + 90, wy1 + 10), "Terminal — ubuntu@oracle-cloud-vps: ~/algo-trade-core (python main.py)", font=get_font(15), fill=TEXT_GRAY)

    # Terminal Logs list
    logs = [
        ("18:14:20.104", "⚡ [WS-FEED]    ", ACCENT_CYAN, "BTC/USDT BBO: 74850.2 / 74850.3 │ Ping: 16.4ms │ Ticks: 118,402"),
        ("18:14:20.250", "🧠 [AI-ENSEMBLE]", ACCENT_PURPLE, "SOL/USDT RF: 0.84 + LGBM: 0.89 ➔ CONSENSUS BUY (86.3%) │ ADX: 34.2"),
        ("18:14:20.310", "🚀 [ORDER-EXEC] ", ACCENT_YELLOW, "BUY MAKER LIMIT #89421 SOL/USDT @ $82.35 │ Fee: 0.02% (Saved 73.3%)"),
        ("18:14:20.680", "📡 [ARBITRAGE]  ", ACCENT_ORANGE, "SUI/USDT Binance ➔ Bybit │ Gross: +0.68% ➔ NET SPREAD: +0.48% (OPP!)"),
        ("18:14:21.140", "⚡ [WS-FEED]    ", ACCENT_CYAN, "ETH/USDT BBO: 2125.4 / 2125.5 │ Ping: 18.1ms │ Ticks: 118,495"),
        ("18:14:21.490", "💰 [TAKE PROFIT]", ACCENT_GREEN, "DOT/USDT TP1 Hit (50% Scaled Out) ➔ +$24.50 USDT (+2.1%) │ Breakeven Set"),
        ("18:14:21.820", "🛡️ [QUANT GUARD]", ACCENT_CYAN, "AVAX/USDT Breakeven Lock Active │ Trailing Stop: +0.45% Locked (Zero Risk)"),
        ("18:14:22.110", "⚡ [WS-FEED]    ", ACCENT_CYAN, "SOL/USDT BBO: 82.45 / 82.46 │ Ping: 15.9ms │ Ticks: 118,610"),
        ("18:14:22.450", "🚀 [ORDER-EXEC] ", ACCENT_YELLOW, "BUY MAKER LIMIT #89455 NEAR/USDT @ $3.59 │ Fee: 0.02% (Maker Saved $0.12)"),
        ("18:14:22.900", "📊 [PORTFOLIO]  ", TEXT_WHITE, "Equity: $1,248.50 │ 24h PnL: +$248.50 USDT │ WinRate: 78.4% │ PF: 2.14"),
        ("18:14:23.200", "⚡ [WS-FEED]    ", ACCENT_CYAN, "SUI/USDT BBO: 0.818 / 0.819 │ Ping: 17.2ms │ Ticks: 118,780"),
        ("18:14:23.640", "📡 [ARBITRAGE]  ", ACCENT_ORANGE, "LINK/USDT Bybit ➔ Binance │ Gross: +0.55% ➔ NET SPREAD: +0.35%"),
        ("18:14:24.010", "💰 [TAKE PROFIT]", ACCENT_GREEN, "SOL/USDT TP2 Final Exit ➔ +$38.20 USDT (+3.4%) │ Trade Logged to DB")
    ]

    # Scrolling effect
    scroll_shift = int((t - 15.5) * 2.5) % len(logs)
    visible_logs = logs[scroll_shift:] + logs[:scroll_shift]

    ly = wy1 + 65
    for ts, tag, tag_col, msg in visible_logs[:12]:
        draw.text((wx1 + 25, ly), ts, font=font_code, fill=TEXT_DIM)
        draw.text((wx1 + 175, ly), tag, font=font_code, fill=tag_col)
        draw.text((wx1 + 360, ly), msg, font=font_code, fill=TEXT_WHITE)
        ly += 33

    # Blinking terminal cursor
    if int(t * 3) % 2 == 0:
        draw.rectangle([wx1 + 25, ly + 2, wx1 + 38, ly + 22], fill=ACCENT_GREEN)

def render_scene_dashboard(draw: ImageDraw.ImageDraw, frame: int, t: float):
    # Scene 4: Web Dashboard Mockup
    font_bold = get_font(20, bold=True)
    font_reg = get_font(15)

    wx1, wy1, wx2, wy2 = 100, 60, WIDTH - 100, HEIGHT - 140
    draw.rounded_rectangle([wx1, wy1, wx2, wy2], radius=14, fill=(11, 15, 23), outline=(40, 52, 78), width=2)

    # Browser Bar
    draw.rectangle([wx1, wy1, wx2, wy1 + 46], fill=(20, 28, 45))
    draw.ellipse([wx1 + 16, wy1 + 16, wx1 + 28, wy1 + 28], fill=(239, 68, 68))
    draw.ellipse([wx1 + 36, wy1 + 16, wx1 + 48, wy1 + 28], fill=(245, 158, 11))
    draw.ellipse([wx1 + 56, wy1 + 16, wx1 + 68, wy1 + 28], fill=(34, 197, 94))

    # Address pill
    draw.rounded_rectangle([wx1 + 160, wy1 + 8, wx2 - 160, wy1 + 38], radius=8, fill=(11, 15, 23))
    draw.text((wx1 + 180, wy1 + 12), "🔒 https://algotrade.pro/bot_monitor/dashboard/  —  AlgoTrade PRO Control Center", font=font_reg, fill=TEXT_GRAY)

    # Top KPI Cards (4 cards)
    kpis = [
        ("TOTAL EQUITY", "$1,248.50", "+24.8% (All-time)", ACCENT_GREEN),
        ("REALIZED PNL", "+$248.50 USDT", "67 Closed Trades", ACCENT_GREEN),
        ("PROFIT FACTOR", "2.14", "Benchmark: > 1.50 Pro", ACCENT_CYAN),
        ("WIN RATE", "78.4%", "36 Wins / 10 Losses", ACCENT_YELLOW)
    ]
    card_w = (wx2 - wx1 - 50 - 3 * 20) // 4
    cx = wx1 + 25
    for title, val, sub, col in kpis:
        draw.rounded_rectangle([cx, wy1 + 65, cx + card_w, wy1 + 160], radius=10, fill=CARD_BG, outline=CARD_BORDER, width=1)
        draw.text((cx + 18, wy1 + 78), title, font=get_font(13, bold=True), fill=TEXT_DIM)
        draw.text((cx + 18, wy1 + 102), val, font=get_font(26, bold=True), fill=col)
        draw.text((cx + 18, wy1 + 135), sub, font=get_font(13), fill=TEXT_GRAY)
        cx += card_w + 20

    # 6 Institutional Tech Pills
    pills = [
        ("Redis: Online", ACCENT_RED),
        ("Celery: Active", ACCENT_CYAN),
        ("Dual AI: RF 55% + LGBM 45%", ACCENT_PURPLE),
        ("Sub-Second Push", ACCENT_GREEN),
        ("⚡ WS Stream: <18ms", ACCENT_GREEN),
        ("💎 Maker: 0.02% (-73%)", ACCENT_YELLOW)
    ]
    px = wx1 + 25
    pill_w = (wx2 - wx1 - 50 - 5 * 14) // 6
    for ptext, pcol in pills:
        draw.rounded_rectangle([px, wy1 + 175, px + pill_w, wy1 + 215], radius=6, fill=(18, 25, 40), outline=pcol, width=1)
        draw.text((px + 10, wy1 + 186), ptext, font=get_font(13, bold=True), fill=TEXT_WHITE)
        px += pill_w + 14

    # Crypto Heatmap (20 pairs miniature grid)
    draw.text((wx1 + 25, wy1 + 235), "● CRYPTO MARKET HEATMAP (20 PAIRS)  │  AI Momentum & Volume Pulse", font=get_font(15, bold=True), fill=TEXT_WHITE)
    hm_pairs = [
        ("BTC", "$74,850", "+1.8%", ACCENT_GREEN),
        ("ETH", "$2,125", "+2.4%", ACCENT_GREEN),
        ("SOL", "$86.40", "+4.2%", ACCENT_GREEN),
        ("SUI", "$0.825", "+5.8%", ACCENT_GREEN),
        ("AVAX", "$8.72", "+3.1%", ACCENT_GREEN),
        ("LINK", "$10.45", "-0.8%", ACCENT_RED),
        ("NEAR", "$3.62", "+2.9%", ACCENT_GREEN),
        ("DOGE", "$0.068", "+1.2%", ACCENT_GREEN),
        ("ADA", "$0.179", "-0.4%", ACCENT_RED),
        ("APT", "$0.590", "+3.5%", ACCENT_GREEN),
        ("DOT", "$0.885", "+2.0%", ACCENT_GREEN),
        ("ARB", "$0.180", "+1.5%", ACCENT_GREEN)
    ]
    hx = wx1 + 25
    hy = wy1 + 265
    tile_w = (wx2 - wx1 - 50 - 5 * 12) // 6
    for i, (sym, pr, chg, ccol) in enumerate(hm_pairs):
        tx = hx + (i % 6) * (tile_w + 12)
        ty = hy + (i // 6) * 75
        draw.rounded_rectangle([tx, ty, tx + tile_w, ty + 65], radius=8, fill=(18, 26, 42), outline=ccol, width=1)
        draw.text((tx + 12, ty + 10), sym, font=get_font(15, bold=True), fill=TEXT_WHITE)
        draw.text((tx + 12, ty + 34), pr, font=get_font(13), fill=TEXT_GRAY)
        draw.text((tx + tile_w - 60, ty + 10), chg, font=get_font(13, bold=True), fill=ccol)

    # Arbitrage Radar Snippet
    draw.text((wx1 + 25, wy1 + 435), "● ARBITRAGE RADAR: BINANCE ↔ BYBIT  │  Spot & Funding APY Scan", font=get_font(15, bold=True), fill=ACCENT_ORANGE)
    ar_rows = [
        ("SUI/USDT", "Binance ($0.816) ➔ Bybit ($0.821)", "+0.61%", "NET: +0.41%", ACCENT_GREEN),
        ("SOL/USDT", "Bybit ($86.20) ➔ Binance ($86.65)", "+0.52%", "NET: +0.32%", ACCENT_GREEN),
        ("NEAR/USDT", "Binance ($3.58) ➔ Bybit ($3.60)", "+0.56%", "NET: +0.36%", ACCENT_GREEN)
    ]
    ay = wy1 + 465
    for sym, route, gross, net, ncol in ar_rows:
        draw.rectangle([wx1 + 25, ay, wx2 - 25, ay + 36], fill=(16, 24, 38))
        draw.text((wx1 + 35, ay + 8), sym, font=get_font(14, bold=True), fill=TEXT_WHITE)
        draw.text((wx1 + 180, ay + 8), route, font=get_font(14), fill=TEXT_GRAY)
        draw.text((wx1 + 580, ay + 8), f"Gross: {gross}", font=get_font(14), fill=TEXT_GRAY)
        draw.text((wx1 + 750, ay + 8), net, font=get_font(14, bold=True), fill=ncol)
        draw.text((wx2 - 120, ay + 8), "ACTIVE OPP", font=get_font(12, bold=True), fill=ACCENT_GREEN)
        ay += 40

def render_scene_outro(draw: ImageDraw.ImageDraw, frame: int, t: float):
    # Scene 5: Outro & High-Converting CTA
    font_h1 = get_font(50, bold=True)
    font_h2 = get_font(24, bold=True)
    font_body = get_font(22, bold=False)
    font_btn = get_font(28, bold=True)

    cx = WIDTH // 2
    cy = HEIGHT // 2 - 20

    # Big Glass Container
    draw.rounded_rectangle([cx - 520, cy - 250, cx + 520, cy + 240], radius=18, fill=(14, 20, 32, 240), outline=ACCENT_CYAN, width=3)

    # Glowing title
    title = "BUILD YOUR TRADING ADVANTAGE"
    bbox = font_h1.getbbox(title)
    draw.text((cx - (bbox[2] - bbox[0]) // 2, cy - 215), title, font=font_h1, fill=TEXT_WHITE)

    sub = "Custom Institutional Trading Bots  •  Python 3.12  •  Oracle Cloud VPS"
    bbox_s = font_h2.getbbox(sub)
    draw.text((cx - (bbox_s[2] - bbox_s[0]) // 2, cy - 145), sub, font=font_h2, fill=ACCENT_CYAN)

    # Bullet points
    bullets = [
        "✓  Ultra-Low Latency WebSocket Streams (<20ms BBO Execution)",
        "✓  Maker-Limit Fee Optimization (Cuts exchange fees by 73.3%)",
        "✓  Dual Machine Learning Ensemble (Random Forest + LightGBM)",
        "✓  Real-Time Web Terminal & Arbitrage Radar (Binance ↔ Bybit)",
        "✓  Full Source Code, Docker Deployment & 24/7 VPS Setup"
    ]
    by = cy - 85
    for b in bullets:
        draw.text((cx - 440, by), b, font=font_body, fill=TEXT_WHITE)
        by += 38

    # Big Pulse CTA Button
    btn_w, btn_h = 620, 72
    btn_x = cx - btn_w // 2
    btn_y = cy + 130
    pulse = math.sin(t * 4.0) * 4
    draw.rounded_rectangle([btn_x - pulse, btn_y, btn_x + btn_w + pulse, btn_y + btn_h], radius=12, fill=ACCENT_YELLOW, outline=(255, 255, 255), width=2)
    btn_text = "📩  ORDER NOW ON FIVERR / UPWORK"
    bbox_b = font_btn.getbbox(btn_text)
    draw.text((cx - (bbox_b[2] - bbox_b[0]) // 2, btn_y + 16), btn_text, font=font_btn, fill=(15, 23, 42))

def render_frame(frame_idx: int, total_frames: int, duration: float) -> Image.Image:
    t = (frame_idx / total_frames) * duration
    img = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(img)

    draw_gradient_background(draw, frame_idx)
    draw_header_badge(draw)

    # Timeline Scene Switcher
    if t < 8.0:
        render_scene_intro(draw, frame_idx, t)
    elif t < 16.5:
        render_scene_code(draw, frame_idx, t)
    elif t < 25.0:
        render_scene_terminal(draw, frame_idx, t)
    elif t < 33.5:
        render_scene_dashboard(draw, frame_idx, t)
    else:
        render_scene_outro(draw, frame_idx, t)

    draw_subtitle_banner(draw, t)
    return img

async def main():
    print("==================================================================")
    print("🎬 AlgoTrade PRO - Automated Promo Video Production Engine")
    print("==================================================================")

    # 1. Voiceover
    if not VOICE_MP3.exists():
        await generate_voiceover(VOICE_MP3)

    dur = get_audio_duration(VOICE_MP3)
    # Add 1.5 seconds safety buffer at the end
    total_duration = max(dur + 1.2, 38.0)
    print(f"⏱️ Video Duration: {total_duration:.2f} seconds")

    # 2. Synthesize background music
    generate_synth_music(MUSIC_WAV, total_duration)

    # 3. Render video frames and pipe directly into FFmpeg
    total_frames = int(total_duration * FPS)
    print(f"🖼️ Rendering {total_frames} frames (1920x1080 @ {FPS}fps)...")

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    # FFmpeg command: combines raw video stream + voiceover + background music
    cmd = [
        ffmpeg_exe,
        "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{WIDTH}x{HEIGHT}",
        "-pix_fmt", "rgb24",
        "-r", str(FPS),
        "-i", "-",  # Video from stdin
        "-i", str(VOICE_MP3),  # Input 1: Voiceover
        "-i", str(MUSIC_WAV),  # Input 2: Background Music
        "-filter_complex",
        "[1:a]volume=1.0[v];[2:a]volume=0.20[m];[v][m]amix=inputs=2:duration=first[aout]",
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(OUTPUT_MP4)
    ]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    start_time = time.time()
    for f in range(total_frames):
        frame_img = render_frame(f, total_frames, total_duration)
        proc.stdin.write(frame_img.tobytes())

        if f % 90 == 0 or f == total_frames - 1:
            progress = (f + 1) / total_frames * 100
            elapsed = time.time() - start_time
            fps_speed = (f + 1) / (elapsed + 1e-5)
            rem = (total_frames - f - 1) / (fps_speed + 1e-5)
            print(f"   Frame {f+1}/{total_frames} ({progress:.1f}%) │ Speed: {fps_speed:.1f} fps │ ETA: {rem:.1f}s")

    proc.stdin.close()
    proc.wait()

    if OUTPUT_MP4.exists():
        size_mb = OUTPUT_MP4.stat().st_size / (1024 * 1024)
        print("==================================================================")
        print(f"🎉 SUCCESS! Video exported to Desktop:")
        print(f"📁 {OUTPUT_MP4}")
        print(f"📊 Size: {size_mb:.2f} MB │ Resolution: 1920x1080 Full HD │ Audio: Stereo AAC")
        print("==================================================================")
    else:
        print("❌ Error: Video file was not created.")

if __name__ == "__main__":
    asyncio.run(main())
