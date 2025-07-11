import json
import os
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any


class ASSConverter:
    def __init__(self, config_path: str = "config/ass_config.json"):
        """
        初始化ASS转换器

        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"配置文件 {self.config_path} 未找到")
        except json.JSONDecodeError:
            raise ValueError("配置文件格式错误")

    def get_style_list(self) -> List[str]:
        """
        获取所有可用的样式名称

        Returns:
            样式名称列表
        """
        return list(self.config.get("styles", {}).keys())

    def get_style_names(self) -> List[str]:
        """
        获取所有样式的内部名称

        Returns:
            样式内部名称列表
        """
        styles = self.config.get("styles", {})
        return [style_config.get("name", key) for key, style_config in styles.items()]

    def _parse_srt_time(self, time_str: str) -> str:
        """
        将SRT时间格式转换为ASS时间格式
        SRT: 00:00:01,000 -> ASS: 0:00:01.00

        Args:
            time_str: SRT格式的时间字符串

        Returns:
            ASS格式的时间字符串
        """
        # 将逗号替换为点，并去掉最后一位毫秒
        time_str = time_str.replace(',', '.')
        # 移除小时前的0和毫秒的最后一位
        parts = time_str.split(':')
        hour = str(int(parts[0]))  # 移除前导0
        minute = parts[1]
        sec_ms = parts[2]
        if '.' in sec_ms:
            sec, ms = sec_ms.split('.')
            ms = ms[:2]  # 只取前两位毫秒
            return f"{hour}:{minute}:{sec}.{ms}"
        return f"{hour}:{minute}:{sec_ms}.00"

    def _parse_srt_file(self, srt_path: str) -> List[Dict[str, str]]:
        """
        解析SRT文件

        Args:
            srt_path: SRT文件路径

        Returns:
            字幕数据列表
        """
        subtitles = []

        try:
            with open(srt_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # 尝试其他编码
            try:
                with open(srt_path, 'r', encoding='gbk') as f:
                    content = f.read()
            except UnicodeDecodeError:
                with open(srt_path, 'r', encoding='latin-1') as f:
                    content = f.read()

        # 分割字幕块
        blocks = re.split(r'\n\s*\n', content.strip())

        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) < 3:
                continue

            # 解析时间行
            time_match = re.match(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', lines[1])
            if not time_match:
                continue

            start_time = self._parse_srt_time(time_match.group(1))
            end_time = self._parse_srt_time(time_match.group(2))

            # 合并字幕文本
            text = '\\N'.join(lines[2:])  # ASS中用\N表示换行

            subtitles.append({
                'start': start_time,
                'end': end_time,
                'text': text
            })

        return subtitles

    def _generate_ass_header(self, styles: List[str]) -> str:
        """
        生成ASS文件头部

        Args:
            styles: 使用的样式名称列表

        Returns:
            ASS文件头部字符串
        """
        header = "[Script Info]\n"
        header += "Title: 转换自SRT字幕\n"
        header += "ScriptType: v4.00+\n"
        header += "WrapStyle: 0\n"
        header += "ScaledBorderAndShadow: yes\n"
        header += "YCbCr Matrix: TV.709\n"
        header += "PlayResX: 1920\n"
        header += "PlayResY: 1080\n\n"

        header += "[V4+ Styles]\n"
        header += "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"

        # 添加选中的样式
        style_configs = self.config.get("styles", {})
        for style_name in styles:
            if style_name in style_configs:
                style_config = style_configs[style_name]
                style_line = self._format_style_line(style_config)
                header += style_line + "\n"

        header += "\n[Events]\n"
        header += "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"

        return header

    def _format_style_line(self, style_config: Dict[str, Any]) -> str:
        """
        格式化样式行

        Args:
            style_config: 样式配置字典

        Returns:
            格式化的样式行
        """
        bold = -1 if style_config.get("bold", False) else 0
        italic = -1 if style_config.get("italic", False) else 0
        underline = -1 if style_config.get("underline", False) else 0
        strikeout = -1 if style_config.get("strikeout", False) else 0

        return (f"Style: {style_config.get('name', 'Default')},"
                f"{style_config.get('fontname', '微软雅黑')},"
                f"{style_config.get('fontsize', 20)},"
                f"{style_config.get('primary_colour', '&H00FFFFFF')},"
                f"{style_config.get('secondary_colour', '&H000000FF')},"
                f"{style_config.get('outline_colour', '&H00000000')},"
                f"{style_config.get('back_colour', '&H80000000')},"
                f"{bold},{italic},{underline},{strikeout},"
                f"{style_config.get('scale_x', 100)},"
                f"{style_config.get('scale_y', 100)},"
                f"{style_config.get('spacing', 0)},"
                f"{style_config.get('angle', 0)},"
                f"{style_config.get('border_style', 1)},"
                f"{style_config.get('outline', 2)},"
                f"{style_config.get('shadow', 2)},"
                f"{style_config.get('alignment', 2)},"
                f"{style_config.get('margin_l', 10)},"
                f"{style_config.get('margin_r', 10)},"
                f"{style_config.get('margin_v', 10)},"
                f"{style_config.get('encoding', 1)}")

    def _apply_effects(self, text: str, style_name: str) -> str:
        """
        应用特效到文本

        Args:
            text: 原始文本
            style_name: 样式名称

        Returns:
            应用特效后的文本
        """
        # 根据样式添加一些动画效果
        if "霓虹发光" in style_name:
            # 添加发光效果
            text = f"{{\\blur2\\be1}}{text}"
        elif "彩虹渐变" in style_name:
            # 添加颜色变化效果
            text = f"{{\\t(0,1000,\\c&H0080FF&)\\t(1000,2000,\\c&HFF8000&)\\t(2000,3000,\\c&H8000FF&)}}{text}"
        elif "可爱卡通" in style_name:
            # 添加弹跳效果
            text = f"{{\\t(0,200,\\fscx120\\fscy120)\\t(200,400,\\fscx100\\fscy100)}}{text}"
        elif "火焰橙红" in style_name:
            # 添加闪烁效果
            text = f"{{\\t(0,500,\\alpha&H00&)\\t(500,1000,\\alpha&H80&)\\t(1000,1500,\\alpha&H00&)}}{text}"

        return text

    def srt_to_ass(self, style_names: List[str], srt_path: str, output_dir: str = "output") -> List[str]:
        """
        将SRT文件转换为ASS文件

        Args:
            style_names: 使用的样式名称列表
            srt_path: SRT文件路径
            output_dir: 输出目录

        Returns:
            生成的ASS文件路径列表
        """
        if not style_names:
            raise ValueError("至少需要选择一个样式")

        # 验证样式名称
        available_styles = self.get_style_list()
        for style_name in style_names:
            if style_name not in available_styles:
                raise ValueError(f"样式 '{style_name}' 不存在，可用样式: {available_styles}")

        # 解析SRT文件
        subtitles = self._parse_srt_file(srt_path)
        if not subtitles:
            raise ValueError("SRT文件中没有找到有效的字幕")

        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)

        # 生成输出文件名前缀
        srt_filename = os.path.splitext(os.path.basename(srt_path))[0]

        output_paths = []
        style_configs = self.config.get("styles", {})

        # 为每个样式生成单独的ASS文件
        for style_name in style_names:
            # 生成单个样式的ASS文件头部
            ass_content = self._generate_ass_header([style_name])

            # 获取当前样式配置
            current_style_config = style_configs[style_name]
            style_internal_name = current_style_config.get("name", style_name)

            # 添加字幕事件（所有字幕都使用同一个样式）
            for subtitle in subtitles:
                # 应用特效
                text = self._apply_effects(subtitle['text'], style_name)

                # 格式化事件行
                event_line = (f"Dialogue: 0,{subtitle['start']},{subtitle['end']},"
                              f"{style_internal_name},,0,0,0,,{text}\n")
                ass_content += event_line

            # 生成输出文件路径
            output_filename = f"{srt_filename}_{style_name}.ass"
            output_path = os.path.join(output_dir, output_filename)

            # 写入文件
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(ass_content)

            output_paths.append(output_path)

        return output_paths


# 便捷函数
def get_available_styles(config_path: str = "config/ass_config.json") -> List[str]:
    """获取可用样式列表"""
    converter = ASSConverter(config_path)
    return converter.get_style_list()


def convert_srt_to_ass(style_names: List[str], srt_path: str, output_dir: str = "output",
                      config_path: str = "config/ass_config.json") -> List[str]:
    """转换SRT到ASS"""
    converter = ASSConverter(config_path)
    return converter.srt_to_ass(style_names, srt_path, output_dir)