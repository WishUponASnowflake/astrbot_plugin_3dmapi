from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
import httpx
import asyncio
import json
from datetime import datetime

@register("astrbot_plugin_3dmapi", "--sora--", "3dmmod 搜索插件", "1.0","https://github.com/sora-yyds/astrbot_plugin_3dmapi")
class ModSearchPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.api_url = "https://mod.3dmgame.com/api/v2/GetModList"
        self.game_id = config.get("game_id", 261)
        self.appkey = config.get("appkey", "{APPKEY}")
        self.max_results = config.get("max_results", 10)

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""
        logger.info("3dmmod搜索插件初始化完成")
        if self.appkey == "{APPKEY}":
            logger.warning("请在插件配置中设置正确的API密钥")
    
    @filter.command("mod搜索")
    async def mod_search(self, event: AstrMessageEvent, message: str = ""):
        """搜索3dmmod站上的mod内容"""
        keyword = message.strip() if message else ""
        if not keyword:
            yield event.plain_result("请提供搜索关键词！\n使用方法: /mod搜索 <关键词>")
            return
            
        if self.appkey == "{APPKEY}":
            yield event.plain_result("× 插件未配置API密钥，请联系管理员配置后使用")
            return
            
        try:
            # 构建请求参数
            payload = {
                "key": keyword,
                "game_id": self.game_id,
                "page": 1,
                "pageSize": self.max_results,
                "order": 0
            }
            
            headers = {
                "Authorization": self.appkey,
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache"
            }
            
            logger.info(f"正在搜索关键词: {keyword}")
            logger.debug(f"API URL: {self.api_url}")
            logger.debug(f"请求参数: {payload}")
            
            # 使用httpx发送异步请求
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    self.api_url,
                    headers=headers,
                    json=payload  # 使用json参数，httpx会自动处理
                )
            
            logger.debug(f"API响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                logger.debug(f"API响应数据: {data}")
                async for result in self._format_search_results(event, data, keyword):
                    yield result
            elif response.status_code == 118:
                logger.error("API返回状态码118，可能是连接被重置或请求被拒绝")
                yield event.plain_result("× API连接异常，请稍后重试或联系管理员检查网络配置")
            elif response.status_code == 401:
                yield event.plain_result("× API密钥无效，请联系管理员检查配置")
            elif response.status_code == 403:
                yield event.plain_result("× API访问被拒绝，请检查权限")
            else:
                logger.error(f"API请求失败，状态码: {response.status_code}, 响应内容: {response.text}")
                yield event.plain_result(f"× 搜索失败，API返回状态码: {response.status_code}")
                        
        except httpx.TimeoutException:
            logger.error("API请求超时")
            yield event.plain_result("× 请求超时，请稍后重试或检查网络连接")
        except httpx.ConnectError as e:
            logger.error(f"网络连接错误: {e}")
            yield event.plain_result("× 网络连接失败，请检查网络连接后重试")
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP状态错误: {e}")
            yield event.plain_result(f"× HTTP请求错误: {e.response.status_code}")
        except Exception as e:
            # 处理所有其他异常
            error_msg = str(e)
            error_type = type(e).__name__
            
            logger.error(f"搜索mod时发生错误: 类型={error_type}, 消息={error_msg}")
            
            if error_msg.strip() == "":
                logger.error(f"发生未知错误（空错误消息），错误类型: {error_type}")
                yield event.plain_result(f"× 发生未知错误({error_type})，请稍后重试或联系管理员")
            else:
                yield event.plain_result(f"× 搜索过程中发生错误: {error_type} - {error_msg}")
    
    async def _format_search_results(self, event: AstrMessageEvent, data: dict, keyword: str):
        """格式化搜索结果"""
        try:
            # 检查API响应格式
            if data.get("code") != "00":
                error_msg = data.get("message", "API返回错误代码")
                yield event.plain_result(f"× 搜索失败: {error_msg}")
                return
            
            # 获取mod列表
            mod_data = data.get("data", {})
            mods = mod_data.get("mod", [])  # 注意：实际API返回的字段是"mod"而不是"list"
            total_count = mod_data.get("count", 0)
            
            if not mods:
                yield event.plain_result(f"· 未找到关键词 '{keyword}' 相关的mod内容")
                return
            
            # 构建结果消息
            result_lines = [
                f"▌3DMGame Mod搜索结果",
                f"▌关键词: {keyword}",
                f"▌找到 {len(mods)} 个相关mod (总计{total_count}个)\n"
            ]
            
            for i, mod in enumerate(mods[:self.max_results], 1):
                title = mod.get("mods_title", "未知标题")
                author = mod.get("user_nickName", "未知作者")
                publish_time = mod.get("mods_createTime", "")
                mod_id = mod.get("id", "")
                downloads = mod.get("mods_download_cnt", 0)
                size = mod.get("mods_resource_size", "未知大小")
                
                # 格式化发布时间
                if publish_time:
                    try:
                        # API返回的是字符串格式的时间，如"2025-04-19 10:05:41"
                        formatted_time = publish_time.split(" ")[0]  # 只取日期部分
                    except Exception as e:
                        formatted_time = str(publish_time)
                else:
                    formatted_time = "未知时间"
                
                # 构建下载链接
                download_link = f"https://mod.3dmgame.com/mod/{mod_id}" if mod_id else "链接不可用"
                
                result_lines.append(
                    f"• {i}. {title}\n"
                    f"  作者: {author}\n"
                    f"  发布: {formatted_time}\n"
                    f"  下载: {downloads}\n"
                    f"  大小: {size}\n"
                    f"  链接: {download_link}\n"
                )
            
            # 添加技术支持信息
            result_lines.append("▌本插件由--sora--提供技术支持")
            
            # 发送结果，如果内容过长则分段发送
            result_text = "\n".join(result_lines)
            
            # 检查消息长度，如果太长则分段发送
            if len(result_text) > 1500:  # 假设消息长度限制
                # 分段发送
                header = "\n".join(result_lines[:3])
                yield event.plain_result(header)
                
                current_text = ""
                for line in result_lines[3:-3]:  # 排除最后的技术支持信息，单独发送
                    if len(current_text + line) > 1200:
                        if current_text:
                            yield event.plain_result(current_text.strip())
                        current_text = line + "\n"
                    else:
                        current_text += line + "\n"
                
                if current_text.strip():
                    yield event.plain_result(current_text.strip())
                
                # 发送技术支持信息
                support_info = "\n".join(result_lines[-3:])
                yield event.plain_result(support_info)
            else:
                yield event.plain_result(result_text)
            
        except Exception as e:
            logger.error(f"格式化搜索结果时发生错误: {str(e)}")
            yield event.plain_result(f"× 处理搜索结果时发生错误: {str(e)}")

    @filter.command("mod帮助")
    async def mod_help(self, event: AstrMessageEvent):
        """显示mod搜索插件的帮助信息"""
        help_text = f"""
▌3DMGame Mod搜索插件帮助

· 可用指令:
  /mod搜索 <关键词> - 搜索3dmgame站上的mod内容
  /mod帮助 - 显示此帮助信息

· 使用示例:
  /mod搜索 武器包
  /mod搜索 车辆模组
  /mod搜索 地图

· 插件信息:
  当前游戏ID: {self.game_id}
  最大结果数: {self.max_results}
  API状态: {'✓ 已配置' if self.appkey != '{APPKEY}' else '× 未配置'}

· 说明:
  结果包含标题、作者、发布时间和下载链接
  如果搜索结果较多会自动分段发送
  如遇问题请联系管理员检查API配置

▌本插件由--sora--提供技术支持
        """
        yield event.plain_result(help_text.strip())

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
        logger.info("3dmmod搜索插件已卸载")
