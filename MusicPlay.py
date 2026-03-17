# MusicPlay.py
import sys
import os
import logging
from datetime import datetime
from typing import List
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QSlider, QLabel, QListWidget,
    QListWidgetItem, QComboBox, QMenu, QSystemTrayIcon, QStyle,
    QTextEdit, QSplitter
)
from PyQt5.QtCore import QUrl, QTimer, Qt
from PyQt5.QtGui import QIcon, QPixmap, QDragEnterEvent, QDropEvent
from PyQt5.QtMultimedia import QMediaPlayer

# ------------------- 日志系统初始化（完整配置） -------------------
def init_logging():
    """初始化日志系统：按日期生成日志文件，支持多级别日志"""
    # 创建logs文件夹（不存在则创建）
    # 获取当前脚本所在目录，确保logs文件夹在MusicPlay_New下
    base_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(base_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    # 日志文件名格式：music_player_YYYY-MM-DD.log
    log_filename = os.path.join(log_dir, f"music_player_{datetime.now().strftime('%Y-%m-%d')}.log")
    
    # 日志格式：时间 - 模块名 - 日志级别 - 消息
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # 配置根日志器
    logging.basicConfig(
        level=logging.DEBUG,  # 最低级别为DEBUG，确保所有级别都能记录
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8'),  # 文件处理器
            logging.StreamHandler()  # 控制台处理器（可选，方便调试）
        ]
    )
    
    # 记录程序启动日志
    logging.info("="*50)
    logging.info("音乐播放器程序启动")
    logging.info(f"日志文件路径: {os.path.abspath(log_filename)}")
    logging.info("="*50)

# 先初始化日志系统
init_logging()

# 导入拆分后的模块
from config_manager import ConfigManager
from playlist_manager import PlaylistManager
from media_core import MediaPlayerCore
from play_mode import PlayModeManager
from meta_data_parser import MetaDataParser

# 平台判断（抽离为工具函数）
def is_windows() -> bool:
    return sys.platform == 'win32'

# 自定义ListWidget（仅保留拖放同步逻辑）
class PlaylistListWidget(QListWidget):
    def __init__(self, playlist_manager: PlaylistManager, parent=None):
        super().__init__(parent)
        self.playlist_manager = playlist_manager
        logging.debug("PlaylistListWidget 初始化完成")

    def dropEvent(self, event: QDropEvent):
        super().dropEvent(event)
        self.playlist_manager.sync_from_ui_drag()  # 委托给PlaylistManager处理
        logging.info("播放列表通过拖放完成排序同步")

class MusicPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = ConfigManager().get_config()
        self.init_core_modules()  # 初始化核心模块
        self.init_ui()  # 初始化UI
        self.init_tray()  # 初始化托盘
        self.load_playlist()  # 加载播放列表
        logging.info("MusicPlayer 主窗口初始化完成")

    def init_core_modules(self):
        """初始化核心模块（解耦UI和业务逻辑）"""
        self.media_core = MediaPlayerCore()
        self.play_mode_manager = PlayModeManager()
        # 元数据解析器
        self.meta_parser = MetaDataParser()
        # 播放列表管理器（后续绑定UI）
        self.playlist_manager = None
        
        # 电源事件相关（仅Windows）
        self.was_playing = False
        self.last_position = 0
        
        # 当前播放索引，默认未选中
        self.current_index = -1
        
        # 播放完成处理标志，避免重复触发下一曲
        self._end_handled = False
        logging.debug("核心模块初始化完成")

    def init_ui(self):
        """初始化UI（拆分后更清晰）"""
        self.setWindowTitle(self.config.window_title)
        self.setGeometry(100, 100, *self.config.window_size)
        self.setWindowIcon(self._get_window_icon())
        
        # 主布局（使用Splitter实现可调整大小的面板）
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        
        # 左侧播放列表区域
        playlist_widget = self._build_playlist_layout()
        
        # 右侧播放控制+歌词区域（垂直拆分）
        right_splitter = QSplitter(Qt.Vertical)
        control_widget = QWidget()
        control_layout = QVBoxLayout(control_widget)
        control_layout.addLayout(self._build_control_layout())
        right_splitter.addWidget(control_widget)
        
        # 歌词显示区域
        lyrics_widget = self._build_lyrics_layout()
        right_splitter.addWidget(lyrics_widget)
        right_splitter.setSizes([400, 200])  # 控制面板和歌词面板的初始大小
        
        main_layout.addWidget(playlist_widget, 1)  # 播放列表占1份宽度
        main_layout.addWidget(right_splitter, 2)   # 右侧面板占2份宽度
        
        # 启用拖放
        self.setAcceptDrops(True)
        logging.debug("UI界面初始化完成")

    def _build_playlist_layout(self) -> QWidget:
        """构建播放列表布局（模块化UI）"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 10, 0)
        
        # 标题
        playlist_label = QLabel("播放列表")
        playlist_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(playlist_label)
        
        # 播放列表Widget
        self.playlist_widget = PlaylistListWidget(None, self)
        self.playlist_widget.itemDoubleClicked.connect(self.play_selected)
        self.playlist_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.playlist_widget.customContextMenuRequested.connect(self.show_context_menu)
        self.playlist_widget.setStyleSheet("""
            QListWidget {border: 1px solid #ccc; border-radius: 4px; padding: 5px;}
            QListWidget::item {padding: 5px; color: black;}
            QListWidget::item:selected {background-color: #0066cc;}
        """)
        # 启用拖放
        self.playlist_widget.setDragEnabled(True)
        self.playlist_widget.setAcceptDrops(True)
        self.playlist_widget.setDragDropMode(QListWidget.DragDrop)
        self.playlist_widget.viewport().setAcceptDrops(True)
        self.playlist_widget.setDropIndicatorShown(True)
        self.playlist_widget.setDefaultDropAction(Qt.MoveAction)
        layout.addWidget(self.playlist_widget)
        
        # 绑定播放列表管理器
        self.playlist_manager = PlaylistManager(self.playlist_widget, self)
        
        # 播放列表按钮
        btn_layout = QHBoxLayout()
        self.add_file_btn = QPushButton('添加文件')
        self.add_folder_btn = QPushButton('添加文件夹')
        self.clear_list_btn = QPushButton('清空列表')
        self.sort_btn = QPushButton('排序')
        
        self.add_file_btn.clicked.connect(self.open_file)
        self.add_folder_btn.clicked.connect(self.open_folder)
        self.clear_list_btn.clicked.connect(self.clear_playlist)
        self.sort_btn.clicked.connect(self.sort_playlist)
        
        btn_layout.addWidget(self.add_file_btn)
        btn_layout.addWidget(self.add_folder_btn)
        btn_layout.addWidget(self.clear_list_btn)
        btn_layout.addWidget(self.sort_btn)
        layout.addLayout(btn_layout)
        
        return widget

    def _build_control_layout(self) -> QVBoxLayout:
        """构建播放控制布局（模块化UI）"""
        layout = QVBoxLayout()
        
        # 歌曲信息面板
        self._build_song_info_panel(layout)
        
        # 进度条
        self._build_progress_layout(layout)
        
        # 音量控制
        self._build_volume_layout(layout)
        
        # 播放模式
        self._build_play_mode_layout(layout)
        
        # 控制按钮
        self._build_control_buttons(layout)
        
        return layout

    def _build_song_info_panel(self, parent_layout: QVBoxLayout):
        """歌曲信息面板"""
        self.song_info_panel = QWidget()
        info_layout = QVBoxLayout(self.song_info_panel)
        
        # 封面
        self.cover_label = QLabel()
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setFixedSize(200, 200)
        self.cover_label.setStyleSheet("QLabel {border: 1px solid #ccc; background-color: #f0f0f0;}")
        # 设置默认封面（可选）
        if self.config.default_cover and os.path.exists(self.config.default_cover):
            self.cover_label.setPixmap(QPixmap(self.config.default_cover).scaled(
                200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation
            ))
        info_layout.addWidget(self.cover_label, 0, Qt.AlignCenter)
        
        # 歌曲信息标签
        self.song_title_label = QLabel("未加载音乐")
        self.song_title_label.setAlignment(Qt.AlignCenter)
        self.song_title_label.setStyleSheet("font-weight: bold; font-size: 16px;")
        
        self.song_artist_label = QLabel("")
        self.song_artist_label.setAlignment(Qt.AlignCenter)
        
        self.song_album_label = QLabel("")
        self.song_album_label.setAlignment(Qt.AlignCenter)
        
        info_layout.addWidget(self.song_title_label)
        info_layout.addWidget(self.song_artist_label)
        info_layout.addWidget(self.song_album_label)
        
        parent_layout.addWidget(self.song_info_panel)

    def _build_progress_layout(self, parent_layout: QVBoxLayout):
        """进度条布局"""
        progress_layout = QHBoxLayout()
        
        self.current_time_label = QLabel("00:00:00")
        self.current_time_label.setFixedWidth(80)
        self.current_time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.current_time_label.setStyleSheet("font-family: monospace;")
        
        self.progress_slider = QSlider(Qt.Horizontal)
        self.progress_slider.sliderMoved.connect(self.set_position)
        # 绑定进度更新
        self.media_core.progress_timer.timeout.connect(self.update_progress)
        
        self.total_time_label = QLabel("00:00:00")
        self.total_time_label.setFixedWidth(80)
        self.total_time_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.total_time_label.setStyleSheet("font-family: monospace;")
        
        progress_layout.addWidget(self.current_time_label)
        progress_layout.addWidget(self.progress_slider)
        progress_layout.addWidget(self.total_time_label)
        parent_layout.addLayout(progress_layout)

    def _build_volume_layout(self, parent_layout: QVBoxLayout):
        """音量控制布局"""
        volume_layout = QHBoxLayout()
        volume_label = QLabel("音量:")
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(self.config.default_volume)
        self.volume_slider.valueChanged.connect(self.set_volume)
        
        self.volume_value_label = QLabel(f"{self.config.default_volume}%")
        self.volume_value_label.setFixedWidth(40)
        self.volume_value_label.setAlignment(Qt.AlignCenter)
        self.volume_value_label.setStyleSheet("font-family: monospace;")
        
        volume_layout.addWidget(volume_label)
        volume_layout.addWidget(self.volume_slider)
        volume_layout.addWidget(self.volume_value_label)
        parent_layout.addLayout(volume_layout)

    def _build_play_mode_layout(self, parent_layout: QVBoxLayout):
        """播放模式布局"""
        mode_layout = QHBoxLayout()
        mode_label = QLabel("播放模式:")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["顺序播放", "随机播放", "单曲循环"])
        self.mode_combo.currentTextChanged.connect(self.change_play_mode)
        
        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.mode_combo)
        parent_layout.addLayout(mode_layout)

    def _build_control_buttons(self, parent_layout: QVBoxLayout):
        """播放控制按钮"""
        btn_layout = QHBoxLayout()
        self.prev_btn = QPushButton('上一曲')
        self.play_btn = QPushButton('播放')
        self.next_btn = QPushButton('下一曲')
        
        self.prev_btn.clicked.connect(self.play_previous)
        self.play_btn.clicked.connect(self.play_pause)
        self.next_btn.clicked.connect(self.play_next)
        
        btn_layout.addWidget(self.prev_btn)
        btn_layout.addWidget(self.play_btn)
        btn_layout.addWidget(self.next_btn)
        parent_layout.addLayout(btn_layout)

    def _build_lyrics_layout(self) -> QWidget:
        """构建歌词显示布局"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        lyrics_label = QLabel("歌词显示")
        lyrics_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(lyrics_label)
        
        from PyQt5.QtWidgets import QListWidget, QListWidgetItem
        self.lyrics_list = QListWidget()
        self.lyrics_list.setStyleSheet("""
            QListWidget {border: 1px solid #ccc; border-radius: 4px; padding: 10px;
                       font-family: 'Microsoft YaHei'; font-size: 15px; background: #fffbe6;}
            QListWidget::item {padding: 2px;}
            QListWidget::item:selected {background: #ffe066; font-weight: bold; color: #d35400;}
        """)
        layout.addWidget(self.lyrics_list)
        
        return widget

    # ------------------- 核心业务逻辑（整合模块） -------------------
    def _get_window_icon(self) -> QIcon:
        """获取窗口图标（容错处理，支持开发/打包环境）"""
        # 优先使用配置中指定的路径
        icon_path = getattr(self.config, "icon_path", "") or ""
        candidates = []
        if icon_path:
            candidates.append(icon_path)
        # 当前脚本目录下的常见位置
        base_dir = os.path.dirname(os.path.abspath(__file__))
        candidates += [
            os.path.join(base_dir, "img", "MusicPlay.ico"),
        ]
        # 打包后的运行时临时目录
        if getattr(sys, "frozen", False):
            meipass = getattr(sys, "_MEIPASS", None)
            if meipass:
                candidates += [
                    os.path.join(meipass, os.path.basename(icon_path)) if icon_path else "",
                    os.path.join(meipass, "img", "MusicPlay.ico"),
                ]
        # 逐个尝试加载，返回第一个有效 QIcon
        for p in candidates:
            try:
                if not p:
                    continue
                if os.path.exists(p):
                    icon = QIcon(p)
                    if not icon.isNull():
                        logging.debug(f"成功加载窗口图标: {p}")
                        return icon
            except Exception as e:
                logging.warning(f"加载图标失败: {p}, 错误: {str(e)}")
                continue
        # 兜底使用系统默认图标（返回 QIcon）
        app = QApplication.instance()
        if app:
            default_icon = app.style().standardIcon(QStyle.SP_FileIcon)
            logging.debug("使用系统默认图标")
            return default_icon
        logging.warning("无法加载任何图标，使用空图标")
        return QIcon()

    def init_tray(self):
        """初始化系统托盘（容错处理）"""
        self.tray = QSystemTrayIcon(self)
        icon = self._get_window_icon()
        # 确保传入的是 QIcon
        if isinstance(icon, QIcon) and not icon.isNull():
            self.tray.setIcon(icon)
            self.setWindowIcon(icon)  # 同步窗口图标
        else:
            # 兜底系统图标
            app = QApplication.instance()
            fallback = app.style().standardIcon(QStyle.SP_FileIcon) if app else QIcon()
            self.tray.setIcon(fallback)
            self.setWindowIcon(fallback)
        self.tray.setToolTip(self.config.window_title)
        # 托盘菜单（可扩展）
        tray_menu = QMenu()
        play_pause_action = tray_menu.addAction("播放/暂停")
        quit_action = tray_menu.addAction("退出")
        play_pause_action.triggered.connect(self.play_pause)
        quit_action.triggered.connect(self.close)
        self.tray.setContextMenu(tray_menu)
        self.tray.show()
        logging.info("系统托盘初始化完成")

    def load_playlist(self):
        """加载播放列表（委托给PlaylistManager）"""
        missing_files = self.playlist_manager.load_playlist()
        if missing_files:
            # 替换QMessageBox为日志
            logging.warning(
                f"加载播放列表时发现以下文件不存在，已跳过：\n{chr(10).join(missing_files[:5])}" +
                ("\n..." if len(missing_files) > 5 else "")
            )

    def open_file(self):
        """添加文件（委托给PlaylistManager）"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择音频文件", "",
            f"音频文件 ({' '.join(['*' + fmt for fmt in self.config.supported_audio_formats])})"
        )
        if files:
            logging.info(f"选择了{len(files)}个文件准备添加到播放列表")
            for file in files:
                self.playlist_manager.add_file(file)
            self.playlist_manager.save_playlist()
            logging.info(f"成功添加{len(files)}个文件到播放列表")
        else:
            logging.debug("用户取消了文件选择对话框")

    def open_folder(self):
        """添加文件夹（委托给PlaylistManager）"""
        folder = QFileDialog.getExistingDirectory(self, "选择音频文件夹")
        if folder:
            added = self.playlist_manager.add_folder(folder)
            # 替换QMessageBox为日志
            if added > 0:
                logging.info(f"成功扫描文件夹 {folder}，新增{added}个音频文件到播放列表")
            else:
                logging.warning(f"扫描文件夹 {folder} 未找到支持的音频文件")
        else:
            logging.debug("用户取消了文件夹选择对话框")

    def clear_playlist(self):
        """清空播放列表"""
        logging.info("开始清空播放列表")
        self.playlist_widget.clear()
        self.playlist_manager.playlist.clear()
        self.media_core.stop()
        self.play_btn.setText("播放")
        # 清空元数据显示
        self.song_title_label.setText("未加载音乐")
        self.song_artist_label.setText("")
        self.song_album_label.setText("")
        self.cover_label.clear()
        self.lyrics_list.clear()
        self.playlist_manager.save_playlist()
        logging.info("播放列表已清空，播放器已停止")

    def sort_playlist(self):
        """排序播放列表"""
        logging.info("开始对播放列表进行排序")
        current_path = self.media_core.current_path
        new_index = self.playlist_manager.sort_playlist(current_path)
        # 高亮当前播放项
        self.highlight_current_item(new_index)
        logging.info("播放列表排序完成")

    def show_context_menu(self, position):
        """右键菜单（删除项）"""
        menu = QMenu()
        remove_action = menu.addAction("删除")
        action = menu.exec_(self.playlist_widget.mapToGlobal(position))
        if action == remove_action:
            logging.debug("用户选择删除选中的播放列表项")
            self.playlist_manager.remove_selected()
        else:
            logging.debug("用户取消了右键菜单操作")

    def _update_metadata_display(self, file_path: str):
        """解析并显示元数据"""
        # 解析元数据
        metadata = self.meta_parser.parse_metadata(file_path)
        # 更新歌曲信息
        self.song_title_label.setText(metadata["title"])
        self.song_artist_label.setText(f"艺术家: {metadata['artist']}" if metadata['artist'] else "")
        self.song_album_label.setText(f"专辑: {metadata['album']}" if metadata['album'] else "")
        # 更新封面
        if metadata["cover_path"] and os.path.exists(metadata["cover_path"]):
            pixmap = QPixmap(metadata["cover_path"]).scaled(
                200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.cover_label.setPixmap(pixmap)
        else:
            # 无封面时显示默认封面
            if self.config.default_cover and os.path.exists(self.config.default_cover):
                self.cover_label.setPixmap(QPixmap(self.config.default_cover).scaled(
                    200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation
                ))
            else:
                self.cover_label.clear()
        # 解析歌词并填充到歌词列表控件
        self.lyric_lines = []
        self.lyric_times = []
        self.lyrics_list.clear()
        raw_lyrics = metadata["lyrics"] if metadata["lyrics"] else "暂无歌词..."
        import re
        lrc_pattern = re.compile(r"\[(\d+):(\d+)(?:\.(\d+))?\](.*)")
        for line in raw_lyrics.splitlines():
            match = lrc_pattern.match(line)
            if match:
                min, sec, ms, text = match.groups()
                total_ms = int(min)*60*1000 + int(sec)*1000 + (int(ms) if ms else 0)*10
                self.lyric_times.append(total_ms)
                self.lyric_lines.append(text.strip() if text else "")
            else:
                if line.strip():
                    self.lyric_times.append(None)
                    self.lyric_lines.append(line.strip())
        if not self.lyric_lines:
            self.lyric_lines = ["暂无歌词..."]
            self.lyric_times = [None]
        for l in self.lyric_lines:
            item = QListWidgetItem(l)
            self.lyrics_list.addItem(item)
        self.current_lyric_index = 0
        self.lyrics_list.setCurrentRow(0)

    def play_selected(self, item: QListWidgetItem):
        """播放选中的项"""
        file_path = item.data(Qt.UserRole)
        if file_path:
            self.current_index = self.playlist_manager.playlist.index(file_path)
            logging.info(f"用户双击选择播放文件: {os.path.basename(file_path)} (索引: {self.current_index})")
            self.media_core.play(file_path)
            self._end_handled = False
            self.play_btn.setText("暂停")
            self.highlight_current_item()
            # 解析并显示元数据（歌词与播放同步）
            self._update_metadata_display(file_path)
        else:
            logging.warning("选中的播放列表项无有效文件路径，无法播放")

    def play_previous(self):
        """上一曲"""
        logging.debug("用户点击上一曲按钮")
        if not self.playlist_manager.playlist:
            logging.warning("尝试播放上一曲，但播放列表为空")
            return
        prev_index = self.play_mode_manager.get_prev_index(
            self.current_index, self.playlist_manager.playlist
        )
        if prev_index != -1:
            self.current_index = prev_index
            play_file = self.playlist_manager.playlist[prev_index]
            logging.info(f"切换到上一曲: {os.path.basename(play_file)} (索引: {prev_index})")
            self.media_core.play(play_file)
            self._end_handled = False
            self.highlight_current_item()
            # 解析并显示元数据（歌词与播放同步）
            self._update_metadata_display(play_file)
        else:
            logging.warning("无法获取上一曲索引，播放列表可能为空")

    def play_next(self):
        """下一曲"""
        logging.debug("用户点击下一曲按钮")
        if not self.playlist_manager.playlist:
            logging.warning("尝试播放下一曲，但播放列表为空")
            return
        next_index = self.play_mode_manager.get_next_index(
            self.current_index, self.playlist_manager.playlist
        )
        if next_index != -1:
            self.current_index = next_index
            play_file = self.playlist_manager.playlist[next_index]
            logging.info(f"切换到下一曲: {os.path.basename(play_file)} (索引: {next_index})")
            self.media_core.play(play_file)
            self._end_handled = False
            self.highlight_current_item()
            # 解析并显示元数据（歌词与播放同步）
            self._update_metadata_display(play_file)
        else:
            logging.warning("无法获取下一曲索引，播放列表可能为空")

    def play_pause(self):
        """播放/暂停切换"""
        logging.debug("用户点击播放/暂停按钮")
        if not self.playlist_manager.playlist:
            # 替换QMessageBox为日志
            logging.warning("尝试播放/暂停，但播放列表为空")
            return
        # 首次播放：播放第一首
        if self.media_core.get_state() == QMediaPlayer.StoppedState:
            self.current_index = 0 if self.current_index == -1 else self.current_index
            play_file = self.playlist_manager.playlist[self.current_index]
            logging.info(f"首次播放，选择播放列表第{self.current_index}首: {os.path.basename(play_file)}")
            self.media_core.play(play_file)
            self._end_handled = False
            self.play_btn.setText("暂停")
            self.highlight_current_item()
            # 解析并显示元数据（歌词与播放同步）
            self._update_metadata_display(play_file)
        elif self.media_core.get_state() == QMediaPlayer.PlayingState:
            logging.info(f"暂停播放: {os.path.basename(self.media_core.current_path)}")
            self.media_core.pause()
            self.play_btn.setText("播放")
        else:
            logging.info(f"恢复播放: {os.path.basename(self.media_core.current_path)}")
            self.media_core.resume()
            self._end_handled = False
            self.play_btn.setText("暂停")

    def change_play_mode(self, mode_name: str):
        """切换播放模式"""
        logging.info(f"用户切换播放模式: {mode_name}")
        self.play_mode_manager.set_mode(mode_name)

    def set_volume(self, volume: int):
        """设置音量（同步显示）"""
        logging.debug(f"用户调整音量到: {volume}%")
        self.media_core.set_volume(volume)
        self.volume_value_label.setText(f"{volume}%")

    def set_position(self, position: int):
        """设置播放进度"""
        logging.debug(f"用户调整播放进度到: {position}ms")
        self.media_core.set_position(position)

    def update_progress(self):
        """更新进度条和时间显示"""
        current_pos = self.media_core.get_position()
        total_duration = self.media_core.get_duration()
        # 更新进度条
        self.progress_slider.setRange(0, total_duration)
        self.progress_slider.setValue(current_pos)
        # 格式化时间（时:分:秒）
        self.current_time_label.setText(self._format_time(current_pos))
        self.total_time_label.setText(self._format_time(total_duration))
        # 歌词逐行高亮滚动
        if hasattr(self, 'lyric_times') and self.lyric_times:
            idx = 0
            for i, t in enumerate(self.lyric_times):
                if t is not None and current_pos >= t:
                    idx = i
            if getattr(self, 'current_lyric_index', -1) != idx:
                self.current_lyric_index = idx
                self.lyrics_list.setCurrentRow(idx)
                self.lyrics_list.scrollToItem(self.lyrics_list.item(idx))
        # 自动切歌：播放结束检测（避免重复触发）
        try:
            if total_duration > 0:
                near_end = current_pos >= max(0, total_duration - 1000)
                not_playing = (self.media_core.get_state() != QMediaPlayer.PlayingState)
                finished_by_position = (near_end or current_pos == 0)
                if not self._end_handled and (near_end or (not_playing and finished_by_position)):
                    self._end_handled = True
                    logging.info(f"歌曲播放完成，准备自动切换下一曲: {os.path.basename(self.media_core.current_path)}")
                    QTimer.singleShot(200, self.play_next)
                elif not near_end and not_playing == False:
                    self._end_handled = False
        except Exception as e:
            logging.error(f"检测播放进度时发生错误: {str(e)}")

    def _format_time(self, ms: int) -> str:
        """格式化毫秒为 HH:MM:SS"""
        seconds = ms // 1000
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def highlight_current_item(self, index: int = None):
        """高亮当前播放项"""
        target_index = index if index is not None else self.current_index
        if 0 <= target_index < self.playlist_widget.count():
            self.playlist_widget.setCurrentRow(target_index)
            logging.debug(f"高亮播放列表第{target_index}项")
        else:
            logging.debug(f"无法高亮播放列表项，索引{target_index}无效")

    # ------------------- 拖放事件（容错处理） -------------------
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            logging.debug("检测到文件拖入，允许拖放操作")
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        """拖放添加文件/文件夹"""
        logging.debug("处理文件拖放操作")
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isdir(path):
                logging.info(f"拖入文件夹: {path}，开始扫描音频文件")
                self.playlist_manager.add_folder(path)
            elif os.path.isfile(path):
                logging.info(f"拖入文件: {path}，添加到播放列表")
                self.playlist_manager.add_file(path)
        self.playlist_manager.save_playlist()
        logging.info("拖放操作完成，已保存播放列表")

    # ------------------- 资源释放（稳定性） -------------------
    def closeEvent(self, event):
        """窗口关闭时释放资源"""
        logging.info("开始关闭音乐播放器，释放资源")
        # 清理元数据解析器的临时文件
        self.meta_parser.cleanup()
        self.media_core.release()
        self.tray.hide()
        self.playlist_manager.save_playlist()
        logging.info("播放器资源已释放，播放列表已保存，临时封面文件已清理")
        logging.info("="*50)
        logging.info("音乐播放器程序正常退出")
        logging.info("="*50)
        event.accept()

    # ------------------- Windows电源事件（可选） -------------------
    def nativeEvent(self, eventType, message):
        if not is_windows():
            return super().nativeEvent(eventType, message)
        # 原电源事件逻辑（可进一步拆分为PowerEventHandler模块）
        try:
            import ctypes
            from ctypes import Structure, c_long, c_uint, c_void_p
            class MSG(Structure):
                _fields_ = [("hwnd", c_void_p), ("message", c_uint), ("wParam", c_long), ("lParam", c_long), ("time", c_uint), ("pt", c_long * 2)]
            msg_ptr = message[0] if isinstance(message, tuple) else message
            msg = MSG.from_address(int(msg_ptr))
            import win32con
            if msg.message == win32con.WM_POWERBROADCAST:
                if msg.wParam == win32con.PBT_APMSUSPEND:
                    logging.info("检测到系统休眠事件，暂停播放")
                    self.was_playing = self.media_core.get_state() == QMediaPlayer.PlayingState
                    self.last_position = self.media_core.get_position()
                    if self.was_playing:
                        self.media_core.pause()
                        self.play_btn.setText("播放")
                elif msg.wParam in (win32con.PBT_APMRESUMESUSPEND, win32con.PBT_APMRESUMEAUTOMATIC):
                    logging.info("检测到系统恢复事件，恢复播放")
                    if self.was_playing and 0 <= self.current_index < len(self.playlist_manager.playlist):
                        play_file = self.playlist_manager.playlist[self.current_index]
                        self.media_core.play(play_file, self.last_position)
                        self.play_btn.setText("暂停")
                        # 重新解析元数据（防止临时文件丢失）
                        self._update_metadata_display(play_file)
                return True, 0
        except Exception as e:
            logging.error(f"处理电源事件失败: {str(e)}")
        return super().nativeEvent(eventType, message)

# ------------------- 程序入口 -------------------
if __name__ == '__main__':
    # 确保日志已初始化（双重保障）
    if not logging.getLogger().handlers:
        init_logging()
    
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 托盘保留时不退出
    player = MusicPlayer()
    player.show()
    logging.info("音乐播放器窗口已显示")
    sys.exit(app.exec_())