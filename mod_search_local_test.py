#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地独立测试脚本：直接调用 3DM v3 接口进行搜索，打印结果。
- 支持回退策略：默认 -> 去掉 gameId -> Bearer 认证 -> 仅 keyword
- 依赖 httpx（已在插件 requirements.txt 中）

用法示例（参数也可从环境变量读取）：
  python mod_search_local_test.py --keyword 工具箱 --appkey <你的APPKEY> --game-id 261
  python mod_search_local_test.py -k 整合包 -a <你的APPKEY>

环境变量：
  APPKEY         接口密钥，若未通过参数提供则从此处读取
  GAME_ID        默认为 261
  PAGE_SIZE      默认为 10
  SORT_BY        默认为 mods_createTime
  SORT_ORDER     默认为 desc
  IS_RECOMMEND   0 或 1，默认 0
"""
from __future__ import annotations
import os
import sys
import json
import argparse
import asyncio
from typing import Dict, Any

import httpx

API_URL = "https://mod.3dmgame.com/api/v3/mods"
ALT_URLS = [
    API_URL,
    "https://mod.3dmgame.com/api/v3/mods/search",
]


def build_headers(appkey: str, bearer: bool = False) -> Dict[str, str]:
    auth = appkey.strip()
    if bearer and not auth.lower().startswith("bearer "):
        auth = f"Bearer {auth}"
    return {
        "Authorization": auth,
        "Content-Type": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }


def build_params(
    keyword: str,
    game_id: int,
    page_size: int,
    sort_by: str,
    sort_order: str,
    is_recommend: int,
) -> Dict[str, Any]:
    return {
        "page": 1,
        "gameId": game_id,
        "isRecommend": 1 if is_recommend else 0,
        "sortBy": sort_by,
        "sortOrder": sort_order if sort_order in {"asc", "desc"} else "desc",
        "pageSize": int(page_size),
        # 同时带上 key 与 keyword，提升兼容性
        "key": keyword,
        "keyword": keyword,
    }


def get_count(data_obj: Dict[str, Any]) -> int:
    # 形态 A: { data: [ ... ], total?: n }
    if isinstance(data_obj.get("data"), list):
        return int(data_obj.get("total", len(data_obj.get("data", []))) or 0)
    # 形态 B: { data: { data: [ ... ], total?: n } }
    if isinstance(data_obj.get("data"), dict):
        d = data_obj.get("data", {})
        if isinstance(d.get("data"), list):
            return int(d.get("total", len(d.get("data", []))) or 0)
        # 形态 C: 旧版：{ data: { mod: [ ... ], count?: n } }
        return int(d.get("count", len(d.get("mod", []))) or 0)
    return 0


async def do_request(url: str, params: Dict[str, Any], headers: Dict[str, str]) -> httpx.Response:
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(url, headers=headers, params=params)
    return resp


def contains_hits(data: Dict[str, Any], keyword: str) -> bool:
    """粗略判断是否命中关键词（看标题/作者是否包含关键词）。"""
    kw = (keyword or "").strip().lower()
    if not kw:
        return False
    mods: list[Dict[str, Any]] = []
    if isinstance(data.get("data"), list):
        mods = data.get("data", [])
    elif isinstance(data.get("data"), dict):
        d = data.get("data", {})
        if isinstance(d.get("data"), list):
            mods = d.get("data", [])
        else:
            mods = d.get("mod", [])
    for m in mods:
        title = str(m.get("title", m.get("mods_title", ""))).lower()
        author = str(m.get("author", m.get("mods_author", m.get("user_nickName", "")))).lower()
        if kw in title or kw in author:
            return True
    return False


async def search_mods(
    appkey: str,
    keyword: str,
    game_id: int = 261,
    page_size: int = 10,
    sort_by: str = "mods_createTime",
    sort_order: str = "desc",
    is_recommend: int = 0,
) -> Dict[str, Any]:
    params_base = build_params(keyword, game_id, page_size, sort_by, sort_order, is_recommend)
    headers_auth = build_headers(appkey, bearer=False)
    headers_bearer = build_headers(appkey, bearer=True)

    # 关键词参数变体
    keyword_variants = [
        {"key": keyword, "keyword": keyword},
        {"keywords": keyword},
        {"wd": keyword},
        {"q": keyword},
        {"search": keyword},
        {"searchKey": keyword},
        {"searchWord": keyword},
        {"title": keyword},
        {"modsTitle": keyword},
    ]

    attempt_id = 0
    last_candidate: Dict[str, Any] = {"data": [], "total": 0}
    for url in ALT_URLS:
        for header_mode, headers in [("Authorization", headers_auth), ("Bearer", headers_bearer)]:
            for include_gid in [True, False]:
                for kv in keyword_variants:
                    attempt_id += 1
                    p = dict(params_base)
                    if not include_gid:
                        p.pop("gameId", None)
                    # 清理旧关键词键
                    for rm in ["key", "keyword", "keywords", "wd", "q", "search", "searchKey", "searchWord", "title", "modsTitle"]:
                        p.pop(rm, None)
                    p.update(kv)

                    print(f"[尝试{attempt_id}] URL={url.split('/api/',1)[-1]} | 头={header_mode} | 含gameId={include_gid} | 关键词键={list(kv.keys())[0]}")
                    resp = await do_request(url, p, headers)
                    print(f"  状态码: {resp.status_code}")
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    # 若接口返回有结果并且命中关键词，则接受
                    if get_count(data) > 0 and contains_hits(data, keyword):
                        data.setdefault("_meta", {})
                        data["_meta"].update({
                            "attempt": attempt_id,
                            "url": url,
                            "header": header_mode,
                            "include_gid": include_gid,
                            "kv_key": list(kv.keys())[0],
                        })
                        return data
                    # 如果有结果但未命中关键词，先记为候选（用于兜底）
                    if get_count(data) > 0:
                        candidate = data
                        candidate.setdefault("_meta", {})
                        candidate["_meta"].update({
                            "attempt": attempt_id,
                            "url": url,
                            "header": header_mode,
                            "include_gid": include_gid,
                            "kv_key": list(kv.keys())[0],
                            "note": "未检测到标题/作者包含关键词，可能接口不支持此参数键。",
                        })
                        # 不立即返回，继续尝试其他变体
                        last_candidate = candidate
                    else:
                        last_candidate = {"data": [], "total": 0}

    # 所有尝试都没有精准命中，返回最后一个候选或空
    return last_candidate


def format_results(data: Dict[str, Any]) -> str:
    mods: list[Dict[str, Any]] = []
    total = 0
    if isinstance(data.get("data"), list):
        mods = data.get("data", [])
        total = int(data.get("total", len(mods)) or 0)
    elif isinstance(data.get("data"), dict):
        d = data.get("data", {})
        if isinstance(d.get("data"), list):
            mods = d.get("data", [])
            total = int(d.get("total", len(mods)) or 0)
        else:
            mods = d.get("mod", [])
            total = int(d.get("count", len(mods)) or 0)

    if not mods:
        return "无结果"

    lines = [f"共 {len(mods)} 条（总计 {total}）\n"]
    for i, m in enumerate(mods[:10], 1):
        title = m.get("title", m.get("mods_title", "未知标题"))
        author = m.get("author", m.get("mods_author", m.get("user_nickName", "未知作者")))
        # 时间字段优先：createTime -> mods_createTime -> 资源时间
        publish_time = m.get("createTime", m.get("mods_createTime", ""))
        if not publish_time:
            try:
                res = m.get("mods_resource", [])
                if res and isinstance(res, list):
                    publish_time = res[0].get("mods_resource_createTime", "")
            except Exception:
                pass
        mod_id = m.get("id", m.get("mods_id", ""))
        downloads = m.get("downloadCnt", m.get("mods_download_cnt", 0))
        size = m.get("size", m.get("mods_resource_size", ""))
        if not size:
            try:
                res = m.get("mods_resource", [])
                if res and isinstance(res, list):
                    size = res[0].get("mods_resource_size", "")
            except Exception:
                pass
        if not size:
            size = "未知大小"
        if publish_time:
            try:
                s = str(publish_time)
                # 支持 ISO 8601
                if "T" in s:
                    s = s.split("T", 1)[0]
                else:
                    s = s.split(" ", 1)[0]
                publish_time = s
            except Exception:
                publish_time = str(publish_time)
        else:
            publish_time = "未知时间"
        link = f"https://mod.3dmgame.com/mod/{mod_id}" if mod_id else "链接不可用"
        lines.append(
            f"{i}. {title} | {author} | {publish_time} | 下载:{downloads} | 大小:{size}\n   {link}"
        )
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="3DM v3 本地搜索测试")
    parser.add_argument("-k", "--keyword", type=str, required=False, default="",
                        help="搜索关键词（必填或通过交互输入）")
    parser.add_argument("-a", "--appkey", type=str, required=False, default=os.getenv("APPKEY", ""),
                        help="API 密钥，也可用环境变量 APPKEY")
    parser.add_argument("--game-id", type=int, default=int(os.getenv("GAME_ID", 261)))
    parser.add_argument("--page-size", type=int, default=int(os.getenv("PAGE_SIZE", 10)))
    parser.add_argument("--sort-by", type=str, default=os.getenv("SORT_BY", "mods_createTime"))
    parser.add_argument("--sort-order", type=str, default=os.getenv("SORT_ORDER", "desc"))
    parser.add_argument("--is-recommend", type=int, choices=[0, 1], default=int(os.getenv("IS_RECOMMEND", 0)))
    return parser.parse_args(argv)


async def amain(argv: list[str]) -> int:
    args = parse_args(argv)
    keyword = (args.keyword or "").strip()
    if not keyword:
        keyword = input("请输入搜索关键词: ").strip()
    if not keyword:
        print("关键词不能为空")
        return 2

    appkey = (args.appkey or "").strip()
    if not appkey:
        appkey = input("请输入 APPKEY（可直接回车使用当前配置，可能 401）: ").strip()
        if not appkey:
            print("未提供 APPKEY，将尝试匿名（可能失败或结果为空）")

    print("\n==== 请求参数 ====")
    print(json.dumps({
        "keyword": keyword,
        "gameId": args.game_id,
        "pageSize": args.page_size,
        "sortBy": args.sort_by,
        "sortOrder": args.sort_order,
        "isRecommend": args.is_recommend,
    }, ensure_ascii=False, indent=2))

    try:
        data = await search_mods(
            appkey=appkey,
            keyword=keyword,
            game_id=args.game_id,
            page_size=args.page_size,
            sort_by=args.sort_by,
            sort_order=args.sort_order,
            is_recommend=args.is_recommend,
        )
    except httpx.TimeoutException:
        print("请求超时")
        return 3
    except httpx.ConnectError as e:
        print(f"网络连接失败: {e}")
        return 4
    except Exception as e:
        print(f"发生异常: {type(e).__name__}: {e}")
        return 5

    print("\n==== 原始响应片段 ====")
    try:
        print(json.dumps(data, ensure_ascii=False)[:1000])
    except Exception:
        print(str(data)[:1000])

    print("\n==== 解析后的结果 ====")
    print(format_results(data))
    if isinstance(data, dict) and data.get("_meta"):
        print("\n==== 命中尝试 ====")
        print(json.dumps(data["_meta"], ensure_ascii=False, indent=2))
    return 0


def main() -> None:
    try:
        rc = asyncio.run(amain(sys.argv[1:]))
    except KeyboardInterrupt:
        rc = 130
    sys.exit(rc)


if __name__ == "__main__":
    main()
