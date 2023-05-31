import sys
import os
from os.path import isfile, join
import cv2
import subprocess
import shutil
import json

import numpy as np
import pandas as pd


# target fps for videos that get converted in preparation for icatcher
TARGET_FPS = 20

RESAMPLING_RATE_WEBGAZER = 20

STIMULUS_WIDTH = 1280.0
STIMULUS_HEIGHT = 960.0

STIMULUS_ASPECT_RATIO = STIMULUS_WIDTH / STIMULUS_HEIGHT

DATA_DIR = "./data"
MEDIA_DIR = "./media"

OUT_DIR = "./output"
WEBCAM_MP4_DIR = os.path.join(OUT_DIR, 'webcam_mp4')
RENDERS_DIR = os.path.join(OUT_DIR, 'renders')
WEBGAZER_DIR = os.path.join(RENDERS_DIR, 'webgazer')
ICATCHER_DIR = os.path.join(RENDERS_DIR, 'icatcher')
ICATCHER_WEBCAM_DIR = os.path.join(ICATCHER_DIR, 'webcam')
ICATCHER_RAW_DIR = os.path.join(ICATCHER_DIR, 'raw_results')


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
        'FAM_RL': 3,
        'FAM_RR': 4,
    },
    'B': {
        'calibration': 0,
        'FAM_LL': 4,
        'FAM_LR': 3,
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
RENDER_WEBCAM_VIDEOS = False


def main():

    participants = prepare_data(RENDER_WEBCAM_VIDEOS)

    webgazer = WebGazerHandler(participants)
    icatcher = ICatcherHandler(participants)

    icatcher.run(RENDER_ICATCHER)
    webgazer.run(RENDER_WEBGAZER)


def prepare_data(render_webcam_videos):
    if not os.path.exists(OUT_DIR):
        os.makedirs(OUT_DIR)

    files = [f for f in os.listdir(DATA_DIR) if isfile(join(DATA_DIR, f))]
    participants = set()

    for filename in files:
        if not (filename.endswith('.webm') or filename.endswith('.json')):
            continue

        split_pos = -2 if filename.endswith(tuple(stimulus_endings)) else -1
        participant = "_".join(filename.split("_")[:split_pos])
        participants.add(participant)

    # prepare videos for icatcher
    if not os.path.exists(WEBCAM_MP4_DIR):
        os.makedirs(WEBCAM_MP4_DIR)

    if render_webcam_videos:
        for p in participants:
            for s in videos_relevant:
                input_file = f'{DATA_DIR}/{p}_{s}.webm'
                temp_file = f'{WEBCAM_MP4_DIR}/{p}_{s}_temp.mp4'
                output_file = f'{WEBCAM_MP4_DIR}/{p}_{s}.mp4'
                if os.path.isfile(input_file) and not os.path.isfile(output_file):

                    subprocess.Popen(['ffmpeg', '-y',
                                      '-i', f'{DATA_DIR}/{p}_{s}.webm',
                                      '-filter:v',
                                      f'fps={TARGET_FPS}',
                                      temp_file,
                                      ]).wait()

                    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                             "format=duration", "-of",
                                             "default=noprint_wrappers=1:nokey=1", temp_file],
                                            stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT)

                    webcam_length = float(result.stdout.splitlines()[-1])
                    mismatch = presentation_duration[s] - webcam_length

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


class EyetrackingHandler:

    def __init__(self, participants):
        self.data = None
        self.data_filtered = None
        self.data_resampled = None
        self.participants = participants

    def run(self, should_render):
        self.preprocess()
        self._filter_data()

        if should_render:
            for s in stimuli:
                for p in self.participants:
                    self.render(p, s)
                self.render_joint(s)

    def preprocess(self):
        pass

    def render(self, participant, stimulus):
        pass

    def _resample_data(self, backfill_cols=None):
        # 38001
        if backfill_cols is None:
            backfill_cols = ['trial']

        tmp_df = pd.DataFrame({'t': range(0, 500, 50), 'new': True})\
            .merge(pd.DataFrame({'id': self.data['id'].unique()}), how='cross')\
            .merge(pd.DataFrame({'stimulus': self.data['stimulus'].unique()}), how='cross')

        self.data_resampled = self.data.copy()
        self.data_resampled['new'] = False
        self.data_resampled = pd.concat([self.data_resampled, tmp_df])\
            .sort_values(['t', 'new'], ascending=[True, True])\
            .groupby(['id', 'stimulus'], as_index=False)\
            .apply(lambda x: x.fillna(method="ffill"))\
            .query('new == True')\
            .drop('new', axis=1)\
            .sort_values(['id', 'stimulus', 't'])\
            .reset_index(drop=True)

        self.data_resampled.loc[:, backfill_cols] = self.data_resampled.loc[:, backfill_cols].bfill()

    def _filter_data(self):
        self.data_filtered = self.data  # TODO 1. add marker (excluded, reason) to data, 2. filter according to data in data_filtered

    @staticmethod
    def _side_to_hit(stimuli, sides):
        targets = ['none' if s not in target_aoi_location.keys() else target_aoi_location[s] for s in stimuli]
        distractors = ['right' if t == 'left' else ('left' if t == 'right' else 'none') for t in targets]
        return ['target' if s == t else ('distractor' if s == d else 'none') for s, t, d in zip(sides, targets, distractors)]

    def render_joint(self, stimulus):
        pass

    @staticmethod
    def _translate_coordinates(video_aspect_ratio, win_height, win_width, vid_height, vid_width, winX, winY):
        """translate the output coordinates of the eye-tracker onto the stimulus video"""
        if win_width / win_height > video_aspect_ratio:  # full height video
            vid_on_screen_width = win_height * video_aspect_ratio
            outside = False

            if winX < (win_width - vid_on_screen_width) / 2 or winX > (
                    (win_width - vid_on_screen_width) / 2 + vid_on_screen_width):
                outside = True
            # scale x
            vid_x = ((winX - (win_width - vid_on_screen_width) / 2) / vid_on_screen_width) * vid_width
            # scale y
            vid_y = (winY / win_height) * vid_height
            return int(vid_x), int(vid_y), outside
        else:  # full width video - not used in current study
            return None, None, True

    @staticmethod
    def _prepare_cv2_video(input_file, dest_file):
        video = cv2.VideoCapture(input_file, )
        fps = video.get(cv2.CAP_PROP_FPS)
        vid_height = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
        vid_width = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))

        video_writer = cv2.VideoWriter(dest_file, cv2.VideoWriter_fourcc('m', 'p', '4', 'v'), fps,
                                       (vid_width, vid_height),
                                       True)
        return video, video_writer, fps

    @staticmethod
    def _overlay_fc(input_path, output_path):
        # add frame counter to video
        subprocess.Popen(['ffmpeg', '-y',
                          '-i', input_path,
                          '-vf',
                          "drawtext=fontfile=Arial.ttf: text='%{frame_num} / %{pts}': start_number=1: x=(w-tw)/2: y=h-lh: fontcolor=black: fontsize=(h/20): box=1: boxcolor=white: boxborderw=5",
                          '-c:a', 'copy', '-c:v', 'libx264', '-crf', '23',
                          output_path,
                          ]).wait()


class WebGazerHandler(EyetrackingHandler):

    def preprocess(self):
        df_dict_list = []
        for p in self.participants:

            data_file = f'{DATA_DIR}/{p}_data.json'
            if not os.path.isfile(data_file):
                continue

            with open(data_file) as f:
                data = json.load(f)

            data = [x for x in data if 'task' in x and x['task'] == 'video']

            p_out_dir = f'{DATA_DIR}/{p}'
            if not os.path.exists(p_out_dir):
                os.makedirs(p_out_dir)

            df_dict = dict()
            df_dict['id'] = p

            for index, trial in enumerate(data):

                df_dict['trial'] = index + 1
                df_dict['stimulus'] = trial['stimulus'][0].split("/")[-1].split(".")[0]

                # calculate sampling rate
                datapoints = trial['webgazer_data']
                sampling_diffs = [datapoints[i + 1]['t'] - datapoints[i]['t'] for i in range(1, len(datapoints) - 1)]
                sampling_rates = [1000 / diff for diff in sampling_diffs]

                df_dict['sampling_rate'] = sum(sampling_rates) / len(sampling_rates)

                for datapoint in datapoints:

                    df_dict['t'] = datapoint["t"]
                    x_stim, y_stim, outside = self._translate_coordinates(STIMULUS_ASPECT_RATIO,
                                                                          trial['windowHeight'],
                                                                          trial['windowWidth'],
                                                                          STIMULUS_HEIGHT,
                                                                          STIMULUS_WIDTH,
                                                                          datapoint["x"],
                                                                          datapoint["y"]
                                                                          )

                    df_dict['x'] = x_stim
                    df_dict['y'] = y_stim
                    df_dict['outside'] = outside

                    df_dict['aoi'] = 'none'
                    if "hitAois" in datapoint:
                        hit_aoi_string = ','.join(datapoint['hitAois'])
                        df_dict['aoi'] = 'left' if 'left' in hit_aoi_string else ('right' if 'right' in hit_aoi_string else 'none')

                    df_dict['side'] = 'left' if x_stim < STIMULUS_WIDTH/2.0 else 'right'

                    df_dict_list.append(dict(df_dict))

        self.data = pd.DataFrame(df_dict_list)\
            .sort_values(['id', 'stimulus', 't'])\
            .reset_index(drop=True)

        self.data['aoi_hit'] = self._side_to_hit(self.data['stimulus'], self.data['aoi'])
        self.data['side_hit'] = self._side_to_hit(self.data['stimulus'], self.data['side'])

        self.data.to_csv(f'{OUT_DIR}/webgazer_data.csv', encoding='utf-8')

        self._resample_data(backfill_cols=['trial', 'sampling_rate'])
        self.data_resampled.to_csv(f'{OUT_DIR}/webgazer_RESAMPLED_data.csv', encoding='utf-8')
        exit()

    def render(self, participant, stimulus):

        """ add the webcam footage as an overlay to the stimulus media file (if footage exists),
            add a frame counter, and visualize the gaze location from the eyetracking data
            saves the video in the output directory
        """

        d = self.data[(self.data['id'] == participant) & (self.data['stimulus'] == stimulus)]
        d.reset_index(drop=True, inplace=True)

        if len(d.index) == 0:
            return

        if not os.path.exists(WEBGAZER_DIR):
            os.makedirs(WEBGAZER_DIR)

        base_path = f'{WEBGAZER_DIR}/{participant}'
        stimulus_file = f'{stimulus}.mp4'

        if not os.path.exists(base_path):
            os.makedirs(base_path)

        pre1_path = f'{base_path}/pre1_{stimulus_file}'
        pre2_path = f'{base_path}/audio_no_dot_{stimulus_file}'
        final_path = f'{base_path}/tagged_{stimulus}.mp4'

        if os.path.isfile(final_path):
            return

        p_webcam_file = f'{WEBCAM_MP4_DIR}/{participant}_{stimulus}.mp4'
        if os.path.isfile(p_webcam_file):
            subprocess.Popen(['ffmpeg', '-y',
                              '-i', f'{MEDIA_DIR}/{stimulus_file}',
                              '-i', p_webcam_file,
                              '-filter_complex',
                              "[1:v]scale=350:-1 [inner];[0:v][inner]overlay=10:10:shortest=0[out]",
                              # [1:v]scale=350:-1,hflip take out the flip for now
                              '-map', '[out]', '-map', '1:a',
                              pre1_path
                              ]).wait()

        else:
            shutil.copy(f'{MEDIA_DIR}/{stimulus_file}', pre1_path)

        self._overlay_fc(pre1_path, pre2_path)

        print(f'Rendering {final_path}...')
        video, video_writer, fps = self._prepare_cv2_video(pre2_path, final_path)

        success, frame = video.read()
        index = 1
        gaze_point_index = 1
        while success:

            if gaze_point_index < len(d.index) - 1 and d['t'][gaze_point_index + 1] <= (index / fps) * 1000:
                gaze_point_index += 1

            if not d.outside[gaze_point_index]:
                cv2.circle(frame, (d.x[gaze_point_index], d.y[gaze_point_index]), radius=10,
                           color=(255, 0, 0), thickness=-1)

            cv2.waitKey(int(1000 / int(fps)))
            video_writer.write(frame)
            success, frame = video.read()
            index += 1

        video.release()
        video_writer.release()

        os.remove(pre1_path)
        os.remove(pre2_path)

    def render_joint(self, stimulus):

        pre_path = f'{WEBGAZER_DIR}/{stimulus}_beeswarm_temp.mp4'
        final_path = f'{WEBGAZER_DIR}/{stimulus}_beeswarm.mp4'

        self._overlay_fc(f'{MEDIA_DIR}/{stimulus}.mp4', pre_path)

        d = self.data_resampled[self.data_resampled['stimulus'] == stimulus]
        d.reset_index(drop=True, inplace=True)

        if len(d.index) == 0:
            return

        video, video_writer, fps = self._prepare_cv2_video(pre_path, final_path)

        success, frame = video.read()
        index = 1
        timestep = 1000 / RESAMPLING_RATE_WEBGAZER
        t = 0

        while success:

            timepoint_data = d[d['t'] == int(t)]
            timepoint_data.reset_index(drop=True, inplace=True)

            if len(timepoint_data.index) == 0:
                return

            for i, row in timepoint_data:
                if not row['outside']:
                    cv2.circle(frame, (row['x'], row['y']), radius=10, color=(255, 0, 0), thickness=-1)

            cv2.circle(frame,
                       (int(sum(timepoint_data['x'])/len(timepoint_data['x'])),
                       int(sum(timepoint_data['y'])/len(timepoint_data['y']))),
                       radius=15,
                       color=(0, 0, 255), thickness=-1)

            cv2.imshow("", frame)
            cv2.waitKey(int(1000 / int(fps)))
            video_writer.write(frame)
            success, frame = video.read()

            if t <= (index / fps) * 1000:
                t += timestep
            index += 1

        video.release()
        video_writer.release()
        os.remove(pre_path)


class ICatcherHandler(EyetrackingHandler):

    def preprocess(self):
        if not os.path.exists(ICATCHER_WEBCAM_DIR):
            os.makedirs(ICATCHER_WEBCAM_DIR)
        if not os.path.exists(ICATCHER_RAW_DIR):
            os.makedirs(ICATCHER_RAW_DIR)

        # run icatcher
        for p in self.participants:
            for s in videos_relevant:
                input_file = f'{WEBCAM_MP4_DIR}/{p}_{s}.mp4'
                output_file_video = f'{ICATCHER_WEBCAM_DIR}/{p}_{s}_output.mp4'
                output_file_data = f'{ICATCHER_RAW_DIR}/{p}_{s}.txt'
                if os.path.isfile(input_file) and \
                        (not os.path.isfile(output_file_video) or not os.path.isfile(output_file_data)):
                    subprocess.Popen(['icatcher',
                                      '--output_video_path',
                                      ICATCHER_WEBCAM_DIR,
                                      '--output_annotation',
                                      ICATCHER_RAW_DIR,
                                      #'--show_output',
                                      '--use_fc_model',  # TODO report this one
                                      input_file
                                      ]).wait()

        df_list = []
        for p in self.participants:
            for s in stimuli + ['calibration']:
                data_file = f'{ICATCHER_RAW_DIR}/{p}_{s}.txt'
                if not os.path.isfile(data_file):
                    continue

                data = pd.read_csv(data_file, sep=",", header=None)
                data.columns = ["frame", "look", "conf"]

                data['id'] = p
                data['stimulus'] = s
                data['trial'] = trial_order_indices[p.split("_")[-1]][s]
                data['t'] = data['frame'] * 1000 / TARGET_FPS
                df_list.append(data)

        self.data = pd.concat(df_list)
        self.data['look'] = self.data['look'].str.strip()

        # Flip the look so that variable represents the participants viewpoint, not the webcams
        self.data.loc[self.data['look'] == 'left', 'look'] = 'tmp'
        self.data.loc[self.data['look'] == 'right', 'look'] = 'left'
        self.data.loc[self.data['look'] == 'tmp', 'look'] = 'right'

        self.data = self.data.drop('frame', axis=1)
        self.data['hit'] = self._side_to_hit(self.data['stimulus'], self.data['look'])

        self.data.to_csv(f'{OUT_DIR}/icatcher_data.csv', encoding='utf-8')

    def render(self, participant, stimulus):
        d = self.data[(self.data['id'] == participant) & (self.data['stimulus'] == stimulus)]
        d.reset_index(drop=True, inplace=True)

        if len(d.index) == 0:
            return

        if not os.path.exists(ICATCHER_DIR):
            os.makedirs(ICATCHER_DIR)

        base_path = f'{ICATCHER_DIR}/{participant}'
        stimulus_file = f'{stimulus}.mp4'
        temp_path = f'{base_path}/pre1_{stimulus_file}'
        final_path = f'{base_path}/{stimulus_file}'

        if os.path.isfile(final_path):
            return

        if not os.path.exists(base_path):
            os.makedirs(base_path)

        print(f'Rendering {final_path}...')

        video, video_writer, fps = self._prepare_cv2_video(f'{MEDIA_DIR}/{stimulus_file}', temp_path)

        success, frame = video.read()
        index = 1
        gaze_point_index = 1
        while success:

            if gaze_point_index < len(d.index) - 1 and d['t'][gaze_point_index + 1] <= (index / fps) * 1000:
                gaze_point_index += 1

            is_valid_look = d['look'][gaze_point_index] == 'left' or d['look'][gaze_point_index] == 'right'
            y, h = 0, int(STIMULUS_HEIGHT)
            w = int(STIMULUS_WIDTH / 2.0) if is_valid_look else int(STIMULUS_WIDTH)
            x = int(STIMULUS_WIDTH / 2.0) if d['look'][gaze_point_index] == 'left' else 0

            sub_img = frame[y:y + h, x:x + w]
            black_rect = np.zeros(sub_img.shape, dtype=np.uint8)
            res = cv2.addWeighted(sub_img, 0.5, black_rect, 0.5, 1.0)

            # Putting the image back to its position
            frame[y:y + h, x:x + w] = res

            if is_valid_look:
                cv2.circle(frame, (int(w / 2 if d['look'][gaze_point_index] == 'left' else w / 2 * 3), int(h / 2)),
                           radius=10, color=(0, 0, 255), thickness=-1)

            cv2.waitKey(int(1000 / int(fps)))
            video_writer.write(frame)
            success, frame = video.read()
            index += 1

        video.release()
        video_writer.release()

        icatcher_webcam_path = f'{ICATCHER_WEBCAM_DIR}/{participant}_{stimulus}_output.mp4'
        if os.path.isfile(icatcher_webcam_path):
            subprocess.Popen(['ffmpeg', '-y',
                              '-i', temp_path,
                              '-i', icatcher_webcam_path,
                              '-filter_complex',
                              "[1:v]scale=350:-1 [inner];[0:v][inner]overlay=10:10:shortest=0[out]",
                              '-map', '[out]',
                              final_path
                              ]).wait()

        else:
            shutil.copy(f'{MEDIA_DIR}/{stimulus_file}', temp_path)

        os.remove(temp_path)


if __name__ == '__main__':
    main()

