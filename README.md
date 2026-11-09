# AAPI Farm Simulation & Computer Vision Guide

Quick-reference command guide to install dependencies, compile the ROS 2 workspace, launch the farm simulation, and run the Computer Vision web dashboard.

---

## 1. Environment & Dependencies

Install ROS 2 Humble (Ubuntu 22.04 LTS), the colcon build tools, and visualization message packages:

```bash
# 1.1 Set locale
sudo apt update && sudo apt install -y locales
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8

# 1.2 Add official ROS 2 repository and key
sudo apt install -y software-properties-common curl gnupg lsb-release
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu jammy main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

# 1.3 Install ROS 2 Humble Desktop & Build tools
sudo apt update
sudo apt install -y ros-humble-desktop python3-colcon-common-extensions python3-rosdep ros-humble-visualization-msgs
```

---

## 2. Compile the Farm Rover Workspace

Navigate to your workspace root and compile with `colcon`:

```bash
# Source ROS 2 base environment
source /opt/ros/humble/setup.bash

# Go to workspace root and build
cd ~/AAPI/farm_simulation/farm_ws
colcon build --symlink-install
```

---

## 3. Run the Simulation

Launch the complete simulation stack (Static TF publisher, Base Station node, Rover fail-safe node, and pre-configured RViz visualizer):

```bash
# Run in Terminal 1
source /opt/ros/humble/setup.bash
cd ~/AAPI/farm_simulation/farm_ws
source install/setup.bash

ros2 launch farm_rover_sim farm_sim.launch.py
```

### (Optional) Inspect Real-Time Telemetry CSV Logs
In a second terminal, monitor real-time probe uploads to the log file:

```bash
# Run in Terminal 2
tail -f ~/AAPI/farm_simulation/soil_probe_log.csv
```

---

## 4. Run the Computer Vision Dashboard

The web server renders real-time mission statistics and vision feeds:

```bash
# 4.1 Ensure CV files are placed in ~/AAPI/Computer_Vision/
mkdir -p ~/AAPI/Computer_Vision
mv ~/AAPI/index.html ~/AAPI/index.txt ~/AAPI/server.py ~/AAPI/Computer_Vision/ 2>/dev/null || true

# 4.2 Start the web server
cd ~/AAPI/Computer_Vision
python3 server.py
```

Open a web browser and navigate to:
```text
http://localhost:8000
```



# Run this if you have already downloaded all necessary things (only for farm simulation): 
source /opt/ros/humble/setup.bash
cd ~/AAPI/farm_simulation/farm_ws
colcon build --symlink-install
source install/setup.bash
ros2 launch farm_rover_sim farm_sim.launch.py