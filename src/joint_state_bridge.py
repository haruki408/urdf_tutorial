#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import traceback
from typing import Dict, List

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import JointState
from std_msgs.msg import Empty

# カスタムメッセージ
from ms_module_msgs.msg import AllJointState  # , JointState as MsJointState  # <- 使ってないのでコメント可


class JointStateBridge(Node):
    """各 limb の AllJointState を購読し、URDF 名へマッピングして /joint_states を配信するブリッジ"""

    def __init__(self):
        super().__init__('joint_state_bridge')

        # ── パラメータ（CSVで受ける） ──
        self.declare_parameter('limb_names', "")  # 例: "limb_n_12,limb_n_13,limb_n_14,body_n_2_limb_n_2"
        self.declare_parameter('topic_template', '/{limb}/joint/out/all_joint_state')
        self.declare_parameter('publish_rate_hz', 30.0)
        self.declare_parameter('qos_reliability', 'reliable')

        limb_csv: str = self.get_parameter('limb_names').get_parameter_value().string_value
        self.limb_names: List[str] = [s.strip() for s in limb_csv.split(',') if s.strip()]
        self.topic_template: str = self.get_parameter('topic_template').get_parameter_value().string_value
        self.rate_hz: float = float(self.get_parameter('publish_rate_hz').value)
        qos_reliability: str = self.get_parameter('qos_reliability').value.lower()

        if not self.limb_names:
            self.get_logger().warn('limb_names が空です。例: "limb_n_12,limb_n_13"')

        # ── QoS ──
        qos = QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=10)
        qos.reliability = ReliabilityPolicy.RELIABLE if qos_reliability != 'best_effort' else ReliabilityPolicy.BEST_EFFORT

        # ── Publisher ──
        self.pub_js = self.create_publisher(JointState, '/joint_states', 10)

        # ── バッファ ──
        self.pos_map: Dict[str, float] = {}
        self.vel_map: Dict[str, float] = {}
        self.eff_map: Dict[str, float] = {}

        # ── Subscribers ──
        self.subs = []
        for limb in self.limb_names:
            topic = self.topic_template.format(limb=limb)
            self.get_logger().info(f'Subscribe: {topic}')
            sub = self.create_subscription(
                AllJointState,
                topic,
                lambda msg, limb=limb: self._safe_on_all_joint_state(msg, limb),
                qos
            )
            self.subs.append(sub)

        # モデル切替通知（任意）
        self.create_subscription(Empty, '/model_switched', self._on_model_switched, 10)
        self.force_until_sec = 0.0

        # ── 定期送信 ──
        period = 1.0 / max(1e-3, self.rate_hz)
        self.timer = self.create_timer(period, self._safe_publish_joint_states)

        # 🔴 ゼロ初期化は __init__ の末尾で「呼び出す」
        self._init_zero_positions(joint_count=4)

        self.get_logger().info(f'JointStateBridge started: limbs={self.limb_names}')

    # 🔵 これは __init__ の“外”に定義（クラスの通常メソッド）
    def _init_zero_positions(self, joint_count: int = 4):
        """実機トピックが来ない間でも /joint_states を安定配信するための 0 初期化"""
        for limb in self.limb_names:
            for i in range(1, joint_count + 1):
                jname = f'{limb}_joint_{i}'
                self.pos_map[jname] = 0.0
                self.vel_map[jname] = 0.0
                self.eff_map[jname] = 0.0

    # 受信ラッパ
    def _safe_on_all_joint_state(self, msg, limb):
        try:
            self._on_all_joint_state(msg, limb)
        except Exception:
            self.get_logger().error(traceback.format_exc())

    def _on_all_joint_state(self, msg: AllJointState, limb: str):
        names = self._joint_names_for_limb(limb, len(msg.joint_state_list))
        for i, js in enumerate(msg.joint_state_list):
            jname = names[i]
            self.pos_map[jname] = float(js.position)
            self.vel_map[jname] = float(js.velocity)
            self.eff_map[jname] = float(js.effort)

    def _joint_names_for_limb(self, limb: str, count: int):
        # URDFの命名に合わせて 1 から
        return [f'{limb}_joint_{i}' for i in range(1, count + 1)]

    def _on_model_switched(self, _):
        import time
        self.force_until_sec = time.time() + 2.0
        self.get_logger().info("model_switched → 2秒間 /joint_states を強制再送")

    def _safe_publish_joint_states(self):
        try:
            self._publish_joint_states()
        except Exception:
            self.get_logger().error(traceback.format_exc())

    def _publish_joint_states(self):
        if not self.pos_map:
            return
        js = JointState()
        js.header.stamp = self.get_clock().now().to_msg()
        names = sorted(self.pos_map.keys())
        js.name = names
        js.position = [self.pos_map[n] for n in names]
        js.velocity = [self.vel_map.get(n, 0.0) for n in names]
        js.effort  = [self.eff_map.get(n, 0.0) for n in names]
        self.pub_js.publish(js)


def main():
    rclpy.init()
    node = JointStateBridge()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
