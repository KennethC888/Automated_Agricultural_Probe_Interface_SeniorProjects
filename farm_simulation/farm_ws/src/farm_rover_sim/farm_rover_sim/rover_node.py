import json
import random
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from visualization_msgs.msg import Marker, MarkerArray
from farm_rover_sim.farm_map import FarmMap

class RoverNode(Node):
    def __init__(self):
        super().__init__('rover_node')
        self.map = FarmMap()
        self.upload_pub = self.create_publisher(String, '/farm/upload', 10)
        self.rover_marker_pub = self.create_publisher(MarkerArray, '/rover/markers', 10)

        self.pos = (0, 0)
        self.battery = 100.0
        self.unvisited = set(self.map.tags.keys())
        self.memory = []
        self.path = []
        self.state = 'DISPATCH'
        self.current_tag = None
        self.probe_wait_ticks = 0

        # BATTERY PARAMETERS
        self.drain_per_cell = 0.20
        self.drain_probe = 0.80
        self.fixed_low_threshold = 35.0
        self.safety_buffer_pct = 5.0     # Extra cushion so it never hits 0%

        self.timer = self.create_timer(0.045, self.step)
        self.get_logger().info(f'Fail-Safe Rover online. Tags to cover: {len(self.unvisited)}')

    def battery_needed_to_reach_base(self, from_pos):
        """Calculates exact path distance from a cell back to (0, 0) using A*."""
        path_home = self.map.astar(from_pos, (0, 0))
        steps = max(0, len(path_home) - 1)
        return steps * self.drain_per_cell

    def is_return_required(self):
        """Checks both the 35% user ceiling AND dynamic point-of-no-return distance."""
        cost_home = self.battery_needed_to_reach_base(self.pos)
        dynamic_critical_limit = cost_home + self.safety_buffer_pct

        # Abort if at or below 35% OR if battery is getting close to the cost to reach home
        if self.battery <= self.fixed_low_threshold:
            return True, f"Hit <= {self.fixed_low_threshold}% threshold"
        if self.battery <= dynamic_critical_limit:
            return True, f"Dynamic limit reached: Batt {self.battery:.1f}% <= Need {dynamic_critical_limit:.1f}%"
        return False, ""

    def publish_rover_markers(self):
        arr = MarkerArray()
        now = self.get_clock().now().to_msg()

        # 1. Rover Body
        body = Marker()
        body.header.frame_id = 'map'
        body.header.stamp = now
        body.ns = 'rover'
        body.id = 1
        body.type = Marker.CYLINDER
        body.action = Marker.ADD
        body.pose.position.x = float(self.pos[0])
        body.pose.position.y = float(self.pos[1])
        body.pose.position.z = 0.5
        body.scale.x, body.scale.y, body.scale.z = 2.2, 2.2, 1.0
        body.color.r, body.color.g, body.color.b, body.color.a = 1.0, 0.15, 0.1, 1.0
        arr.markers.append(body)

        # 2. Overhead HUD
        overhead_hud = Marker()
        overhead_hud.header.frame_id = 'map'
        overhead_hud.header.stamp = now
        overhead_hud.ns = 'rover_overhead'
        overhead_hud.id = 2
        overhead_hud.type = Marker.TEXT_VIEW_FACING
        overhead_hud.action = Marker.ADD
        overhead_hud.pose.position.x = float(self.pos[0])
        overhead_hud.pose.position.y = float(self.pos[1])
        overhead_hud.pose.position.z = 3.6
        overhead_hud.scale.z = 2.8

        cost_home = self.battery_needed_to_reach_base(self.pos)
        overhead_hud.text = f"🔋 {self.battery:.1f}%\n[Return Cost: {cost_home:.1f}%]"

        if self.battery > 50.0:
            overhead_hud.color.r, overhead_hud.color.g, overhead_hud.color.b = 0.1, 1.0, 0.2
        elif self.battery > 35.0:
            overhead_hud.color.r, overhead_hud.color.g, overhead_hud.color.b = 1.0, 0.85, 0.1
        else:
            overhead_hud.color.r, overhead_hud.color.g, overhead_hud.color.b = 1.0, 0.1, 0.1
        overhead_hud.color.a = 1.0
        arr.markers.append(overhead_hud)

        # 3. Off-Grid Dashboard Billboard
        board_backdrop = Marker()
        board_backdrop.header.frame_id = 'map'
        board_backdrop.header.stamp = now
        board_backdrop.ns = 'hud_board'
        board_backdrop.id = 10
        board_backdrop.type = Marker.CUBE
        board_backdrop.action = Marker.ADD
        board_backdrop.pose.position.x = -18.0
        board_backdrop.pose.position.y = 50.0
        board_backdrop.pose.position.z = 8.0
        board_backdrop.scale.x = 2.0
        board_backdrop.scale.y = 30.0
        board_backdrop.scale.z = 22.0
        board_backdrop.color.r, board_backdrop.color.g, board_backdrop.color.b, board_backdrop.color.a = 0.05, 0.05, 0.08, 0.92
        arr.markers.append(board_backdrop)

        bars = int(max(0.0, self.battery) // 5)
        battery_bar = "█" * bars + "░" * (20 - bars)

        hud_text = Marker()
        hud_text.header.frame_id = 'map'
        hud_text.header.stamp = now
        hud_text.ns = 'hud_text'
        hud_text.id = 11
        hud_text.type = Marker.TEXT_VIEW_FACING
        hud_text.action = Marker.ADD
        hud_text.pose.position.x = -18.0
        hud_text.pose.position.y = 50.0
        hud_text.pose.position.z = 8.0
        hud_text.scale.z = 3.2

        hud_text.text = (
            f"=== FAIL-SAFE ROVER ===\n"
            f"BATTERY:     {self.battery:.1f}%\n"
            f"[{battery_bar}]\n"
            f"COST HOME:   {cost_home:.1f}%\n"
            f"SAFETY BUFF: {self.safety_buffer_pct:.1f}%\n"
            f"STATUS:      {self.state}\n"
            f"TAGS:        {len(self.memory)}/8 Completed\n"
            f"POS:         ({self.pos[0]}, {self.pos[1]})"
        )

        if self.battery > 50.0:
            hud_text.color.r, hud_text.color.g, hud_text.color.b = 0.2, 1.0, 0.2
        elif self.battery > 35.0:
            hud_text.color.r, hud_text.color.g, hud_text.color.b = 1.0, 0.85, 0.1
        else:
            hud_text.color.r, hud_text.color.g, hud_text.color.b = 1.0, 0.1, 0.1
        hud_text.color.a = 1.0
        arr.markers.append(hud_text)

        self.rover_marker_pub.publish(arr)

    def find_nearest_plant_crop(self, tag_coord):
        tx, ty = tag_coord
        for dy in range(-6, 7):
            for dx in range(-3, 4):
                coord = (tx + dx, ty + dy)
                if coord in self.map.plants:
                    return self.map.plants[coord]
        return '🌱'

    def step(self):
        if self.state == 'DISPATCH':
            if not self.unvisited:
                self.get_logger().info('All tags sampled! Navigating back to base (0, 0).')
                full_path = self.map.astar(self.pos, (0, 0))
                self.path = full_path[1:] if len(full_path) > 1 else []
                self.state = 'RETURNING_HOME'
                return

            # Check if return is already mandated before dispatching to a new tag
            needs_return, reason = self.is_return_required()
            if needs_return:
                self.get_logger().warn(f'Safe return triggered ({reason}). Heading to base!')
                full_path = self.map.astar(self.pos, (0, 0))
                self.path = full_path[1:] if len(full_path) > 1 else []
                self.state = 'RETURNING_HOME'
                return

            # Select nearest tag whose round-trip cost is safe
            feasible_tags = []
            for tid in self.unvisited:
                t_pos = self.map.tags[tid]
                path_to_tag = self.map.astar(self.pos, t_pos)
                cost_to_tag = max(0, len(path_to_tag) - 1) * self.drain_per_cell
                cost_tag_to_base = self.battery_needed_to_reach_base(t_pos)
                total_mission_cost = cost_to_tag + self.drain_probe + cost_tag_to_base + self.safety_buffer_pct

                if (self.battery - cost_to_tag) > self.fixed_low_threshold and self.battery > total_mission_cost:
                    dist = abs(t_pos[0] - self.pos[0]) + abs(t_pos[1] - self.pos[1])
                    feasible_tags.append((dist, tid, path_to_tag))

            if not feasible_tags:
                self.get_logger().warn('No tags reachable within safe battery margins. Heading to base.')
                full_path = self.map.astar(self.pos, (0, 0))
                self.path = full_path[1:] if len(full_path) > 1 else []
                self.state = 'RETURNING_HOME'
                return

            feasible_tags.sort(key=lambda x: x[0])
            _, self.current_tag, full_path = feasible_tags[0]
            self.path = full_path[1:] if len(full_path) > 1 else []
            self.state = 'NAVIGATING'

        elif self.state == 'NAVIGATING':
            # Continually check if remaining charge requires an immediate abort home
            needs_return, reason = self.is_return_required()
            if needs_return:
                self.get_logger().warn(f'ABORTING MISSION ({reason}). Safely routing to base (0, 0)!')
                full_path = self.map.astar(self.pos, (0, 0))
                self.path = full_path[1:] if len(full_path) > 1 else []
                self.state = 'RETURNING_HOME'
                return

            if self.path:
                next_cell = self.path.pop(0)
                if next_cell not in self.map.blocked:
                    self.pos = next_cell
                    self.battery = max(0.0, self.battery - self.drain_per_cell)
            else:
                self.state = 'PROBING'
                self.probe_wait_ticks = 12

        elif self.state == 'PROBING':
            if self.probe_wait_ticks > 0:
                self.probe_wait_ticks -= 1
                return

            self.battery = max(0.0, self.battery - self.drain_probe)
            moisture = round(random.uniform(10.0, 80.0), 2)
            temp = round(random.uniform(55.0, 95.0), 2)

            crop_emoji = self.find_nearest_plant_crop(self.pos)
            plant_pic = '🥀' if moisture < 20.0 else crop_emoji

            reading = {
                'tag_id': self.current_tag,
                'x': self.pos[0],
                'y': self.pos[1],
                'soil_moisture_pct': moisture,
                'temperature_f': temp,
                'plant_emoji': plant_pic
            }
            self.memory.append(reading)
            self.unvisited.remove(self.current_tag)

            self.get_logger().info(
                f'PROBED Tag #{self.current_tag} at {self.pos}: {plant_pic} ({moisture}% M, {temp}°F) | Batt: {self.battery:.1f}%'
            )
            self.state = 'DISPATCH'

        elif self.state == 'RETURNING_HOME':
            if self.path:
                next_cell = self.path.pop(0)
                if next_cell not in self.map.blocked:
                    self.pos = next_cell
                    self.battery = max(0.0, self.battery - self.drain_per_cell)
            else:
                self.get_logger().info(f'Safely docked at Base Station. Uploading {len(self.memory)} records...')
                msg = String()
                msg.data = json.dumps(self.memory)
                self.upload_pub.publish(msg)
                self.memory.clear()

                self.battery = 100.0
                self.get_logger().info('Recharge complete: Battery restored to 100.0%.')

                if self.unvisited:
                    self.state = 'DISPATCH'
                else:
                    self.get_logger().info('Mission Complete! All 8 tags probed and uploaded. Rover parked.')
                    self.publish_rover_markers()
                    self.timer.cancel()
                    return

        self.publish_rover_markers()

def main(args=None):
    rclpy.init(args=args)
    node = RoverNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
