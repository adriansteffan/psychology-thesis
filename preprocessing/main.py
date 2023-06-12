import os
from os.path import isfile, join
import subprocess
import shutil
import argparse
import json

import pandas as pd

import settings
from src import utils
from src.icatcher_handler import ICatcherHandler
from src.webgazer_handler import WebGazerHandler
from src.owlet_handler import OWLETHandler


# TODO:
"""
# The refactored version of OWLET works - except for some edge cases where the y coordinate defaults to 
a different value than the original. Therefore, OWLET support remains experimental for now.

TODO: Create a "dumb" wrapper around OWLET as a command line tool
that calibrates for each trial individually.
"""


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--step",
                        help="specify step when preprocessing with exclusions",
                        type=int, choices=[1, 2, 3]
                        )
    args = parser.parse_args()

    participants = set()
    general_exclusions = None
    exclusion_path = os.path.join(settings.EXCLUSION_DIR, '_exclusions_general.csv')

    if not os.path.exists(settings.EXCLUSION_DIR):
        os.makedirs(settings.EXCLUSION_DIR)

    if (not args.step and not os.path.isfile(exclusion_path)) or (args.step and args.step == 1):
        participants = get_participants()
    elif not os.path.isfile(exclusion_path):
        exit(f'No general exclusion file found at {exclusion_path} even though one is required for the specified steps')
    elif not args.step or (args.step and (args.step == 2 or args.step == 3)):
        general_exclusions = pd.read_csv(exclusion_path)
        utils.validate_exclusions(general_exclusions, exclusion_path)
        participants = set(general_exclusions['id'].unique())
    else:
        exit("Should not happen")

    prepare_data(participants, settings.RENDER_WEBCAM_VIDEOS)

    if args.step and args.step == 1:
        if os.path.isfile(exclusion_path):
            exit(f'Exclusion file  at {exclusion_path} already exists. '
                 f'To make sure that you are not accidentally overwriting it, please remove it first.')

        exclusion_df = utils.create_empty_general_exclusion_df(participants)
        exclusion_df.to_csv(exclusion_path, encoding='utf-8', index=False)
        return

    icatcher = ICatcherHandler(settings.GAZECODER_NAMES['ICATCHER'], participants, general_exclusions)
    webgazer = WebGazerHandler(settings.GAZECODER_NAMES['WEBGAZER'], participants, general_exclusions, dot_color=(255, 0, 0))
    #owlet_nocalib = OWLETHandler(settings.GAZECODER_NAMES['OWLET_NOCALIB'], participants, general_exclusions, dot_color=(125, 255, 0), calibrate=False)
    #owlet = OWLETHandler(settings.GAZECODER_NAMES['OWLET'], participants, general_exclusions, dot_color=(0, 0, 0), calibrate=True)

    #owlet_nocalib.run(step=args.step, should_render=settings.RENDER_OWLET_NOCALIB)
    #owlet.run(step=args.step, should_render=settings.RENDER_OWLET)
    icatcher.run(step=args.step, should_render=settings.RENDER_ICATCHER)
    webgazer.run(step=args.step, should_render=settings.RENDER_WEBGAZER)




def get_participants():

    files = [f for f in os.listdir(settings.DATA_DIR) if isfile(join(settings.DATA_DIR, f))]
    participants = set()

    for filename in files:
        if not (filename.endswith('.webm') or filename.endswith('.json')):
            continue

        special_stimulus_endings = [s + ".webm" for s in settings.stimuli_critical]
        split_pos = -2 if filename.endswith(tuple(special_stimulus_endings)) else -1
        participant = "_".join(filename.split("_")[:split_pos])
        participants.add(participant)

    return participants


def prepare_data(participants, render_webcam_videos):
    if not os.path.exists(settings.OUT_DIR):
        os.makedirs(settings.OUT_DIR)

    if not os.path.exists(settings.WEBCAM_MP4_DIR):
        os.makedirs(settings.WEBCAM_MP4_DIR)

    # extract a table with window sizes from the online data -> other eyetrackers might need the dimensions.
    # due to how the data is structured, we have to assume that the window size did not change over
    # the course of the experiment, as calibration and validation did not provide that data.
    # However, as the experiment went into fullscreen, constant window dimensions are likely.
    window_sizes_path = os.path.join(settings.OUT_DIR, '_window_sizes.csv')
    if not os.path.isfile(window_sizes_path):
        ws_dict_list = []
        for p in participants:

            data_file = f'{settings.DATA_DIR}/{p}_data.json'
            if not os.path.isfile(data_file):
                print(p)
                continue
            with open(data_file) as f:
                data = json.load(f)

            first_trial = [x for x in data if 'task' in x and x['task'] == 'video'][0]

            ws_dict_list.append({'id': p,
                                 'window_width': first_trial["windowWidth"],
                                 'window_height': first_trial["windowHeight"]
                                 })

        pd.DataFrame(ws_dict_list).to_csv(window_sizes_path, encoding='utf-8', index=False)

    if render_webcam_videos:
        for p in participants:
            for s in settings.stimuli:
                input_file = f'{settings.DATA_DIR}/{p}_{s}.webm'
                temp_file = f'{settings.WEBCAM_MP4_DIR}/{p}_{s}_temp.mp4'
                output_file = f'{settings.WEBCAM_MP4_DIR}/{p}_{s}.mp4'

                if os.path.isfile(input_file) and not os.path.isfile(output_file):

                    subprocess.Popen(['ffmpeg', '-y',
                                      '-i', f'{settings.DATA_DIR}/{p}_{s}.webm',
                                      '-filter:v',
                                      f'fps={settings.TARGET_FPS}',
                                      temp_file,
                                      ]).wait()

                    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                             "format=duration", "-of",
                                             "default=noprint_wrappers=1:nokey=1", temp_file],
                                            stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT)

                    webcam_length = float(result.stdout.splitlines()[-1])
                    mismatch = settings.STIMULI[s]['presentation_duration'] - webcam_length

                    if mismatch > 0.0:
                        subprocess.Popen(['ffmpeg', '-y',
                                          '-i', temp_file,
                                          '-filter_complex',
                                          f'[0:v]tpad=start_duration={mismatch}[v];[0:a]adelay={mismatch*1000}s:all=true[a]',
                                          "-map", "[v]", "-map", "[a]",
                                          output_file,
                                          ]).wait()
                    elif mismatch < 0.0:
                        subprocess.Popen(['ffmpeg',
                                          '-y',
                                          '-i',
                                          temp_file,
                                          '-ss',
                                          f'00:00:{(-1.0) * mismatch:06.3f}',
                                          output_file,
                                          ]).wait()
                    else:
                        shutil.copy(temp_file, output_file)

                    os.remove(temp_file)

    return participants


if __name__ == '__main__':
    main()

