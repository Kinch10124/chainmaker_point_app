#!/usr/bin/env bash
# 一键启动：建虚拟环境、装依赖、起服务
set -e
cd "$(dirname "$0")/.."

if [ ! -x ./venv/bin/python ]; then
  echo "创建虚拟环境 venv ..."
  python3 -m venv ./venv
fi

echo "安装依赖 ..."
./venv/bin/pip install -q -r backend/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

echo "启动服务： http://0.0.0.0:5000"
exec ./venv/bin/python backend/app.py
