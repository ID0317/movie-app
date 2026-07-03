"""
第五课：豆瓣电影 Web 应用 —— 完整项目
=======================================
一个带搜索、排序功能的电影排行榜网页

运行方式：
    python app.py

然后在浏览器打开 http://127.0.0.1:5000

你学的技术栈串联：
    requests + BS4（爬数据） → CSV（存数据） → Flask（展示数据）
"""
import csv
import os
from flask import Flask, render_template, request

# ============================================================
# Flask 应用初始化
# ============================================================
# __name__ 告诉 Flask 这是主程序
# template_folder 指定 HTML 模板的文件夹
app = Flask(__name__, template_folder="templates")

# ============================================================
# 加载数据（只做一次，服务启动时加载）
# ============================================================
def load_movies():
    """从 CSV 加载电影数据"""
    csv_path = os.path.join(os.path.dirname(__file__), "douban_top250.csv")
    movies = []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            movies.append({
                "rank": int(row["rank"]),
                "title": row["title"],
                "rating": float(row["rating"]),
                "rating_people": row["rating_people"],
                "quote": row["quote"],
            })
    return movies

MOVIES = load_movies()
print(f"已加载 {len(MOVIES)} 部电影数据")

# ============================================================
# 路由：定义用户能访问的页面
# ============================================================

@app.route("/")
def index():
    """
    首页 —— 展示所有电影
    支持 URL 参数：
        ?search=关键词    → 按标题搜索
        ?sort=rating      → 按评分排序
        ?sort=rank        → 按排名排序（默认）
    """
    # 获取 URL 参数
    search = request.args.get("search", "").strip()  # 搜索关键词
    sort_by = request.args.get("sort", "rank")        # 排序方式

    # 1. 如果有搜索词，就过滤
    movies = MOVIES
    if search:
        movies = [m for m in movies if search.lower() in m["title"].lower()]

    # 2. 排序
    if sort_by == "rating":
        movies = sorted(movies, key=lambda m: m["rating"], reverse=True)
    else:
        movies = sorted(movies, key=lambda m: m["rank"])

    # 3. 渲染模板（把数据传给 HTML）
    return render_template(
        "index.html",
        movies=movies,
        search=search,
        sort_by=sort_by,
        total=len(movies),
    )


@app.route("/movie/<int:rank>")
def movie_detail(rank):
    """电影详情页 —— 点击某部电影后看到的页面"""
    movie = None
    for m in MOVIES:
        if m["rank"] == rank:
            movie = m
            break

    if movie is None:
        return "电影没找到", 404

    return render_template("detail.html", movie=movie)


# ============================================================
# 启动服务器
# ============================================================
if __name__ == "__main__":
    import sys
    # 自动适配：本地用 debug 模式，部署时用生产模式
    is_production = "--prod" in sys.argv

    if is_production:
        # 生产模式：Render / 云平台
        print("生产模式启动...")
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
    else:
        # 开发模式：本地调试
        print("\n" + "=" * 50)
        print("  服务器已启动！")
        print("  在浏览器打开：http://127.0.0.1:5000")
        print("  按 Ctrl+C 关闭服务器")
        print("=" * 50 + "\n")
        app.run(debug=True, host="127.0.0.1", port=5000)
