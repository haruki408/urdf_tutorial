#!/usr/bin/env python3
import os
import subprocess

import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from std_msgs.msg import Bool, String
from rcl_interfaces.srv import SetParameters
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy


class ModelSwitcher(Node):
    """
    /modelchange (std_msgs/Bool) を受けて xacro を再展開し、
    robot_state_publisher の robot_description を set_parameters で更新する。
    ・サービス呼び出しは非ブロッキング（done コールバック）で実行
    ・オプションで /robot_description をトピックでも Publish（GUI互換）
    """

    def __init__(self):
        super().__init__('model_switcher')

        # ---- パラメータ ----
        self.declare_parameter('xacro_path', '')
        self.declare_parameter('rsp_node_name', 'robot_state_publisher')  # 例: 'robot_state_publisher' or '/robot1/robot_state_publisher'
        self.declare_parameter('publish_topic_robot_description', True)   # GUI互換: /robot_description をトピック出力

        self.xacro_path = self.get_parameter('xacro_path').get_parameter_value().string_value
        self.rsp_name   = self.get_parameter('rsp_node_name').get_parameter_value().string_value
        self.pub_topic  = bool(self.get_parameter('publish_topic_robot_description').value)

        if not self.xacro_path or not os.path.exists(self.xacro_path):
            self.get_logger().error(f'xacro_path が不正です: {self.xacro_path}')

        # ---- robot_state_publisher の set_parameters サービス クライアント ----
        service_name = f'{self.rsp_name}/set_parameters'.replace('//', '/')
        self.cli = self.create_client(SetParameters, service_name)

        # ---- /robot_description（トピック）出力（GUIの“待ち”対策） ----
        self.desc_pub = None
        if self.pub_topic:
            self.desc_pub = self.create_publisher(
                String,
                '/robot_description',
                QoSProfile(
                    depth=1,
                    reliability=ReliabilityPolicy.RELIABLE,
                    durability=DurabilityPolicy.TRANSIENT_LOCAL  # ラッチ相当
                )
            )

        # ---- /modelchange を購読 ----
        self.sub = self.create_subscription(Bool, '/modelchange', self.on_toggle, 10)

        # ---- 初期適用のためにサービス準備を待つ ----
        self.current_use_alt = False
        self.wait_timer = self.create_timer(0.3, self._try_init_once)
        self.wait_elapsed = 0.0
        self.get_logger().info(f'waiting for service: {service_name}')

    # 1回だけ初期適用
    def _try_init_once(self):
        # 十分待つ（例: 最大10秒）
        if self.cli.service_is_ready() or self.cli.wait_for_service(timeout_sec=0.3):
            self.wait_timer.cancel()
            self.get_logger().info(f'service ready: {self.cli.srv_name}')
            self._apply_xacro(use_alt=False)  # 初期モデル
            return

        self.wait_elapsed += 0.3
        if self.wait_elapsed >= 10.0:
            self.wait_timer.cancel()
            # デバッグ用に候補を列挙
            names = [n.name for n in self.get_service_names_and_types() if n.name.endswith('set_parameters')]
            self.get_logger().error(f'サービスが見つかりません: {self.cli.srv_name} candidates={names}')

    def on_toggle(self, msg: Bool):
        if not (self.cli.service_is_ready() or self.cli.wait_for_service(timeout_sec=0.1)):
            self.get_logger().warn(f'service not ready: {self.cli.srv_name}')
            return
        use_alt = bool(msg.data)
        if use_alt == self.current_use_alt:
            self.get_logger().info(f'既に use_alt={use_alt}')
            return
        self._apply_xacro(use_alt)

    def _apply_xacro(self, use_alt: bool):
        """xacro を展開して robot_description を set_parameters（非ブロッキング）"""
        try:
            cmd = ['xacro', self.xacro_path, f'use_alt:={"true" if use_alt else "false"}']
            urdf_xml = subprocess.check_output(cmd).decode('utf-8')

            # 1) robot_state_publisher のパラメータ更新（非ブロッキング）
            param_msg = Parameter(
                name='robot_description',
                type_=Parameter.Type.STRING,
                value=urdf_xml
            ).to_parameter_msg()

            req = SetParameters.Request()
            req.parameters = [param_msg]
            future = self.cli.call_async(req)

            # 応答は done コールバックで処理（コールバック内でブロックしない）
            def _on_done(fut):
                try:
                    res = fut.result()
                    if res is None:
                        self.get_logger().error('set_parameters 応答 None（タイムアウト/通信失敗）')
                        return
                    if any(r.successful for r in res.results):
                        self.current_use_alt = use_alt
                        self.get_logger().info(f'robot_description を更新しました use_alt={use_alt}')
                    else:
                        self.get_logger().error('robot_description の更新が失敗ステータスでした')
                except Exception as e:
                    self.get_logger().error(f'set_parameters 応答処理エラー: {e}')

            future.add_done_callback(_on_done)

            # 2) GUI向けに /robot_description（トピック）も出す（任意）
            if self.desc_pub is not None:
                self.desc_pub.publish(String(data=urdf_xml))

        except subprocess.CalledProcessError as e:
            self.get_logger().error(f'xacro 実行エラー（returncode={e.returncode}）: {e.output}')
        except Exception as e:
            self.get_logger().error(f'xacro適用エラー: {e}')


def main():
    rclpy.init()
    node = ModelSwitcher()
    # 単スレッドでもOK（非ブロッキング化済み）。必要なら下の2行を有効化してマルチスレッドでも良い。
    # from rclpy.executors import MultiThreadedExecutor
    # executor = MultiThreadedExecutor(); executor.add_node(node); executor.spin()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
