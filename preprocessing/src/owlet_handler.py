import os

import pandas as pd

import settings
from .base_xy_handler import EyetrackingHandler
from .owlet_slim.owlet import OWLET


class OWLETHandler(EyetrackingHandler):

    def __init__(self, name, participants, dot_color, calibrate=True):
        super().__init__(name, participants, dot_color)

        self.calibrate = calibrate
        self.raw_dir = os.path.join(self.render_dir, 'raw_results')

    def _translate_coordinates_df(self, row):  # TODO: Test this with values

        x, y, outside = self._translate_coordinates(settings.STIMULUS_ASPECT_RATIO,
                                                    row['window_height'],
                                                    row['window_width'],
                                                    settings.STIMULUS_HEIGHT,
                                                    settings.STIMULUS_WIDTH,
                                                    row["x"],
                                                    row["y"]
                                                    )

        return pd.Series(dict(zip(['t', 'x', 'y', 'outside'], [row['t'], x, y, outside])))

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
                data = data.apply(self._translate_coordinates_df)

                data['id'] = p
                data['stimulus'] = s
                data['trial'] = settings.trial_order_indices[p.split("_")[-1]][s]

                data['side'] = 'left' if data['x'] < settings.STIMULUS_WIDTH / 2.0 else 'right'
                df_list.append(data)

        self.data = pd.concat(df_list)\
            .sort_values(['id', 'trial', 't']) \
            .reset_index(drop=True)

        # TODO create aoi data here

        #self.data['aoi_hit'] = self._side_to_hit(self.data['stimulus'], self.data['aoi'])
        self.data['side_hit'] = self._side_to_hit(self.data['stimulus'], self.data['side'])

        self.backfill_cols += ['trial']
