# 3DMGame Mod 搜索插件

在 3DMGame Mod 站按关键词搜索并返回结果的 AstrBot 插件，已适配 v3 接口与异步 httpx。

## 功能特性

- 🔍 关键词搜索（支持 v3 接口，使用 `search` 参数）
- 🧾 结果包含：标题、作者、发布/更新日期、下载量、大小、详情链接
- ⏫ “时间排序”将按更新时间降序显示（优先资源最新时间，其次更新字段，最后创建时间）
- ⚙️ 可配置 API Key、游戏 ID、最大结果数、排序等
- 📱 长消息自动分段发送

## 安装与配置

1. 将插件拷贝到 AstrBot 的插件目录（通常在 `AstrBot/data/plugins` 下）。
2. 启动 AstrBot，打开 WebUI → 插件管理 → 找到 `astrbot_plugin_3dmapi` → 管理 → 插件配置。
3. 配置项说明（对应 `_conf_schema.json`）：
   - `appkey`：3DM API 密钥（必填）。
   - `game_id`：游戏 ID（默认 261）。
   - `max_results`：单次返回结果条数（默认 10）。
  - `sort_order`：展示排序方式（默认“时间排序”，本地按“更新时间”降序）。

## 使用方法

指令：

- 搜索：`/mod搜索 <关键词>`
- 帮助：`/mod帮助`

示例：

- `/mod搜索 工具箱`
- `/mod搜索 整合包`

## 输出示例

```
▌3DMGame Mod搜索结果
▌关键词: 工具箱
▌找到 5 个相关mod (总计5个) - 按时间排序

• 1. [GTA5增强版]工具箱 (解决OpenIV无法识别增强版目录)
  作者: 随梦&而飞
  发布: 2025-08-31
  更新: 2025-09-07
  下载: 12551
  大小: 229.33KB
  链接: https://mod.3dmgame.com/mod/222796

...（其余若干条）

▌本插件由--sora--提供技术支持
```

说明：

- 发布/更新时间将自动兼容 ISO 8601（含 `T`/`Z`）与常规日期字符串。
- 大小字段会从 `size`/`mods_resource_size` 回填，不存在时显示“未知大小”。

## 接口说明

- 基础接口：`https://mod.3dmgame.com/api/v3/mods`
- 关键词参数：优先使用 `search`，同时保留 `key`/`keyword` 以兼容服务端差异。
- 认证：`Authorization: <APPKEY>`；必要时也兼容 `Bearer <APPKEY>`。

## 本地联调脚本（可选）

仓库提供了独立测试脚本 `mod_search_local_test.py`，可不依赖 AstrBot 直接验证关键词是否能查到结果：

示例（PowerShell）：

```
python mod_search_local_test.py -k 工具箱 -a <你的APPKEY>
```

脚本会尝试多种参数变体和认证方式，并输出“命中尝试”信息，便于排查。

## 依赖

- `httpx>=0.24.0`（见 `requirements.txt`）

## 常见问题

- 提示未配置 API Key：请在插件配置中填写 `appkey`。
- 无搜索结果：尝试更换关键词，或确认 3DM 站点端是否存在该关键词条目；也可先用 `mod_search_local_test.py` 验证接口可用性。
- 排序不符合预期：当选择“时间排序”时，插件会按“更新时间”进行客户端排序，确保最近更新靠前。

## 许可证

请参见 `LICENSE` 文件。

## 贡献与支持

欢迎提交 Issue/PR 改进本插件。

参考文档：
- [AstrBot 插件开发文档](https://docs.astrbot.app/dev/star/plugin.html)
- [3DM Mod API](https://mod.3dmgame.com/Workshop/Api)
