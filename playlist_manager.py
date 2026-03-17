# playlist_manager.py
import os
import json
import logging
from typing import List, Optional
from PyQt5.QtWidgets import QListWidget, QListWidgetItem
from PyQt5.QtCore import Qt
from config_manager import ConfigManager

class PlaylistManager:
    def __init__(self, playlist_widget: QListWidget, main_window):
        self.config = ConfigManager().get_config()
        self.playlist_widget = playlist_widget
        self.main_window = main_window
        self.playlist: List[str] = []  # 存储音频文件绝对路径
        logging.info("PlaylistManager 初始化完成")
    
    def normalize_path(self, path: str) -> str:
        """统一路径格式（跨平台兼容）"""
        return path.lower() if os.name == "nt" else path
    
    def add_file(self, file_path: str) -> bool:
        """添加单个文件到播放列表（去重+格式校验）"""
        if not os.path.exists(file_path):
            logging.warning(f"文件不存在，跳过添加: {file_path}")
            return False
        if not file_path.lower().endswith(self.config.supported_audio_formats):
            logging.debug(f"不支持的文件格式，跳过添加: {file_path}")
            return False
        norm_path = self.normalize_path(file_path)
        if norm_path in [self.normalize_path(p) for p in self.playlist]:
            logging.debug(f"文件已存在于播放列表，跳过添加: {file_path}")
            return False
        
        # 添加到列表并同步UI
        self.playlist.append(file_path)
        item = QListWidgetItem(os.path.basename(file_path))
        item.setData(Qt.UserRole, file_path)
        self.playlist_widget.addItem(item)
        logging.debug(f"添加文件到播放列表: {file_path}")
        return True
    
    def add_folder(self, folder_path: str) -> int:
        """递归添加文件夹内的音频文件，返回新增数量"""
        added = 0
        if not os.path.isdir(folder_path):
            logging.warning(f"文件夹不存在，跳过添加: {folder_path}")
            return added
        logging.info(f"开始扫描文件夹内的音频文件: {folder_path}")
        for root, _, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                if self.add_file(file_path):
                    added += 1
        logging.info(f"扫描完成，新增{added}个音频文件到播放列表: {folder_path}")
        return added
    
    def remove_selected(self) -> None:
        """删除选中的项，同步列表和UI"""
        selected_items = self.playlist_widget.selectedItems()
        if not selected_items:
            logging.debug("未选中任何项，跳过删除操作")
            return
        
        # 收集要删除的路径
        remove_paths = []
        for item in selected_items:
            path = item.data(Qt.UserRole)
            if path:
                remove_paths.append(path)
                logging.debug(f"从播放列表删除文件: {path}")
            self.playlist_widget.takeItem(self.playlist_widget.row(item))
        
        # 同步playlist列表
        self.playlist = [p for p in self.playlist if p not in remove_paths]
        self.save_playlist()
        logging.info(f"从播放列表删除{len(remove_paths)}个文件")
    
    def sort_playlist(self, current_playing_path: Optional[str] = None) -> int:
        """排序播放列表，保留当前播放文件的索引"""
        logging.info("开始排序播放列表")
        # 按文件名小写排序
        self.playlist.sort(key=lambda x: os.path.basename(x).lower())
        # 同步UI
        self.playlist_widget.clear()
        for path in self.playlist:
            item = QListWidgetItem(os.path.basename(path))
            item.setData(Qt.UserRole, path)
            self.playlist_widget.addItem(item)
        
        # 恢复当前播放索引
        new_index = -1
        if current_playing_path and current_playing_path in self.playlist:
            new_index = self.playlist.index(current_playing_path)
            logging.debug(f"排序后恢复当前播放文件索引: {new_index}，文件: {current_playing_path}")
        self.save_playlist()
        logging.info("播放列表排序完成")
        return new_index
    
    def load_playlist(self) -> List[str]:
        """加载保存的播放列表，过滤无效文件"""
        missing_files = []
        self.playlist.clear()
        self.playlist_widget.clear()
        logging.info(f"开始加载播放列表文件: {self.config.playlist_file}")
        
        if os.path.exists(self.config.playlist_file):
            try:
                with open(self.config.playlist_file, "r", encoding="utf8") as f:
                    saved_playlist = json.load(f)
                for path in saved_playlist:
                    if self.add_file(path):
                        continue
                    missing_files.append(path)
                logging.info(f"加载播放列表完成，共{len(saved_playlist)}个条目，跳过{len(missing_files)}个无效文件")
            except Exception as e:
                logging.error(f"加载播放列表失败: {str(e)}")
        else:
            logging.warning(f"播放列表文件不存在: {self.config.playlist_file}")
        return missing_files
    
    def save_playlist(self) -> bool:
        """保存播放列表到文件"""
        try:
            with open(self.config.playlist_file, "w", encoding="utf8") as f:
                json.dump(self.playlist, f, ensure_ascii=False, indent=2)
            logging.info(f"保存播放列表成功，共{len(self.playlist)}个条目: {self.config.playlist_file}")
            return True
        except Exception as e:
            logging.error(f"保存播放列表失败: {str(e)}")
            return False
    
    def sync_from_ui_drag(self) -> None:
        """从UI拖放后的列表同步playlist（解决原代码拖放同步问题）"""
        self.playlist.clear()
        for i in range(self.playlist_widget.count()):
            item = self.playlist_widget.item(i)
            path = item.data(Qt.UserRole)
            if path and os.path.exists(path):
                self.playlist.append(path)
        self.save_playlist()
        logging.info("从UI拖放同步播放列表完成")
    
    def get_valid_index(self, index: int) -> int:
        """索引越界保护，返回有效索引"""
        if not self.playlist:
            logging.debug("播放列表为空，返回无效索引-1")
            return -1
        valid_index = max(0, min(index, len(self.playlist)-1))
        if valid_index != index:
            logging.warning(f"索引{index}越界，修正为有效索引{valid_index}")
        return valid_index