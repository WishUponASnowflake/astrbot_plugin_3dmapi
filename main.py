from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
import httpx
import asyncio
import json
from datetime import datetime

@register("astrbot_plugin_3dmapi", "--sora--", "3dmmod 搜索插件", "2.0","https://github.com/sora-yyds/astrbot_plugin_3dmapi")
class ModSearchPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.api_url = "https://mod.3dmgame.com/api/v3/mods"
        self.game_id = config.get("game_id", 261)
        self.appkey = config.get("appkey", "{APPKEY}")
        self.max_results = config.get("max_results", 10)
        self.sort_order = config.get("sort_order", "时间排序")
        # 这些高级项已从配置中移除，这里固定为安全默认值
        self.sort_by = "mods_createTime"
        self.sort_order_api = "desc"
        self.is_recommend = False

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""
        logger.info("3dmmod搜索插件初始化完成")
        if self.appkey == "{APPKEY}":
            logger.warning("请在插件配置中设置正确的API密钥")
    
    @filter.command("mod搜索")
    async def mod_search(self, event: AstrMessageEvent, message: str = ""):
        """搜索3dmmod站上的mod内容"""
        # 仅从消息文本中解析关键词，避免额外参数注入导致 Context 初始化错误
        raw = (getattr(event, "message_str", "") or "").strip()
        keyword = ""
        # 移除常见的指令前缀，例如：/mod搜索 关键词
        for prefix in ["/mod搜索", "mod搜索", "/mod 搜索", "/modsearch"]:
            if raw.startswith(prefix):
                keyword = raw[len(prefix):].strip()
                break
        # 如果未匹配到前缀，尝试按空格切分获取第二段作为关键词
        if not keyword and raw:
            parts = raw.split(None, 1)
            if parts and (parts[0] in {"/mod搜索", "mod搜索"}) and len(parts) == 2:
                keyword = parts[1].strip()
        # 若框架已解析出第一个参数到 message，兜底采用它
        if not keyword and message:
            keyword = str(message).strip()
        if not keyword:
            yield event.plain_result("请提供搜索关键词！\n使用方法: /mod搜索 <关键词>")
            return
        if self.appkey == "{APPKEY}":
            yield event.plain_result("× 插件未配置API密钥，请联系管理员配置后使用")
            return
        try:
            # V3 API参数适配
            sort_by_mapping = {
                "时间排序": "mods_createTime",
                "下载量排序": "mods_download_cnt",
                "综合排序": "id"  # 假设id为综合排序
            }
            sort_by = sort_by_mapping.get(self.sort_order, self.sort_by)
            sort_order_api = "desc"
            # 构建V3 API参数（注意将布尔转换为 0/1）
            payload_base = {
                "page": 1,
                "gameId": self.game_id,
                "isRecommend": 1 if bool(self.is_recommend) else 0,
                "sortBy": sort_by,
                "sortOrder": sort_order_api,
                "pageSize": int(self.max_results),
                # 关键词参数，search 为当前验证可用键；保留其它以兼容旧实现
                "search": keyword,
                "key": keyword,
                "keyword": keyword,
            }
            
            headers_auth = {
                "Authorization": self.appkey,
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache"
            }
            headers_bearer = dict(headers_auth)
            if not str(self.appkey).lower().startswith("bearer "):
                headers_bearer["Authorization"] = f"Bearer {self.appkey}"
            
            logger.info(f"正在搜索关键词: {keyword}")
            logger.debug(f"API URL: {self.api_url}")
            logger.debug(f"请求参数: {payload_base}")

            async def do_request(params: dict, headers: dict):
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(self.api_url, headers=headers, params=params)
                return resp

            # 尝试 1：默认参数 + Authorization 头
            response = await do_request(payload_base, headers_auth)
            logger.debug(f"API响应状态码(尝试1): {response.status_code}")

            def get_count(data_obj: dict) -> int:
                # 形态A：{ data: [ ... ], total? }
                if isinstance(data_obj.get("data"), list):
                    return int(data_obj.get("total", len(data_obj.get("data", []))) or 0)
                # 形态B：{ data: { data: [ ... ], total? } }
                if isinstance(data_obj.get("data"), dict):
                    d = data_obj.get("data", {})
                    if isinstance(d.get("data"), list):
                        return int(d.get("total", len(d.get("data", []))) or 0)
                    # 形态C：旧版 { data: { mod: [ ... ], count? } }
                    return int(d.get("count", len(d.get("mod", []))) or 0)
                return 0

            data = None
            if response.status_code == 200:
                data = response.json()
                total_cnt = get_count(data)
                if total_cnt == 0:
                    # 尝试 2：去掉 gameId（全站搜索）
                    payload_no_gid = dict(payload_base)
                    payload_no_gid.pop("gameId", None)
                    logger.debug("结果为空，尝试去掉 gameId 进行全站搜索")
                    resp2 = await do_request(payload_no_gid, headers_auth)
                    if resp2.status_code == 200:
                        data2 = resp2.json()
                        if get_count(data2) > 0:
                            data = data2
                        else:
                            # 尝试 3：使用 Bearer 认证
                            logger.debug("全站搜索仍为空，尝试 Bearer 认证方式")
                            resp3 = await do_request(payload_base, headers_bearer)
                            if resp3.status_code == 200:
                                data3 = resp3.json()
                                if get_count(data3) > 0:
                                    data = data3
                                else:
                                    # 尝试 4：仅使用 keyword 参数
                                    payload_kw_only = dict(payload_base)
                                    payload_kw_only.pop("key", None)
                                    logger.debug("Bearer 仍为空，尝试仅使用 keyword 参数")
                                    resp4 = await do_request(payload_kw_only, headers_auth)
                                    if resp4.status_code == 200:
                                        data4 = resp4.json()
                                        if get_count(data4) > 0:
                                            data = data4
                # 正常返回（不管是否经过回退），统一格式化
                if data is not None:
                    logger.debug(f"API响应数据(最终): {data}")
                    async for result in self._format_search_results(event, data, keyword):
                        yield result
                    return
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
            # 如果走到这里，说明 200 但没有任何回退拿到结果
            if data is None and response.status_code == 200:
                async for result in self._format_search_results(event, {"data": [], "total": 0}, keyword):
                    yield result
                        
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
            # 兼容 V2/V3 的响应结构
            mods = []
            total_count = 0
            if isinstance(data.get("data"), list):
                # 形态A
                mods = data.get("data", [])
                total_count = int(data.get("total", len(mods)) or 0)
            elif isinstance(data.get("data"), dict):
                # 形态B 或 形态C
                d = data.get("data", {})
                if isinstance(d.get("data"), list):
                    mods = d.get("data", [])
                    total_count = int(d.get("total", len(mods)) or 0)
                else:
                    # 形态C（旧版）
                    mods = d.get("mod", [])
                    total_count = int(d.get("count", len(mods)) or 0)
            else:
                # 旧接口错误码处理
                code = data.get("code")
                if code is not None and str(code) not in ("00", "0"):
                    error_msg = data.get("message", "API返回错误")
                    yield event.plain_result(f"× 搜索失败: {error_msg}")
                    return
            if not mods:
                yield event.plain_result(f"· 未找到关键词 '{keyword}' 相关的mod内容")
                return
            # 可选：按更新时间进行本地排序（优先资源的最新时间，其次更新字段，最后创建时间）
            def parse_time(s: str) -> float:
                if not s:
                    return 0.0
                try:
                    ss = str(s).strip()
                    # ISO 8601：2025-09-12T05:55:54.736Z
                    if "T" in ss:
                        # 去掉尾部 Z
                        if ss.endswith("Z"):
                            ss = ss[:-1]
                        # 带毫秒
                        try:
                            dt = datetime.fromisoformat(ss)
                            return dt.timestamp()
                        except Exception:
                            pass
                        # 兜底：仅取日期部分
                        try:
                            return datetime.strptime(ss.split("T", 1)[0], "%Y-%m-%d").timestamp()
                        except Exception:
                            return 0.0
                    # 常见日期：YYYY-MM-DD 或 YYYY/MM/DD
                    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
                        try:
                            return datetime.strptime(ss.split(" ", 1)[0], fmt).timestamp()
                        except Exception:
                            continue
                except Exception:
                    return 0.0
                return 0.0

            def latest_resource_time(mod: dict) -> str:
                try:
                    res = mod.get("mods_resource", [])
                    if not res:
                        return ""
                    # 优先 latest_version
                    latest = None
                    for r in res:
                        if r.get("mods_resource_latest_version"):
                            latest = r
                            break
                    if not latest:
                        # 按资源创建时间取最大
                        latest = max(res, key=lambda x: parse_time(x.get("mods_resource_createTime", "")))
                    return latest.get("mods_resource_createTime", "") or ""
                except Exception:
                    return ""

            def pick_publish_time(mod: dict) -> str:
                pt = mod.get("createTime", mod.get("mods_createTime", ""))
                if pt:
                    return pt
                # 兜底用资源时间
                return latest_resource_time(mod)

            def pick_update_time(mod: dict) -> str:
                ut = mod.get("updateTime", mod.get("mods_updateTime", ""))
                if ut:
                    return ut
                # 若无显式更新时间，使用资源最新创建时间
                res_t = latest_resource_time(mod)
                if res_t:
                    return res_t
                # 最后回退到创建时间
                return mod.get("createTime", mod.get("mods_createTime", ""))

            # 如果用户选择“时间排序”，则按更新时间本地排序，保证最近更新靠前
            if self.sort_order == "时间排序" and mods:
                mods.sort(key=lambda m: parse_time(pick_update_time(m)), reverse=True)

            # 构建结果消息
            sort_desc = f" - 按{self.sort_order}"
            result_lines = [
                f"▌3DMGame Mod搜索结果",
                f"▌关键词: {keyword}",
                f"▌找到 {len(mods)} 个相关mod (总计{total_count}个){sort_desc}\n"
            ]
            
            for i, mod in enumerate(mods[:self.max_results], 1):
                title = mod.get("title", mod.get("mods_title", "未知标题"))
                author = mod.get("author", mod.get("mods_author", mod.get("user_nickName", "未知作者")))
                publish_time = pick_publish_time(mod)
                update_time = pick_update_time(mod)
                mod_id = mod.get("id", mod.get("mods_id", ""))
                downloads = mod.get("downloadCnt", mod.get("mods_download_cnt", 0))
                size = mod.get("size", mod.get("mods_resource_size", ""))
                if not size:
                    try:
                        res = mod.get("mods_resource", [])
                        if res and isinstance(res, list):
                            size = res[0].get("mods_resource_size", "")
                    except Exception:
                        pass
                if not size:
                    size = "未知大小"
                # 格式化发布时间
                if publish_time:
                    try:
                        s = str(publish_time)
                        formatted_pub = s.split("T", 1)[0] if "T" in s else s.split(" ", 1)[0]
                    except Exception:
                        formatted_pub = str(publish_time)
                else:
                    formatted_pub = "未知时间"
                # 格式化更新时间
                if update_time:
                    try:
                        su = str(update_time)
                        formatted_upd = su.split("T", 1)[0] if "T" in su else su.split(" ", 1)[0]
                    except Exception:
                        formatted_upd = str(update_time)
                else:
                    formatted_upd = formatted_pub
                # 构建下载链接
                download_link = f"https://mod.3dmgame.com/mod/{mod_id}" if mod_id else "链接不可用"
                result_lines.append(
                    f"• {i}. {title}\n"
                    f"  作者: {author}\n"
                    f"  发布: {formatted_pub}\n"
                    f"  更新: {formatted_upd}\n"
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
  排序方式: {self.sort_order}
  API状态: {'✓ 已配置' if self.appkey != '{APPKEY}' else '× 未配置'}

· 说明:
  默认按时间排序显示最新内容
  结果包含标题、作者、发布时间、更新时间、下载次数、文件大小和下载链接
  如果搜索结果较多会自动分段发送
  如遇问题请联系管理员检查API配置

▌本插件由--sora--提供技术支持
        """
        yield event.plain_result(help_text.strip())

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
        logger.info("3dmmod搜索插件已卸载")
