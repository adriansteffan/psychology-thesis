# Thesis Project about Automatic Webcam-based Gaze-Coders or something 

This repository contains the code for my bachelors thesis at LMU's Chair of Clinical Psychology in Childhood and Adolescense (Lehr- und Forschungseinheit Klinische Psychologie des Kindes- und Jugendalters & Beratungspsychologie). The goal of the thesis is to validate and compare currently available open-source approaches to automatic gaze-coding and eye-tracking in infant research.

The code in this repository offers more streamlined preprocessing on the data created by [MB-ManyWebcams](https://github.com/adriansteffan/manywebcams-eyetracking) and analyzes the captured webcam footage with both [ICatcher+](https://github.com/erelyotam/icatcher_plus) and [OWLET](https://github.com/denisemw/OWLET).

<!--The raw webcam data was collected during a spinoff of [ManyBabies](https://manybabies.org/). 
While we cannot share the original webcam footage due to privacy concerns, the results of the preprocessing can be found in the `output` folder.-->

## Getting Started

To get a local copy of this software up and running, first clone this repository:

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

It is higly recommended to create a virtual environment when running the programm.
To do so, run

```sh
python3.9 -m venv venv
```

To activate the virtual environment before running the script, run

```sh
source venv/bin/activate
```

Before running the programming, run the following commnad inside the virtual environment to install the necessary dependencies:

```sh
pip3.9 install -r requirements.txt
``` 

Create a directory for your data and move it there (the script expects the data to be in a format created by [manywebcams](https://github.com/adriansteffan/manywebcams-eyetracking) repository)

```sh
mkdir data
``` 

To execute the program, run 

```sh
python3.9 main.py
```


### Analysis

TBD

## Built with

### OWLET
This repository distributes a modified version of [OWLET](https://github.com/denisemw/OWLET), originally developed and released by Denise Werchan. Details on the system can be found in the accompanying publication:

Werchan, D. M., Thomason, M. E., & Brito, N. H. (2022). OWLET: An Automated, Open-Source Method for Infant Gaze Tracking using Smartphone and Webcam Recordings. Behavior Research Methods.

The modified files can be found in [preprocessing/src/owlet_slim](preprocessing/src/owlet_slim) and were trimmed down to the functionality needed for this project and extended to fit into our workflow. No changes to the original eyetracking algorithm were made.

### ICatcher+
This project leverages [ICatcher+](https://github.com/erelyotam/icatcher_plus), as described in the following publication:

Erel, Y., Shannon, K. A., Chu, J., Scott, K., Struhl, M. K., Cao, P., Tan, X., Hart, P., Raz, G., Piccolo, S., Mei, C., Potter, C., Jaffe-Dax, S., Lew-Williams, C., Tenenbaum, J., Fairchild, K., Bermano, A., & Liu, S. (2023). iCatcher+: Robust and Automated Annotation of Infants’ and Young Children’s Gaze Behavior From Videos Collected in Laboratory, Field, and Online Studies. Advances in Methods and Practices in Psychological Science.



## License

This project is licensed under the [GNU GPLv3](LICENSE.md) - see the [LICENSE.md](LICENSE.md) file for
details

## Contact

- **Adrian Steffan** [adriansteffan](https://github.com/adriansteffan) [website](https://adriansteffan.com/)

