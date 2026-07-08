"""
第10课：定时任务调度器
=====================
用 APScheduler 让爬虫定时自动运行，无需手动点按钮。

核心概念：
    BackgroundScheduler  后台调度器，不阻塞主程序（和 Flask 并行跑）
    IntervalTrigger      每隔 N 分钟执行一次
    CronTrigger          在指定时间执行（如每天 8:00）

两种调度方式：
    IntervalTrigger(minutes=30)  → "每隔30分钟"
    CronTrigger(hour=8, minute=0) → "每天早上8点"

为什么会话要每次新建？
    SQLite 连接不能跨线程共享，每个任务线程必须有自己的连接。
"""
import os
import atexit
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger


# 自动刷新间隔（分钟），可通过环境变量配置
REFRESH_MINUTES = int(os.environ.get("NEWS_REFRESH", "30"))

# 全局调度器实例
scheduler = BackgroundScheduler()


def auto_refresh_news():
    """
    自动刷新新闻 —— 由调度器定期调用。

    每次调用都是独立的数据库连接，不存在跨线程共享问题。
    """
    from database import save_articles
    from news_scraper import scrape_hackernews, get_demo_articles

    print(f"\n[定时任务] {datetime.now().strftime('%H:%M:%S')} 开始自动刷新新闻...")

    try:
        articles = scrape_hackernews()
        if not articles:
            print("[定时任务] 网络不通，使用演示数据")
            articles = get_demo_articles()
        count = save_articles(articles)
        print(f"[定时任务] 刷新完成，已保存 {count} 篇 → "
              f"下次刷新：约 {REFRESH_MINUTES} 分钟后")
    except Exception as e:
        print(f"[定时任务] 出错：{e}")


def start_scheduler():
    """
    启动后台调度器。

    在 Flask 启动时调用一次即可。
    atexit 注册退出时自动关闭调度器，防止进程卡住。
    """
    # 添加定时任务
    scheduler.add_job(
        func=auto_refresh_news,
        trigger=IntervalTrigger(minutes=REFRESH_MINUTES),
        id="auto_refresh_news",
        name="自动刷新新闻",
        replace_existing=True,
    )

    # 启动
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown(wait=False))

    print(f"[调度器] 已启动，每 {REFRESH_MINUTES} 分钟自动刷新新闻")


def get_scheduler_info():
    """
    返回调度器运行状态（给网页用）。
    """
    job = scheduler.get_job("auto_refresh_news")
    if job is None:
        return {"running": False}

    next_run = job.next_run_time
    return {
        "running": scheduler.running,
        "interval_minutes": REFRESH_MINUTES,
        "next_run": next_run.strftime("%H:%M:%S") if next_run else "无",
    }


# ============================================================
# 独立测试
# ============================================================
if __name__ == "__main__":
    import time

    print(f"调度器测试 —— 每 {REFRESH_MINUTES} 分钟刷新一次")
    print("按 Ctrl+C 停止\n")

    # 先手动跑一次看效果
    print("[测试] 首次运行...")
    auto_refresh_news()

    # 启动调度器
    start_scheduler()

    # 保持运行
    try:
        while True:
            time.sleep(5)
            info = get_scheduler_info()
            if info["running"]:
                print(f"  下次刷新：{info['next_run']}", end="\r")
    except KeyboardInterrupt:
        print("\n\n调度器已停止")
