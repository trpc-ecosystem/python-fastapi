#!/bin/bash

pip install --upgrade pip

pip3 uninstall -y trpc_fastapi

pip3 install -r requirements.txt

pip install -e .[all] -i https://mirrors.tencent.com/repository/pypi/tencent_pypi/simple/ --extra-index-url https://pypi.org/simple/

# 检查依赖解析
pip install --dry-run .
