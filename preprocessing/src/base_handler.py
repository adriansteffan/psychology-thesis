import os
import cv2
import subprocess
import shutil
import pandas as pd

import settings
from . import utils


class GazecodingHandler:

    def __init__(self, name, participants, general_exclusions=None):
        self.data = None
        self.data_resampled = None
        self.backfill_cols = []

        self.name = name
        self.participants = participants
        self.general_exclusions = general_exclusions
        self.specific_exclusions_path = os.path.join(settings.EXCLUSION_DIR,
                                                                      f'exclusions_{self.name}.csv')
        self.render_dir = os.path.join(settings.RENDERS_DIR, self.name)

        self.stimulus_blacklist = settings.STIMULUS_BLACKLIST[self.name] if self.name in settings.STIMULUS_BLACKLIST else []

    def run(self, step, should_render):
        if step and step not in [2, 3]:
            exit("Invalid step provided to GazecodingHandler")

        if self.general_exclusions is None:
            self.general_exclusions = utils.create_empty_general_exclusion_df(self.participants)

        self._preprocess()

        if not step or step == 2:
            if os.path.isfile(self.specific_exclusions_path):
                # already there, do nothing if you are doing a full run, abort if you are on step 2
                if step == 2:
                    exit(f'Specific exclusion file  at {self.specific_exclusions_path} already exists. '
                         f'To make sure that you are not accidentally overwriting it, please remove it first.')
                specific_exclusions = pd.read_csv(self.specific_exclusions_path)
                utils.validate_exclusions(specific_exclusions, self.specific_exclusions_path, strict=step)
            else:
                specific_exclusions = self.general_exclusions[(self.general_exclusions['excluded'] != 'x') & (~self.general_exclusions['stimulus'].isin(self.stimulus_blacklist))].reset_index(drop=True)
                specific_exclusions['excluded'] = ''
                specific_exclusions['exclusion_reason'] = ''

                specific_exclusions = self._automatically_exclude_specific(specific_exclusions)
                specific_exclusions.to_csv(self.specific_exclusions_path, encoding='utf-8', index=False)

            if should_render:
                # Only render trials that were not excluded generally or automatically
                included_so_far = specific_exclusions[specific_exclusions['excluded'] != 'x']
                for _, row in included_so_far.iterrows():
                    if row['stimulus'] in self.stimulus_blacklist:
                        continue
                    #self._render(row['id'], row['stimulus'])

        if not step or step == 3:

            self._filter_data(step)
            self._resample_data()

            if should_render:
                for s in settings.stimuli:
                    if s in self.stimulus_blacklist:
                        continue
                    self._render_joint(s)

            self._save_data()

    def _should_process_trial(self, participant, stimulus):
        return self.general_exclusions[(self.general_exclusions['id'] == participant) & (self.general_exclusions['stimulus'] == stimulus)]['excluded'].iloc[0] != 'x' and stimulus not in self.stimulus_blacklist

    def _preprocess(self):
        pass

    def _get_exclusion_functions(self):
        return []

    def _automatically_exclude_specific(self, general_exclusions):

        # tag all participants that are missing in the eyetracking data of the given tracker (dont appear in the data)
        in_data = self.data[['id', 'stimulus']].drop_duplicates(keep='first').reset_index(drop=True)
        in_exclusion = general_exclusions[['id', 'stimulus']].drop_duplicates(keep='first').reset_index(drop=True)
        nodata_table = pd.merge(in_exclusion, in_data, indicator=True, how='outer').query('_merge=="left_only"').drop('_merge', axis=1)
        nodata_table['excluded'] = 'x'
        nodata_table['exclusion_reason'] = '_no_tracker_data'

        exclusion_tables = [nodata_table]

        for fun, reason in self._get_exclusion_functions():
            excl_table = fun(self.data)
            excl_table['excluded'] = 'x'
            excl_table['exclusion_reason'] = reason
            exclusion_tables.append(excl_table)

        return pd.concat(exclusion_tables + [general_exclusions]).drop_duplicates(subset=['id', 'stimulus'],
                                                                      keep="first").reset_index(drop=True)

    def _filter_data(self, step):
        specific_exclusions = pd.read_csv(self.specific_exclusions_path)
        utils.validate_exclusions(specific_exclusions, self.specific_exclusions_path, strict=step and step == 3)
        exclusions_all = pd.concat([specific_exclusions, self.general_exclusions])
        excluded = exclusions_all[(exclusions_all['excluded'] == 'x') & (~exclusions_all['stimulus'].isin(self.stimulus_blacklist))].reset_index(drop=True)
        self.data = pd.merge(self.data, excluded, on=['id', 'stimulus'], how='outer')
        self.data = self.data[self.data['excluded'] != 'x']\
            .drop(['excluded', 'exclusion_reason'], axis=1)\
            .reset_index(drop=True)

    def _resample_data(self, backfill_cols=None):
        if backfill_cols is None:
            backfill_cols = ['trial']

        # use the max trial duration for all stimuli to simplify temp_df creation -> delete the nonsensical rows in the next step
        max_duration_seconds = max([stim['presentation_duration'] for key, stim in settings.STIMULI.items()])
        tmp_df = pd.DataFrame({'t': range(0, int(max_duration_seconds * 1000 + 1), int(1000 / settings.RESAMPLING_RATE)), 'new': True})\
            .merge(self.data[['id', 'stimulus']].drop_duplicates(keep='first').reset_index(drop=True), how='cross')

        tmp_df['max_timestamp'] = [settings.STIMULI[stim]['presentation_duration'] * 1000 for stim in tmp_df['stimulus']]
        tmp_df = tmp_df[tmp_df['t'] <= tmp_df['max_timestamp']]\
            .drop('max_timestamp', axis=1)\
            .reset_index(drop=True)

        self.data_resampled = self.data.copy()
        self.data_resampled['new'] = False
        self.data_resampled = pd.concat([self.data_resampled, tmp_df])\
            .sort_values(['t', 'new'], ascending=[True, True])\
            .groupby(['id', 'stimulus'], as_index=False)\
            .apply(lambda x: x.fillna(method="ffill"))\
            .query('new == True')\
            .drop('new', axis=1)\
            .sort_values(['id', 'stimulus', 't'])\
            .reset_index(drop=True)

        self.data_resampled.loc[:, backfill_cols] = self.data_resampled.loc[:, backfill_cols].bfill()
        self.data_resampled = self.data_resampled.sort_values(['id', 'trial', 't']).reset_index(drop=True)

    def _save_data(self):
        self.data.to_csv(f'{settings.OUT_DIR}/{self.name}_data.csv', encoding='utf-8', index=False)
        self.data_resampled.to_csv(f'{settings.OUT_DIR}/{self.name}_RESAMPLED_data.csv', encoding='utf-8', index=False)

    def _render_pre_loop(self, input_path, output_path, participant, stimulus):
        """
        Whatever needs to be done before the main rendering loop runs, rendering the data on the data
        """
        shutil.copy(input_path, output_path)

    def _render_frame(self, frame, index, data):
        pass

    def _render_post_loop(self, input_path, output_path, participant, stimulus):
        """
        Whatever needs to be done after the main rendering loop runs, rendering the data on the data
        """
        shutil.copy(input_path, output_path)

    def _render(self, participant, stimulus):
        d = self.data[(self.data['id'] == participant) & (self.data['stimulus'] == stimulus)]
        d.reset_index(drop=True, inplace=True)

        if len(d.index) == 0:
            return

        if not os.path.exists(self.render_dir):
            os.makedirs(self.render_dir)

        base_path = f'{self.render_dir}/{participant}'

        if not os.path.exists(base_path):
            os.makedirs(base_path)

        stimulus_file = f'{stimulus}.mp4'
        pre1_path = f'{base_path}/pre1_{stimulus_file}'
        pre2_path = f'{base_path}/pre2_{stimulus_file}'
        final_path = f'{base_path}/{stimulus_file}'

        if os.path.isfile(final_path):
            return
        print(f'Rendering {final_path}...')

        self._render_pre_loop(f'{settings.MEDIA_DIR}/{stimulus_file}', pre1_path, participant, stimulus)

        video, video_writer, fps = self._prepare_cv2_video(pre1_path, pre2_path)
        success, frame = video.read()
        frame_index = 1
        gaze_point_index = 1

        while success:
            if gaze_point_index < len(d.index) - 1 and d['t'][gaze_point_index + 1] <= (frame_index / fps) * 1000:
                gaze_point_index += 1

            self._render_frame(frame, gaze_point_index, d)

            #cv2.imshow("", frame)
            #cv2.waitKey(int(1000 / int(fps)))
            video_writer.write(frame)
            success, frame = video.read()
            frame_index += 1

        video.release()
        video_writer.release()

        self._render_post_loop(pre2_path, final_path, participant, stimulus)

        try:
            os.remove(pre1_path)
        except OSError:
            pass

        try:
            os.remove(pre2_path)
        except OSError:
            pass

    def _render_frame_joint(self, frame, index, data):
        pass

    def _render_joint(self, stimulus):

        if not os.path.exists(self.render_dir):
            os.makedirs(self.render_dir)

        pre_path = f'{self.render_dir}/{stimulus}_all_temp.mp4'
        final_path = f'{self.render_dir}/{stimulus}_all.mp4'

        if os.path.isfile(final_path):
            return

        self._overlay_fc(f'{settings.MEDIA_DIR}/{stimulus}.mp4', pre_path)

        d = self.data_resampled[self.data_resampled['stimulus'] == stimulus]
        d.reset_index(drop=True, inplace=True)

        if len(d.index) == 0:
            return

        video, video_writer, fps = self._prepare_cv2_video(pre_path, final_path)

        success, frame = video.read()
        frame_index = 1
        timestep = 1000 / settings.RESAMPLING_RATE
        t = 0

        while success:

            self._render_frame_joint(frame, t, d)

            #cv2.imshow("", frame)
            #cv2.waitKey(int(1000 / int(fps)))
            video_writer.write(frame)
            success, frame = video.read()

            if t <= (frame_index / fps) * 1000:
                t += timestep
            frame_index += 1

        video.release()
        video_writer.release()
        os.remove(pre_path)

    @staticmethod
    def _side_to_hit(stimuli, sides):

        targets = [settings.STIMULI[s]['target_aoi'] for s in stimuli]
        distractors = ['right' if t == 'left' else ('left' if t == 'right' else 'none') for t in targets]
        return ['target' if s == t else ('distractor' if s == d else 'none') for s, t, d in zip(sides, targets, distractors)]

    @staticmethod
    def _prepare_cv2_video(input_file, dest_file):
        video = cv2.VideoCapture(input_file, )
        fps = video.get(cv2.CAP_PROP_FPS)
        vid_height = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
        vid_width = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))

        video_writer = cv2.VideoWriter(dest_file, cv2.VideoWriter_fourcc('m', 'p', '4', 'v'), fps,
                                       (vid_width, vid_height),
                                       True)
        return video, video_writer, fps

    @staticmethod
    def _overlay_fc(input_path, output_path):
        # add frame counter to video
        subprocess.Popen(['ffmpeg', '-y',
                          '-i', input_path,
                          '-vf',
                          "drawtext=fontfile=Arial.ttf: text='%{frame_num} / %{pts}': start_number=1: x=(w-tw)/2: y=h-lh: fontcolor=black: fontsize=(h/20): box=1: boxcolor=white: boxborderw=5",
                          '-c:a', 'copy', '-c:v', 'libx264', '-crf', '23',
                          output_path,
                          ]).wait()

    @staticmethod
    def _overlay_webcam(input_path, output_path, webcam_path, audio=False):
        if os.path.isfile(webcam_path):
            subprocess.Popen(['ffmpeg', '-y',
                              '-i', input_path,
                              '-i', webcam_path,
                              '-filter_complex',
                              "[1:v]scale=350:-1 [inner];[0:v][inner]overlay=10:10:shortest=0[out]",
                              # [1:v]scale=350:-1,hflip take out the flip for now - especially for icatcher
                              '-map', '[out]'] + (['-map', '1:a'] if audio else []) + [output_path]
                            ).wait()

        else:
            shutil.copy(input_path, output_path)
