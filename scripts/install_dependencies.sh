apt install -y python3-pip git cmake
python3 -m pip install meson ninja --upgrade

chmod +x _install_aravis.sh
chmod +x _install_tiscamera.sh

./_install_aravis.sh
./_install_tiscamera.sh