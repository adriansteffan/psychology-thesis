import os
import cv2
import json
import statistics

import pandas as pd

import settings
from base_handler import EyetrackingHandler


class WebGazerHandler(EyetrackingHandler):

    def preprocess(self):
        df_dict_list = []
        for p in self.participants:

            data_file = f'{settings.DATA_DIR}/{p}_data.json'
            if not os.path.isfile(data_file):
                continue

            with open(data_file) as f:
                data = json.load(f)

            data = [x for x in data if 'task' in x and x['task'] == 'video']

            p_out_dir = f'{settings.DATA_DIR}/{p}'
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
                    x_stim, y_stim, outside = self._translate_coordinates(settings.STIMULUS_ASPECT_RATIO,
                                                                          trial['windowHeight'],
                                                                          trial['windowWidth'],
                                                                          settings.STIMULUS_HEIGHT,
                                                                          settings.STIMULUS_WIDTH,
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

                    df_dict['side'] = 'left' if x_stim < settings.STIMULUS_WIDTH/2.0 else 'right'

                    df_dict_list.append(dict(df_dict))

        self.data = pd.DataFrame(df_dict_list)\
            .sort_values(['id', 'trial', 't'])\
            .reset_index(drop=True)

        self.data['aoi_hit'] = self._side_to_hit(self.data['stimulus'], self.data['aoi'])
        self.data['side_hit'] = self._side_to_hit(self.data['stimulus'], self.data['side'])

        self.backfill_cols += ['trial', 'sampling_rate']

    def _render_pre_loop(self, input_path, output_path, participant, stimulus):

        path, _, ending = output_path.rpartition('.')
        tmp_path = f'{path}_tmp.{ending}'

        webcam_path = f'{settings.WEBCAM_MP4_DIR}/{participant}_{stimulus}.mp4'
        self._overlay_webcam(input_path, tmp_path, webcam_path, audio=True)
        self._overlay_fc(tmp_path, output_path)

        try:
            os.remove(tmp_path)
        except OSError:
            pass

    def _render_frame(self, frame, index, data):
        if not data.outside[index]:
            cv2.circle(frame, (data.x[index], data.y[index]), radius=10,
                       color=(255, 0, 0), thickness=-1)

    def _render_frame_joint(self, frame, t, data):
        timepoint_data = data[(data['t'] == int(t)) & (data['x'].notna()) & (data['y'].notna())]
        timepoint_data.reset_index(drop=True, inplace=True)

        if len(timepoint_data.index) > 0:

            for _, row in timepoint_data.iterrows():
                if not row['outside']:
                    cv2.circle(frame, (int(row['x']), int(row['y'])), radius=10, color=(255, 0, 0), thickness=-1)

            cv2.circle(frame,
                       (int(statistics.mean(timepoint_data['x'])),
                        int(statistics.mean(timepoint_data['y']))),
                       radius=15,
                       color=(0, 0, 255), thickness=-1)

            cv2.ellipse(frame,
                        (int(statistics.mean(timepoint_data['x'])), int(statistics.mean(timepoint_data['y']))),
                        (int(statistics.stdev(timepoint_data['x'])), int(statistics.stdev(timepoint_data['y']))), 0.,
                        0., 360,
                        (255, 255, 255), thickness=3)

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