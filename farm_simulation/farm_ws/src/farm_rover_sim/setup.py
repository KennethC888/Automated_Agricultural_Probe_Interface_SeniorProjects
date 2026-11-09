import os
from glob import glob
from setuptools import setup

package_name = 'farm_rover_sim'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'rviz'), glob('rviz/*.rviz')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='kchan',
    maintainer_email='kchan@seniorproject.local',
    description='Farm Rover ROS 2 Simulation',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'base_station_node = farm_rover_sim.base_station_node:main',
            'rover_node = farm_rover_sim.rover_node:main',
        ],
    },
)
