# Check for presence of Docker/Podman engines
if command -v docker &> /dev/null
then
    export container_engine=docker
elif command -v podman &> /dev/null
then
    export container_engine=podman
else
    echo "Error: Docker or Podman not found. Please install container engine and try again."
    exit 1
fi
# Return if no inputs passed
if [ -z "$1" ]
then
    echo "Error: no data directory specified."
    exit 1
fi
# Set data directory to absolute path of input
export datadir=$( cd $1; pwd )
# Set mount directory to data directory if not specified
if [ -z "$2" ]
then
    echo "No mount directory specified: defaulting to $datadir"
    export mountdir=$datadir
else
    export mountdir=$2
fi
# Start visualizer
$container_engine build . -f Containerfile -t clams-mmif-visualizer
$container_engine run --name clams-mmif-visualizer --rm -p 5001:5000 -e PYTHONUNBUFFERED=1 -v $datadir:$mountdir -v $datadir:/app/static/$mountdir clams-mmif-visualizer
echo "MMIF Visualizer is running in the background and can be accessed at http://localhost:5001/. To shut it down, run '$container_engine kill clams-mmif-visualizer'"