#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
import time

class LimbGoalPublisher(Node):
    """
    limb_trajectory_driver へ /<limb>/goal を publish するノード
    position のみを送信するシンプルなパブリッシャ。
    """

    def __init__(self):
        super().__init__('limb_goal_publisher')

        # --- パラメータ ---
        self.declare_parameter('limb_name', 'limb_n_12')
        self.declare_parameter('goal_positions', '0.0,0.0,0.0,0.0')
        self.declare_parameter('wait_sec', 2.0)

        limb_name = self.get_parameter('limb_name').get_parameter_value().string_value
        goal_str = self.get_parameter('goal_positions').get_parameter_value().string_value
        self.wait_sec = float(self.get_parameter('wait_sec').value)

        # CSV → float list
        try:
            self.goal_positions = [float(x) for x in goal_str.split(',')]
        except Exception:
            self.get_logger().error(f'goal_positions の形式が不正です: {goal_str}')
            self.goal_positions = [0.0, 0.0, 0.0, 0.0]

        topic_name = f'/{limb_name}/goal'
        self.pub = self.create_publisher(JointState, topic_name, 10)
        self.get_logger().info(f'Publishing to {topic_name} after {self.wait_sec}s')

        # 指定時間後に一度だけ送信
        self.create_timer(self.wait_sec, self._publish_once)

    def _publish_once(self):
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.position = self.goal_positions
        self.pub.publish(msg)
        self.get_logger().info(f'Sent goal: {msg.position}')
        # 一度送信したら終了
        time.sleep(0.5)
        rclpy.shutdown()


def main():
    rclpy.init()
    node = LimbGoalPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
