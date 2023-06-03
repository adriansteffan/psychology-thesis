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

from __future__ import division
import os
import cv2
import dlib

from .eye import Eye


class GazeTracking(object):
    """
    This class tracks the user's gaze.
    It provides useful information like the position of the eyes
    and pupils and allows to know if the eyes are open or closed
    """

    def __init__(self, mean, maximum, minimum, ratio, length):
        self.frame = None
        self.eye_left = None
        self.eye_right = None
        self.face_index = 0
        self.face = None
        # _face_detector is used to detect faces
        self._face_detector = dlib.get_frontal_face_detector()
        self.eye_scale = mean
        self.blink_thresh = maximum * 1.1
        self.blink_thresh2 = minimum * .9
        self.leftpoint = None
        self.rightpoint = None
        self.leftright_eyeratio = ratio
        self.length = length

        # _predictor is used to get facial landmarks of a given face
        model_path = os.path.join(os.path.dirname(__file__), "shape_predictor_68_face_landmarks.dat")
        self._predictor = dlib.shape_predictor(model_path)
        # eyepath = os.path.join(os.path.dirname(__file__), "=haarcascade_eye.xml")) # Missing from repository
        # self.eye_classifier = cv2.CascadeClassifier(eyepath)

    @property
    def pupils_located(self):
        """Check that the pupils have been located"""
        try:
            int(self.eye_left.pupil.x)
            int(self.eye_left.pupil.y)
            int(self.eye_right.pupil.x)
            int(self.eye_right.pupil.y)
            return True
        except Exception:
            return False

    def _analyze(self):
        """Detects the face and initialize Eye objects"""
     
        frame = cv2.cvtColor(self.frame, cv2.COLOR_BGR2GRAY)
        
        faces = self._face_detector(frame)
            
        # if there are two faces detected, take the lower face
        self.face_index = 1 if len(faces) > 1 and (faces[1].bottom() > faces[0].bottom()) else 0
        
        try:
            landmarks = self._predictor(frame, faces[self.face_index])
            self.landmarks = landmarks
            self.eye_left = Eye(frame, landmarks, 0, self.leftpoint)
            self.eye_right = Eye(frame, landmarks, 1, self.rightpoint)
            self.face = faces[self.face_index]
            self.chin = landmarks.part(8).y
            try:
                self.leftpoint = (self.eye_left.pupil.x, self.eye_left.pupil.y)
                self.rightpoint = (self.eye_right.pupil.x, self.eye_right.pupil.y)
            except:
                self.leftpoint = None
                self.rightpoint = None

        except IndexError:
                self.eye_left = None
                self.eye_right = None
                self.face = None

    def refresh(self, frame):
        """Refreshes the frame and analyzes it.
        Arguments:
            frame (numpy.ndarray): The frame to analyze
        """
        self.frame = frame
        self._analyze()
        
    def pupil_coords(self, side):
        """Returns the xy coordinates and radius of the specified pupil"""
        if side not in ['left', 'right']:
            exit("invalid eye")

        if not self.pupils_located:
            return (None, None), None

        eye = self.eye_left if side == 'left' else (self.eye_right if side == 'right' else None)

        x = eye.origin[0] + eye.pupil.x
        y = eye.origin[1] + eye.pupil.y
        return (x, y), eye.pupil.radius

    def check_face(self):
        """Returns whether a face was found or not"""
        return ((self.face_index == 4 or self.face is None) and
                self.eye_left is None and self.eye_right is None)

    def face_coords(self):
        """Returns the coordinates of the baby's face"""
        try:
            faces = self._face_detector(self.frame)
            x = faces[self.face_index].left()
            y = faces[self.face_index].top()
            w = faces[self.face_index].right()
            h = faces[self.face_index].bottom()
            return x, y, w, h
        except IndexError:
            return None, None, None, None
        
    def get_eye_area(self):
        """Returns the average area of the baby's right and left eyes"""
        try:
            return (self.eye_left.area + self.eye_right.area)/2
        except Exception:
            return None
        
    def get_LR_eye_area(self):
        """Returns the  areas of the baby's right and left eyes"""
        try:
            return self.eye_left.area, self.eye_right.area
        except Exception:
            return None

    def get_eye_area_ratio(self):
        """Returns the ratio of the baby's right and left eye areas"""
        try:
            return self.eye_left.area / self.eye_right.area
        except Exception:
            return None

    def xy_gaze_position(self):
        """Returns values reflecting the average horizontal  
        and vertical direction of the pupils. The extreme
        values are determined during calibration or are
        set to average values imputed from prior videos
        """
        if not self.pupils_located:
            return None, None, None, None
            
        xleft = self.eye_left.pupil.x / self.eye_left.width
        xright = self.eye_right.pupil.x / self.eye_right.width
        xavg = (xleft + xright)/2

        yleft = self.eye_left.pupil.y / self.eye_left.inner_y
        yright = self.eye_right.pupil.y / self.eye_right.inner_y
        yavg_unscaled = (yleft + yright)/2

        scale = self.eye_scale / self.eye_ratio()
        yavg = yavg_unscaled * scale

        return xavg, yavg, yleft, yright

    def horizontal_gaze_scaled(self):
        """Returns a value reflecting the horizontal 
        gaze direction. This is calcuated by integrating 
        the pupil position with the degree that the head 
        is rotated, estimated by the eye area ratio
        """
        if not self.pupils_located:
            return None

        left, right = self.horizontal_gaze()
        area_ratio = (self.eye_left.area / self.eye_right.area) / self.leftright_eyeratio
        scaled_avg = ((left + right)/2)*area_ratio
        return scaled_avg

    def horizontal_gaze(self):
        """Returns values reflecting the horizontal direction
        of the left and right pupils. The extreme values are 
        determined during calibration or are set to average 
        values imputed from prior videos.
        """
        if not self.pupils_located:
            return None, None

        pupil_left = self.eye_left.pupil.x / self.eye_left.width
        pupil_right = self.eye_right.pupil.x / self.eye_right.width
        return pupil_left, pupil_right

    def is_blinking(self):
        """Returns true if the current blinking ratio is greater than 
        the threshold set during calibration
        """
        if not self.pupils_located:
            return None

        blinking_ratio = self.eye_ratio()
        return blinking_ratio > self.blink_thresh or blinking_ratio < self.blink_thresh2
        
    def eye_ratio(self):
        """Returns the average width/height (blinking ratio) of left/right eyes"""
        return (self.eye_left.blinking + self.eye_right.blinking)/2 if self.pupils_located else 1

    def annotated_frame(self):
        """Returns the frame with pupils highlighted"""
        frame = self.frame.copy()
        if not self.pupils_located:
            return frame

        color = (255, 255, 0)
        left_coords, r_left = self.pupil_coords('left')
        right_coords, r_right = self.pupil_coords('right')
        for coords in [left_coords, right_coords]:
            cv2.circle(frame, coords, 3, color, 1)

        return frame
