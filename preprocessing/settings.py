import os
import csv

# target fps for videos that get converted in preparation for icatcher and owlet
TARGET_FPS = 20

RESAMPLING_RATE = 20

___STIMULUS_WIDTH = 1280.0
___STIMULUS_HEIGHT = 960.0

SCREEN_WIDTH = 960#1920
SCREEN_HEIGHT = 540#1080

____STIMULUS_ASPECT_RATIO = ___STIMULUS_WIDTH / ___STIMULUS_HEIGHT

BASE_PATH = os.path.dirname(__file__)

DATA_DIR = os.path.join(BASE_PATH, 'data')
MEDIA_DIR = os.path.join(BASE_PATH, 'media')
OUT_DIR = os.path.join(BASE_PATH, 'output')
EXCLUSION_DIR = os.path.join(BASE_PATH, 'exclusion')

WEBCAM_MP4_DIR = os.path.join(OUT_DIR, 'webcam_mp4')
CROPPED_WEBCAM_MP4_DIR = os.path.join(OUT_DIR, 'webcam_16_9_mp4')
RENDERS_DIR = os.path.join(OUT_DIR, 'renders')

RENDER_WEBGAZER = True
RENDER_ICATCHER = True
RENDER_OWLET_NOCALIB = True
RENDER_OWLET = True
RENDER_WEBCAM_VIDEOS = True
RENDER_WEBCAM_VIDEOS_16_9 = False

WEBGAZER_SAMPLING_CUTOFF = 10

GAZECODER_NAMES = {
    'OWLET': 'owlet',
    'OWLET_NOCALIB': 'owlet_nocalib',
    'WEBGAZER': 'webgazer',
    'ICATCHER': 'icatcher',
}

STIMULUS_BLACKLIST = {
    GAZECODER_NAMES['OWLET']: [],#'calibration'],
    GAZECODER_NAMES['OWLET_NOCALIB']: [],
    GAZECODER_NAMES['WEBGAZER']: ['calibration', 'validation1', 'validation2'],
    GAZECODER_NAMES['ICATCHER']: ['validation1', 'validation2']
}


STIMULI = {}
with open(os.path.join(os.path.dirname(__file__), "stimuli_metadata.csv"), 'r') as f:
    for row in csv.DictReader(f):
        STIMULI[row['name']] = dict(row)

for key_o, stimulus in STIMULI.items():
    for key_i, value_i in stimulus.items():
        try:
            STIMULI[key_o][key_i] = int(value_i)
        except ValueError:
            try:
                STIMULI[key_o][key_i] = float(value_i)
            except ValueError:
                STIMULI[key_o][key_i] = value_i

stimuli = list(STIMULI.keys())
stimuli_critical = list({k: v for k, v in STIMULI.items() if v['critical'] == 1}.keys())




