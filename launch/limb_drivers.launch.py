from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch.actions import TimerAction

def generate_launch_description():
    limb_csv = LaunchConfiguration('limb_names')
    rate_hz = LaunchConfiguration('rate_hz')
    speed = LaunchConfiguration('speed_rad_per_sec')
    init_csv = LaunchConfiguration('initial_positions')

    return LaunchDescription([
        DeclareLaunchArgument(
            'limb_names',
            default_value='limb_n_12,limb_n_13,limb_n_14',
            description='起動する limb 名のCSV（ネームスペースにも使用）'
        ),
        DeclareLaunchArgument('rate_hz', default_value='30.0'),
        DeclareLaunchArgument('speed_rad_per_sec', default_value='0.5'),
        DeclareLaunchArgument('initial_positions', default_value='0,0,0,0'),

        # Python から複数生成しづらいので、簡易: OpaqueFunction 不使用の一括起動例
        # → 実運用では必要な limb の数だけ launch を複製 or GroupActionで展開してください
        # ここでは3つを例示（必要に応じて増減/編集）
        Node(
            package='urdf_tutorial',
            executable='limb_trajectory_driver.py',
            namespace='limb_n_12',
            name='driver',
            output='screen',
            parameters=[{
                'limb_name': 'limb_n_12',
                'rate_hz': rate_hz,
                'speed_rad_per_sec': speed,
                'initial_positions': init_csv,
            }],
        ),
        Node(
            package='urdf_tutorial',
            executable='limb_trajectory_driver.py',
            namespace='limb_n_13',
            name='driver',
            output='screen',
            parameters=[{
                'limb_name': 'limb_n_13',
                'rate_hz': rate_hz,
                'speed_rad_per_sec': speed,
                'initial_positions': init_csv,
            }],
        ),
        Node(
            package='urdf_tutorial',
            executable='limb_trajectory_driver.py',
            namespace='limb_n_14',
            name='driver',
            output='screen',
            parameters=[{
                'limb_name': 'limb_n_14',
                'rate_hz': rate_hz,
                'speed_rad_per_sec': speed,
                'initial_positions': init_csv,
            }],
        ),
        

        TimerAction(
            period=5.0,
            actions=[
                Node(
                    package='urdf_tutorial',
                    executable='limb_goal_publisher.py',
                    name='goal_pub_12',
                    output='screen',
                    parameters=[{
                        'limb_name': 'limb_n_12',
                        'goal_positions': '0.5,-0.3,0.6,0.1',
                        'wait_sec': 0.5,
                    }],
                ),
            ]
        ),

    ])
