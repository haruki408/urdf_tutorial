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
    /wheel_on (std_msgs/Bool) を受けて xacro を再展開し、
    robot_state_publisher の robot_description を set_parameters で更新する。
    ・サービス呼び出しは非ブロッキング（done コールバック）
    ・GUI互換のため /robot_description をトピックでもラッチ配信（任意）
    ・xacro 側は <xacro:arg name="use_wheel" default="true"/> を想定
    """

    def __init__(self):
        super().__init__('model_switcher')

        # ---- パラメータ ----
        # xacro_path: 展開対象の .xacro の絶対パス or パッケージshareからの実パス
        self.declare_parameter('xacro_path', '')
        # rsp_node_name: 例) 'robot_state_publisher' / '/robot1/robot_state_publisher'
        self.declare_parameter('rsp_node_name', 'robot_state_publisher')
        # /robot_description をトピックでも配信するか（joint_state_publisher_gui互換）
        self.declare_parameter('publish_topic_robot_description', True)

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

        # ---- /wheel_on を購読（true=生成, false=非生成）----
        self.use_wheel = True  # 初期値（必要に応じ変更可）
        self.sub_wheel = self.create_subscription(Bool, '/wheel_on', self.on_wheel, 10)

        # ---- 初期適用のためにサービス準備を待つ ----
        self.wait_timer = self.create_timer(0.3, self._try_init_once)
        self.wait_elapsed = 0.0
        self.get_logger().info(f'waiting for service: {service_name}')

    # 初回だけ適用
    def _try_init_once(self):
        if self.cli.service_is_ready() or self.cli.wait_for_service(timeout_sec=0.3):
            self.wait_timer.cancel()
            self.get_logger().info(f'service ready: {self.cli.srv_name}')
            self._apply_xacro()  # 現在の self.use_wheel で適用
            return

        self.wait_elapsed += 0.3
        if self.wait_elapsed >= 10.0:
            self.wait_timer.cancel()
            # デバッグ用に候補を列挙
            names = [n.name for n in self.get_service_names_and_types() if n.name.endswith('set_parameters')]
            self.get_logger().error(f'サービスが見つかりません: {self.cli.srv_name} candidates={names}')

    def on_wheel(self, msg: Bool):
        new_val = bool(msg.data)
        if new_val == self.use_wheel:
            self.get_logger().info(f'wheel は既に {new_val}')
            return

        self.use_wheel = new_val
        if not (self.cli.service_is_ready() or self.cli.wait_for_service(timeout_sec=0.1)):
            self.get_logger().warn(f'service not ready: {self.cli.srv_name}')
            return
        self._apply_xacro()

    def _apply_xacro(self):
        """use_wheel を渡して xacro を展開 → robot_description を更新（非ブロッキング）"""
        try:
            cmd = [
                'xacro', self.xacro_path,
                f'use_wheel:={"true" if self.use_wheel else "false"}',
            ]
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

            def _on_done(fut):
                try:
                    res = fut.result()
                    if res is None:
                        self.get_logger().error('set_parameters 応答 None（タイムアウト/通信失敗）')
                        return
                    if any(r.successful for r in res.results):
                        self.get_logger().info(f'robot_description を更新しました use_wheel={self.use_wheel}')
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
    try:
        rclpy.spin(node)  # 非ブロッキング化しているので単スレッドでOK
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
