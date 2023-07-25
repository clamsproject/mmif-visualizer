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
| Screenshots & HTML5 video navigation of TimeFrames | [Chyron text recognition](https://github.com/clamsproject/app-chyron-text-recognition), [Slate detection](https://github.com/clamsproject/app-slatedetection), [Bars detection](https://github.com/clamsproject/app-barsdetection) |



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

The data sources used here are copy righted and are NOT in the repository.

The data sources are embedded in a MMIF file and it is the MMIF file that is handed to the visualizer. There is an example input MMIF file in `kaldi-spacy.json`, this file refers to three media files:

1. /data/video/cpb-aacip-507-z31ng4hp5t.part.mp4
2. /data/audio/cpb-aacip-507-z31ng4hp5t.part.wav
3. /data/text/cpb-aacip-507-z31ng4hp5t.part.trn

The Flask server will look for these files in `static/data/video`, `static/data/audio` and `static/data/text`, and those directories should point at the appropriate location:

- If you run the visualizer in a Docker container, then the `-v` option in the docker-run command is used to mount the local data directory `/Users/shared/archive` to the `/data` directory on the container and the `static/data` symlink already points to that.
- If you run the visualizer on your local machine without using a container, then you have a couple of options (where you may need to remove the current link first):
  - Make sure that the `static/data` symlink points at the local data directory 
    `$ ln -s /Users/Shared/archive/ static/data`
  - Copy the contents of `/Users/Shared/archive` into `static/data`.
  - You could choose to copy the data to any spot in the `static` folder but then you would have to edit the MMIF input file.

