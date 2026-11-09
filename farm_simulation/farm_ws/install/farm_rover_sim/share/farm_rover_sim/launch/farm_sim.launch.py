import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    pkg_dir = get_package_share_directory('farm_rover_sim')
    rviz_config = os.path.join(pkg_dir, 'rviz', 'farm_view.rviz')

    return LaunchDescription([
        # 1. Transform publisher to fix "No tf data"
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            arguments=['0', '0', '0', '0', '0', '0', 'map', 'base_link'],
            name='static_tf_pub'
        ),
        # 2. Base Station
        Node(
            package='farm_rover_sim',
            executable='base_station_node',
            name='base_station',
            output='screen'
        ),
        # 3. Rover Node
        Node(
            package='farm_rover_sim',
            executable='rover_node',
            name='rover',
            output='screen'
        ),
        # 4. RViz auto-loaded with all markers & correct camera angle
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            arguments=['-d', rviz_config],
            output='screen'
        )
    ])
