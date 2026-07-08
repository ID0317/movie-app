"""
第10课：定时任务 —— 无人值守
=============================
用 APScheduler 让爬虫定时自动运行，真正实现"部署后就忘了它"。

新增：
    APScheduler         后台定时调度
    BackgroundScheduler 和 Flask 并行跑，不阻塞
    IntervalTrigger     每隔 N 分钟触发
    start_scheduler()   应用启动时自动开始
"""
import os
import sys
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash

from database import (
    init_db, init_news_table, init_users_table,
    count_movies,
    get_all_movies, get_movie,
    add_movie, update_movie, delete_movie,
    import_from_csv,
    save_articles, get_articles, get_last_scrape_time,
    create_user, get_user_by_username, get_user_by_id,
)
from news_scraper import scrape_hackernews, get_demo_articles
from scheduler import start_scheduler, get_scheduler_info

# ============================================================
# Flask 初始化
# ============================================================
app = Flask(__name__, template_folder="templates")
app.secret_key = "jiazhi-movie-app-2026"

# ============================================================
# Flask-Login 初始化
# ============================================================
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"        # 未登录时跳转到登录页
login_manager.login_message = "请先登录后再操作"  # 跳转时显示的提示


class User(UserMixin):
    """
    Flask-Login 要求的用户类。

    UserMixin 提供了 Flask-Login 需要的四个方法：
        is_authenticated, is_active, is_anonymous, get_id
    我们只需要设置 id 属性即可。
    """
    def __init__(self, user_dict):
        self.id = str(user_dict["id"])
        self.username = user_dict["username"]
        self.password_hash = user_dict["password_hash"]


@login_manager.user_loader
def load_user(user_id):
    """
    Flask-Login 每次请求都会调用这个函数，
    根据 session 中保存的 user_id 重新加载用户对象。

    这就是"记住登录状态"的原理：
        登录时 → session 存 user_id
        每次请求 → 调这个函数 → 查出用户是谁
    """
    user_dict = get_user_by_id(int(user_id))
    if user_dict is None:
        return None
    return User(user_dict)


# ============================================================
# 启动时初始化
# ============================================================
init_db()
init_news_table()
init_users_table()

if count_movies() == 0:
    csv_path = os.path.join(os.path.dirname(__file__), "douban_top250.csv")
    if os.path.exists(csv_path):
        import_from_csv(csv_path)

print(f"数据库就绪，共 {count_movies()} 部电影")

# 启动后台定时任务（失败不影响网站运行）
try:
    start_scheduler()
except Exception as e:
    print(f"[启动] 调度器启动失败（不影响网站）：{e}")


# ============================================================
# 辅助：把 current_user 注入所有模板
# ============================================================

@app.context_processor
def inject_globals():
    """所有模板自动可用的变量"""
    return {
        "current_user": current_user,
        "scheduler_info": get_scheduler_info(),
    }


# ============================================================
# 公开路由 —— 不需要登录
# ============================================================

@app.route("/")
def index():
    """首页：电影榜单"""
    search = request.args.get("search", "").strip()
    sort_by = request.args.get("sort", "rank")
    movies = get_all_movies(search=search, sort_by=sort_by)
    return render_template(
        "index.html",
        movies=movies, search=search, sort_by=sort_by, total=len(movies),
    )


@app.route("/movie/<int:rank>")
def movie_detail(rank):
    """电影详情"""
    movie = get_movie(rank)
    if movie is None:
        return "电影没找到", 404
    return render_template("detail.html", movie=movie)


@app.route("/news")
def news():
    """新闻聚合页"""
    articles = get_articles()
    last_scrape = get_last_scrape_time()
    return render_template(
        "news.html",
        articles=articles,
        last_scrape=last_scrape,
        scheduler_info=get_scheduler_info(),
    )


# ============================================================
# 认证路由 —— 登录 / 注册 / 登出
# ============================================================

@app.route("/register", methods=["GET", "POST"])
def register():
    """
    注册新用户。

    流程：
        GET  → 显示注册表单
        POST → 校验 → 哈希密码 → 存入数据库 → 自动登录
    """
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        password2 = request.form.get("password2", "").strip()

        # 校验
        errors = []
        if not username or len(username) < 2:
            errors.append("用户名至少 2 个字符")
        if not password or len(password) < 4:
            errors.append("密码至少 4 个字符")
        if password != password2:
            errors.append("两次密码不一致")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("register.html", username=username)

        # 创建用户（密码先哈希再存储！）
        password_hash = generate_password_hash(password)
        success, message = create_user(username, password_hash)

        if success:
            # 注册成功 → 自动登录
            user_dict = get_user_by_username(username)
            user = User(user_dict)
            login_user(user)
            flash(f"欢迎 {username}！注册成功。", "success")
            return redirect(url_for("index"))
        else:
            flash(message, "error")
            return render_template("register.html", username=username)

    return render_template("register.html", username="")


@app.route("/login", methods=["GET", "POST"])
def login():
    """
    登录。

    check_password_hash(数据库里的哈希, 用户输入的密码)
        → 密码正确返回 True，否则 False

    整个验证过程从不去"解密"密码（哈希不可逆），
    而是把用户输入用同样算法哈希后对比。
    """
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        remember = request.form.get("remember") == "on"

        user_dict = get_user_by_username(username)

        if user_dict and check_password_hash(user_dict["password_hash"], password):
            user = User(user_dict)
            login_user(user, remember=remember)
            flash(f"欢迎回来，{username}！", "success")

            # 如果有"原本想去但被拦截的页面"，跳回去
            next_page = request.args.get("next")
            if next_page:
                return redirect(next_page)
            return redirect(url_for("index"))
        else:
            flash("用户名或密码错误", "error")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    """登出"""
    username = current_user.username
    logout_user()
    flash(f"{username} 已安全退出", "success")
    return redirect(url_for("index"))


# ============================================================
# 保护路由 —— 必须登录后才能操作
# ============================================================

@app.route("/add", methods=["GET", "POST"])
@login_required
def add():
    """添加电影（需登录）"""
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        rating = request.form.get("rating", "0").strip()
        rating_people = request.form.get("rating_people", "").strip()
        quote = request.form.get("quote", "").strip()

        if not title:
            flash("电影名不能为空", "error")
            return render_template("add.html", title=title, rating=rating,
                                   rating_people=rating_people, quote=quote)

        try:
            new_rank = add_movie(title, float(rating), rating_people, quote)
            flash(f"《{title}》添加成功！", "success")
            return redirect(url_for("movie_detail", rank=new_rank))
        except Exception as e:
            flash(f"添加失败：{e}", "error")

    return render_template("add.html", title="", rating="",
                           rating_people="", quote="")


@app.route("/edit/<int:rank>", methods=["GET", "POST"])
@login_required
def edit(rank):
    """编辑电影（需登录）"""
    movie = get_movie(rank)
    if movie is None:
        return "电影没找到", 404

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        rating = request.form.get("rating", "0").strip()
        rating_people = request.form.get("rating_people", "").strip()
        quote = request.form.get("quote", "").strip()

        if not title:
            flash("电影名不能为空", "error")
            return render_template("edit.html", movie=movie)

        try:
            update_movie(rank, title, float(rating), rating_people, quote)
            flash(f"《{title}》修改成功！", "success")
            return redirect(url_for("movie_detail", rank=rank))
        except Exception as e:
            flash(f"修改失败：{e}", "error")

    return render_template("edit.html", movie=movie)


@app.route("/delete/<int:rank>", methods=["POST"])
@login_required
def delete(rank):
    """删除电影（需登录）"""
    movie = get_movie(rank)
    if movie is None:
        flash("电影不存在", "error")
        return redirect(url_for("index"))

    try:
        delete_movie(rank)
        flash(f"《{movie['title']}》已删除", "success")
    except Exception as e:
        flash(f"删除失败：{e}", "error")

    return redirect(url_for("index"))


@app.route("/news/refresh", methods=["POST"])
@login_required
def refresh_news():
    """刷新新闻（需登录）"""
    try:
        articles = scrape_hackernews()
        if not articles:
            flash("Hacker News 无法访问，使用演示数据。", "error")
            articles = get_demo_articles()
        if articles:
            save_articles(articles)
            flash(f"刷新成功！共 {len(articles)} 篇文章", "success")
        else:
            flash("未抓取到文章，请检查网络连接。", "error")
    except Exception as e:
        flash(f"刷新失败：{e}", "error")

    return redirect(url_for("news"))


# ============================================================
# 启动
# ============================================================

if __name__ == "__main__":
    is_production = "--prod" in sys.argv or "RENDER" in os.environ

    if is_production:
        print("生产模式启动...")
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
    else:
        print("\n" + "=" * 50)
        print("  服务器已启动！http://127.0.0.1:5000")
        print("  电影榜单    http://127.0.0.1:5000")
        print("  新闻聚合    http://127.0.0.1:5000/news")
        print("  注册        http://127.0.0.1:5000/register")
        print("  登录        http://127.0.0.1:5000/login")
        print("=" * 50 + "\n")
        app.run(debug=True, host="127.0.0.1", port=5000)
