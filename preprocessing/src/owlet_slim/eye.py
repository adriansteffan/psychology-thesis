import math
import numpy as np
import cv2


class Pupil(object):
    """
    This class detects the iris of an eye and estimates
    the position of the pupil
    """

    def __init__(self, eye_frame, eyeonly):
        self.iris_frame = None
        self.x = None
        self.y = None
        self.radius = None
        self.eyeonly = eyeonly
        self.detect_iris(eye_frame.copy())

    @staticmethod
    def get_color(eye_frame):
        """Detects the average color of the non-white portions of the
        eye frame, which is used to estimate the threshold.

        Arguments:
            eye_frame (numpy.ndarray): Frame containing an eye and nothing else
        Returns:
            The mean and standard deviation of the eye frame color
        """
        indices = np.where(eye_frame != 255)
        mn, sd = cv2.meanStdDev(eye_frame[indices])
        return mn[0][0], sd[0][0]

    def detect_iris(self, eye_frame):
        """Detects the iris and estimates the position of the pupil by
        calculating the centroid of the iris.

        Arguments:
            eye_frame (numpy.ndarray): Frame containing an eye and nothing else
        """

        try:
            eye_frame1 = cv2.GaussianBlur(eye_frame, (5, 5), 5)
            eye_frame1 = cv2.bilateralFilter(eye_frame1, 10, 15, 15)

            indices = np.where(eye_frame < 127)
            color, sd2 = self.get_color(eye_frame1[indices])

            # threshold can be modified for babies with very dark or light eyes
            threshold = color

            eye_frame2 = cv2.threshold(eye_frame1, threshold, 255, cv2.THRESH_BINARY)[1]

            contours, _ = cv2.findContours(eye_frame2, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            contours = sorted(contours, key=cv2.contourArea, reverse=False)
            hull = cv2.convexHull(contours[-2])
            moments = cv2.moments(hull)

            x = int(moments['m10'] / moments['m00'])
            y = int(moments['m01'] / moments['m00'])

            self.x, self.y, self.radius = x, y, 3

        except:
            self.x = None
            self.y = None
            self.radius = None
            print("cant find pupils")


class Eye(object):
    """
    This class creates a new frame to isolate the eye and
    initiates the pupil detection.
    """

    LEFT_EYE_POINTS = [36, 37, 38, 39, 40, 41]
    RIGHT_EYE_POINTS = [42, 43, 44, 45, 46, 47]
    CHIN_NOSE = [8, 33]
    NOSE = [33, 28]

    def __init__(self, original_frame, landmarks, side, pupilpoint):
        self.frame = None
        self.origin = None
        self.center = None
        self.height = None
        self.width = None
        self.pupil = None
        self.min_x = None
        self.max_x = None
        self.min_y = None
        self.max_y = None
        self.region = None
        self.point = pupilpoint

        self._analyze(original_frame, landmarks, side)

    def _isolate(self, frame, landmarks, points):
        """Isolate an eye, to have a frame without other part of the face.

        Arguments:
            frame (numpy.ndarray): Frame containing the face
            landmarks (dlib.full_object_detection): Facial landmarks for the face region
            points (list): Points of an eye (from the 68 Multi-PIE landmarks)
        """

        region = np.array([(landmarks.part(point).x, landmarks.part(point).y) for point in points])
        region = region.astype(np.int32)
       
        self.region = region
        
        height, width = frame.shape[:2]   
        black_frame = np.zeros((height, width), np.uint8)
        mask = np.full((height, width), 255, np.uint8)
        cv2.fillPoly(mask, [region], (0, 0, 0))
        eye_frame = cv2.bitwise_not(black_frame, frame.copy(), mask=mask)

        margin = 5
        self.min_x = int(np.min(region[:, 0]) - margin)
        self.max_x = int(np.max(region[:, 0]) + margin)
        self.min_y = int(np.min(region[:, 1]) - margin)
        self.max_y = int(np.max(region[:, 1]) + margin)
        
        self.frame = eye_frame[self.min_y:self.max_y, self.min_x:self.max_x]
        height, width = self.frame.shape[:2]
        n_white_pix = np.sum(self.frame == 255)
        self.area = (height*width) - n_white_pix
        
        self.origin = (self.min_x, self.min_y)
        x = math.floor(width/2)
        y = math.floor(height/2)
        self.center = (x, y)

        height, width = self.frame.shape[:2]
        x = math.floor(width/2)
        y = math.floor(height/2)
        self.center = (x, y)

    def _blinking_ratio(self, landmarks, side):
        """Calculates the ratio between the width and height of the eye frame,
        shich can be used to determine whether the eye is closed or open.
        It's the division of the width of the eye, by its height.

        Arguments:
            landmarks (dlib.full_object_detection): Facial landmarks for the face region
            side: indicates eye

        Returns:
            The computed ratio
        """

        ep = self.LEFT_EYE_POINTS if side == 0 else (self.RIGHT_EYE_POINTS if side == 1 else None)
        inner = ep[3] if side == 0 else (ep[0] if side == 1 else None)

        try:
            self.width = math.dist((landmarks.part(ep[0]).x, landmarks.part(ep[0]).y),
                                   (landmarks.part(ep[3]).x, landmarks.part(ep[3]).y))

            a = math.dist((landmarks.part(ep[2]).x, landmarks.part(ep[2]).y),
                          (landmarks.part(ep[4]).x, landmarks.part(ep[4]).y))

            b = math.dist((landmarks.part(ep[1]).x, landmarks.part(ep[1]).y),
                          (landmarks.part(ep[5]).x, landmarks.part(ep[5]).y))

            ratio = (2.0 * self.width) / (a + b)
            self.height = (a + b) / 2
            self.inner_y = landmarks.part(inner).y
            self.inner_x = landmarks.part(inner).x

        except Exception:
            ratio = None

        return ratio

    def _analyze(self, original_frame, landmarks, side):
        """Isolates the eye in a new frame and initializes Pupil object.

        Arguments:
            original_frame (numpy.ndarray): Frame passed by the user
            landmarks (dlib.full_object_detection): Facial landmarks for the face region
            side: Indicates whether it's the left eye (0) or the right eye (1)
        """
        if side not in [0, 1]:
            return
        points = self.LEFT_EYE_POINTS if side == 0 else (self.RIGHT_EYE_POINTS if side == 1 else None)

        self.blinking = self._blinking_ratio(landmarks, side)
        self._isolate(original_frame, landmarks, points)
        self.pupil = Pupil(self.frame, eyeonly=False)
