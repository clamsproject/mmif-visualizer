# The MMIF Visualization Server

This application creates an HTML server that visualizes annotation components in a [MMIF](https://mmif.clams.ai) file. It contains the following visualizations for any valid MMIF:

- Video or Audio file player with HTML5 (assuming file refers to video and/or audio document).
- Pretty-printed MMIF contents.
- Interactive, searchable MMIF tree view with [JSTree](https://www.jstree.com/).
- Embedded [Universal Viewer](https://universalviewer.io/) (assuming file refers to video and/or image document).


The application also includes tailored visualizations depending on the annotations present in the input MMIF:
| Visualization | Supported CLAMS apps |
|---|---|
| [WebVTT](https://www.w3.org/TR/webvtt1/) for showing alignments of video captions. | [Whisper](https://github.com/clamsproject/app-whisper-wrapper), [Kaldi](https://github.com/clamsproject/app-aapb-pua-kaldi-wrapper) |
| Javascript bounding boxes for image and OCR annotations. | [Tesseract](https://github.com/clamsproject/app-tesseractocr-wrapper), [EAST](https://github.com/clamsproject/app-east-textdetection) |
| Named entity annotations with [displaCy.](https://explosion.ai/demos/displacy-ent) | [SPACY](https://github.com/clamsproject/app-spacy-wrapper) |                                                                        |



Requirements:

- A command line interface.
- Git (to get the code).
- [Docker](https://www.docker.com/) or [Podman](https://podman.io/) (if you run the visualizer in a container).
- Python 3.6 or later (if you want to run the server containerless).

To get this code if you don't already have it:

```bash
$ git clone https://github.com/clamsproject/mmif-visualizer
```



## Running the server in a container

Download or clone this repository and build an image using the `Dockerfile` (you may use another name for the -t parameter, for this example we use `clams-mmif-visualizer` throughout). **NOTE**: if using podman, just substitute `docker` for `podman` in the following commands.

```bash
$ docker build . -f Containerfile -t clams-mmif-visualizer
```

In these notes we assume that the data are in a local directory named `/Users/Shared/archive` with sub directories `audio`, `image`, `text` and `video` (those subdirectories are standard in CLAMS, but the parent directory could be any directory depending on your local set up). We can now run a Docker container with

```bash
$ docker run --rm -d -p 5000:5000 -v /Users/Shared/archive:/data clams-mmif-visualizer
```

After this, all you need to do is point your browser at [http://0.0.0.0:5000/upload](http://0.0.0.0:5000/upload), click "Choose File", select a MMIF file and then click "Visualize". See the *Data source repository and input MMIF file* section below for a description of the MMIF file. Assuming you have not made any changes to the directory structure you can use the example MMIF files in the `input` folder.

**Some background**

With the docker command above we do two things of note:

1. The container port 5000 (the default for a Flask server) is exposed to the same port on your Docker host (your local computer) with the `-p` option.
2. The local data repository `/Users/Shared/archive` is mounted to `/data` on the container with the `-v` option.

Another useful piece of information is that the Flask server on the Docker container has no direct access to `/data` since it can only see data in the `static` directory of this repository. Therefore we have created a symbolic link `static/data` that links to `/data`:

```bash
$ ln -s /data static/data
```

With this, the mounted directory `/data` in the container is accessable from inside the `/app/static` directory of the container. You do not need to use this command unless you change your set up because the symbolic link is part of this repository. 



## Running the server without Docker/Podman

First install the python dependencies listed in `requirements.txt`:

````bash
$ pip install -r requirements.txt
````

Let's again assume that the data are in a local directory `/Users/Shared/archive` with sub directories `audio`, `image`, `text` and`video`. You need to copy, symlink, or mount that local directory into the `static` directory. Note that the `static/data` symbolic link that is in the repository is set up to work with the docker containers, if you keep it in that form your data need to be in `/data`, otherwise you need to change the link to fit your needs, for example, you could remove the symbolic link and replace it with one that uses your local directory:

```bash
$ rm static/data
$ ln -s /Users/Shared/archive static/data
```

To run the server do:

```bash
$ python app.py
```

Then point your browser at [http://0.0.0.0:5000/upload](http://0.0.0.0:5000/upload), click "Choose File" and then click "Visualize".



## Data source repository and input MMIF file
The data source includes video, audio, and text (transcript) files that are subjects for the CLAMS analysis tools. As mentioned above, to make this visualizer work with those files and be able to display the contents on the web browser, those source files need to be accessible from inside the `static` directory.

This repository contains an example MMIF file in `input/whisper-spacy.json`. This file refers to three media files:

1. service-mbrs-ntscrm-01181182.mp4
2. service-mbrs-ntscrm-01181182.wav
3. service-mbrs-ntscrm-01181182.txt

These files can be found in the directory `input/example-documents`.  They can be moved anywhere on the host machine, as long as they are placed in the subdirectories `video`, `audio`, and `text` respectively. (e.g. `/Users/Shared/archive/video`, etc.)

According to the MMIF file, those three files should be found in their respective subdirectories in `/data`. The Flask server will look for these files in `static/data/video`, `static/data/audio` and `static/data/text`, amd those directories should point at the appropriate location:

- If you run the visualizer in a Docker container, then the `-v` option in the docker-run command is used to mount the local data directory `/Users/shared/archive` to the `/data` directory on the container and the `static/data` symlink already points to that.
- If you run the visualizer on your local machine without using a container, then you have a couple of options (where you may need to remove the current link first):
  - Make sure that the `static/data` symlink points at the local data directory 
    `$ ln -s /Users/Shared/archive/ static/data`
  - Copy the contents of `/Users/Shared/archive` into `static/data`.
  - You could choose to copy the data to any spot in the `static` folder but then you would have to edit the MMIF input file.


---
Note on source/copyright: these documents are sourced from [the National Screening Room collection in the Library of Congress Online Catalog](https://hdl.loc.gov/loc.mbrsmi/ntscrm.01181182). The collection provides the following copyright information:

> The Library of Congress is not aware of any U.S. copyright or other restrictions in the vast majority of motion pictures in these collections. Absent any such restrictions, these materials are free to use and reuse.

---
