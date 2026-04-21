from __future__ import annotations
import json
from pathlib import Path
BASE_DIR=Path(__file__).resolve().parent.parent
CONFIG_DIR=BASE_DIR/'config'
OUTPUT_DIR=BASE_DIR/'outputs'
DATA_DIR=BASE_DIR/'data'

def load_json_config(filename:str)->dict:
    return json.loads((CONFIG_DIR/filename).read_text(encoding='utf-8'))

def ensure_directories()->None:
    for p in [OUTPUT_DIR/'json',OUTPUT_DIR/'markdown',OUTPUT_DIR/'txt',OUTPUT_DIR/'briefs',DATA_DIR/'raw']:
        p.mkdir(parents=True,exist_ok=True)
