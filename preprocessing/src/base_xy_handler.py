import os
import cv2
import statistics
import numpy as np

import settings
from .base_handler import GazecodingHandler


class EyetrackingHandler(GazecodingHandler):

    def __init__(self, name, participants, general_exclusions, dot_color):
        super().__init__(name, participants, general_exclusions)

        self.dot_color = dot_color

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

            x_values_drawn = []
            y_values_drawn = []
            for _, row in timepoint_data.iterrows():
                if not row['outside']:
                    cv2.circle(frame, (int(row['x']), int(row['y'])), radius=10, color=self.dot_color, thickness=-1)
                    x_values_drawn.append(row['x'])
                    y_values_drawn.append(row['y'])

            if len(x_values_drawn) == 0:
                return

            cv2.circle(frame,
                       (int(statistics.median(x_values_drawn)),
                        int(statistics.median(y_values_drawn))),
                       radius=15,
                       color=(0, 0, 255), thickness=-1)

            if len(x_values_drawn) == 1:
                return

            cv2.ellipse(frame,
                        (int(statistics.median(x_values_drawn)), int(statistics.median(y_values_drawn))),
                        (int(statistics.stdev(x_values_drawn)), int(statistics.stdev(y_values_drawn))), 0.,
                        0., 360,
                        (255, 255, 255), thickness=3)

    @staticmethod
    def _translate_coordinates(video_aspect_ratio, win_height, win_width, vid_height, vid_width, winX, winY):
        """translate the output coordinates of the eye-tracker onto the stimulus video"""
        if winX is None or np.isnan(winX) or winY is None or np.isnan(winY):
            return None, None, True
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
