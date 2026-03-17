# media_core.py
import os
import time
import logging
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtCore import QUrl, QTimer, Qt, QThread, pyqtSignal
from config_manager import ConfigManager

# 媒体加载线程（避免阻塞UI）
class MediaLoadThread(QThread):
    load_finished = pyqtSignal(str, bool)  # (file_path, success)
    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = file_path
        logging.debug(f"MediaLoadThread 初始化，目标文件: {os.path.basename(file_path)}")
    
    def run(self):
        """模拟耗时的媒体加载（实际可扩展为格式校验、元数据预解析）"""
        try:
            # 这里可扩展：校验文件完整性、格式支持等
            time.sleep(0.1)  # 模拟IO耗时
            self.load_finished.emit(self.file_path, True)
            logging.debug(f"MediaLoadThread 加载完成: {os.path.basename(self.file_path)}")
        except Exception as e:
            logging.error(f"MediaLoadThread 加载失败: {str(e)}")
            self.load_finished.emit(self.file_path, False)

class MediaPlayerCore:
    def __init__(self):
        self.config = ConfigManager().get_config()
        self.player = QMediaPlayer()
        self.current_path = ""
        self.load_retry_count = 0
        self.load_thread = None  # 加载线程
        
        # 定时器：加载超时、进度更新
        self.progress_timer = QTimer()
        self.progress_timer.timeout.connect(self.on_progress_update)
        self.load_timeout_timer = QTimer()
        self.load_timeout_timer.setSingleShot(True)
        self.load_timeout_timer.timeout.connect(self.on_load_timeout)
        
        # 信号绑定
        self.player.error.connect(self.on_media_error)
        self.player.mediaStatusChanged.connect(self.on_media_status_changed)
        logging.info("MediaPlayerCore 初始化完成")
    
    def play(self, file_path: str, position: int = 0) -> None:
        """播放指定文件（异步加载，避免UI阻塞）"""
        if self.load_thread and self.load_thread.isRunning():
            self.load_thread.terminate()  # 终止未完成的加载
            logging.debug(f"终止未完成的加载线程: {os.path.basename(file_path)}")
        
        self.current_path = file_path
        self.load_retry_count = 0
        self._start_load_file(file_path, position)
        logging.info(f"开始播放文件: {os.path.basename(file_path)}，起始位置: {position}ms")
    
    def _start_load_file(self, file_path: str, position: int = 0) -> None:
        """启动文件加载（含重试逻辑）"""
        # 异步加载文件，避免UI卡顿
        self.load_thread = MediaLoadThread(file_path)
        self.load_thread.load_finished.connect(lambda path, ok: self.on_load_complete(path, ok, position))
        self.load_thread.start()
        logging.debug(f"启动文件加载线程: {os.path.basename(file_path)}")
        
        # 启动加载超时定时器
        self.load_timeout_timer.start(self.config.load_timeout)
    
    def on_load_complete(self, file_path: str, success: bool, position: int) -> None:
        """加载完成回调"""
        self.load_timeout_timer.stop()
        if not success:
            self.load_retry_count += 1
            logging.warning(f"文件加载失败: {os.path.basename(file_path)}，重试次数: {self.load_retry_count}")
            if self.load_retry_count <= self.config.max_retry_count:
                # 延迟重试
                QTimer.singleShot(self.config.retry_delay, lambda: self._start_load_file(file_path, position))
                logging.debug(f"计划{self.config.retry_delay}ms后重试加载: {os.path.basename(file_path)}")
                return
            else:
                self.on_media_error(f"文件加载失败：{file_path}（重试{self.config.max_retry_count}次后仍失败）")
                return
        
        # 加载成功，设置媒体源并播放
        media_content = QMediaContent(QUrl.fromLocalFile(file_path))
        self.player.setMedia(media_content)
        self.player.setPosition(position)
        self.player.play()
        self.progress_timer.start(1000)
        logging.debug(f"文件加载成功并开始播放: {os.path.basename(file_path)}")
    
    def on_load_timeout(self) -> None:
        """加载超时处理"""
        if self.load_thread and self.load_thread.isRunning():
            self.load_thread.terminate()
            logging.debug(f"终止超时的加载线程: {os.path.basename(self.current_path)}")
        self.on_media_error(f"文件加载超时：{self.current_path}")
        self.load_retry_count += 1
        logging.warning(f"文件加载超时: {os.path.basename(self.current_path)}，重试次数: {self.load_retry_count}")
        if self.load_retry_count <= self.config.max_retry_count:
            QTimer.singleShot(self.config.retry_delay, lambda: self._start_load_file(self.current_path))
            logging.debug(f"计划{self.config.retry_delay}ms后重试加载: {os.path.basename(self.current_path)}")
    
    def on_media_error(self, error: str = None) -> None:
        """媒体错误处理"""
        if not error:
            error = f"播放错误：{self.player.errorString()}"
        logging.error(f"媒体错误: {error}")
        self.progress_timer.stop()
    
    def on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        """媒体状态变化处理"""
        status_map = {
            QMediaPlayer.NoMedia: "无媒体文件",
            QMediaPlayer.LoadingMedia: "正在加载媒体",
            QMediaPlayer.LoadedMedia: "媒体加载完成",
            QMediaPlayer.BufferingMedia: "正在缓冲",
            QMediaPlayer.BufferedMedia: "缓冲完成",
            QMediaPlayer.EndOfMedia: "播放完成",
            QMediaPlayer.InvalidMedia: "无效媒体"
        }
        status_text = status_map.get(status, f"未知状态({status})")
        logging.debug(f"媒体状态变化: {status_text}")
        
        if status == QMediaPlayer.EndOfMedia:
            self.progress_timer.stop()
            logging.info(f"文件播放完成: {os.path.basename(self.current_path)}")
    
    def on_progress_update(self) -> None:
        """进度更新（暴露给上层UI调用）"""
        pass
    
    def pause(self) -> None:
        """暂停播放"""
        self.player.pause()
        self.progress_timer.stop()
        logging.info(f"暂停播放: {os.path.basename(self.current_path)}")
    
    def resume(self) -> None:
        """恢复播放"""
        self.player.play()
        self.progress_timer.start(1000)
        logging.info(f"恢复播放: {os.path.basename(self.current_path)}")
    
    def stop(self) -> None:
        """停止播放，释放资源"""
        self.player.stop()
        self.progress_timer.stop()
        if self.load_thread and self.load_thread.isRunning():
            self.load_thread.terminate()
            logging.debug(f"终止加载线程: {os.path.basename(self.current_path)}")
        logging.info(f"停止播放: {os.path.basename(self.current_path) if self.current_path else '无当前播放文件'}")
    
    def get_position(self) -> int:
        """获取当前播放位置"""
        pos = self.player.position()
        logging.debug(f"获取当前播放位置: {pos}ms")
        return pos
    
    def set_position(self, position: int) -> None:
        """设置播放位置"""
        self.player.setPosition(position)
        logging.debug(f"设置播放位置: {position}ms，文件: {os.path.basename(self.current_path)}")
    
    def set_volume(self, volume: int) -> None:
        """设置音量"""
        self.player.setVolume(volume)
        logging.debug(f"设置音量: {volume}%")
    
    def get_duration(self) -> int:
        """获取媒体总时长"""
        dur = self.player.duration()
        logging.debug(f"获取媒体总时长: {dur}ms")
        return dur
    
    def get_state(self) -> QMediaPlayer.State:
        """获取播放状态"""
        state = self.player.state()
        state_map = {
            QMediaPlayer.StoppedState: "停止",
            QMediaPlayer.PlayingState: "播放中",
            QMediaPlayer.PausedState: "暂停"
        }
        logging.debug(f"获取播放状态: {state_map.get(state, f'未知({state})')}")
        return state
    
    def release(self) -> None:
        """释放资源"""
        self.stop()
        self.player.deleteLater()
        self.progress_timer.deleteLater()
        self.load_timeout_timer.deleteLater()
        logging.info("释放媒体播放器资源完成")