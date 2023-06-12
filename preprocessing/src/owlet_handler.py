import os
import subprocess

import pandas as pd

import settings
from .base_xy_handler import EyetrackingHandler
from .owlet_slim.owlet import OWLET


class OWLETHandler(EyetrackingHandler):

    LEFT_AOI = {'TOP_LEFT': (0, settings.STIMULI['FAM_LL']['height']*0.34),
                'BOTTOM_RIGHT': (settings.STIMULI['FAM_LL']['width']*0.45, settings.STIMULI['FAM_LL']['height'])}

    RIGHT_AOI = {'TOP_LEFT': (settings.STIMULI['FAM_LL']['width']*0.55, settings.STIMULI['FAM_LL']['height']*0.34),
                 'BOTTOM_RIGHT': (settings.STIMULI['FAM_LL']['width'], settings.STIMULI['FAM_LL']['height'])}

    def __init__(self, name, participants, general_exclusions, dot_color, calibrate=True):
        super().__init__(name, participants, general_exclusions,  dot_color)

        self.calibrate = calibrate
        self.raw_dir = os.path.join(self.render_dir, 'raw_results')

    def _get_exclusion_functions(self):
        parent_functions = super()._get_exclusion_functions()

        # TODO no screen size data present

        owlet_exclusion_functions = []
        if self.calibrate:
            def exclude_no_calib(data):
                return self.general_exclusions[(self.general_exclusions['excluded'] == 'x') & (self.general_exclusions['stimulus'] == 'calibration')][
                    ['id']].drop_duplicates(keep='first').reset_index(drop=True).merge(pd.DataFrame({'stimulus': list(set(settings.stimuli) - set(settings.STIMULUS_BLACKLIST[self.name]))}), how='cross')

            def exclude_calib_failed(data):
                exclude_tracking = data[data['calibration_failure']][
                    ['id', 'stimulus']].drop_duplicates(keep='first').reset_index(drop=True)
                return exclude_tracking

            owlet_exclusion_functions += [(exclude_no_calib, '_no_calib_owlet'), (exclude_calib_failed, '_calib_failed_ow')]

        return parent_functions + owlet_exclusion_functions

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

        x, y, outside = self._translate_coordinates(settings.STIMULI[row['stimulus']]['width'] / settings.STIMULI[row['stimulus']]['height'],
                                                    row['window_height'],
                                                    row['window_width'],
                                                    settings.STIMULI[row['stimulus']]['height'],
                                                    settings.STIMULI[row['stimulus']]['width'],
                                                    row["x"],
                                                    row["y"]
                                                    )

        return pd.Series(dict(zip(['t', 'x', 'y', 'outside', 'calibration_failure', 'stimulus'],
                                  [row['t'], x, y, outside, row['calibration_failure'], row['stimulus']])))

    def _preprocess(self):

        # Prepare videos by cropping webcam videos to owlets preferred
        if not os.path.exists(settings.CROPPED_WEBCAM_MP4_DIR):
            os.makedirs(settings.CROPPED_WEBCAM_MP4_DIR)

        if settings.RENDER_WEBCAM_VIDEOS_16_9:
            for p in self.participants:
                for s in settings.stimuli:
                    webcam_path = f'{settings.WEBCAM_MP4_DIR}/{p}_{s}.mp4'
                    cropped_webcam_path = f'{settings.CROPPED_WEBCAM_MP4_DIR}/{p}_{s}.mp4'
                    if os.path.isfile(webcam_path) and not os.path.isfile(cropped_webcam_path):
                        subprocess.Popen(['ffmpeg', '-y',
                                          '-i', webcam_path,
                                          '-filter:v',
                                          'crop=iw:9*iw/16',
                                          cropped_webcam_path,
                                          ]).wait()

        if not os.path.exists(self.raw_dir):
            os.makedirs(self.raw_dir)

        for p in self.participants:
            owlet = None
            for s in settings.stimuli:

                if not self._should_process_trial(p, s):
                    continue

                input_file = f'{settings.CROPPED_WEBCAM_MP4_DIR}/{p}_{s}.mp4'
                output_file_data = f'{self.raw_dir}/{p}_{s}.csv'
                if os.path.isfile(input_file) and not os.path.isfile(output_file_data):

                    if owlet is None:
                        owlet = OWLET(settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT)
                        if self.calibrate:
                            calibration_file = f'{settings.CROPPED_WEBCAM_MP4_DIR}/{p}_calibration.mp4'
                            if not os.path.isfile(calibration_file):
                                print(f'No calibration file found for {p}, skipping')
                                break
                            print(f'Calibrating {p}')
                            owlet.calibrate_gaze(calibration_file, show_output=False)

                    print(f'Processing {input_file}')
                    owlet.process_video(input_file, output_file_data)

        df_list = []
        for p in self.participants:
            for s in settings.stimuli:
                data_file = f'{self.raw_dir}/{p}_{s}.csv'
                if not os.path.isfile(data_file):
                    continue

                data = pd.read_csv(data_file)
                if not self.calibrate:
                    data['calibration_failure'] = False
                data['stimulus'] = s
                data['window_height'] = 540
                data['window_width'] = 960
                data = data.apply(self._translate_coordinates_df, axis=1)

                data['id'] = p
                data['trial'] = settings.STIMULI[s][f'{p.split("_")[-1]}_index']

                data['side'] = [None if x is None else ('left' if x < settings.STIMULI[s]['width'] / 2.0 else 'right') for x in data['x']]
                df_list.append(data)

        self.data = pd.concat(df_list)\
            .sort_values(['id', 'trial', 't']) \
            .reset_index(drop=True)

        self.data['aoi'] = self._xy_to_aoi_vec(self.data['x'], self.data['y'])
        self.data['aoi_hit'] = self._side_to_hit(self.data['stimulus'], self.data['aoi'])  # target vs distractor
        self.data['side_hit'] = self._side_to_hit(self.data['stimulus'], self.data['side'])  # target vs distractor

        self.backfill_cols += ['trial']
