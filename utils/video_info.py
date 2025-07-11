import os
import json
import subprocess
from pathlib import Path

# 将字幕文件内嵌到视频中
def embed_subtitles(video_path, subtitle_files, output_path, preserve_ass_styles=True):
    print(subtitle_files)
    """
    将字幕文件内嵌到视频中

    Args:
        video_path (str): 视频文件路径
        subtitle_files (list): 字幕文件信息列表，每个元素是字典格式:
            [
                {
                    "path": "字幕文件路径",
                    "language": "语言代码（如 chi, eng, jpn 等）",
                    "title": "字幕标题"
                },
                ...
            ]
        output_path (str): 输出文件夹路径
        preserve_ass_styles (bool): 是否保持ASS字幕样式，默认True

    Returns:
        dict: 包含操作结果的字典
    """
    try:
        # 检查视频文件是否存在
        if not os.path.exists(video_path):
            return {"success": False, "error": f"视频文件不存在: {video_path}"}

        # 检查字幕文件列表
        if not subtitle_files:
            return {"success": False, "error": "字幕文件列表为空"}

        # 检查字幕文件格式和存在性
        for i, sub_info in enumerate(subtitle_files):
            if not isinstance(sub_info, dict):
                return {"success": False, "error": f"字幕文件 {i + 1} 格式错误，应为字典格式"}

            if "path" not in sub_info:
                return {"success": False, "error": f"字幕文件 {i + 1} 缺少 'path' 字段"}

            sub_path = sub_info["path"]
            if not os.path.exists(sub_path):
                return {"success": False, "error": f"字幕文件不存在: {sub_path}"}

        # 检查输出路径
        if not output_path:
            return {"success": False, "error": "输出文件夹路径不能为空"}

        # 获取ffmpeg的相对路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        ffmpeg_path = os.path.join(project_root, "ffmpeg", "bin", "ffmpeg.exe")

        # 检查ffmpeg是否存在
        if not os.path.exists(ffmpeg_path):
            return {"success": False, "error": f"ffmpeg不存在: {ffmpeg_path}"}

        # 确保输出目录存在
        if not os.path.exists(output_path):
            try:
                os.makedirs(output_path, exist_ok=True)
            except Exception as e:
                return {"success": False, "error": f"无法创建输出目录: {e}"}

        # 生成输出文件路径 - 保持原始格式
        video_name = os.path.splitext(os.path.basename(video_path))[0]
        video_ext = os.path.splitext(video_path)[1]  # 获取原始扩展名
        output_file_path = os.path.join(output_path, f"{video_name}_with_subtitles{video_ext}")

        # 根据视频格式选择合适的字幕编码
        # 检查是否有ASS字幕文件
        has_ass_subtitles = any(sub_info["path"].lower().endswith('.ass') for sub_info in subtitle_files)

        # 根据容器格式和字幕类型选择编码方式
        if preserve_ass_styles and video_ext.lower() in ['.mkv', '.avi', '.mov'] and has_ass_subtitles:
            # MKV/AVI/MOV容器且有ASS字幕，保持ASS格式以保留样式
            subtitle_codec = "ass"
        elif video_ext.lower() == '.mp4':
            # MP4容器使用mov_text
            subtitle_codec = "mov_text"
        else:
            # 其他情况使用srt格式
            subtitle_codec = "srt"

        # 构建ffmpeg命令
        cmd = [ffmpeg_path]

        # 添加视频输入
        cmd.extend(["-i", video_path])

        # 添加所有字幕文件作为输入
        for sub_info in subtitle_files:
            cmd.extend(["-i", sub_info["path"]])

        # 映射视频和音频流
        cmd.extend(["-map", "0"])  # 映射第一个输入的所有流（视频+音频）

        # 映射字幕流并设置元数据
        for i, sub_info in enumerate(subtitle_files):
            cmd.extend(["-map", f"{i + 1}"])  # 映射每个字幕文件

            # 设置语言元数据
            if sub_info.get("language"):
                cmd.extend([f"-metadata:s:s:{i}", f"language={sub_info['language']}"])

            # 设置标题元数据
            if sub_info.get("title"):
                cmd.extend([f"-metadata:s:s:{i}", f"title={sub_info['title']}"])

        # 编码设置
        cmd.extend(["-c", "copy"])  # 复制所有流
        cmd.extend(["-c:s", subtitle_codec])  # 根据格式选择字幕编码

        # 如果是ASS字幕且容器支持，额外设置一些参数
        if subtitle_codec == "ass":
            # 保持ASS字幕的原始样式
            cmd.extend(["-disposition:s", "default"])  # 设置第一个字幕为默认

        # 静默模式，减少输出信息
        cmd.extend(["-loglevel", "error"])

        # 输出设置
        cmd.extend(["-y", output_file_path])  # 覆盖输出文件

        # 执行命令（静默模式）
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')

        if result.returncode != 0:
            return {
                "success": False,
                "error": f"ffmpeg执行失败: {result.stderr}",
                "command": " ".join(cmd)
            }

        # 检查输出文件是否创建成功
        if not os.path.exists(output_file_path):
            return {"success": False, "error": "输出文件未创建成功"}

        return {
            "success": True,
            "input_video": video_path,
            "subtitle_files": subtitle_files,
            "output_folder": output_path,
            "output_video": output_file_path,
            "output_size": os.path.getsize(output_file_path),
            "subtitle_codec": subtitle_codec,
            "preserve_ass_styles": preserve_ass_styles
        }

    except Exception as e:
        return {"success": False, "error": f"内嵌字幕时出错: {str(e)}"}

# 获取视频文件的详细信息
def get_video_info(video_path):
    """
    获取视频文件的详细信息

    Args:
        video_path (str): 视频文件路径

    Returns:
        dict: 包含视频详细信息的字典
    """
    try:
        # 检查视频文件是否存在
        if not os.path.exists(video_path):
            return {"error": f"视频文件不存在: {video_path}"}

        # 获取ffprobe的相对路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        ffprobe_path = os.path.join(project_root, "ffmpeg", "bin", "ffprobe.exe")

        # 检查ffprobe是否存在
        if not os.path.exists(ffprobe_path):
            return {"error": f"ffprobe不存在: {ffprobe_path}"}

        # 构建ffprobe命令
        cmd = [
            ffprobe_path,
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            video_path
        ]

        # 执行命令
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')

        if result.returncode != 0:
            return {"error": f"ffprobe执行失败: {result.stderr}"}

        # 解析JSON输出
        probe_data = json.loads(result.stdout)

        # 提取视频流信息
        video_stream = None
        subtitle_streams = []

        for stream in probe_data.get('streams', []):
            if stream.get('codec_type') == 'video':
                video_stream = stream
            elif stream.get('codec_type') == 'subtitle':
                subtitle_streams.append(stream)

        if not video_stream:
            return {"error": "未找到视频流"}

        # 获取格式信息
        format_info = probe_data.get('format', {})

        # 计算视频帧率（每秒帧数）
        fps = 'Unknown'
        if video_stream.get('r_frame_rate'):
            try:
                # r_frame_rate格式通常是 "30/1" 或 "2997/100"
                fps_parts = video_stream.get('r_frame_rate').split('/')
                if len(fps_parts) == 2:
                    fps = round(float(fps_parts[0]) / float(fps_parts[1]), 2)
            except:
                fps = 'Unknown'

        # 提取视频信息
        video_info = {
            "video_name": os.path.basename(video_path),
            "video_size": format_info.get('size', 'Unknown'),
            "video_duration": format_info.get('duration', 'Unknown'),
            "video_path": os.path.abspath(video_path),
            "video_format": format_info.get('format_name', 'Unknown'),
            "video_codec": video_stream.get('codec_name', 'Unknown'),
            "video_resolution": f"{video_stream.get('width', 'Unknown')}x{video_stream.get('height', 'Unknown')}",
            "video_bitrate": format_info.get('bit_rate', 'Unknown'),
            "video_fps": fps,  # 每秒帧数
            "embedded_subtitles": []  # 内嵌字幕列表
        }

        # 格式化一些数据
        # 转换文件大小为更易读的格式
        if video_info["video_size"] != 'Unknown':
            try:
                size_bytes = int(video_info["video_size"])
                if size_bytes < 1024:
                    video_info["video_size_formatted"] = f"{size_bytes} B"
                elif size_bytes < 1024 * 1024:
                    video_info["video_size_formatted"] = f"{size_bytes / 1024:.2f} KB"
                elif size_bytes < 1024 * 1024 * 1024:
                    video_info["video_size_formatted"] = f"{size_bytes / (1024 * 1024):.2f} MB"
                else:
                    video_info["video_size_formatted"] = f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
            except:
                video_info["video_size_formatted"] = "Unknown"

        # 格式化时长
        if video_info["video_duration"] != 'Unknown':
            try:
                duration_seconds = float(video_info["video_duration"])
                hours = int(duration_seconds // 3600)
                minutes = int((duration_seconds % 3600) // 60)
                seconds = int(duration_seconds % 60)
                video_info["video_duration_formatted"] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            except:
                video_info["video_duration_formatted"] = "Unknown"

        # 格式化码率为 Mbps
        if video_info["video_bitrate"] != 'Unknown':
            try:
                bitrate_bps = int(video_info["video_bitrate"])
                video_info["video_bitrate_formatted"] = f"{bitrate_bps / 1000000:.2f} Mbps"
            except:
                video_info["video_bitrate_formatted"] = "Unknown"

        # 处理内嵌字幕信息
        if subtitle_streams:
            for sub_stream in subtitle_streams:

                sub_info = {
                    "index": sub_stream.get('index', 0),
                    "codec": sub_stream.get('codec_name', 'Unknown'),
                    "language": sub_stream.get('tags', {}).get('language', 'Unknown'),
                    "title": sub_stream.get('tags', {}).get('title', 'Unknown')
                }
                video_info["embedded_subtitles"].append(sub_info)

        return video_info

    except Exception as e:
        return {"error": f"获取视频信息时出错: {str(e)}"}

# 式化视频信息为易读的字符串
def format_video_info(video_info):
    """
    格式化视频信息为易读的字符串

    Args:
        video_info (dict): 视频信息字典

    Returns:
        str: 格式化后的视频信息字符串
    """
    if "error" in video_info:
        return f"错误: {video_info['error']}"

    formatted_info = f"""
视频信息:
========================================
视频名称: {video_info.get('video_name', 'Unknown')}
视频大小: {video_info.get('video_size_formatted', video_info.get('video_size', 'Unknown'))}
视频时长: {video_info.get('video_duration_formatted', video_info.get('video_duration', 'Unknown'))}
视频路径: {video_info.get('video_path', 'Unknown')}
视频格式: {video_info.get('video_format', 'Unknown')}
视频编码: {video_info.get('video_codec', 'Unknown')}
视频分辨率: {video_info.get('video_resolution', 'Unknown')}
视频码率: {video_info.get('video_bitrate_formatted', video_info.get('video_bitrate', 'Unknown'))}
视频帧率: {video_info.get('video_fps', 'Unknown')} fps
内嵌字幕: {len(video_info.get('embedded_subtitles', []))} 个
"""

    if video_info.get('embedded_subtitles', []):
        formatted_info += "\n字幕详情:\n"
        for i, sub_info in enumerate(video_info['embedded_subtitles']):
            formatted_info += f"  字幕轨道 {i + 1}: {sub_info.get('codec', 'Unknown')} | "
            formatted_info += f"语言: {sub_info.get('language', 'Unknown')} | "
            formatted_info += f"标题: {sub_info.get('title', 'Unknown')}\n"

    return formatted_info