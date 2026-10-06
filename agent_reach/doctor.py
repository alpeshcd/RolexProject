# -*- coding: utf-8 -*-
"""Environment health checker — powered by channels.

Each channel knows how to check itself. Doctor just collects the results.
"""

from typing import Dict

from rich.markup import escape

from agent_reach.channels import get_all_channels
from agent_reach.config import Config
from agent_reach.utils.text import scrub_url_credentials

# Translation mapping for English rendering
TRANSLATIONS = {
    "Agent Reach 状态": "Agent Reach Status",
    "图例：[green]✅[/green] 可用  [yellow][!][/yellow] 已装但需配置/登录  [red][X][/red] 未安装": "Legend: [green]✅[/green] Available  [yellow][!][/yellow] Installed (needs config/login)  [red][X][/red] Not Installed",
    "✅ 装好即用：": "✅ Ready out-of-the-box:",
    "可选渠道（已安装）：": "Optional Channels (Installed):",
    "个渠道可用": "channels available",
    "任意网页": "Any Webpage",
    "GitHub 仓库和代码": "GitHub Repositories & Code",
    "YouTube 视频和字幕": "YouTube Videos & Subtitles",
    "RSS/Atom 订阅源": "RSS/Atom Feeds",
    "全网语义搜索": "Full-Web Semantic Search (Exa)",
    "V2EX 节点、主题与回复": "V2EX Forum Posts & Replies",
    "Twitter/X 推文": "Twitter/X Tweets & Timelines",
    "Reddit 帖子和评论": "Reddit Posts & Comments",
    "Facebook 帖子、主页和群组": "Facebook Posts & Pages",
    "Instagram 用户、主页和指定用户帖子": "Instagram Profiles & Posts",
    "B站视频、字幕和搜索": "Bilibili Videos & Subtitles",
    "小红书笔记": "Xiaohongshu (XHS) Notes",
    "小宇宙播客转文字": "Xiaoyuzhou Podcast Transcripts",
    "雪球股票行情与社区动态": "Xueqiu Stock Market Data",
    "LinkedIn 职业社交": "LinkedIn Profiles & Jobs",
    "Boss直聘 职位搜索与 JD": "Boss Zhipin Job Search",
    "gh CLI 未安装。安装：": "gh CLI not installed. Install: ",
    "gh CLI 已安装": "gh CLI installed",
    "通过 Jina Reader 读取任意网页（curl https://r.jina.ai/URL）": "Read any webpage via Jina Reader (curl https://r.jina.ai/URL)",
    "可读取 RSS/Atom 源": "Can read RSS/Atom feeds",
    "需要 mcporter + Exa MCP。安装：": "Requires mcporter + Exa MCP. Install:",
}

def translate_msg(text: str) -> str:
    for zh, en in TRANSLATIONS.items():
        text = text.replace(zh, en)
    # Common inline phrases
    text = text.replace("已安装但未配置", "Installed but not configured")
    text = text.replace("连接失败（可能需要代理）", "Connection failed (may need proxy)")
    text = text.replace("体检异常：", "Check failed: ")
    return text

def check_all(config: Config) -> Dict[str, dict]:
    """Check all channels and return status dict."""
    results = {}
    for ch in get_all_channels():
        try:
            status, message = ch.check(config)
            active = getattr(ch, "active_backend", None)
        except Exception as e:
            status = "error"
            message = f"Check failed: {e}"
            active = None
        message = scrub_url_credentials(message)
        name = TRANSLATIONS.get(ch.description, ch.description)
        results[ch.name] = {
            "status": status,
            "name": name,
            "message": translate_msg(message),
            "tier": ch.tier,
            "backends": ch.backends,
            "active_backend": active,
        }
    return results


def _name_msg(r: dict, escape) -> str:
    """Render one channel line; show the active backend when there is a choice."""
    text = f"[bold]{escape(r['name'])}[/bold] — {escape(r['message'])}"
    active = r.get("active_backend")
    if active and len(r.get("backends", [])) > 1:
        text += f" [dim](Active backend: {escape(active)})[/dim]"
    return text


def format_report(results: Dict[str, dict]) -> str:
    """Format results as a readable text report (with Rich markup)."""
    lines = []
    lines.append("[bold cyan]Agent Reach Status[/bold cyan]")
    lines.append("[cyan]" + "=" * 40 + "[/cyan]")
    lines.append("Legend: [green]✅[/green] Available  [yellow][!][/yellow] Installed (needs config)  [red][X][/red] Not Installed")

    ok_count = sum(1 for r in results.values() if r["status"] == "ok")
    total = len(results)

    # Tier 0 — zero config
    lines.append("")
    lines.append("[bold]✅ Ready out-of-the-box:[/bold]")
    for key, r in results.items():
        if r["tier"] == 0:
            name_msg = _name_msg(r, escape)
            if r["status"] == "ok":
                lines.append(f"  [green]✅[/green] {name_msg}")
            elif r["status"] == "warn":
                lines.append(f"  [yellow][!][/yellow]  {name_msg}")
            elif r["status"] in ("off", "error"):
                lines.append(f"  [red][X][/red]  {name_msg}")

    # Tier 1 — needs free key / login
    tier1 = {k: r for k, r in results.items() if r["tier"] == 1}
    tier1_active = {k: r for k, r in tier1.items() if r["status"] == "ok"}
    tier1_inactive = {k: r for k, r in tier1.items() if r["status"] != "ok"}
    if tier1_active:
        lines.append("")
        lines.append("[bold]Optional Channels (Active):[/bold]")
        for key, r in tier1_active.items():
            lines.append(f"  [green]✅[/green] {_name_msg(r, escape)}")

    # Tier 2 — optional complex setup
    tier2 = {k: r for k, r in results.items() if r["tier"] == 2}
    tier2_active = {k: r for k, r in tier2.items() if r["status"] == "ok"}
    tier2_inactive = {k: r for k, r in tier2.items() if r["status"] != "ok"}
    if tier2_active:
        if not tier1_active:
            lines.append("")
            lines.append("[bold]Optional Channels (Active):[/bold]")
        for key, r in tier2_active.items():
            lines.append(f"  [green]✅[/green] {_name_msg(r, escape)}")

    lines.append("")
    status_color = "green" if ok_count == total else ("yellow" if ok_count > 0 else "red")
    lines.append(f"Status: [{status_color}]{ok_count}/{total}[/{status_color}] channels available")

    # Summarize inactive optional channels in one line
    all_inactive = list(tier1_inactive.values()) + list(tier2_inactive.values())
    if all_inactive:
        names = [r["name"] for r in all_inactive]
        lines.append(
            f"There are {len(names)} optional channels to unlock ({', '.join(names)}). "
            "Tell your Agent 'help me configure XXX' to activate."
        )

    # Security check: config file permissions (Unix only)
    import stat
    import sys

    config_path = Config.CONFIG_DIR / "config.yaml"
    if config_path.exists() and sys.platform != "win32":
        try:
            mode = config_path.stat().st_mode
            if mode & (stat.S_IRGRP | stat.S_IROTH):
                lines.append("")
                lines.append(
                    "[bold red][!]  Security Warning: config.yaml permissions too open[/bold red]"
                )
                lines.append("   Fix: chmod 600 ~/.agent-reach/config.yaml")
        except OSError:
            pass

    return "\n".join(lines)

