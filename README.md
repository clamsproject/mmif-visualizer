# MMIF Visualization 

This web app visualizes different annotation component in a single MMIF file. For details of MMIF format, please refer to the [MMIF website](https://mmif.clams.ai). 

## Supported annotations

1. Video or Audio file player via HTML5
1. [WebVTT](https://www.w3.org/TR/webvtt1/)
1. Raw and pretty-printed MMIF contents (MMIF is syntactically JSON)
1. NE annotations via [displaCy](https://explosion.ai/demos/displacy-ent)

## Installation using Docker

Running via [docker](https://www.docker.com/) is the preferred way. Download or clone this repository and build an image using `Dockerfile` (you may use another name for the -t parameter).

```bash
$ git clone https://github.com/clamsproject/mmif-visualizer
$ docker build -t clams-mmif-visualizer .
```

Once the image is ready, run it in such a way that the container port 5000 is exposed (`-p XXXX:5000`) and that the data repository is mounted inside the `/app/static` directory of the container.

```bash
$ docker run --rm -d -p 5000:5000 -v /home/var/archive:/var/archive clams-mmif-visualizer                              
```

This assumes that there is a local directory `/home/var/archive` which has the data (see the last section for more details on the data repository). The repository contains a symbolic link in `static/var` that links to `/var` and that link, plus the volume mount with the -v parameter, ensures that files in `/home/var/archive` are accessible on the docker container as well as by the Flask server that runs on the docker container (which only has access to the contents of the `static` directory).

## Native installation

Requirements:

1. Python 3.6 or later
1. git command line interface

Simply clone this repository and install the python dependencies listed in `requirements.txt`. Then copy, symlink, or mount your primary data source into the `static` directory. See next section for more details on the data repository.

And then copy (or symlink/mount) your primary data source into `static` directory. 

There is an example input file in `input`, this file refers to two file paths:

1. cpb-aacip-507-z31ng4hp5t.part.mp4
2. cpb-aacip-507-z31ng4hp5t.part.trn

These two paths should be in `/mmif-viz/static/archive/video` and `/mmif-viz/static/archive/text`.

## Data source repository. 
Data source includes video, audio, and text (transcript) files that are subjects for the CLAMS analysis tools. To make this visualizer accessible to those files and able to display the contents on the web browser, source files needs to be located inside `static` directory. For example, if the path to a source file encoded in the MMIF is `/local/path/to/data/some-video-file.mp4`, the same file must exist as `static/local/path/to/data/some-video-file.mp4`. 
