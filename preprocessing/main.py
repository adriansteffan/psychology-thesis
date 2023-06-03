import os
from os.path import isfile, join
import subprocess
import shutil

import settings
from src.icatcher_handler import ICatcherHandler
from src.webgazer_handler import WebGazerHandler
from src.owlet_handler import OWLETHandler


def main():

    participants = prepare_data(settings.RENDER_WEBCAM_VIDEOS)

    icatcher = ICatcherHandler('icatcher', participants)
    webgazer = WebGazerHandler('webgazer', participants, dot_color=(255, 0, 0))
    owlet_nocalib = OWLETHandler('owlet_nocalib', participants, dot_color=(0, 255, 0), calibrate=False)
    owlet = OWLETHandler('owlet', participants, dot_color=(255, 255, 0), calibrate=True)

    icatcher.run(settings.RENDER_ICATCHER)
    webgazer.run(settings.RENDER_WEBGAZER)
    owlet_nocalib.run(settings.RENDER_OWLET_NOCALIB)
    owlet.run(settings.RENDER_OWLET)


def prepare_data(render_webcam_videos):
    if not os.path.exists(settings.OUT_DIR):
        os.makedirs(settings.OUT_DIR)

    files = [f for f in os.listdir(settings.DATA_DIR) if isfile(join(settings.DATA_DIR, f))]
    participants = set()

    for filename in files:
        if not (filename.endswith('.webm') or filename.endswith('.json')):
            continue

        split_pos = -2 if filename.endswith(tuple(settings.stimulus_endings)) else -1
        participant = "_".join(filename.split("_")[:split_pos])
        participants.add(participant)

    if not os.path.exists(settings.WEBCAM_MP4_DIR):
        os.makedirs(settings.WEBCAM_MP4_DIR)

    if render_webcam_videos:
        for p in participants:
            for s in settings.videos_relevant:
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
                    mismatch = settings.presentation_duration[s] - webcam_length

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

