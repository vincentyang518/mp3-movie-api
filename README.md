# MP3 Part 1 — Movie API

这是独立的 MP3 项目。原 MP2 文件未修改。基于本机 `mp2-rest-api` 项目复制了原来的 `data_pipeline`、`ProcessConfig`、日志工具及请求中间件，改用 SQLite 存储。

## 启动（macOS / VS Code 终端）

本机已经创建并验证了本项目独立的 `venv/`，可直接执行 `source venv/bin/activate`。若使用解压后的 ZIP，则先创建环境。

在本项目文件夹打开终端，执行：

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8003
```

浏览器打开 http://127.0.0.1:8003/docs 。使用 8003 端口方便与 MP2 分开运行。
每次都从 MP3 项目根目录启动，数据库会自动生成在 `data/movies.db`。

## 按作业顺序演示

1. `POST /upload`：上传 `fixtures/sample_movies.csv`，返回 20 行、4 列。
2. `GET /movies`：设置 `limit=2`，返回 Movie A、Movie B，`total_rows=20`。
3. `GET /movies/search`：默认 `columns=title`，设置 `min_rating=8.5, limit=2`，返回 id=4 的 Movie C 和 id=2 的 Movie B。
4. 搜索时把 `columns` 设为两个条目 `title` 和 `rating`，返回上述电影及评分 9.0、8.5。URL 使用重复参数：`?columns=title&columns=rating&min_rating=8.5&limit=2`。
5. 在终端按 Ctrl+C 停止，再用相同命令启动；不重新上传即可读取原来的 20 行。
6. 再上传同一文件，仍为 20 行，覆盖旧集合。
7. 上传 `.txt` 文件返回 400；随后 `/health` 仍返回正常状态。
8. `POST /movies/process`：把 `process_config.json` 的内容复制进请求体。启用去重和 rating 的 IQR 异常值清理后，20 行变为 16 行。

处理接口沿用 MP2 的嵌套配置 `validation` / `processing`。传 `{}` 使用 MP2 的默认设置，只去重和去除缺失行，本样例得到 18 行。处理不能删掉四个固定电影字段；若 `missing.axis="columns"` 导致字段被删除，返回 400 并保留原数据。

## 测试

激活虚拟环境后，从项目根目录执行：

```bash
python -m pytest -q
```

测试使用临时 SQLite 数据库，不会覆盖演示数据库。包括题目给出的完整响应、覆盖上传、独立 Python 进程读取持久化数据、SQL 事务回滚、NULL、错误文件、参数验证及 MP2 清洗流程。

## 文件说明

- `main.py`：健康检查、上传、查询、搜索、处理接口。
- `src/database.py`：连接及建表；电影字段允许 SQL NULL。
- `src/storage.py`：使用 SQL 插入、覆盖、过滤、排序、计数；每次连接都关闭，覆盖写入在同一个事务内。
- `src/models.py`：原 MP2 配置及 MP3 响应模型。
- `data_pipeline/`：从 MP2 复制的 MP1 清洗模块。
- `fixtures/`：题目样例数据。
- `tests/`：API 和持久化测试。

依赖文件使用与本次测试兼容的直接依赖范围，避免照搬原 MP2 中与本项目无关的完整环境锁定列表。

## GitHub 提交

代码已在本地准备好；尚未创建或推送 GitHub 仓库。需要在自己的 GitHub 新建空仓库后，从本项目根目录执行（把 `YOUR_REPOSITORY_URL` 换成实际地址）：

```bash
git init -b main
git add .
git commit -m "Add SQLite movie storage and SQL queries"
git remote add origin YOUR_REPOSITORY_URL
git push -u origin main
```

`.gitignore` 已排除数据库、虚拟环境和缓存。ZIP 也不包含这些生成文件；首次运行会自动建立数据库。
