# Thesis Project about Automatic Webcam-based Gaze-Coders or something 

This repository contains the code for my bachelor's thesis at LMU's Chair of Clinical Psychology in Childhood and Adolescence (Lehr- und Forschungseinheit Klinische Psychologie des Kindes- und Jugendalters & Beratungspsychologie). The thesis aims to validate and compare currently available open-source approaches to automatic gaze-coding and eye-tracking in infant research.

The code in this repository offers more streamlined preprocessing on the data created by [MB-ManyWebcams](https://github.com/adriansteffan/manywebcams-eyetracking) and analyzes the captured webcam footage with both [ICatcher+](https://github.com/erelyotam/icatcher_plus) and [OWLET](https://github.com/denisemw/OWLET).

<!--The raw webcam data was collected during a spinoff of [ManyBabies](https://manybabies.org/). 
While we cannot share the original webcam footage due to privacy concerns, the results of the preprocessing can be found in the `output` folder.-->

## Prerequisites

To get a local copy of this software up and running, clone this repository first:

   ```sh
   git clone https://github.com/adriansteffan/psychology-thesis.git
   cd psychology-thesis
   ```

### Preprocessing


To run the preprocessing script, you will need an [ffmpeg](https://www.ffmpeg.org/) installation and [Python3.9](https://www.python.org/downloads/) or newer. You will also need to install [cmake](https://cmake.org/install/) and add it to your PATH.


From the root directory, change into the `preprocessing` directory:

```sh
cd preprocessing
```

It is highly recommended to create a virtual environment when running the program.
To do so, run

```sh
python3.9 -m venv venv
```

To activate the virtual environment before running the script, run

```sh
source venv/bin/activate
```

Before running the program, run the following command inside the virtual environment to install the necessary dependencies:

```sh
pip3.9 install -r requirements.txt
``` 

Create a directory for your data and move it there (the script expects the data to be in a format created by [manywebcams](https://github.com/adriansteffan/manywebcams-eyetracking) repository)

```sh
mkdir data
``` 

## Usage - Preprocessing - Information below does not reflect current functionality, exclusions are WIP 

If you want to analyze the eye-tracking data in a research environment, it is encouraged to follow option A) to ensure that participant exclusions are handled correctly. Doing so will reduce redundant rendering of excluded participants and result in combined plots (e.g. beeswarm) that only reflect the included sample.



### A) Running the pipeline step by step

To create the exclusion files step by step, you will need to do the following:

After placing your data in `preprocessing/data`, run:

```
python3.9 main.py --step 1
```

What the program did:
* Transform all participant's .webm videos to .mp4 videos with a framerate of TARGET_FPS from `preprocessing/settings.py` - padded to the length of stimulus presentation. These are saved at `preprocessing/output/webcam_mp4/`
* Create an empty exclusion file at `preprocessing/exclusion/_exclusions_general.csv` for all participant + stimulus combinations

What you need to do:

* Go through the exclusion file line by line, watch the relevant mp4 webcam video and decide if the trial(as defined by participant + stimulus) fits your inclusion criteria. If you have external criteria (e.g. age requirements), it could also make sense to exclude the participant here in order to reduce the renders in the following step.

* Put an `x` in the `excluded` columns if the participant should be excluded; otherwise, put an `i`. You can populate the `exclusion_reason` column if you wish to perform a breakdown of exclusion criteria in your analysis of the data output.
* If participants appear that should not be included and should not pollute the exclusion statistics (e.g. test videos performed by researchers), remove the lines from the csv. The following steps will only consider the participants and stimuli that appear in the file.

Once you are done with the `preprocessing/exclusion/_exclusions_general.csv` file, save it and run

```
python3.9 main.py --step 2
```

What the program did:
* Render tracker-specific videos for all participants, overlaying stimulus footage, webcam video and tracker-specific information (e.g. gaze dots). The videos can be found at `preprocessing/output/renders/{tracker_name}/{participant_id}/{stimulus_name}.mp4` and only include trials (participant + stimulus) that were not excluded in the previous step. 
* Create tracker-specific exclusion files. They can be found at `preprocessing/exclusion/exclusion_{tracker_name}.csv` and only include trials (participant + stimulus) that were not excluded in the previous step. These already include prefilled tracker-specific exclusions (e.g. low webgazer sampling rate, no face found, calibration failed).


What you need to do:
* For every tracker:
    * Go through the exclusion file line by line, watch the relevant rendered video and decide if the tracking performance of a trial(participant + stimulus) fits your inclusion criteria. "Tracking Quality" can be subjective, you if you are unsure about your rating here, it is recommended to get a second rater or skip this step entirely.

    * Put an x in the excluded columns if the participant should be excluded; otherwise, put an i. You can populate the exclusion_reason column if you wish to perform a breakdown of exclusion criteria in your analysis of the data output.
    `low_tracking_quality` is prefilled for open cases, but you can replace the reason if you wish.

Once you have updated and saved all exclusion files, run

```
python3.9 main.py --step 3
```

What the program did:
* Render a combined video for every (tracker + stimulus) combination, showing the tracker performance of the entire sample for a given stimulus (e.g. beeswarm plots). These can be found at `preprocessing/output/renders/{eyetracker_name}/{stimulus_name}_all.mp4`
* Export all preprocessed eye-tracking data to `preprocessing/output/{tracker_name}_data.csv` and `preprocessing/output/{tracker_name}_RESAMPLED_data.csv`


Note that the excluded participants still show up in the final data export, being tagged with the columns `excluded` and `exclusion_reason`. This approach enables a detailed analysis of exclusions later while still making it easy to clean up the data with a single filter function.

### B) Running the entire pipeline at once

If you already have created the exclusion files, just want to test the system or do not care about exclusions, you can run the entire pipeline by executing:

```
python3.9 main.py
```

in the `preprocessing` directory. The output of this operation is dependent on the existence of the exclusion files:

* Exclusion files do not exist: 
    * All eye-tracker outputs will be rendered onto stimuli videos
    * The combined renders include *all* participants
    * The final exports only include tracker-generated exclusion criteria
* Exclusion files exist:
    * The exact same output of the step-by-step process.




### Analysis

TBD

## Built with

### OWLET
This repository distributes a modified version of [OWLET](https://github.com/denisemw/OWLET), originally developed and released by Denise Werchan. Details on the system can be found in the accompanying publication:

Werchan, D. M., Thomason, M. E., & Brito, N. H. (2022). OWLET: An Automated, Open-Source Method for Infant Gaze Tracking using Smartphone and Webcam Recordings. Behavior Research Methods.

The modified files can be found in [preprocessing/src/owlet_slim](preprocessing/src/owlet_slim) and were trimmed down to the functionality needed for this project and extended to fit into our workflow. No changes to the original eye-tracking algorithm were made.

### ICatcher+
This project leverages [ICatcher+](https://github.com/erelyotam/icatcher_plus), as described in the following publication:

Erel, Y., Shannon, K. A., Chu, J., Scott, K., Struhl, M. K., Cao, P., Tan, X., Hart, P., Raz, G., Piccolo, S., Mei, C., Potter, C., Jaffe-Dax, S., Lew-Williams, C., Tenenbaum, J., Fairchild, K., Bermano, A., & Liu, S. (2023). iCatcher+: Robust and Automated Annotation of Infants’ and Young Children’s Gaze Behavior From Videos Collected in Laboratory, Field, and Online Studies. Advances in Methods and Practices in Psychological Science.



## License

This project is licensed under the [GNU GPLv3](LICENSE.md) - see the [LICENSE.md](LICENSE.md) file for
details

## Contact

- **Adrian Steffan** [adriansteffan](https://github.com/adriansteffan) [website](https://adriansteffan.com/)

