# config_manager.py
import os
import logging
from dataclasses import dataclass
from typing import List

@dataclass
class AppConfig:
    """应用配置类，集中管理所有可配置项"""
    # 播放列表相关
    playlist_file: str = "playlist.json"
    supported_audio_formats: List[str] = (".mp3", ".wav", ".ogg", ".flac")  # 扩展支持格式
    # 媒体加载相关
    max_retry_count: int = 2
    retry_delay: int = 1000  # 毫秒
    load_timeout: int = 5000  # 加载超时时间
    # UI相关
    window_size: tuple = (900, 600)
    window_title: str = "音乐播放器"
    default_volume: int = 50
    # 路径相关
    icon_path: str = "MusicPlay.ico"  # 可通过外部配置覆盖
    # 元数据相关
    # 支持开发环境和PyInstaller打包环境的默认封面路径
    @property
    def default_cover(self) -> str:
        import sys
        import os
        # 开发环境
        base_dir = os.path.dirname(os.path.abspath(__file__))
        dev_path = os.path.join(base_dir, "img", "default_cover.png")
        # PyInstaller打包环境
        if getattr(sys, 'frozen', False):
            meipass = getattr(sys, '_MEIPASS', None)
            if meipass:
                exe_path = os.path.join(meipass, "img", "default_cover.png")
                if os.path.exists(exe_path):
                    return exe_path
        # 优先返回开发环境路径
        return dev_path if os.path.exists(dev_path) else ""

class ConfigManager:
    _instance = None  # 单例模式，避免重复加载
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.config = AppConfig()
            # 可选：从外部json文件加载配置，覆盖默认值
            cls._instance.load_from_file("app_config.json")
            logging.info("ConfigManager 单例初始化完成，加载默认配置")
        return cls._instance
    
    def load_from_file(self, config_file: str):
        """从JSON文件加载配置（可选扩展）"""
        if os.path.exists(config_file):
            try:
                import json
                with open(config_file, "r", encoding="utf8") as f:
                    file_config = json.load(f)
                # 覆盖默认配置
                for key, value in file_config.items():
                    if hasattr(self.config, key):
                        setattr(self.config, key, value)
                        logging.debug(f"从配置文件加载项: {key} = {value}")
                logging.info(f"成功从 {config_file} 加载自定义配置")
            except Exception as e:
                logging.error(f"加载配置文件失败: {str(e)}")
        else:
            logging.debug(f"配置文件 {config_file} 不存在，使用默认配置")
    
    def get_config(self) -> AppConfig:
        return self.config