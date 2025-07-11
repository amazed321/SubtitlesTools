import os
import math
import subprocess
import json
import re
import time
from typing import List, Dict
from openai import OpenAI
from .subtitle_translator import SubtitleTranslator


class AudioTranslator:
    def __init__(self, api_key: str):
        """音频转字幕翻译器"""
        self.client = OpenAI(api_key=api_key)
        self.subtitle_translator = SubtitleTranslator()
        self._setup_ffmpeg_path()

    def _setup_ffmpeg_path(self):
        """设置FFmpeg路径"""
        # 获取当前脚本所在目录的ffmpeg路径
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ffmpeg_bin = os.path.join(current_dir, "ffmpeg", "bin")

        if os.path.exists(ffmpeg_bin) and ffmpeg_bin not in os.environ.get('PATH', ''):
            os.environ['PATH'] = ffmpeg_bin + os.pathsep + os.environ.get('PATH', '')
            print(f"设置FFmpeg路径: {ffmpeg_bin}")

    def check_ffmpeg(self):
        """检查FFmpeg是否可用"""
        try:
            result = subprocess.run(['ffmpeg', '-version'],
                                    capture_output=True, text=True,
                                    encoding='utf-8', errors='ignore', timeout=10)
            return result.returncode == 0
        except Exception as e:
            print(f"检查FFmpeg失败: {e}")
            return False

    def get_video_duration(self, video_path: str) -> float:
        """获取视频时长"""
        cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', video_path]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True,
                                    encoding='utf-8', errors='ignore', timeout=30)
            if result.returncode != 0:
                print(f"获取视频时长失败，返回码: {result.returncode}")
                return None

            if not result.stdout.strip():
                print("ffprobe未返回视频格式信息")
                return None

            info = json.loads(result.stdout)
            duration = info.get('format', {}).get('duration')
            if duration:
                return float(duration)
            else:
                print("无法从视频信息中获取时长")
                return None

        except json.JSONDecodeError as e:
            print(f"解析视频信息JSON时出错: {e}")
            return None
        except Exception as e:
            print(f"获取视频时长失败: {e}")
            return None

    def extract_audio_chunks(self, video_path: str, chunk_duration: int = 180) -> List[Dict]:
        """提取音频分段"""
        total_duration = self.get_video_duration(video_path)
        if not total_duration:
            print("无法获取视频时长")
            return []

        # 创建临时音频目录
        output_dir = "temp_audio"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        num_chunks = math.ceil(total_duration / chunk_duration)
        audio_chunks = []

        print(f"视频总时长: {total_duration:.1f}秒，将分割为 {num_chunks} 段")

        for i in range(num_chunks):
            start_time = i * chunk_duration
            end_time = min((i + 1) * chunk_duration, total_duration)
            duration = end_time - start_time

            chunk_path = os.path.join(output_dir, f"chunk_{i:03d}.mp3")

            cmd = [
                'ffmpeg', '-i', video_path,
                '-ss', str(start_time), '-t', str(duration),
                '-vn', '-acodec', 'mp3', '-ar', '16000', '-ac', '1',
                '-y', chunk_path
            ]

            try:
                print(f"提取音频段 {i + 1}/{num_chunks}: {start_time:.1f}s - {end_time:.1f}s")
                result = subprocess.run(cmd, capture_output=True, text=True,
                                        encoding='utf-8', errors='ignore', timeout=60)

                if result.returncode == 0 and os.path.exists(chunk_path):
                    file_size = os.path.getsize(chunk_path)
                    if file_size > 1000:  # 文件大小大于1KB才认为有效
                        audio_chunks.append({
                            'path': chunk_path,
                            'start_time': start_time,
                            'end_time': end_time,
                            'chunk_index': i
                        })
                    else:
                        print(f"  音频段 {i + 1} 文件过小，跳过")
                        if os.path.exists(chunk_path):
                            os.remove(chunk_path)
                else:
                    print(f"  音频段 {i + 1} 提取失败，返回码: {result.returncode}")
                    if result.stderr:
                        print(f"  错误信息: {result.stderr}")

            except Exception as e:
                print(f"提取音频段 {i + 1} 失败: {e}")
                continue

        print(f"成功提取 {len(audio_chunks)} 个有效音频段")
        return audio_chunks

    def transcribe_audio_chunk(self,audio_model:str, audio_path: str, chunk_start_time: float) -> List[Dict]:
        """转录单个音频段"""
        try:
            with open(audio_path, "rb") as audio_file:
                transcription = self.client.audio.transcriptions.create(
                    model=audio_model,
                    file=audio_file,
                    response_format="verbose_json",
                    timestamp_granularities=["segment"]
                )

                segments = []
                if hasattr(transcription, 'segments') and transcription.segments:
                    for segment in transcription.segments:
                        start_time = chunk_start_time + segment.start
                        end_time = chunk_start_time + segment.end
                        text = segment.text.strip()

                        if text:
                            segments.append({
                                'start_time': start_time,
                                'end_time': end_time,
                                'text': text
                            })

                return segments

        except Exception as e:
            print(f"转录音频失败: {e}")
            return []

    def detect_embedded_subtitles(self, video_path: str) -> List[Dict]:
        """检测视频内封字幕"""
        cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', video_path]

        try:
            # 明确指定编码方式避免Windows编码问题
            result = subprocess.run(cmd, capture_output=True, text=True,
                                    encoding='utf-8', errors='ignore', timeout=30)

            if result.returncode != 0:
                print(f"ffprobe执行失败，返回码: {result.returncode}")
                if result.stderr:
                    print(f"错误信息: {result.stderr}")
                return []

            if not result.stdout.strip():
                print("ffprobe未返回任何输出")
                return []

            info = json.loads(result.stdout)
            subtitle_streams = []

            for stream in info.get('streams', []):
                if stream.get('codec_type') == 'subtitle':
                    subtitle_streams.append({
                        'index': stream.get('index'),
                        'language': stream.get('tags', {}).get('language', 'unknown'),
                        'codec': stream.get('codec_name', 'unknown'),
                        'title': stream.get('tags', {}).get('title', '')
                    })

            return subtitle_streams

        except json.JSONDecodeError as e:
            print(f"解析JSON时出错: {e}")
            print(f"ffprobe输出: {result.stdout[:500] if 'result' in locals() else 'N/A'}")
            return []
        except Exception as e:
            print(f"检测内封字幕时出错: {e}")
            return []

    def extract_embedded_subtitles(self, video_path: str, output_path: str = None) -> str:
        """提取内封字幕为SRT文件"""
        subtitle_streams = self.detect_embedded_subtitles(video_path)

        if not subtitle_streams:
            print("未检测到内封字幕")
            return None

        print(f"检测到 {len(subtitle_streams)} 个字幕流")
        for i, stream in enumerate(subtitle_streams):
            lang = stream['language']
            codec = stream['codec']
            title = stream['title']
            print(f"  {i + 1}. 语言: {lang}, 编码: {codec}, 标题: {title}")

        # 选择第一个字幕流
        selected_stream = subtitle_streams[0]
        stream_index = selected_stream['index']

        # 设置输出路径
        if not output_path:
            base_name = os.path.splitext(os.path.basename(video_path))[0]
            output_path = f"temp_{base_name}_extracted.srt"

        # 提取字幕 - 使用流的绝对索引
        cmd = [
            'ffmpeg', '-i', video_path,
            '-map', f'0:{stream_index}',  # 使用绝对流索引而不是字幕流索引
            '-c:s', 'srt',
            '-y', output_path
        ]

        try:
            print(f"正在提取内封字幕...")
            result = subprocess.run(cmd, capture_output=True, text=True,
                                    encoding='utf-8', errors='ignore', timeout=60)

            if result.returncode == 0 and os.path.exists(output_path):
                # 检查生成的文件是否有内容
                if os.path.getsize(output_path) > 0:
                    print("内封字幕提取成功")
                    return output_path
                else:
                    print("字幕文件为空")
                    if os.path.exists(output_path):
                        os.remove(output_path)
                    return None
            else:
                print(f"字幕提取失败，返回码: {result.returncode}")
                if result.stderr:
                    print(f"错误信息: {result.stderr}")
                return None

        except Exception as e:
            print(f"提取字幕时出错: {e}")
            return None

    def seconds_to_srt_time(self, seconds: float) -> str:
        """将秒数转换为SRT时间格式"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        milliseconds = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"

    def segments_to_srt_format(self, segments: List[Dict]) -> List[Dict]:
        """将转录段落转换为SRT格式"""
        srt_subtitles = []

        for i, segment in enumerate(segments, 1):
            start_time = self.seconds_to_srt_time(segment['start_time'])
            end_time = self.seconds_to_srt_time(segment['end_time'])

            srt_subtitles.append({
                'index': i,
                'timeline': f"{start_time} --> {end_time}",
                'text': segment['text']
            })

        return srt_subtitles

    def cleanup_temp_files(self, audio_chunks: List[Dict]):
        """清理临时文件"""
        try:
            for chunk_info in audio_chunks:
                if os.path.exists(chunk_info['path']):
                    os.remove(chunk_info['path'])

            temp_dir = "temp_audio"
            if os.path.exists(temp_dir) and not os.listdir(temp_dir):
                os.rmdir(temp_dir)

        except Exception as e:
            print(f"清理临时文件时出错: {e}")


def generate_subtitles(video_path: str, api_key: str, text_models:str,audio_models:str, output_path: str = "output",
                       mode: str = "auto", translation_type: str = "双语",
                       batch_size: int = 10, batch_min: int = 3) -> str:
    """
    生成视频字幕并翻译

    Args:
        video_path: 视频文件路径
        api_key: OpenAI API密钥
        output_path: 输出文件夹路径
        mode: 处理模式 ("auto" 或 "翻译内")
        translation_type: 翻译类型 ("双语", "英文", "中文")
        batch_size: 批量翻译大小
        batch_min: 最小批量大小

    Returns:
        生成的字幕文件路径，失败返回 None
    """

    # 检查视频文件是否存在
    if not os.path.exists(video_path):
        print(f"视频文件不存在: {video_path}")
        return None

    # 创建翻译器
    translator = AudioTranslator(api_key)

    # 检查FFmpeg
    if not translator.check_ffmpeg():
        print("FFmpeg不可用，请检查安装")
        return None

    # 确保输出目录存在
    os.makedirs(output_path, exist_ok=True)

    # 生成输出文件名
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    output_file = os.path.join(output_path, f"{video_name}_{translation_type}_audio.srt")

    try:
        if mode == "只翻内封":
            # 模式1: 翻译内封字幕
            print("🔍 模式: 翻译内封字幕")

            # 检测内封字幕
            embedded_subs = translator.detect_embedded_subtitles(video_path)
            if not embedded_subs:
                print("未检测到内封字幕，无法使用此模式")
                return "未检测到内封字幕，无法使用此模式"

            # 提取内封字幕
            temp_srt = translator.extract_embedded_subtitles(video_path)
            if not temp_srt:
                print("内封字幕提取失败")
                return "内封字幕提取失败"

            # 解析SRT文件
            subtitles = translator.subtitle_translator.parse_srt(open(temp_srt, 'r', encoding='utf-8').read())
            if not subtitles:
                print("字幕解析失败")
                # 清理临时文件
                if os.path.exists(temp_srt):
                    os.remove(temp_srt)
                return "字幕解析失败"

            print(f"成功解析 {len(subtitles)} 条字幕")

            # 翻译字幕
            print("🌐 开始翻译字幕...")

            # 提取文本进行翻译
            texts = [sub['text'] for sub in subtitles]

            # 分批翻译
            translated_texts = []
            total_batches = (len(texts) + batch_size - 1) // batch_size

            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                current_batch = i // batch_size + 1

                print(f"正在翻译第 {current_batch}/{total_batches} 批次，包含 {len(batch_texts)} 条字幕...")

                # 使用我们之前写的翻译函数
                if len(batch_texts) >= batch_min:
                    translated_batch = translator.subtitle_translator.translate_texts_batch(
                        api_key=api_key,
                        model=text_models,
                        texts=batch_texts,
                        translation_type=translation_type
                    )
                else:
                    # 如果批次太小，逐条翻译
                    translated_batch = translator.subtitle_translator._translate_one_by_one(
                        api_key=api_key,
                        model=text_models,
                        texts=batch_texts,
                        translation_type=translation_type,
                        max_retries=3
                    )

                translated_texts.extend(translated_batch)
                time.sleep(0.5)  # 避免API请求过频

            # 格式化翻译结果
            for i, subtitle in enumerate(subtitles):
                if i < len(translated_texts):
                    formatted_text = translator.subtitle_translator.format_translated_subtitle(
                        subtitle['text'], translated_texts[i], translation_type
                    )
                    subtitle['text'] = formatted_text

            # 生成SRT文件
            srt_content = translator.subtitle_translator.generate_srt(subtitles)

            # 清理临时文件
            if os.path.exists(temp_srt):
                os.remove(temp_srt)

        elif mode == "auto":
            # 模式2: 自动选择最佳方式
            print("🤖 模式: 自动选择")

            # 先检查是否有内封字幕
            embedded_subs = translator.detect_embedded_subtitles(video_path)

            if embedded_subs:
                print("检测到内封字幕，优先使用内封字幕翻译")
                # 递归调用翻译内封字幕模式
                return generate_subtitles(
                    video_path=video_path,
                    api_key=api_key,
                    output_path=output_path,
                    mode="只翻内封",
                    translation_type=translation_type,
                    batch_size=batch_size,
                    batch_min=batch_min
                )

            # 没有内封字幕，使用语音转录
            print("未检测到内封字幕，使用语音转录模式")
            print("🎤 开始语音转录...")

            # 提取音频分段
            audio_chunks = translator.extract_audio_chunks(video_path, chunk_duration=180)
            if not audio_chunks:
                print("音频提取失败")
                return None

            # 转录所有音频段，保持分段结构
            audio_segments_groups = []
            for i, chunk_info in enumerate(audio_chunks):
                print(f"🎤 转录第 {i + 1}/{len(audio_chunks)} 段...")

                segments = translator.transcribe_audio_chunk(
                    audio_models,
                    chunk_info['path'],
                    chunk_info['start_time'],

                )

                if segments:
                    audio_segments_groups.append(segments)
                    print(f"  获得 {len(segments)} 个语音段落")
                else:
                    print("  该段无语音内容")
                    audio_segments_groups.append([])  # 保持分组结构

            # 检查是否有有效的转录结果
            total_segments = sum(len(group) for group in audio_segments_groups)
            if total_segments == 0:
                print("未获得任何转录结果")
                translator.cleanup_temp_files(audio_chunks)
                return None

            print(f"转录完成，共获得 {total_segments} 个语音段落，分布在 {len(audio_segments_groups)} 个音频段中")

            # 翻译转录结果 - 按音频段分批翻译
            print("🌐 开始翻译转录文本...")

            translated_segments_groups = []

            for i, segments_group in enumerate(audio_segments_groups):
                if not segments_group:  # 跳过空的分组
                    translated_segments_groups.append([])
                    continue

                print(f"正在翻译第 {i + 1}/{len(audio_segments_groups)} 个音频段，包含 {len(segments_group)} 条字幕...")

                # 提取当前音频段的文本
                texts = [segment['text'] for segment in segments_group]

                # 判断是否需要批量翻译还是逐条翻译
                if len(texts) >= batch_min:
                    translated_texts = translator.subtitle_translator.translate_texts_batch(
                        api_key=api_key,
                        model=text_models,
                        texts=texts,
                        translation_type=translation_type
                    )
                else:
                    translated_texts = translator.subtitle_translator._translate_one_by_one(
                        api_key=api_key,
                        model=text_models,
                        texts=texts,
                        translation_type=translation_type,
                        max_retries=3
                    )

                # 格式化翻译结果并保存
                translated_segments = []
                for j, segment in enumerate(segments_group):
                    if j < len(translated_texts):
                        formatted_text = translator.subtitle_translator.format_translated_subtitle(
                            segment['text'], translated_texts[j], translation_type
                        )

                        translated_segment = segment.copy()
                        translated_segment['text'] = formatted_text
                        translated_segments.append(translated_segment)

                translated_segments_groups.append(translated_segments)
                time.sleep(0.5)  # 避免API请求过频

            # 合并所有翻译后的段落
            all_translated_segments = []
            for group in translated_segments_groups:
                all_translated_segments.extend(group)

            # 转换为SRT格式
            srt_subtitles = translator.segments_to_srt_format(all_translated_segments)

            # 生成SRT内容
            srt_content = translator.subtitle_translator.generate_srt(srt_subtitles)

            # 清理临时文件
            translator.cleanup_temp_files(audio_chunks)

        elif mode == "只翻音频":
            audio_chunks = translator.extract_audio_chunks(video_path, chunk_duration=180)
            if not audio_chunks:
                print("音频提取失败")
                return None

            # 转录所有音频段，保持分段结构
            audio_segments_groups = []
            for i, chunk_info in enumerate(audio_chunks):
                print(f"🎤 转录第 {i + 1}/{len(audio_chunks)} 段...")

                segments = translator.transcribe_audio_chunk(
                    audio_models,
                    chunk_info['path'],
                    chunk_info['start_time']
                )

                if segments:
                    audio_segments_groups.append(segments)
                    print(f"  获得 {len(segments)} 个语音段落")
                else:
                    print("  该段无语音内容")
                    audio_segments_groups.append([])  # 保持分组结构

            # 检查是否有有效的转录结果
            total_segments = sum(len(group) for group in audio_segments_groups)
            if total_segments == 0:
                print("未获得任何转录结果")
                translator.cleanup_temp_files(audio_chunks)
                return None

            print(f"转录完成，共获得 {total_segments} 个语音段落，分布在 {len(audio_segments_groups)} 个音频段中")

            # 翻译转录结果 - 按音频段分批翻译
            print("🌐 开始翻译转录文本...")

            translated_segments_groups = []

            for i, segments_group in enumerate(audio_segments_groups):
                if not segments_group:  # 跳过空的分组
                    translated_segments_groups.append([])
                    continue

                print(f"正在翻译第 {i + 1}/{len(audio_segments_groups)} 个音频段，包含 {len(segments_group)} 条字幕...")

                # 提取当前音频段的文本
                texts = [segment['text'] for segment in segments_group]

                # 判断是否需要批量翻译还是逐条翻译
                if len(texts) >= batch_min:
                    translated_texts = translator.subtitle_translator.translate_texts_batch(
                        api_key=api_key,
                        model=text_models,
                        texts=texts,
                        translation_type=translation_type
                    )
                else:
                    translated_texts = translator.subtitle_translator._translate_one_by_one(
                        api_key=api_key,
                        model=text_models,
                        texts=texts,
                        translation_type=translation_type,
                        max_retries=3
                    )

                # 格式化翻译结果并保存
                translated_segments = []
                for j, segment in enumerate(segments_group):
                    if j < len(translated_texts):
                        formatted_text = translator.subtitle_translator.format_translated_subtitle(
                            segment['text'], translated_texts[j], translation_type
                        )

                        translated_segment = segment.copy()
                        translated_segment['text'] = formatted_text
                        translated_segments.append(translated_segment)

                translated_segments_groups.append(translated_segments)
                time.sleep(0.5)  # 避免API请求过频

            # 合并所有翻译后的段落
            all_translated_segments = []
            for group in translated_segments_groups:
                all_translated_segments.extend(group)

            # 转换为SRT格式
            srt_subtitles = translator.segments_to_srt_format(all_translated_segments)

            # 生成SRT内容
            srt_content = translator.subtitle_translator.generate_srt(srt_subtitles)

            # 清理临时文件
            translator.cleanup_temp_files(audio_chunks)

        else:
            print(mode)
            return {'error':'没有这个选项'}

        # 写入文件
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(srt_content)

        print(f"✅ 字幕生成成功: {output_file}")
        return output_file

    except Exception as e:
        print(f"❌ 生成字幕时出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return None