import os

import pandas as pd

import settings
from .base_xy_handler import EyetrackingHandler
from .owlet_slim.owlet import OWLET


class OWLETHandler(EyetrackingHandler):

    LEFT_AOI = {'TOP_LEFT': (0, settings.STIMULUS_HEIGHT*0.34),
                'BOTTOM_RIGHT': (settings.STIMULUS_WIDTH*0.45, settings.STIMULUS_HEIGHT)}

    RIGHT_AOI = {'TOP_LEFT': (settings.STIMULUS_WIDTH*0.55, settings.STIMULUS_HEIGHT*0.34),
                 'BOTTOM_RIGHT': (settings.STIMULUS_WIDTH, settings.STIMULUS_HEIGHT)}

    def __init__(self, name, participants, dot_color, calibrate=True):
        super().__init__(name, participants, dot_color)

        self.calibrate = calibrate
        self.raw_dir = os.path.join(self.render_dir, 'raw_results')

    def _xy_to_aoi_vec(self, xv, yv):

        def check_aoi(aoi, x, y):
            return (aoi['TOP_LEFT'][0] <= x <= aoi['BOTTOM_RIGHT'][0] and
                    (aoi['TOP_LEFT'][1] <= y <= aoi['BOTTOM_RIGHT'][1]))

        def xy_to_aoi(x, y):
            if check_aoi(self.LEFT_AOI, x, y):
                return 'left'
            elif check_aoi(self.RIGHT_AOI, x, y):
                return 'right'

            return 'none'

        return [xy_to_aoi(x, y) for x, y in zip(xv, yv)]

    def _translate_coordinates_df(self, row):

        x, y, outside = self._translate_coordinates(settings.STIMULUS_ASPECT_RATIO,
                                                    row['window_height'],
                                                    row['window_width'],
                                                    settings.STIMULUS_HEIGHT,
                                                    settings.STIMULUS_WIDTH,
                                                    row["x"],
                                                    row["y"]
                                                    )

        return pd.Series(dict(zip(['t', 'x', 'y', 'outside', 'calibration_failure'],
                                  [row['t'], x, y, outside, row['calibration_failure']])))

    def preprocess(self):
        if not os.path.exists(self.raw_dir):
            os.makedirs(self.raw_dir)

        for p in self.participants:
            owlet = None
            for s in settings.videos_relevant:

                input_file = f'{settings.WEBCAM_MP4_DIR}/{p}_{s}.mp4'
                output_file_data = f'{self.raw_dir}/{p}_{s}.csv'
                if os.path.isfile(input_file) and not os.path.isfile(output_file_data):

                    if owlet is None:
                        owlet = OWLET(settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT)
                        if self.calibrate:
                            calibration_file = f'{settings.WEBCAM_MP4_DIR}/{p}_calibration.mp4'
                            if not os.path.isfile(calibration_file):
                                print(f'No calibration file found for {p}, skipping')
                                break
                            print(f'Calibrating {p}')
                            owlet.calibrate_gaze(calibration_file, show_output=False)

                    print(f'Processing {input_file}')
                    owlet.process_video(input_file, output_file_data)

        df_list = []
        for p in self.participants:
            for s in settings.videos_relevant:
                data_file = f'{self.raw_dir}/{p}_{s}.csv'
                if not os.path.isfile(data_file):
                    continue

                data = pd.read_csv(data_file)
                if not self.calibrate:
                    data['calibration_failure'] = False
                data = data.apply(self._translate_coordinates_df, axis=1)

                data['id'] = p
                data['stimulus'] = s
                data['trial'] = settings.trial_order_indices[p.split("_")[-1]][s]

                data['side'] = [None if x is None else ('left' if x < settings.STIMULUS_WIDTH / 2.0 else 'right') for x in data['x']]
                df_list.append(data)

        self.data = pd.concat(df_list)\
            .sort_values(['id', 'trial', 't']) \
            .reset_index(drop=True)

        self.data['aoi'] = self._xy_to_aoi_vec(self.data['x'], self.data['y'])
        self.data['aoi_hit'] = self._side_to_hit(self.data['stimulus'], self.data['aoi'])  # target vs distractor
        self.data['side_hit'] = self._side_to_hit(self.data['stimulus'], self.data['side'])  # target vs distractor

        self.backfill_cols += ['trial']
