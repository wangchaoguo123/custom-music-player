# 音乐播放器测试说明

## 环境准备

1. 安装测试依赖：
```bash
pip install -r requirements-dev.txt
```

2. 确保已安装项目依赖：
```bash
pip install PyQt5==5.15.9 mutagen>=1.46.0
```

## 运行测试

### 运行所有测试
```bash
pytest tests/ -v
```

### 运行特定测试文件
```bash
pytest tests/test_music_player.py -v
```

### 运行特定测试类
```bash
pytest tests/test_music_player.py::TestPlayModeManager -v
```

### 运行特定测试用例
```bash
pytest tests/test_music_player.py::TestPlayModeManager::test_set_play_mode -v
```

### 生成测试覆盖率报告
```bash
pytest tests/ --cov=. --cov-report=html
```

## 测试覆盖模块

### 1. 音频播放核心控制 (TestMediaCore)
- 测试 MediaPlayerCore 初始化
- 音量控制功能验证
- 播放位置控制测试

### 2. 播放列表管理 (TestPlaylistManager)
- 添加单个音频文件
- 添加多个文件
- 添加整个音频文件夹
- 清空播放列表
- 验证支持的音频格式

### 3. 播放模式切换 (TestPlayModeManager)
- 默认播放模式验证
- 三种模式切换功能
- 顺序播放索引计算
- 单曲循环模式
- 随机播放模式

### 4. 可视化展示 (间接测试)
- 元数据解析测试 (TestMetaDataParser)
- 歌曲信息解析
- 外部歌词文件解析
- 临时文件清理

### 5. 系统集成 (TestLoggingSystem, TestTrayIcon)
- 日志目录创建
- 日志文件命名格式
- 系统托盘菜单创建
- 托盘图标操作

### 6. 容错处理 (TestErrorHandling)
- 图标加载容错
- 文件路径容错
- 音频解析容错

### 7. 配置管理 (TestConfigManager)
- 配置默认值验证
- 单例模式测试
- 支持的音频格式验证

## 测试用例命名规范

所有测试用例遵循以下命名格式：
- `test_<功能描述>`：清晰描述测试的功能点
- 例如：`test_add_single_file`、`test_set_play_mode`

## 扩展测试

如需添加新的测试用例，请在相应的测试类中添加，并遵循现有的结构和命名规范。
