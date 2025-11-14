# urdf_tutorial/launch/limb_sequence.launch.py

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    # YAML ファイルのパス（デフォルトはパッケージ内 config/limb_sequence.yaml）
    yaml_path = LaunchConfiguration('yaml_path')
    rate_hz   = LaunchConfiguration('rate_hz')

    pkg_share = FindPackageShare('urdf_tutorial')
    default_yaml = PathJoinSubstitution([pkg_share, 'config', 'limb_sequence.yaml'])

    return LaunchDescription([
        DeclareLaunchArgument(
            'yaml_path',
            default_value=default_yaml,
            description='limb シーケンス定義の YAML ファイルパス'
        ),
        DeclareLaunchArgument(
            'rate_hz',
            default_value='10.0',
            description='シーケンスチェック周期 [Hz]'
        ),

        Node(
            package='urdf_tutorial',
            executable='limb_sequence_player.py',
            name='limb_sequence_player',
            output='screen',
            parameters=[{
                'yaml_path': yaml_path,
                'rate_hz': rate_hz,
            }],
        ),
    ])
