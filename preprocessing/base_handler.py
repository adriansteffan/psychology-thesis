import os
import cv2
import subprocess
import shutil
import pandas as pd

import settings


class EyetrackingHandler:

    def __init__(self, name, participants):
        self.data = None
        self.data_filtered = None
        self.data_resampled = None
        self.backfill_cols = []

        self.name = name
        self.participants = participants
        self.render_dir = os.path.join(settings.RENDERS_DIR, self.name)

    def run(self, should_render):
        self.preprocess()
        self._filter_data()
        self._resample_data()
        self._save_data()

        if should_render:
            for s in settings.stimuli:
                for p in self.participants:
                    self.render(p, s)
                self.render_joint(s)

    def preprocess(self):
        pass

    def _filter_data(self):
        self.data_filtered = self.data  # TODO 1. add marker (excluded, reason) to data, 2. filter according to data in data_filtered

    def _resample_data(self, backfill_cols=None):
        if backfill_cols is None:
            backfill_cols = ['trial']

        # use the max trial duration for all stimuli to simplify temp_df creation -> delete the nonsensical rows in the next step
        tmp_df = pd.DataFrame({'t': range(0, int(max(settings.presentation_duration.values())*1000 + 1), int(1000/settings.RESAMPLING_RATE)), 'new': True})\
            .merge(pd.DataFrame({'id': self.data['id'].unique()}), how='cross')\
            .merge(pd.DataFrame({'stimulus': self.data['stimulus'].unique()}), how='cross')

        tmp_df['max_timestamp'] = [settings.presentation_duration[stim]*1000 for stim in tmp_df['stimulus']]
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
        self.data.to_csv(f'{settings.OUT_DIR}/{self.name}_data.csv', encoding='utf-8')
        self.data_resampled.to_csv(f'{settings.OUT_DIR}/{self.name}_RESAMPLED_data.csv', encoding='utf-8')

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

    def render(self, participant, stimulus):
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
            cv2.waitKey(int(1000 / int(fps)))
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

    def render_joint(self, stimulus):
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
            cv2.waitKey(int(1000 / int(fps)))
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
        targets = ['none' if s not in settings.target_aoi_location.keys() else settings.target_aoi_location[s] for s in stimuli]
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
