# meta_data_parser.py
import os
import tempfile
import logging
from typing import Optional, Dict, Any
from mutagen import File
from mutagen.flac import FLAC, Picture
from mutagen.id3 import ID3, APIC, USLT
from mutagen.wave import WAVE

class MetaDataParser:
    """音频元数据解析器，支持FLAC/WAV格式的封面、歌词、基础信息解析"""
    def __init__(self):
        # 创建临时目录存储封面图片
        self.temp_dir = tempfile.mkdtemp(prefix="music_player_cover_")
        self.cover_path: Optional[str] = None
        logging.info(f"MetaDataParser 初始化完成，临时封面目录: {self.temp_dir}")

    def parse_metadata(self, file_path: str) -> Dict[str, Any]:
        """解析音频文件元数据，返回结构化结果"""
        result = {
            "title": os.path.basename(file_path),  # 默认标题为文件名
            "artist": "",
            "album": "",
            "cover_path": None,
            "lyrics": ""
        }

        if not os.path.exists(file_path):
            logging.warning(f"文件不存在，无法解析元数据: {file_path}")
            return result

        try:
            # 根据文件格式选择解析方式
            ext = os.path.splitext(file_path)[1].lower()
            if ext == ".flac":
                self._parse_flac(file_path, result)
            elif ext == ".wav":
                self._parse_wav(file_path, result)
            else:
                # 其他格式降级处理（仅基础信息）
                audio = File(file_path)
                if audio:
                    result["title"] = audio.get("title", [result["title"]])[0]
                    result["artist"] = audio.get("artist", [""])[0]
                    result["album"] = audio.get("album", [""])[0]

            # 补充解析外部歌词文件（同目录同名.lrc）
            result["lyrics"] = self._parse_external_lyrics(file_path) or result["lyrics"]
            logging.debug(f"元数据解析完成: {file_path} -> 标题: {result['title']}, 艺术家: {result['artist']}")
        except Exception as e:
            logging.error(f"解析元数据失败: {file_path}, 错误: {str(e)}")

        return result

    def _parse_flac(self, file_path: str, result: Dict[str, Any]):
        """解析FLAC格式元数据"""
        flac = FLAC(file_path)
        # 基础信息
        result["title"] = flac.get("title", [result["title"]])[0]
        result["artist"] = flac.get("artist", [""])[0]
        result["album"] = flac.get("album", [""])[0]
        # 嵌入式歌词
        result["lyrics"] = flac.get("lyrics", [""])[0] or flac.get("LYRICS", [""])[0]
        # 封面图片
        pictures = flac.pictures
        if pictures:
            self.cover_path = self._extract_cover(pictures[0], file_path)
            result["cover_path"] = self.cover_path

    def _parse_wav(self, file_path: str, result: Dict[str, Any]):
        """解析WAV格式元数据（支持ID3v2标签）"""
        wav = WAVE(file_path)
        # 基础信息（优先读取ID3标签）
        if wav.tags:
            result["title"] = wav.tags.get("TIT2", [result["title"]])[0]
            result["artist"] = wav.tags.get("TPE1", [""])[0]
            result["album"] = wav.tags.get("TALB", [""])[0]
        # 尝试读取ID3扩展标签（封面/歌词）
        try:
            id3 = ID3(file_path)
            # 嵌入式歌词
            uslt_frames = id3.getall("USLT")
            if uslt_frames:
                result["lyrics"] = uslt_frames[0].text
            # 封面图片
            apic_frames = id3.getall("APIC")
            if apic_frames:
                self.cover_path = self._extract_cover_from_apic(apic_frames[0], file_path)
                result["cover_path"] = self.cover_path
        except Exception as e:
            logging.debug(f"WAV文件无ID3标签: {file_path}, 错误: {str(e)}")

    def _extract_cover(self, picture: Picture, file_path: str) -> str:
        """从FLAC Picture对象提取封面并保存为临时文件"""
        ext = self._get_image_ext(picture.mime_type)
        cover_filename = f"cover_{os.path.basename(file_path).replace(os.path.splitext(file_path)[1], '')}{ext}"
        cover_path = os.path.join(self.temp_dir, cover_filename)
        with open(cover_path, "wb") as f:
            f.write(picture.data)
        logging.debug(f"提取FLAC封面到临时文件: {cover_path}")
        return cover_path

    def _extract_cover_from_apic(self, apic: APIC, file_path: str) -> str:
        """从ID3 APIC帧提取封面并保存为临时文件"""
        ext = self._get_image_ext(apic.mime)
        cover_filename = f"cover_{os.path.basename(file_path).replace(os.path.splitext(file_path)[1], '')}{ext}"
        cover_path = os.path.join(self.temp_dir, cover_filename)
        with open(cover_path, "wb") as f:
            f.write(apic.data)
        logging.debug(f"提取WAV封面到临时文件: {cover_path}")
        return cover_path

    def _get_image_ext(self, mime_type: str) -> str:
        """根据MIME类型返回图片扩展名"""
        mime_map = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/gif": ".gif"
        }
        return mime_map.get(mime_type, ".jpg")

    def _parse_external_lyrics(self, file_path: str) -> Optional[str]:
        """解析外部LRC歌词文件（同目录同名.lrc）"""
        lrc_path = os.path.splitext(file_path)[0] + ".lrc"
        if not os.path.exists(lrc_path):
            return None
        try:
            # 尝试多种编码读取歌词
            encodings = ["utf-8", "gbk", "gb2312", "utf-16"]
            for enc in encodings:
                with open(lrc_path, "r", encoding=enc) as f:
                    lyrics = f.read()
                    logging.debug(f"读取外部LRC歌词: {lrc_path} (编码: {enc})")
                    return lyrics
        except Exception as e:
            logging.warning(f"读取外部歌词失败: {lrc_path}, 错误: {str(e)}")
        return None

    def cleanup(self):
        """清理临时封面文件"""
        try:
            if self.cover_path and os.path.exists(self.cover_path):
                os.remove(self.cover_path)
            os.rmdir(self.temp_dir)
            logging.info("临时封面文件清理完成")
        except Exception as e:
            logging.warning(f"清理临时文件失败: {str(e)}")