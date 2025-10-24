from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch.substitutions import Command

def generate_launch_description():
    pkg = FindPackageShare('urdf_tutorial')
    xacro_rel = LaunchConfiguration('xacro_rel', default='xacro/palette.xacro')
    xacro_path = PathJoinSubstitution([pkg, xacro_rel])

    # RViz の設定ファイル（.rviz）をパッケージ内の既定に
    rviz_config = PathJoinSubstitution([pkg, 'rviz', 'urdf.rviz'])

    return LaunchDescription([
        DeclareLaunchArgument(
            'xacro_rel',
            default_value='xacro/palette.xacro',
            description='urdf_tutorial share からの相対パス'
        ),

        # 初期ロボット記述（wheel_on版に合わせて use_wheel を渡す）
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            parameters=[{
                'robot_description': Command(['xacro ', xacro_path, ' use_wheel:=true'])
            }]
        ),

        Node(package='joint_state_publisher_gui', executable='joint_state_publisher_gui'),

        # ★ RViz に .rviz を指定して起動
        Node(
            package='rviz2',
            executable='rviz2',
            output='screen',
            arguments=['-d', rviz_config]
        ),

        # /wheel_on を受けて robot_description を差し替えるノード
        Node(
            package='urdf_tutorial',
            executable='model_switcher.py',
            name='model_switcher',
            output='screen',
            parameters=[{
                'xacro_path': xacro_path,
                'rsp_node_name': 'robot_state_publisher',
                'publish_topic_robot_description': True
            }]
        ),
    ])
