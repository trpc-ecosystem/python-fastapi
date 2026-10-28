#!/bin/bash

for pid in $(pidof python3); do
    kill -9 $pid
done

ps aux | grep "trpc_main" | grep -v grep | awk '{print $2}' | xargs kill -9
