"""
Created by Denise Werchan, 2022
Modified by Adrian Steffan, 2023

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import cv2
import numpy as np

from .gaze_tracking import GazeTracking


class LookingCalibration(object):

    def __init__(self, show_output):
        self.invert_calib_order = False
        self.frame = None
        self.eye_left = None
        self.eye_right = None
        self.gaze = GazeTracking(2.7, 4, 1, 1, 1) # eventually replace this with means from babies
        self.hor_ratios = []
        self.hor_ratios2 = []
        self.left_ratios = []
        self.right_ratios = []
        self.ver_ratios = []
        self.ver_ratios_left = []
        self.ver_ratios_right = []
        self.blinks = []
        self.areas = []
        self.eye_areas = []
        self.lengths = []
        self.timestamp = 0
        self.show_output = show_output

    def calibrate_eyes(self, file):
        video = cv2.VideoCapture(file, )
        success, frame = video.read()

        while success:

            self.timestamp = video.get(cv2.CAP_PROP_POS_MSEC)

            # We send this frame to GazeTracking to analyze it
            self.gaze.refresh(frame)

            frame = self.gaze.annotated_frame()
            hor_look2 = self.gaze.horizontal_gaze_scaled()
            hor_look, ver_look, ver_look_left, ver_look_right = self.gaze.xy_gaze_position()

            eyearea = self.gaze.get_eye_area()
            if eyearea is not None:
                self.areas.append(eyearea)

            eyeratio = self.gaze.get_eye_area_ratio()
            if eyeratio is not None:
                self.eye_areas.append(eyeratio)

            blink = self.gaze.eye_ratio()
            if blink != 0:
                self.blinks.append(blink)

            if hor_look is not None and not self.gaze.is_blinking() and \
                    eyeratio is not None and (.77 < eyeratio < 1.3):
                self.hor_ratios.append(hor_look)
                self.hor_ratios2.append(hor_look2)

            if ver_look is not None and not self.gaze.is_blinking() and \
                    eyeratio is not None and (.77 < eyeratio < 1.3):
                self.ver_ratios.append(ver_look)
                self.ver_ratios_left.append(ver_look_left)
                self.ver_ratios_right.append(ver_look_right)

            if self.show_output:
                cv2.putText(frame, "Calibrating...", (20, 30), cv2.FONT_HERSHEY_DUPLEX, 0.9, (255, 255, 0), 1)
                cv2.imshow("Calibration", frame)
            if cv2.waitKey(1) == 27:
                break

            success, frame = video.read()

        video.release()
        
    def get_eye_area_ratio(self):

        l=np.array(self.eye_areas)
        blinks = l[(l>np.quantile(l,0)) & (l<np.quantile(l,1))].tolist()
        blinks.sort()
        mean = sum(blinks)/len(blinks)
        maximum = blinks[-1]
        minimum = blinks[0]

        return mean, maximum, minimum

    def get_eye_ratio(self):
        l=np.array(self.blinks)
        blinks = l[(l>np.quantile(l, 0)) & (l<np.quantile(l, 1))].tolist()
        blinks.sort()
        mid = len(blinks)//2
        mean = blinks[mid]
        maximum = blinks[-1]
        minimum = blinks[0]

        return mean, maximum, minimum

    def get_avg_length(self):
        return 100  # this was in the original code
        
    def get_eye_area(self):
        l=np.array(self.areas)
        final_areas = l[(l>np.quantile(l,.1)) & (l<np.quantile(l,.9))].tolist()
        mean = sum(final_areas)/len(final_areas)
        return mean

    def get_min_max_hor(self, ratio_num):
        if ratio_num != 1 and ratio_num != 2:
            exit("invalid ratio number")
        ratios = self.hor_ratios if ratio_num == 1 else (self.hor_ratios2 if ratio_num == 2 else None)

        looks = np.array(ratios)
        mid = len(looks) // 2
        if self.invert_calib_order:
            looks = looks[mid:len(looks)]
        else:
            looks = looks[0:mid]
        looks.sort()
        min_look = looks[0]
        max_look = looks[-1]
        range_vals = max_look - min_look
        middle = (min_look + max_look) / 2

        return min_look, max_look, range_vals, middle

    def get_min_max_ver(self):
        looks = np.array(self.ver_ratios)
        mid = len(looks)//2
        if self.invert_calib_order:
            looks = looks[0:mid]
        else:
            looks = looks[mid:len(looks)]

        looks.sort()
        toplook_outer = looks[0]
        downlook = looks[-1]
        range_vals = downlook - toplook_outer

        def get_lookrange(ratios):
            looks=np.array(ratios)
            mid = len(looks)//2
            looks=looks[mid:len(looks)]
            looks.sort()
            toplook = looks[0]
            downlook = looks[-1]
            range_vals = downlook - toplook_outer
            middle = (toplook_outer + downlook) / 2

            return toplook, range_vals, middle, downlook

        # this replicates a bug in the original implementation, where only he middle and downlook values of "ver_ratios_right" are considered
        toplook_left, range_vals_left, _, _ = get_lookrange(self.ver_ratios_left)
        toplook_right, range_vals_right, middle, downlook = get_lookrange(self.ver_ratios_right)

        return toplook_outer, downlook, range_vals, middle, range_vals_left, range_vals_right, toplook_left, toplook_right








