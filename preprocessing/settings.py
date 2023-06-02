import os

# target fps for videos that get converted in preparation for icatcher and owlet
TARGET_FPS = 20

RESAMPLING_RATE = 20

STIMULUS_WIDTH = 1280.0
STIMULUS_HEIGHT = 960.0

SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080

STIMULUS_ASPECT_RATIO = STIMULUS_WIDTH / STIMULUS_HEIGHT

BASE_PATH = os.path.dirname(__file__)

DATA_DIR = os.path.join(BASE_PATH, 'data')
MEDIA_DIR = os.path.join(BASE_PATH, 'media')
OUT_DIR = os.path.join(BASE_PATH, 'output')

WEBCAM_MP4_DIR = os.path.join(OUT_DIR, 'webcam_mp4')
RENDERS_DIR = os.path.join(OUT_DIR, 'renders')


target_aoi_location = {
    "FAM_LL": "left",
    "FAM_LR": "right",
    "FAM_RL": "left",
    "FAM_RR": "right",
}

trial_order_indices = {
    'A': {
        'calibration': 0,
        'FAM_LL': 2,
        'FAM_LR': 1,
        'FAM_RR': 3,
        'FAM_RL': 4,
    },
    'B': {
        'calibration': 0,
        'FAM_LL': 3,
        'FAM_LR': 4,
        'FAM_RL': 1,
        'FAM_RR': 2,
    },
}

presentation_duration = {
    "FAM_LL": 38.0,
    "FAM_LR": 38.0,
    "FAM_RL": 38.0,
    "FAM_RR": 38.0,
    "calibration": 27.0,
    "validation1": 4.0,
    "validation2": 4.0,
}

stimuli = list(target_aoi_location.keys())
stimulus_endings = [stimulus + ".webm" for stimulus in stimuli]

videos_relevant = stimuli + ['calibration', 'validation1', 'validation2']

RENDER_WEBGAZER = True
RENDER_ICATCHER = True
RENDER_OWLET_NOCALIB = True
RENDER_OWLET = True
RENDER_WEBCAM_VIDEOS = False
