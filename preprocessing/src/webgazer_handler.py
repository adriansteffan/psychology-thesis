import os
import json

import pandas as pd

import settings
from .base_xy_handler import EyetrackingHandler


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

                    df_dict['side'] = 'left' if x_stim < settings.STIMULUS_WIDTH / 2.0 else 'right'

                    df_dict_list.append(dict(df_dict))

        self.data = pd.DataFrame(df_dict_list)\
            .sort_values(['id', 'trial', 't'])\
            .reset_index(drop=True)

        self.data['aoi_hit'] = self._side_to_hit(self.data['stimulus'], self.data['aoi'])
        self.data['side_hit'] = self._side_to_hit(self.data['stimulus'], self.data['side'])

        self.backfill_cols += ['trial', 'sampling_rate']
