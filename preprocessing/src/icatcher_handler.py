import os
import cv2
import subprocess

import numpy as np
import pandas as pd

import settings
from .base_handler import GazecodingHandler


class ICatcherHandler(GazecodingHandler):

    def __init__(self, name, participants):
        super().__init__(name, participants)

        self.webcam_dir = os.path.join(self.render_dir, 'webcam')
        self.raw_dir = os.path.join(self.render_dir, 'raw_results')

    def preprocess(self):

        if not os.path.exists(self.webcam_dir):
            os.makedirs(self.webcam_dir)
        if not os.path.exists(self.raw_dir):
            os.makedirs(self.raw_dir)

        # run icatcher
        for p in self.participants:
            for s in settings.videos_relevant:
                input_file = f'{settings.WEBCAM_MP4_DIR}/{p}_{s}.mp4'
                output_file_video = f'{self.webcam_dir}/{p}_{s}_output.mp4'
                output_file_data = f'{self.raw_dir}/{p}_{s}.txt'
                if os.path.isfile(input_file) and \
                        (not os.path.isfile(output_file_video) or not os.path.isfile(output_file_data)):
                    subprocess.Popen(['icatcher',
                                      '--output_video_path',
                                      self.webcam_dir,
                                      '--output_annotation',
                                      self.raw_dir,
                                      #'--show_output',
                                      '--use_fc_model',  # TODO report this one
                                      input_file
                                      ]).wait()

        df_list = []
        for p in self.participants:
            for s in settings.stimuli + ['calibration']:
                data_file = f'{self.raw_dir}/{p}_{s}.txt'
                if not os.path.isfile(data_file):
                    continue

                data = pd.read_csv(data_file, sep=",", header=None)
                data.columns = ["frame", "look", "conf"]

                data['id'] = p
                data['stimulus'] = s
                data['trial'] = settings.trial_order_indices[p.split("_")[-1]][s]
                data['t'] = data['frame'] * 1000 / settings.TARGET_FPS
                df_list.append(data)

        self.data = pd.concat(df_list)
        self.data['look'] = self.data['look'].str.strip()

        # Flip the look so that variable represents the participants viewpoint, not the webcams
        self.data.loc[self.data['look'] == 'left', 'look'] = 'tmp'
        self.data.loc[self.data['look'] == 'right', 'look'] = 'left'
        self.data.loc[self.data['look'] == 'tmp', 'look'] = 'right'

        self.data = self.data.drop('frame', axis=1)\
            .sort_values(['id', 'trial', 't']) \
            .reset_index(drop=True)

        self.data['hit'] = self._side_to_hit(self.data['stimulus'], self.data['look'])
        self.data.to_csv(f'{settings.OUT_DIR}/icatcher_data.csv', encoding='utf-8')

        self.data = self.data[['id', 'stimulus', 'trial', 't', 'look', 'conf', 'hit']] # maybe refactor so that the colnames have a ssot?
        self.backfill_cols += ['trial']

    @staticmethod
    def _paint_black_rect(fr, side, opacity):
        y, h = 0, int(settings.STIMULUS_HEIGHT)
        w = int(settings.STIMULUS_WIDTH / 2.0)
        x = 0 if side == 'left' else int(settings.STIMULUS_WIDTH / 2.0)

        sub_img = fr[y:h, x:x + w]
        black_rect = np.zeros(sub_img.shape, dtype=np.uint8)
        res = cv2.addWeighted(sub_img, 1 - opacity, black_rect, opacity, 1.0)
        fr[y:h, x:x + w] = res

    def _render_frame(self, frame, index, data):
        is_valid_look = data['look'][index] == 'left' or data['look'][index] == 'right'

        if data['look'][index] != 'left':
            self._paint_black_rect(frame, 'left', 0.5)
        if data['look'][index] != 'right':
            self._paint_black_rect(frame, 'right', 0.5)

        if is_valid_look:
            w = int(settings.STIMULUS_WIDTH / 2.0)
            h = int(settings.STIMULUS_HEIGHT)
            cv2.circle(frame, (int(w / 2 if data['look'][index] == 'left' else w / 2 * 3), int(h / 2)),
                       radius=10, color=(0, 0, 255), thickness=-1)

    def _render_post_loop(self, input_path, output_path, participant, stimulus):
        icatcher_webcam_path = f'{self.webcam_dir}/{participant}_{stimulus}_output.mp4'
        self._overlay_webcam(input_path, output_path, icatcher_webcam_path)

    def _render_frame_joint(self, frame, t, data):
        timepoint_data = data[(data['t'] == int(t)) & ((data['look'] == 'left') | (data['look'] == 'right'))].reset_index(
            drop=True)
        if len(timepoint_data.index) > 0:
            value_counts = timepoint_data['look'].value_counts()
            left_per = value_counts.get('left', 0) / (value_counts.get('left', 0) + value_counts.get('right', 0))

            self._paint_black_rect(frame, 'left', 1 - left_per)
            self._paint_black_rect(frame, 'right', left_per)

            def put_percentage(fr, x, percentage):
                cv2.putText(fr, f'{(int(percentage * 100)):02d}%', (int(x), 50), cv2.FONT_HERSHEY_SIMPLEX, 1.5,
                            (0, 0, 255), 2, cv2.LINE_AA)

            put_percentage(frame, 30, left_per)
            put_percentage(frame, settings.STIMULUS_WIDTH - 130, 1 - left_per)
