#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import yaml

import rclpy
from rclpy.node import Node

from std_msgs.msg import Float64MultiArray, Bool
from ament_index_python.packages import get_package_share_directory


class LimbSequencePlayer(Node):
    """
    YAML に書いたシーケンスに従って、
    - 各 limb の /<limb>/goal (std_msgs/Float64MultiArray)
    - /wheel_attach, /gripper_attach (std_msgs/Bool)
    を時間軸に沿って順番に publish するノード
    """

    def __init__(self):
        super().__init__('limb_sequence_player')

        # ==== パラメータ ====
        # 明示指定があればそちらを優先、なければパッケージの config/limb_sequence.yaml
        self.declare_parameter('sequence_yaml_path', '')

        yaml_param = self.get_parameter(
            'sequence_yaml_path'
        ).get_parameter_value().string_value

        if yaml_param:
            yaml_path = yaml_param
        else:
            share_dir = get_package_share_directory('urdf_tutorial')
            yaml_path = os.path.join(share_dir, 'config', 'limb_sequence.yaml')

        self.get_logger().info(f'Loading sequence YAML: {yaml_path}')

        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)

        self.steps = data.get('sequence', [])
        if not self.steps:
            self.get_logger().error('YAML に "sequence" が定義されていません')
            raise RuntimeError('empty sequence')

        # time でソートしておく
        self.steps.sort(key=lambda s: float(s.get('time', 0.0)))

        # ==== limb ごとの publisher を準備 ====
        self.limb_publishers = {}  # limb_name -> Publisher(Float64MultiArray)

        for step in self.steps:
            limbs = step.get('limbs', {})
            for limb_name in limbs.keys():
                if limb_name in self.limb_publishers:
                    continue
                topic = f'/{limb_name}/goal'
                pub = self.create_publisher(Float64MultiArray, topic, 10)
                self.limb_publishers[limb_name] = pub
                self.get_logger().info(f'Advertise goal publisher: {topic}')

        # wheel / gripper attach 用
        self.pub_wheel   = self.create_publisher(Bool, '/wheel_attach', 10)
        self.pub_gripper = self.create_publisher(Bool, '/gripper_attach', 10)

        # 現在どの step まで実行したか
        self.current_step_index = -1
        self.start_time = self.get_clock().now()

        # 50ms ごとにシーケンスを進める
        self.timer = self.create_timer(0.05, self.on_timer)

    # =========================
    # タイマーコールバック
    # =========================
    def on_timer(self):
        now = self.get_clock().now()
        elapsed = (now - self.start_time).nanoseconds / 1e9

        # 経過時間に応じて実行すべき step を決定
        next_idx = self.current_step_index
        while (next_idx + 1) < len(self.steps) and \
                elapsed >= float(self.steps[next_idx + 1].get('time', 0.0)):
            next_idx += 1

        # まだ新しい step に進んでいなければ何もしない
        if next_idx == self.current_step_index:
            return

        # 新しい step に進む
        self.current_step_index = next_idx
        step = self.steps[self.current_step_index]
        self.get_logger().info(
            f'Executing step {self.current_step_index}: t={step.get("time", 0.0)}s'
        )

        # ---- limb の goal を publish ----
        limbs = step.get('limbs', {})
        for limb_name, pos_list in limbs.items():
            pub = self.limb_publishers.get(limb_name)
            if pub is None:
                self.get_logger().warn(
                    f'Publisher not found for limb "{limb_name}", skip.')
                continue

            try:
                # YAML から来たリストを必ず float のリストに変換
                pos = [float(x) for x in pos_list]
            except Exception as e:
                self.get_logger().error(
                    f'Invalid position list for limb "{limb_name}": '
                    f'{pos_list} ({e})'
                )
                continue

            msg = Float64MultiArray()
            msg.data = pos
            pub.publish(msg)

        # ---- wheel / gripper attach 制御 ----
        if 'wheel_attach' in step:
            self.pub_wheel.publish(Bool(data=bool(step['wheel_attach'])))
        if 'gripper_attach' in step:
            self.pub_gripper.publish(Bool(data=bool(step['gripper_attach'])))

        # 最終 step まで行ったら、あとはそのまま保持（終了は Ctrl+C）
        if self.current_step_index == len(self.steps) - 1:
            # 必要ならここで self.timer.cancel() しても良い
            pass


def main():
    rclpy.init()
    node = LimbSequencePlayer()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
