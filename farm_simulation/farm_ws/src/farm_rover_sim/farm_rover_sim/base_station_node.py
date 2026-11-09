import csv
import json
import os
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from visualization_msgs.msg import Marker, MarkerArray
from farm_rover_sim.farm_map import FarmMap

class BaseStationNode(Node):
    def __init__(self):
        super().__init__('base_station_node')
        self.map = FarmMap()
        base_dir = os.path.expanduser('~/AAPI/farm_simulation')
        self.csv_path = os.path.join(base_dir, 'soil_probe_log.csv')
        self.total_records = 0

        self.sub = self.create_subscription(String, '/farm/upload', self.handle_upload, 10)
        self.marker_pub = self.create_publisher(MarkerArray, '/farm/markers', 10)
        self.timer = self.create_timer(1.0, self.publish_markers)

        self.get_logger().info(f'Base Station online. Data writing to: {self.csv_path}')

    def handle_upload(self, msg):
        readings = json.loads(msg.data)
        file_exists = os.path.isfile(self.csv_path)

        with open(self.csv_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['tag_id', 'x', 'y', 'soil_moisture_pct', 'temperature_f', 'plant_emoji'])
            for r in readings:
                writer.writerow([r['tag_id'], r['x'], r['y'], r['soil_moisture_pct'], r['temperature_f'], r['plant_emoji']])

        self.total_records += len(readings)
        self.get_logger().info(f'Received upload batch of {len(readings)} records! Cumulative: {self.total_records}')

    def publish_markers(self):
        arr = MarkerArray()
        now = self.get_clock().now().to_msg()

        # 1. Base Station Marker
        base = Marker()
        base.header.frame_id = 'map'
        base.header.stamp = now
        base.ns = 'farm_base'
        base.id = 0
        base.type = Marker.CUBE
        base.action = Marker.ADD
        base.pose.position.x = 0.0
        base.pose.position.y = 0.0
        base.pose.position.z = 0.5
        base.scale.x, base.scale.y, base.scale.z = 3.0, 3.0, 1.0
        base.color.r, base.color.g, base.color.b, base.color.a = 0.1, 0.3, 0.9, 1.0
        arr.markers.append(base)

        # 2. All Plants Rendered in Uniform Bright Green
        for i, (px, py) in enumerate(self.map.plants.keys()):
            m = Marker()
            m.header.frame_id = 'map'
            m.header.stamp = now
            m.ns = 'plants'
            m.id = 1000 + i
            m.type = Marker.CYLINDER
            m.action = Marker.ADD
            m.pose.position.x = float(px)
            m.pose.position.y = float(py)
            m.pose.position.z = 0.5
            m.scale.x = 0.8
            m.scale.y = 0.8
            m.scale.z = 0.6

            # Uniform agricultural green
            m.color.r = 0.1
            m.color.g = 0.85
            m.color.b = 0.2
            m.color.a = 0.9
            arr.markers.append(m)

        # 3. 10 AprilTag Waypoints
        for tid, (tx, ty) in self.map.tags.items():
            tag_marker = Marker()
            tag_marker.header.frame_id = 'map'
            tag_marker.header.stamp = now
            tag_marker.ns = 'tags'
            tag_marker.id = 20000 + tid
            tag_marker.type = Marker.SPHERE
            tag_marker.action = Marker.ADD
            tag_marker.pose.position.x = float(tx)
            tag_marker.pose.position.y = float(ty)
            tag_marker.pose.position.z = 0.5
            tag_marker.scale.x, tag_marker.scale.y, tag_marker.scale.z = 1.4, 1.4, 1.4
            tag_marker.color.r, tag_marker.color.g, tag_marker.color.b, tag_marker.color.a = 1.0, 0.9, 0.0, 1.0
            arr.markers.append(tag_marker)

            tag_text = Marker()
            tag_text.header.frame_id = 'map'
            tag_text.header.stamp = now
            tag_text.ns = 'tag_labels'
            tag_text.id = 30000 + tid
            tag_text.type = Marker.TEXT_VIEW_FACING
            tag_text.action = Marker.ADD
            tag_text.pose.position.x = float(tx)
            tag_text.pose.position.y = float(ty)
            tag_text.pose.position.z = 2.4
            tag_text.scale.z = 1.8
            tag_text.text = f"TAG #{tid}"
            tag_text.color.r, tag_text.color.g, tag_text.color.b, tag_text.color.a = 1.0, 1.0, 0.2, 1.0
            arr.markers.append(tag_text)

        self.marker_pub.publish(arr)

def main(args=None):
    rclpy.init(args=args)
    node = BaseStationNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
