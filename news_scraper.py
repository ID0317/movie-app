"""
第8课：新闻爬虫模块
==================
把第1-3课学的爬虫技术封装成可复用的模块，
每次调用都返回最新数据，直接存入数据库。

架构设计：
    scrape_hackernews()  →  [{title, url, points, ...}, ...]
         ↓
    database.save_articles()  →  articles 表
         ↓
    app.py /news  →  网页展示

为什么封装成函数？
    - 可以在网页里调用（点按钮触发）
    - 可以定时任务调用（后面第10课）
    - 可以在终端里单独测试（python news_scraper.py）
"""
import requests
from bs4 import BeautifulSoup
import time
import os

# 代理配置：自动检测常见的代理地址
# Clash 默认端口通常是 7897 或 7890
_PROXY_CANDIDATES = [
    os.environ.get("HN_PROXY", ""),       # 环境变量优先
    "http://127.0.0.1:7897",              # Clash 默认
    "http://127.0.0.1:7890",              # Clash 旧版
    "http://127.0.0.1:10809",             # Clash Verge
]


def _detect_proxy():
    """自动检测哪个代理可用"""
    for proxy in _PROXY_CANDIDATES:
        if not proxy:
            continue
        try:
            resp = requests.get("https://news.ycombinator.com",
                                proxies={"http": proxy, "https": proxy},
                                timeout=3)
            if resp.status_code == 200:
                print(f"[爬虫] 自动检测到可用代理：{proxy}")
                return proxy
        except Exception:
            continue
    print("[爬虫] 未检测到可用代理，将直连（国内可能无法访问）")
    return ""


def _get_session():
    """创建带代理的 requests 会话（自动检测可用代理）"""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"
    })
    proxy = _detect_proxy()
    if proxy:
        session.proxies = {"http": proxy, "https": proxy}
    return session


def scrape_hackernews():
    """
    抓取 Hacker News 首页热门文章。

    Hacker News 是 Y Combinator 旗下的科技新闻社区，
    HTML 结构简单、无反爬，非常适合练习。

    返回：
        [{title, url, points, comments, source}, ...]
        失败时返回空列表 []
    """
    url = "https://news.ycombinator.com/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"
    }

    articles = []

    try:
        session = _get_session()
        print(f"[爬虫] 正在请求：{url}")
        resp = session.get(url, timeout=15)
        resp.raise_for_status()  # 如果状态码不是 200，抛出异常
        print(f"[爬虫] 响应成功，状态码：{resp.status_code}")

        soup = BeautifulSoup(resp.text, "html.parser")

        # Hacker News 的文章行都有 class="athing"
        items = soup.find_all("tr", class_="athing")
        print(f"[爬虫] 找到 {len(items)} 篇文章")

        for item in items[:20]:  # 只取前 20 条
            # --- 标题和链接 ---
            title_tag = item.find("span", class_="titleline")
            if not title_tag:
                continue

            link = title_tag.find("a")
            if not link:
                continue

            title = link.text.strip()
            article_url = link.get("href", "")
            # 如果是 HN 内部链接（Ask HN 等），补全域名
            if article_url.startswith("item?"):
                article_url = f"https://news.ycombinator.com/{article_url}"

            # --- 分数和评论数（在下一行） ---
            # HN 结构：<tr class="athing"> 后面跟着 <tr> 包含分数
            subtext_row = item.find_next_sibling("tr")
            points = 0
            comments = 0

            if subtext_row:
                score_tag = subtext_row.find("span", class_="score")
                if score_tag:
                    # "123 points" → 123
                    points_text = score_tag.text.split()[0]
                    points = int(points_text) if points_text.isdigit() else 0

                # 评论链接："123 comments" 或 "discuss"
                for a in subtext_row.find_all("a"):
                    if "comment" in a.text:
                        comments_text = a.text.split()[0]
                        comments = int(comments_text) if comments_text.isdigit() else 0
                        break

            articles.append({
                "title": title,
                "url": article_url,
                "points": points,
                "comments": comments,
                "source": "hackernews",
            })

    except requests.exceptions.Timeout:
        print("[爬虫] 请求超时，请检查网络")
    except requests.exceptions.ConnectionError:
        print("[爬虫] 连接失败，可能需要代理")
    except requests.exceptions.HTTPError as e:
        print(f"[爬虫] HTTP 错误：{e}")
    except Exception as e:
        print(f"[爬虫] 未知错误：{e}")

    print(f"[爬虫] 成功解析 {len(articles)} 篇文章")
    return articles


def get_demo_articles():
    """
    演示数据 —— 网络不通时也可以看到完整流程。

    实际项目中不会这样写，这里只是为了让你在没有代理的情况下
    也能先看到"爬虫→数据库→网页"的完整链路。
    """
    return [
        {"title": "OpenAI 发布 GPT-5 正式版", "url": "https://example.com/1", "points": 1523, "comments": 487, "source": "demo"},
        {"title": "Rust 语言 2026 路线图公布", "url": "https://example.com/2", "points": 892, "comments": 201, "source": "demo"},
        {"title": "Linux 内核 6.15 LTS 发布", "url": "https://example.com/3", "points": 671, "comments": 155, "source": "demo"},
        {"title": "Python 4.0 首个 Alpha 版本释出", "url": "https://example.com/4", "points": 1204, "comments": 398, "source": "demo"},
        {"title": "Claude Code 发布 Windows 原生版本", "url": "https://example.com/5", "points": 945, "comments": 267, "source": "demo"},
        {"title": "SQLite 官方发布 Wasm 版本", "url": "https://example.com/6", "points": 534, "comments": 123, "source": "demo"},
        {"title": "为什么我们选择放弃微服务回归单体", "url": "https://example.com/7", "points": 2103, "comments": 689, "source": "demo"},
        {"title": "HTMX 2.0 正式发布", "url": "https://example.com/8", "points": 756, "comments": 198, "source": "demo"},
        {"title": "用 SQLite 替代 Redis 的经验分享", "url": "https://example.com/9", "points": 634, "comments": 176, "source": "demo"},
        {"title": "2026 年最值得学的编程语言排行", "url": "https://example.com/10", "points": 1102, "comments": 432, "source": "demo"},
    ]


# ============================================================
# 独立测试：直接运行本文件看效果
# ============================================================
if __name__ == "__main__":
    print("=" * 50)
    print("  新闻爬虫测试")
    print("=" * 50)
    print()
    print("提示：如果 HN 被墙，设置代理后重试：")
    print("  Windows CMD:  set HN_PROXY=http://127.0.0.1:7897")
    print("  Git Bash:     export HN_PROXY=http://127.0.0.1:7897")
    print()

    result = scrape_hackernews()

    if not result:
        print("\n⚠️  网络抓取失败，使用演示数据。")
        print("   设置代理后重新运行即可抓取真实数据。\n")
        result = get_demo_articles()

    print(f"共 {len(result)} 篇文章：\n")
    for i, a in enumerate(result, 1):
        print(f"  {i}. {a['title']}")
        print(f"     {a['url']}")
        print(f"     👍 {a['points']} 分  💬 {a['comments']} 评论")
        print()
