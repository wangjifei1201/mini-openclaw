"""
网络信息获取工具 - 抓取网页内容并转换为 Markdown
"""
import socket
import ipaddress
from urllib.parse import urlparse
from typing import Type, Tuple

import httpx
import html2text
import json
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool

from config import settings


# 私有/内网 IP 段（SSRF 防护）
_PRIVATE_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),      # Loopback
    ipaddress.ip_network("10.0.0.0/8"),       # Private Class A
    ipaddress.ip_network("172.16.0.0/12"),    # Private Class B
    ipaddress.ip_network("192.168.0.0/16"),   # Private Class C
    ipaddress.ip_network("169.254.0.0/16"),   # Link-local
    ipaddress.ip_network("0.0.0.0/8"),        # Current network
    ipaddress.ip_network("::1/128"),          # IPv6 Loopback
    ipaddress.ip_network("fc00::/7"),         # IPv6 Private
    ipaddress.ip_network("fe80::/10"),        # IPv6 Link-local
]


class FetchURLInput(BaseModel):
    """Fetch URL 工具输入参数"""
    url: str = Field(description="要获取内容的 URL 地址")


class FetchURLTool(BaseTool):
    """
    网络信息获取工具
    
    用于获取指定 URL 的网页内容，自动将 HTML 转换为 Markdown
    """
    name: str = "fetch_url"
    description: str = """获取指定 URL 的网页内容。自动将 HTML 转换为 Markdown 格式，便于阅读。
可用于查询天气、新闻、API 数据等网络信息。
注意：出于安全考虑，不允许访问内网地址或私有 IP。
输入参数：url - 完整的 URL 地址（包含 http:// 或 https://）"""
    args_schema: Type[BaseModel] = FetchURLInput
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 配置 html2text
        self._h2t = html2text.HTML2Text()
        self._h2t.ignore_links = False
        self._h2t.ignore_images = True
        self._h2t.ignore_emphasis = False
        self._h2t.body_width = 0  # 不自动换行
    
    def _is_url_safe(self, url: str) -> Tuple[bool, str]:
        """
        检查 URL 是否安全（SSRF 防护）。
        Returns: (is_safe: bool, error_msg: str)
        """
        try:
            parsed = urlparse(url)
        except Exception:
            return False, "URL 格式无效"
        
        # 仅允许 http/https 协议
        if parsed.scheme not in ("http", "https"):
            return False, f"安全限制：不允许使用 {parsed.scheme}:// 协议，仅支持 http/https"
        
        hostname = parsed.hostname
        if not hostname:
            return False, "URL 缺少主机名"
        
        # DNS 解析，获取实际 IP（防止 DNS rebinding）
        try:
            addr_infos = socket.getaddrinfo(hostname, None)
        except socket.gaierror:
            return False, f"无法解析主机名: {hostname}"
        
        for addr_info in addr_infos:
            try:
                ip = ipaddress.ip_address(addr_info[4][0])
                for network in _PRIVATE_NETWORKS:
                    if ip in network:
                        return False, f"安全限制：不允许访问内网地址 ({hostname} -> {ip})"
            except ValueError:
                # 无法解析为 IP 地址，跳过
                continue
        
        return True, ""
    
    def _run(self, url: str) -> str:
        """同步获取 URL 内容"""
        # URL 安全检查
        is_safe, error_msg = self._is_url_safe(url)
        if not is_safe:
            return f"错误：{error_msg}"
        
        try:
            # 发起请求
            with httpx.Client(timeout=settings.FETCH_TIMEOUT, follow_redirects=True) as client:
                response = client.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    }
                )
                response.raise_for_status()
            
            content_type = response.headers.get("content-type", "")
            
            # 处理 JSON 响应
            if "application/json" in content_type:
                try:
                    data = response.json()
                    output = json.dumps(data, indent=2, ensure_ascii=False)
                except:
                    output = response.text
            # 处理 HTML 响应
            elif "text/html" in content_type:
                output = self._h2t.handle(response.text)
            # 处理纯文本
            else:
                output = response.text
            
            # 截断过长输出
            if len(output) > settings.MAX_OUTPUT_LENGTH:
                output = output[:settings.MAX_OUTPUT_LENGTH] + "\n...[内容已截断]"
            
            return output if output.strip() else "获取成功但内容为空"
            
        except httpx.TimeoutException:
            return f"错误：请求超时（{settings.FETCH_TIMEOUT}秒）"
        except httpx.HTTPStatusError as e:
            return f"错误：HTTP {e.response.status_code} - {e.response.reason_phrase}"
        except Exception as e:
            return f"错误：{type(e).__name__}: {str(e)}"
    
    async def _arun(self, url: str) -> str:
        """异步获取 URL 内容"""
        # URL 安全检查
        is_safe, error_msg = self._is_url_safe(url)
        if not is_safe:
            return f"错误：{error_msg}"
        
        try:
            async with httpx.AsyncClient(timeout=settings.FETCH_TIMEOUT, follow_redirects=True) as client:
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    }
                )
                response.raise_for_status()
            
            content_type = response.headers.get("content-type", "")
            
            if "application/json" in content_type:
                try:
                    data = response.json()
                    output = json.dumps(data, indent=2, ensure_ascii=False)
                except:
                    output = response.text
            elif "text/html" in content_type:
                output = self._h2t.handle(response.text)
            else:
                output = response.text
            
            if len(output) > settings.MAX_OUTPUT_LENGTH:
                output = output[:settings.MAX_OUTPUT_LENGTH] + "\n...[内容已截断]"
            
            return output if output.strip() else "获取成功但内容为空"
            
        except httpx.TimeoutException:
            return f"错误：请求超时（{settings.FETCH_TIMEOUT}秒）"
        except httpx.HTTPStatusError as e:
            return f"错误：HTTP {e.response.status_code} - {e.response.reason_phrase}"
        except Exception as e:
            return f"错误：{type(e).__name__}: {str(e)}"


def create_fetch_url_tool() -> FetchURLTool:
    """创建 Fetch URL 工具实例"""
    return FetchURLTool()
