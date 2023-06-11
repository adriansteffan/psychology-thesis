import os
import json

import pandas as pd

import settings
from .base_xy_handler import EyetrackingHandler


class WebGazerHandler(EyetrackingHandler):

    def __init__(self, name, participants, general_exclusions, dot_color):
        super().__init__(name, participants, general_exclusions, dot_color)
        self.data_validation = None

    def _get_exclusion_functions(self):
        parent_functions = super()._get_exclusion_functions()

        def exclude_no_tracking_data(data):
            exclude_tracking = data[data.apply(lambda r: not os.path.isfile(f'{settings.DATA_DIR}/{r["id"]}_data.json'), axis=1)][
                ['id', 'stimulus']].drop_duplicates(keep='first').reset_index(drop=True)
            return exclude_tracking

        def exclude_samplingrate(data):
            exclude_sampling = data[data['sampling_rate'] < settings.WEBGAZER_SAMPLING_CUTOFF][
                ['id', 'stimulus']].drop_duplicates(keep='first').reset_index(drop=True)
            return exclude_sampling

        return parent_functions + [(exclude_no_tracking_data, '_no_tracking_data_wg'), (exclude_samplingrate, '_low_sampling_wg')]

    def _preprocess(self):
        df_dict_list = []
        df_dict_list_validation = []
        for p in self.participants:

            data_file = f'{settings.DATA_DIR}/{p}_data.json'
            if not os.path.isfile(data_file):
                continue

            with open(data_file) as f:
                data = json.load(f)

            self._append_validation_data(df_dict_list_validation, data, p)

            data = [x for x in data if 'task' in x and x['task'] == 'video']

            p_out_dir = f'{settings.DATA_DIR}/{p}'
            if not os.path.exists(p_out_dir):
                os.makedirs(p_out_dir)

            df_dict = dict()
            df_dict['id'] = p

            for index, trial in enumerate(data):

                df_dict['trial'] = index + 1
                df_dict['stimulus'] = trial['stimulus'][0].split("/")[-1].split(".")[0]

                if not self._should_process_trial(p, df_dict['stimulus']):
                    continue

                # calculate sampling rate
                datapoints = trial['webgazer_data']
                sampling_diffs = [datapoints[i + 1]['t'] - datapoints[i]['t'] for i in range(1, len(datapoints) - 1)]
                sampling_rates = [1000 / diff for diff in sampling_diffs]

                df_dict['sampling_rate'] = sum(sampling_rates) / len(sampling_rates)

                for datapoint in datapoints:

                    df_dict['t'] = datapoint["t"]
                    x_stim, y_stim, outside = self._translate_coordinates(settings.STIMULI[df_dict['stimulus']]['width'] / settings.STIMULI[df_dict['stimulus']]['height'],
                                                                          trial['windowHeight'],
                                                                          trial['windowWidth'],
                                                                          settings.STIMULI[df_dict['stimulus']]['height'],
                                                                          settings.STIMULI[df_dict['stimulus']]['width'],
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

                    df_dict['side'] = 'left' if x_stim < settings.STIMULI[df_dict['stimulus']]['width'] / 2.0 else 'right'

                    df_dict_list.append(dict(df_dict))

        self.data_validation = pd.DataFrame(df_dict_list_validation)\
            .sort_values(['id', 'index'])\
            .reset_index(drop=True)

        self.data = pd.DataFrame(df_dict_list)\
            .sort_values(['id', 'trial', 't'])\
            .reset_index(drop=True)

        self.data['aoi_hit'] = self._side_to_hit(self.data['stimulus'], self.data['aoi'])
        self.data['side_hit'] = self._side_to_hit(self.data['stimulus'], self.data['side'])

        self.backfill_cols += ['trial', 'sampling_rate']

    def _save_data(self):
        super(WebGazerHandler, self)._save_data()
        self.data_validation.to_csv(f'{settings.OUT_DIR}/{self.name}_validation.csv', encoding='utf-8', index=False)

    @staticmethod
    def _append_validation_data(df_dict_list, data, participant):
        # a hacky addition to allow for simple analysis of jspsych webgazer validation trials

        data_validation = [x for x in data if 'trial_type' in x and x['trial_type'] == 'webgazer-validate']

        # hacky way to get the window height and width, as the validation data does not contain that information
        first_trial = [x for x in data if 'task' in x and x['task'] == 'video'][0]

        df_dict = dict()
        df_dict['id'] = participant
        for index, validation_trial in enumerate(data_validation):

            df_dict['index'] = index
            df_dict['avg_offset_x'] = validation_trial['average_offset'][0]['x']
            df_dict['avg_offset_y'] = validation_trial['average_offset'][0]['y']
            df_dict['mean_distance'] = validation_trial['average_offset'][0]['r']
            df_dict['window_width'] = first_trial[
                "windowWidth"]  # assumes height stays constant across trials
            df_dict['window_height'] = first_trial[
                "windowHeight"]  # assumes height stays constant across trials
            df_dict['avg_offset_x_percent'] = df_dict['avg_offset_x'] / df_dict[
                'window_width'] * 100
            df_dict['avg_offset_y_percent'] = df_dict['avg_offset_y'] / df_dict[
                'window_height'] * 100
            df_dict['roi_radius'] = 200  # harcoded for now, as this is not present in the data
            df_dict['gaze_percent_in_roi'] = validation_trial['percent_in_roi'][0]

            df_dict_list.append(dict(df_dict))

