import os


APP_NAME = "TactiReader"
BOOKMARK_DIR_NAME = "tactireader_bookmarks"

appdata = os.getenv("APPDATA")
if appdata:
    CONFIG_DIR = os.path.join(appdata, APP_NAME, BOOKMARK_DIR_NAME)
else:
    CONFIG_DIR = BOOKMARK_DIR_NAME
os.makedirs(CONFIG_DIR, exist_ok=True)

GLOBAL_CONFIG_FILE = os.path.join(CONFIG_DIR, "global_settings.json")
RENDER_SCALE = 2.0

PEN_COLOR_PRESETS = [
    (255, 0, 0),
    (0, 0, 255),
    (0, 255, 0),
    (255, 255, 0),
    (255, 0, 255),
    (0, 255, 255),
    (255, 128, 0),
    (128, 0, 255),
    (255, 0, 128),
    (0, 0, 0),
]

RECT_COLOR_PRESETS = [
    (255, 255, 0, 128),
    (255, 200, 200, 128),
    (200, 255, 200, 128),
    (200, 200, 255, 128),
    (255, 255, 200, 128),
    (255, 200, 255, 128),
    (200, 255, 255, 128),
    (255, 220, 180, 128),
]

TEXT_COLOR_PRESETS = [
    (0, 0, 0),
    (255, 0, 0),
    (0, 0, 255),
    (0, 100, 0),
    (128, 0, 128),
    (139, 69, 19),
]
