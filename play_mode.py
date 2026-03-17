# play_mode.py
import random
import logging
from abc import ABC, abstractmethod
from typing import List

class BasePlayMode(ABC):
    """播放模式抽象接口"""
    @abstractmethod
    def get_next_index(self, current_index: int, playlist: List[str]) -> int:
        """获取下一曲索引"""
        pass
    
    @abstractmethod
    def get_prev_index(self, current_index: int, playlist: List[str]) -> int:
        """获取上一曲索引"""
        pass

class SequencePlayMode(BasePlayMode):
    """顺序播放"""
    def get_next_index(self, current_index: int, playlist: List[str]) -> int:
        if not playlist:
            return -1
        next_idx = (current_index + 1) % len(playlist)
        logging.debug(f"顺序播放-下一曲索引: {current_index} -> {next_idx}")
        return next_idx
    
    def get_prev_index(self, current_index: int, playlist: List[str]) -> int:
        if not playlist:
            return -1
        prev_idx = (current_index - 1) % len(playlist)
        logging.debug(f"顺序播放-上一曲索引: {current_index} -> {prev_idx}")
        return prev_idx

class RandomPlayMode(BasePlayMode):
    """随机播放（避免连续重复）"""
    def __init__(self):
        self.last_index = -1
        logging.debug("RandomPlayMode 初始化，last_index = -1")
    
    def get_next_index(self, current_index: int, playlist: List[str]) -> int:
        if not playlist:
            return -1
        if len(playlist) == 1:
            logging.debug("随机播放-播放列表仅1首，返回索引0")
            return 0
        # 避免连续播放同一首
        new_index = random.randint(0, len(playlist)-1)
        while new_index == self.last_index:
            new_index = random.randint(0, len(playlist)-1)
        self.last_index = new_index
        logging.debug(f"随机播放-下一曲索引: {current_index} -> {new_index}")
        return new_index
    
    def get_prev_index(self, current_index: int, playlist: List[str]) -> int:
        # 随机播放的上一曲也随机（可自定义逻辑）
        prev_idx = self.get_next_index(current_index, playlist)
        logging.debug(f"随机播放-上一曲索引: {current_index} -> {prev_idx}")
        return prev_idx

class SingleLoopPlayMode(BasePlayMode):
    """单曲循环"""
    def get_next_index(self, current_index: int, playlist: List[str]) -> int:
        if not playlist:
            return -1
        logging.debug(f"单曲循环-下一曲索引: {current_index} -> {current_index}")
        return current_index
    
    def get_prev_index(self, current_index: int, playlist: List[str]) -> int:
        if not playlist:
            return -1
        logging.debug(f"单曲循环-上一曲索引: {current_index} -> {current_index}")
        return current_index

class PlayModeManager:
    """播放模式管理器"""
    def __init__(self):
        self.mode_map = {
            "顺序播放": SequencePlayMode(),
            "随机播放": RandomPlayMode(),
            "单曲循环": SingleLoopPlayMode()
        }
        self.current_mode = "顺序播放"
        logging.info(f"PlayModeManager 初始化完成，默认播放模式: {self.current_mode}")
    
    def set_mode(self, mode_name: str) -> None:
        """设置播放模式"""
        if mode_name in self.mode_map:
            self.current_mode = mode_name
            logging.info(f"切换播放模式为: {mode_name}")
        else:
            logging.error(f"无效的播放模式: {mode_name}，保留当前模式: {self.current_mode}")
    
    def get_next_index(self, current_index: int, playlist: List[str]) -> int:
        """获取下一曲索引"""
        return self.mode_map[self.current_mode].get_next_index(current_index, playlist)
    
    def get_prev_index(self, current_index: int, playlist: List[str]) -> int:
        """获取上一曲索引"""
        return self.mode_map[self.current_mode].get_prev_index(current_index, playlist)