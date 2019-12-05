# MMIF Visualization 

This web app visualizes different annotation component in a single MMIF file. For details of MMIF format, please refer to the [MMIF website](https://mmif.clams.ai). 

## Supported annotation

1. Video or Audio file player via HTML5
1. raw and pretty-printed MMIF contents (MMIF is syntactically JSON)
1. NE annotations via [displaCy](https://explosion.ai/demos/displacy-ent)

## Installation 

## via Docker 

Running via [docker](https://www.docker.com/) is preferred way. Download or clone this repository and build a image using `Dockerfile`. Once the image is ready, run it with container port 5000 is exposed (`-p XXXX:5000`) and data repository is mounted inside `/app/static` directory of the container. See the last section for more details on data repository.  

## Native installation

### Requirements

1. Python 3.6 or later
1. git command line interface

### Instruction
Simply clone this repository and install python dependencies listed in `requirements.txt`. Copy, symlink, or mount your primary data source into `static` directory. See next section for more details. 

And then copy (or symlink/mount) your primary data source into `static` directory. 

# Data source repository. 
Data source includes video, audio, and text (transcript) files that are subjects for the CLAMS analysis tools. To make this visualizer accessible to those files and able to display the contents on the web browser, source files needs to be located inside `static` directory. For example, if the path to a source file encoded in the MMIF is `/local/path/to/data/some-video-file.mp4`, the same file must exist as `static/local/path/to/data/some-video-file.mp4`. 
