# VideoWall - VisionController code

Source code to be run on the VisionController. Originally devloped for NVIDIA Jetson devices, but later changed to x86 architecture.

## Quick Start
- Build and run
```sh
   docker compose up --build videowall
   ```





## Prerequisites

- x86 Computer running Ubuntu >= 22.04
- Nvidia GPU
- Nvidia GPU driver >= 535.54.03
- Docker, Docker Compose and Nvidia-Container-Toolkit

## Running the Application

```sh
cd <path/to/VideoWallOrin>
python -m VisionController
```

<!-- ### Running Tests


```sh
cd <path/to/VideoWallOrin>
PYTHONPATH=$(pwd) pytest
``` -->

## Using Docker

See Dockerfile for custom build argumetns (Deepstream version, inference toggle, etc.). Compose sets these arguments explicitly.
1. Install Docker, Docker Compose, and nvidia-container-toolkit.
2. Build and run the container:

   ```sh
   docker compose up --build videowall
   ```
2. Only run

   ```sh
   docker compose up videowall
   ```


## Project Structure

<!-- - `features/` – BDD tests (Behave) for pipeline and OSD -->
- `VisionController/` – Main application, pipeline manager, camera and source modules
- `research/` – Experimental scripts and pipelines
- `scripts/` – Dependency installation scripts
- `data/` – Sample media files
- `vapix-python/` – Axis Vapix API Python wrapper

## Configuration

- Configuration files are found in `VisionController/config/`
- For convenience, I recommend a symbolic link. `ln -s config.yml VisionController/config/config_vwcontroller.yml` 


## Fonts
Default font for text: `Noto Serif Bold`

For symbols use either of:
- `MaterialSymbolsOutlined-Medium`
- `MaterialSymbolsSharp-Medium`
- `MaterialSymbolsRounded-Medium`

## Notes

- For new camera types, extend the source bin modules in `VisionController/libs/cameras/`. Then, add to config file.
- For troubleshooting, check logs and the output of `docker compose logs`.
- Check [Confluence](https://seaonics.atlassian.net/wiki/spaces/9ROAA/pages/310345730/95109.522+-+ADAS+-+Camera+and+Video+Wall) for more info

