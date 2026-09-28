"""
============================================================================
fufu新闻 — 一键启动脚本 (launch.py)  v2.0
============================================================================
功能：
  1. 自动检测 Python 3.10+ / Node.js 18+
  2. 自动安装 Python 依赖（首次）+ npm 依赖（首次）
  3. 同时启动 Python 后端（端口 8800）+ Vite 前端（端口 3000）
  4. 浏览器自动打开 http://localhost:3000

用法：
  - Windows：双击「启动.bat」
  - 命令行：python launch.py
  - 仅启动后端：python launch.py --backend-only
============================================================================
"""
import subprocess
import sys
import time
import webbrowser
import urllib.request
import argparse
import signal
import os
from pathlib import Path

# ========== 路径常量 ==========
ROOT = Path(__file__).resolve().parent          # 项目根目录
SERVER_DIR = ROOT / "fufu-server"               # Python FastAPI 后端
FRONTEND_DIR = ROOT / "fufu-web"                # Vite + React 前端
DATA_DIR = ROOT / "data"                         # SQLite 数据库
VENV_PYTHON = SERVER_DIR / ".venv" / "Scripts" / "python.exe"  # 虚拟环境 Python

# 端口分配
BACKEND_PORT = 8800   # Python FastAPI API 服务
FRONTEND_PORT = 3000  # Vite 前端页面

# 子进程引用（用于 Ctrl+C 时统一关闭）
backend_proc = None
frontend_proc = None


def step(msg: str) -> None:
    """输出步骤信息"""
    print(f"  {msg}")


def run(cmd: list[str], cwd: Path, desc: str = "", timeout: int = 300) -> bool:
    """
    执行命令并返回是否成功
    返回 True=成功, False=失败
    """
    try:
        subprocess.run(cmd, cwd=str(cwd), check=True, timeout=timeout)
        return True
    except Exception as e:
        print(f"  [错误] {desc}: {e}")
        return False


def check_python() -> bool:
    """检查 Python 版本 >= 3.10"""
    print("  [1/6] 检查 Python 环境...")
    if sys.version_info < (3, 10):
        print("  [错误] 需要 Python 3.10 或更高版本！")
        print(f"  当前版本: {sys.version_info.major}.{sys.version_info.minor}")
        return False
    print(f"  [通过] Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    return True


def check_node() -> bool:
    """检查 Node.js >= 18"""
    print("  [2/6] 检查 Node.js 环境...")
    try:
        r = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            raise OSError("node 命令不可用")
        ver = r.stdout.strip().lstrip('v')
        major = int(ver.split('.')[0])
        if major < 18:
            print(f"  [错误] Node.js 版本过低 ({ver})，需要 18+")
            return False
        print(f"  [通过] Node.js {r.stdout.strip()}")
        return True
    except Exception:
        print("  [错误] Node.js 未安装，请从 https://nodejs.org/ 下载安装")
        return False


def setup_backend() -> bool:
    """配置 Python 后端：创建虚拟环境 + 安装依赖"""
    print()
    print("  [3/6] 配置 Python 后端...")

    # 创建虚拟环境（如果不存在）
    if not VENV_PYTHON.exists():
        step("创建 Python 虚拟环境...")
        if not run([sys.executable, "-m", "venv", str(SERVER_DIR / ".venv")], ROOT, "创建 venv"):
            return False

    # 安装/更新依赖
    step("检查 Python 依赖...")
    if not run([str(VENV_PYTHON), "-m", "pip", "install", "-r", "requirements.txt", "-q"], SERVER_DIR, "pip install"):
        return False

    print("  [通过] 后端依赖就绪")
    return True


def setup_frontend() -> bool:
    """配置 Vite 前端：安装 npm 依赖"""
    print()
    print("  [4/6] 配置 Vite 前端...")

    node_modules = FRONTEND_DIR / "node_modules"
    if node_modules.exists():
        step("npm 依赖已安装，跳过...")
    else:
        step("npm install（首次运行，可能需要几分钟）...")
        if not run(["npm", "install"], FRONTEND_DIR, "npm install", timeout=600):
            return False

    print("  [通过] 前端依赖就绪")
    return True


def start_services() -> bool:
    """启动两个服务：Python 后端 + Next.js 前端"""
    global backend_proc, frontend_proc

    print()
    print("  [5/6] 启动服务...")

    # 清理 SQLite WAL 临时文件（避免上次异常退出导致的锁问题）
    for suffix in (".db-journal", ".db-wal", ".db-shm"):
        p = DATA_DIR / f"fufu{suffix}"
        if p.exists():
            try:
                p.unlink()
            except PermissionError:
                pass  # 文件被其他进程占用，跳过清理

    # ---- 端口冲突检测与清理 ----
    if not _kill_port(BACKEND_PORT):
        print(f"  [错误] 无法释放端口 {BACKEND_PORT}，请手动关闭占用程序后重试")
        return False
    if not _kill_port(FRONTEND_PORT):
        print(f"  [错误] 无法释放端口 {FRONTEND_PORT}，请手动关闭占用程序后重试")
        return False

    # ---- 启动 Python 后端 (端口 8800) ----
    step("启动 Python 后端 (端口 8800)...")
    try:
        backend_proc = subprocess.Popen(
            [str(VENV_PYTHON), "-m", "uvicorn", "app.main:app",
             "--host", "0.0.0.0", "--port", str(BACKEND_PORT)],
            cwd=str(SERVER_DIR),
            # 不捕获 stdout/stderr，让日志直接输出到终端
        )
    except Exception as e:
        print(f"  [错误] 无法启动后端: {e}")
        return False

    # ---- 启动 Vite 前端 (端口 3000) ----
    step("启动 Vite 前端 (端口 3000)...")
    try:
        # Windows: 使用 shell=True 以正确调用 npm.cmd
        if sys.platform == "win32":
            frontend_proc = subprocess.Popen(
                "npm run dev",
                cwd=str(FRONTEND_DIR),
                shell=True,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        else:
            frontend_proc = subprocess.Popen(
                ["npm", "run", "dev"],
                cwd=str(FRONTEND_DIR),
                start_new_session=True,
            )
    except Exception as e:
        print(f"  [错误] 无法启动前端: {e}")
        return False

    # ---- 等待两个服务就绪 ----
    print()
    print("  等待服务就绪...")

    backend_ready = _wait_for_url(f"http://localhost:{BACKEND_PORT}/api/v1/health", "后端")
    frontend_ready = _wait_for_url(f"http://localhost:{FRONTEND_PORT}", "前端")

    print()
    if backend_ready:
        print(f"  [就绪] Python 后端    → http://localhost:{BACKEND_PORT}")
    else:
        print(f"  [警告] 后端可能启动较慢，请手动检查 http://localhost:{BACKEND_PORT}/api/v1/health")

    if frontend_ready:
        print(f"  [就绪] Next.js 前端   → http://localhost:{FRONTEND_PORT}")
    else:
        print(f"  [警告] 前端可能启动较慢，请手动访问 http://localhost:{FRONTEND_PORT}")

    return True


def _wait_for_url(url: str, name: str, max_wait: int = 60) -> bool:
    """轮询等待某个 URL 可用"""
    for i in range(max_wait):
        time.sleep(1)
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            if i % 5 == 0 and i > 0:
                print(f"  ...{name} 启动中 ({i}s)")
    return False


def signal_handler(signum, frame):
    """Ctrl+C 信号处理：优雅关闭所有子进程"""
    global backend_proc, frontend_proc
    print()
    print("  正在关闭服务...")

    for proc, name in [(frontend_proc, "前端"), (backend_proc, "后端")]:
        if proc and proc.poll() is None:
            print(f"  停止 {name} (PID {proc.pid})...")
            try:
                if sys.platform == "win32":
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                else:
                    proc.send_signal(signal.SIGTERM)
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
            except Exception:
                pass
    print("  fufu新闻 已关闭")
    sys.exit(0)


def _safe_input(prompt: str = "") -> str:
    """安全的 input()，在无交互终端时不抛异常"""
    try:
        return input(prompt)
    except EOFError:
        return ""


def _check_port(port: int) -> bool:
    """检查端口是否已被占用"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("0.0.0.0", port))
            return False  # 端口空闲
        except OSError:
            return True   # 端口被占用


def _kill_port(port: int) -> bool:
    """
    强制释放指定端口 — 查找占用端口的进程并终止。
    返回 True 表示端口已释放（或本来就没占用）。
    """
    if not _check_port(port):
        return True  # 端口空闲，无需处理

    print(f"  [清理] 端口 {port} 被占用，正在释放...")

    if sys.platform == "win32":
        try:
            # 用 netstat 找到占用端口的 PID
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True, text=True, timeout=10
            )
            for line in result.stdout.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.strip().split()
                    pid = parts[-1]
                    if pid.isdigit():
                        kill_result = subprocess.run(
                            ["taskkill", "/F", "/PID", pid],
                            capture_output=True, text=True, timeout=10
                        )
                        if kill_result.returncode != 0:
                            print(f"  [清理] taskkill PID {pid} 失败: {kill_result.stderr.strip()}")
            time.sleep(1.5)
            if not _check_port(port):
                print(f"  [清理] 端口 {port} 已释放")
                return True
        except Exception as e:
            print(f"  [清理] 释放端口 {port} 失败: {e}")
    else:
        # macOS / Linux: 用 lsof 找到进程
        try:
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True, text=True, timeout=10
            )
            for pid in result.stdout.strip().split():
                if pid.isdigit():
                    os.kill(int(pid), signal.SIGKILL)
            time.sleep(1)
            if not _check_port(port):
                print(f"  [清理] 端口 {port} 已释放")
                return True
        except Exception as e:
            print(f"  [清理] 释放端口 {port} 失败: {e}")

    return False


def main() -> int:
    """主流程"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="fufu新闻启动器")
    parser.add_argument("--backend-only", action="store_true", help="仅启动后端 API 服务")
    parser.add_argument("--frontend-only", action="store_true", help="仅启动前端 Next.js")
    args = parser.parse_args()

    # 注册 Ctrl+C 处理
    signal.signal(signal.SIGINT, signal_handler)

    print()
    print("  ╔══════════════════════════════════════════╗")
    print("  ║     ☁️  fufu新闻 v2.0 — 启动器         ║")
    print("  ╚══════════════════════════════════════════╝")
    print()
    print(f"  项目目录: {ROOT}")
    print()

    # ========== 环境检查 ==========
    if not args.frontend_only:
        if not check_python():
            _safe_input("  按 Enter 退出...")
            return 1

    if not args.backend_only:
        if not check_node():
            _safe_input("  按 Enter 退出...")
            return 1

    # ========== 安装依赖 ==========
    if not args.frontend_only:
        if not setup_backend():
            _safe_input("  按 Enter 退出...")
            return 1

    if not args.backend_only:
        if not setup_frontend():
            _safe_input("  按 Enter 退出...")
            return 1

    # ========== 启动服务 ==========
    if not start_services():
        _safe_input("  按 Enter 退出...")
        return 1

    # ========== 打开浏览器 ==========
    print()
    print("  [6/6] 打开浏览器...")
    target_url = f"http://localhost:{FRONTEND_PORT}"
    webbrowser.open(target_url)
    print(f"  已打开 {target_url}")

    # ========== 启动成功 ==========
    print()
    print("  ╔══════════════════════════════════════════╗")
    print("  ║         fufu新闻 启动成功！             ║")
    print("  ╠══════════════════════════════════════════╣")
    print(f"  ║  前端页面    http://localhost:{FRONTEND_PORT}       ║")
    print(f"  ║  后端 API    http://localhost:{BACKEND_PORT}       ║")
    print(f"  ║  默认账户    fufu / fufu123             ║")
    print("  ║                                          ║")
    print("  ║  按 Ctrl+C 停止所有服务                 ║")
    print("  ╚══════════════════════════════════════════╝")
    print()

    # ========== 等待进程 ==========
    try:
        # 等待任意子进程退出
        procs = [p for p in [backend_proc, frontend_proc] if p is not None]
        while procs:
            for p in procs[:]:
                ret = p.poll()
                if ret is not None:
                    name = "后端" if p == backend_proc else "前端"
                    if ret != 0 and ret != -15:  # -15 = SIGTERM（正常关闭）
                        print(f"  [警告] {name} 进程异常退出 (exit code: {ret})")
                    procs.remove(p)
            if procs:
                time.sleep(0.5)
    except KeyboardInterrupt:
        signal_handler(None, None)

    return 0


if __name__ == "__main__":
    sys.exit(main())
