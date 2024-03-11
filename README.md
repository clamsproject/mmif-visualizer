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

## Requirements:

- A command line interface.
- Git (to get the code).
- [Docker](https://www.docker.com/) or [Podman](https://podman.io/) (if you run the visualizer in a container).
- Python 3.6 or later (if you want to run the server containerless).

To get this code if you don't already have it:

```bash
$ git clone https://github.com/clamsproject/mmif-visualizer
```

## Startup 

### Quick start

If you just want to get the server up and running quickly, the repository contains a shell script `start_visualizer.sh` to immediately launch the visualizer in a container. You can invoke it with the following command:

```
./start_visualizer.sh <data_directory> <mount_directory>
```

* The **required**  `data_directory` argument should be the absolute or relative path of the media files on your machine which the MMIF files reference.
* The **optional** `mount_directory` argument should be specified if your MMIF files point to a different directory than where your media files are stored on the host machine. For example, if your video, audio, and text data is stored locally at `/home/archive` but your MMIF files refer to `/data/...`, you should set this variable to `/data`. (If this variable is not set, the mount directory will default to the data directory)

For example, if your media files are stored at `/my_data` and your MMIF files specify the document location as `"location": "file:///data/...`, you can start the visualizer with the following command: 
```
./start_visualizer.sh /my_data /data
```

The server can then be accessed at `http://localhost:5001/upload`

The following is breakdown of the script's functionality:

### Running the server natively

First install the python dependencies listed in `requirements.txt`:

````bash
$ pip install -r requirements.txt
````

You will also need to install opencv-python if you are not running within a container (`pip install opencv-python`).
Then, to run the server do:

```bash
$ python app.py
```

Running the server natively means that the source media file paths in the target MMIF file are all accessible in the local file system, under the same directory paths. 
If that's not the case, and the paths in the MMIF is beyond your FS permission, using container is recommended. See the next section for an example. 

#### Data source repository and example MMIF file
This repository contains an example MMIF file in `example/whisper-spacy.json`. This file refers to three media files:

1. service-mbrs-ntscrm-01181182.mp4
2. service-mbrs-ntscrm-01181182.wav
3. service-mbrs-ntscrm-01181182.txt
 
> [!NOTE]
> Note on source/copyright: these documents are sourced from [the National Screening Room collection in the Library of Congress Online Catalog](https://hdl.loc.gov/loc.mbrsmi/ntscrm.01181182). The collection provides the following copyright information:
> > The Library of Congress is not aware of any U.S. copyright or other restrictions in the vast majority of motion pictures in these collections. Absent any such restrictions, these materials are free to use and reuse.

These files can be found in the directory `example/example-documents`. But according to the `whisper-spacy.json` MMIF file, those three files should be found in their respective subdirectories in `/data`. 
Easy way to align these paths is probably to create a symbolic link to the `example-documents` directory in the `/data` directory.
However, since `/data` is located at the root directory, you might not have permission to write a new symlink to the FS root.
In this case you can more easily re-map the `examples/example-documents` directory to `/data` by using the `-v` option in the docker-run command. See below. 

### Running the server in a container

Download or clone this repository and build an image using the `Containerfile` (you may use another name for the -t parameter,
for this example we use `clams-mmif-visualizer` throughout).

> [!NOTE]
> if using podman, just substitute `docker` for `podman` in the following commands.

```bash
$ docker build . -f Containerfile -t clams-mmif-visualizer
```

In these notes we assume that the data are in a local directory named `/home/myuser/public` with subdirectories `audio`, `image`, `text` and `video`. We can now run a container with

```bash
$ docker run --rm -d -p 5001:5000 -v /home/myuser/public:/data clams-mmif-visualizer
```

> [!NOTE]
> With the docker command above we do two things of note:
> 1. The container port 5000 (the default for a Flask server) is exposed to the same port on your host (your local computer) with the `-p` option.
> 2. The local data repository `/home/myuser/public` is mounted to `/data` on the container with the `-v` option.

Now, when you use the `example/example-documents` directory as the data source to visualize `examples/whisper-spacy.json` MMIF file, you need to triple-mount the example directory to the container, as `audio`, `video`, and `text` respectively.

$ docker run --rm -d -p 5001:5000 -v $(pwd)/example/example-documents:/data/audio -v $(pwd)/example/example-documents:/data/video -v $(pwd)/example/example-documents:/data/text clams-mmif-visualizer

## Usage
Use the visualizer by uploading files. MMIF files can be uploaded to the visualization server one of two ways:
* Point your browser to http://0.0.0.0:5000/upload, click "Choose File" and then click "Visualize". This will generate a static URL containing the visualization of the input file (e.g. `http://localhost:5000/display/HaTxbhDfwakewakmzdXu5e`). Once the file is uploaded, the page will automatically redirect to the file's visualization.
* Using a command line, enter:
  ``` 
  curl -X POST -F "file=@<filename>" -s http://localhost:5000/upload
  ```
  This will upload the file and print the unique identifier for the file visualization. The visualization can be accessed at `http://localhost:5000/display/<id>`

The server will maintain a cache of up to 50MB for these temporary files, so the visualizations can be repeatedly accessed without needing to re-upload any files. Once this limit is reached, the server will delete stored visualizations until enough space is reclaimed, drawing from oldest/least recently accessed pages first. If you attempt to access the /display URL of a deleted file, you will be redirected back to the upload page instead.

