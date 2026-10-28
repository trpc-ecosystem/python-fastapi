#!/bin/bash

python3 -m pip install --upgrade pip

pip3 install --upgrade --force-reinstall yapf


# 查找并格式化 Python 文件
yapf -i -r .
