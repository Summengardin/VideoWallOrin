# VideoWall - VisionController code

Source code to be run on the VisionController. Originally devloped for NVIDIA Jetson devices, but later changed to x86 architecture.

## Features

- Multi-camera and multi-source video wall with tiling
- Dynamic source add/remove (RTSP, Aravis, file, test sources)
- On-screen display (OSD) overlays and text management
- DeepStream YOLOv8/YOLOv11 inference integration
- MQTT-based remote control and status reporting
- Recording of RTSP streams with timestamp overlays
- Dockerized deployment and development environment

## Getting Started

### Prerequisites

- x86 Computer running Ubuntu >= 22.04
- Nvidia GPU
- Nvidia GPU driver >= 535.54.03
- Docker, Docker Compose and Nvidia-Container-Toolkit

### Running the Application

```sh
cd <path/to/VideoWallOrin>
python -m VisionController
```

### Running Tests

```sh
cd <path/to/VideoWallOrin>
PYTHONPATH=$(pwd) pytest
```

### Using Docker

1. Install Docker, Docker Compose, and nvidia-container-toolkit.
2. Build and run the container:

   ```sh
   docker compose up --build visioncontroller
   ```
2. Only run

   ```sh
   docker compose up visioncontroller
   ```


## Project Structure

- `VisionController/` – Main application, pipeline manager, camera and source modules
- `features/` – BDD tests (Behave) for pipeline and OSD
- `research/` – Experimental scripts and pipelines
- `scripts/` – Dependency installation scripts
- `data/` – Sample media files
- `vapix-python/` – Axis Vapix API Python wrapper

## Configuration

- Configuration files are found in `VisionController/config/`


## Handover Notes

- See `requirements.txt` and `dev-requirements.txt` for dependencies.
- Use the provided Dockerfile for reproducible builds.
- For new camera types, extend the source bin modules in `VisionController/libs/cameras/`.
- For troubleshooting, check logs and the output of `docker compose logs`.


## Troubleshooting



## Contact

For further questions, refer to the code comments or contact the original maintainer.