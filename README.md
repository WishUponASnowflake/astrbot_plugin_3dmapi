# 3DMGame Mod搜索插件

这是一个用于在3DMGame mod站搜索mod内容的AstrBot插件。

## 功能特性

- 🔍 支持关键词搜索3DMGame mod站内容
- 📊 显示前10条搜索结果（可配置）
- 📝 包含详细信息：标题、作者、发布时间、下载链接
- ⚙️ 支持配置自定义API密钥和游戏ID
- 📱 智能分段发送长消息

## 安装配置

1. 将插件放置到AstrBot的插件目录
2. 在AstrBot管理面板中找到"astrbot_plugin_3dmapi"插件
3. 点击"插件管理" -> "插件配置"
4. 设置以下配置项：
   - `appkey`: 您的[3DMGame API](https://mod.3dmgame.com/Workshop/Api)密钥
   - `game_id`: 要搜索的游戏ID（默认261）
   - `max_results`: 最大搜索结果数量（默认10）

## 使用方法

### 搜索mod
```
/mod搜索 <关键词>
```

示例：
- `/mod搜索 武器包`
- `/mod搜索 车辆模组`
- `/mod搜索 地图`

### 查看帮助
```
/mod帮助
```

## 输出格式

搜索结果将按以下格式显示：

```
▌3DMGame Mod搜索结果
▌关键词: 武器
▌找到 2 个相关mod (总计50个)

• 1. 高级武器包v2.0
  作者: ModMaker
  发布: 2024-01-15
  下载: 1500
  大小: 25MB
  链接: https://mod.3dmgame.com/mod/12345

• 2. 现代武器模组
  作者: WeaponMaster
  发布: 2024-02-10
  下载: 890
  大小: 18MB
  链接: https://mod.3dmgame.com/mod/23456

      本插件由--sora--提供技术支持
```

## API说明

本插件使用3DMGame官方API：
- 接口：`https://mod.3dmgame.com/api/v2/GetModList`
- 需要有效的API密钥才能使用

## 依赖项

- `aiohttp>=3.8.0` - 用于异步HTTP请求

## 错误处理

- ❌ API密钥无效 - 请检查配置中的appkey
- ❌ 请求超时 - 网络连接问题，请稍后重试
- ❌ 搜索失败 - API返回错误，请检查关键词或联系管理员

## 许可证

本插件遵循开源许可证，具体请查看LICENSE文件。

## 贡献

欢迎提交问题和改进建议！

## 支持

[AstrBot帮助文档](https://astrbot.app)
