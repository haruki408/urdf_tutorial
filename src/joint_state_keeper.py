#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Empty
import time

class JointStateKeeper(Node):
    def __init__(self):
        super().__init__('joint_state_keeper')
        self.sub = self.create_subscription(JointState, '/joint_states', self.on_js, 50)
        self.sub_sw = self.create_subscription(Empty, '/model_switched', self.on_switched, 10)
        self.pub = self.create_publisher(JointState, '/joint_states', 10)
        self.last_js = None

    def on_js(self, msg: JointState):
        # 最新を保持（position以外もあるなら丸ごと）
        self.last_js = msg

    def on_switched(self, _):
        if self.last_js is None:
            self.get_logger().warn('保持しているJointStateがありません')
            return
        self.get_logger().info('モデル切替→関節角を再送します')
        # 数秒だけ上書き送信してTFを安定させる（GUIなし想定）
        start = time.time()
        rate = self.create_rate(30.0)  # 30Hz
        while rclpy.ok() and time.time() - start < 2.0:
            self.pub.publish(self.last_js)
            rate.sleep()

def main():
    rclpy.init()
    node = JointStateKeeper()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
