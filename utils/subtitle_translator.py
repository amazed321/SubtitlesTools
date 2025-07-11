import os
import re
import time
from typing import List, Dict, Tuple
from . import openai_api


class SubtitleTranslator:
    def __init__(self):
        self.translation_rules_dict = {
            "双语": "你需要把用户提供的语言翻译成英文和中文，英文在上，中文在下",
            "英文": "你需要把用户提供的语言翻译成英文",
            "中文": "你需要把用户提供的语言翻译成中文",
        }

    # 解析SRT字幕文件内容
    def parse_srt(self, srt_content: str) -> List[Dict]:
        """解析SRT字幕文件内容"""
        # 按空行分割字幕块
        blocks = re.split(r'\n\s*\n', srt_content.strip())
        subtitles = []

        for block in blocks:
            if not block.strip():
                continue

            lines = block.strip().split('\n')
            if len(lines) < 3:
                continue

            # 提取序号
            try:
                index = int(lines[0])
            except ValueError:
                continue

            # 提取时间轴
            time_line = lines[1]
            if '-->' not in time_line:
                continue

            # 提取文本内容（可能多行）
            text_lines = lines[2:]
            text = '\n'.join(text_lines)

            subtitles.append({
                'index': index,
                'timeline': time_line,
                'text': text
            })

        return subtitles

    # 翻译单条字幕文本
    def translate_single_text(self, api_key: str, model: str, text: str,
                              translation_type: str, max_retries: int = 3) -> str:
        """翻译单条字幕文本"""
        system_prompt = f'你是一个翻译助手，翻译规则：\n{self.translation_rules_dict[translation_type]}'

        message = [
            {
                'role': 'system',
                'content': system_prompt,
            },
            {
                "role": "user",
                "content": text,
            }
        ]

        # 重试机制
        for attempt in range(max_retries):
            try:
                result = openai_api.text_to_text(api_key=api_key, message=message, model=model)
                return result['ai_text'].strip()

            except Exception as e:
                print(f"翻译失败，尝试第 {attempt + 1} 次，错误：{str(e)}")
                if attempt == max_retries - 1:
                    print(f"翻译失败，已达到最大重试次数，返回原文")
                    return text
                time.sleep(1)  # 等待1秒后重试

        return text
    # 批量翻译文本
    def translate_texts_batch(self, api_key: str, model: str, texts: List[str],
                              translation_type: str, max_retries: int = 3) -> List[str]:
        """批量翻译文本 - 使用改进的批量方法"""
        if not texts:
            return []

        # 如果只有1条字幕，直接逐条翻译
        if len(texts) <= 1:
            return self._translate_one_by_one(api_key, model, texts, translation_type, max_retries)

        # 使用编号格式进行批量翻译
        system_prompt = f'你是一个翻译助手，翻译规则：\n{self.translation_rules_dict[translation_type]}'

        # 构造带编号的文本，每条单独翻译
        if translation_type == "双语":
            user_prompt = "请翻译以下字幕文本，每条字幕都要按照翻译规则输出（英文在上，中文在下），然后用 ===NEXT=== 分隔下一条字幕的翻译结果：\n\n"
        else:
            user_prompt = f"请翻译以下字幕文本为{translation_type}，每条字幕的翻译结果用 ===NEXT=== 分隔：\n\n"

        for i, text in enumerate(texts, 1):
            user_prompt += f"字幕{i}：{text}\n\n"

        message = [
            {
                'role': 'system',
                'content': system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            }
        ]

        print(f"发送给AI的文本：")
        print(f"系统提示：{system_prompt}")
        print(f"用户输入：{user_prompt}")
        print("=" * 50)

        # 重试机制
        for attempt in range(max_retries):
            try:
                result = openai_api.text_to_text(api_key=api_key, message=message, model=model)
                translated_text = result['ai_text']

                print(f"AI返回的原始结果：")
                print(f"'{translated_text}'")
                print("=" * 50)

                # 解析翻译结果
                translated_parts = self._parse_batch_translation(translated_text, len(texts))

                print(f"解析后的结果数量：{len(translated_parts)}, 期望数量：{len(texts)}")
                for i, part in enumerate(translated_parts):
                    print(f"第{i + 1}部分：'{part}'")
                print("=" * 50)

                if len(translated_parts) >= len(texts) - 1:  # 允许少1个的容错
                    # 如果翻译结果少了，用原文补齐
                    while len(translated_parts) < len(texts):
                        translated_parts.append(texts[len(translated_parts)])
                    return translated_parts[:len(texts)]  # 确保不超过原始数量
                else:
                    print(f"批量翻译结果数量不匹配，改为逐条翻译")
                    return self._translate_one_by_one(api_key, model, texts, translation_type, max_retries)

            except Exception as e:
                print(f"批量翻译失败，尝试第 {attempt + 1} 次，错误：{str(e)}")
                if attempt == max_retries - 1:
                    print(f"批量翻译失败，改为逐条翻译")
                    return self._translate_one_by_one(api_key, model, texts, translation_type, max_retries)
                time.sleep(1)

        return texts

    # 解析批量翻译结果
    def _parse_batch_translation(self, translated_text: str, expected_count: int) -> List[str]:
        """解析批量翻译结果"""
        print(f"开始解析翻译结果，期望得到 {expected_count} 个部分")

        # 按分隔符分割
        parts = translated_text.split('===NEXT===')
        print(f"按 '===NEXT===' 分割后得到 {len(parts)} 个部分：")
        for i, part in enumerate(parts):
            print(f"  部分{i}: '{part.strip()}'")

        # 清理每个部分
        cleaned_parts = []
        for part in parts:
            cleaned = part.strip()
            if cleaned:
                # 移除"字幕X："前缀，保留翻译内容
                cleaned = re.sub(r'^字幕\d+[:：]\s*', '', cleaned)
                cleaned = cleaned.strip()

                if cleaned:
                    cleaned_parts.append(cleaned)

        print(f"清理后得到 {len(cleaned_parts)} 个有效部分：")
        for i, part in enumerate(cleaned_parts):
            print(f"  清理后部分{i}: '{part}'")

        return cleaned_parts

    # 逐条翻译作为备用方案
    def _translate_one_by_one(self, api_key: str, model: str, texts: List[str],
                              translation_type: str, max_retries: int) -> List[str]:
        """逐条翻译作为备用方案"""
        translated_results = []

        for i, text in enumerate(texts):
            print(f"  正在翻译第 {i + 1}/{len(texts)} 条...")
            translated_text = self.translate_single_text(
                api_key=api_key,
                model=model,
                text=text,
                translation_type=translation_type,
                max_retries=max_retries
            )
            translated_results.append(translated_text)

            # 避免API请求过频
            if i < len(texts) - 1:
                time.sleep(0.3)

        return translated_results

    # 格式化翻译后的字幕
    def format_translated_subtitle(self, original_text: str, translated_text: str,
                                   translation_type: str) -> str:
        """格式化翻译后的字幕"""
        if translation_type == "双语":
            # 检查翻译结果是否已经包含双语格式
            lines = translated_text.split('\n')
            if len(lines) >= 2:
                # 如果翻译结果已经是多行，直接使用
                return translated_text
            else:
                # 如果是单行，说明可能只有一种语言，需要添加原文
                # 根据原文语言判断翻译结果是哪种语言
                if self._is_chinese(original_text):
                    # 原文是中文，翻译结果应该是英文
                    return f"{translated_text}\n{original_text}"
                else:
                    # 原文是英文或其他语言，翻译结果应该是中文
                    return f"{translated_text}\n{original_text}"
        else:
            # 单语模式：只返回翻译结果
            return translated_text
    # 判断文本是否主要包含中文
    def _is_chinese(self, text: str) -> bool:
        """判断文本是否主要包含中文"""
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        total_chars = len(re.sub(r'\s', '', text))
        return chinese_chars > total_chars * 0.3 if total_chars > 0 else False
    # 生成SRT格式的字幕
    def generate_srt(self, subtitles: List[Dict]) -> str:
        """生成SRT格式的字幕"""
        srt_content = []

        for subtitle in subtitles:
            srt_content.append(str(subtitle['index']))
            srt_content.append(subtitle['timeline'])
            srt_content.append(subtitle['text'])
            srt_content.append('')  # 空行分隔

        return '\n'.join(srt_content)

# 翻译SRT字幕文件
def translate_srt_file(api_key: str, model: str, srt_file_path: str,
                       output_folder: str = "output", translation_type: str = "中文",
                       batch_size: int = 50) -> str:
    """
    翻译SRT字幕文件

    Args:
        api_key: OpenAI API密钥
        model: 模型名称
        srt_file_path: SRT文件路径
        output_folder: 输出文件夹路径
        translation_type: 翻译类型（双语、英文、中文）
        batch_size: 每次翻译的字幕条数

    Returns:
        输出文件的完整路径
    """
    translator = SubtitleTranslator()

    # 检查翻译类型是否支持
    if translation_type not in translator.translation_rules_dict:
        raise ValueError(f"不支持的翻译类型：{translation_type}")

    # 读取SRT文件
    if not os.path.exists(srt_file_path):
        raise FileNotFoundError(f"SRT文件不存在：{srt_file_path}")

    with open(srt_file_path, 'r', encoding='utf-8') as file:
        srt_content = file.read()

    # 解析SRT文件
    subtitles = translator.parse_srt(srt_content)
    if not subtitles:
        raise ValueError("无法解析SRT文件或文件为空")

    print(f"成功解析 {len(subtitles)} 条字幕")

    # 分批翻译
    translated_subtitles = []
    total_batches = (len(subtitles) + batch_size - 1) // batch_size

    for i in range(0, len(subtitles), batch_size):
        batch_subtitles = subtitles[i:i + batch_size]
        batch_texts = [sub['text'] for sub in batch_subtitles]

        current_batch = i // batch_size + 1
        print(f"正在翻译第 {current_batch}/{total_batches} 批次，包含 {len(batch_texts)} 条字幕...")

        # 翻译当前批次
        translated_texts = translator.translate_texts_batch(
            api_key=api_key,
            model=model,
            texts=batch_texts,
            translation_type=translation_type
        )

        # 格式化翻译结果
        for j, subtitle in enumerate(batch_subtitles):
            original_text = subtitle['text']
            translated_text = translated_texts[j] if j < len(translated_texts) else original_text

            formatted_text = translator.format_translated_subtitle(
                original_text, translated_text, translation_type
            )

            translated_subtitles.append({
                'index': subtitle['index'],
                'timeline': subtitle['timeline'],
                'text': formatted_text
            })

        print(f"第 {current_batch} 批次翻译完成")

        # 避免API请求过频
        if current_batch < total_batches:
            time.sleep(0.5)

    # 生成输出文件名
    input_filename = os.path.basename(srt_file_path)
    name_without_ext = os.path.splitext(input_filename)[0]
    output_filename = f"{name_without_ext}_{translation_type}.srt"

    # 确保输出文件夹存在
    os.makedirs(output_folder, exist_ok=True)
    output_path = os.path.join(output_folder, output_filename)

    # 生成并保存翻译后的SRT文件
    translated_srt_content = translator.generate_srt(translated_subtitles)

    with open(output_path, 'w', encoding='utf-8') as file:
        file.write(translated_srt_content)

    print(f"翻译完成，输出文件：{output_path}")
    return output_path