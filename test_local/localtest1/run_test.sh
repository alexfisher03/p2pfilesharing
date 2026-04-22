#!/bin/zsh
DIR="$(cd "$(dirname "$0")" && pwd)"

osascript -e "tell app \"Terminal\" to do script \"cd '$DIR' && python3 ../../peerProcess.py 1001\""
sleep 1
osascript -e "tell app \"Terminal\" to do script \"cd '$DIR' && python3 ../../peerProcess.py 1002\""
sleep 1
osascript -e "tell app \"Terminal\" to do script \"cd '$DIR' && python3 ../../peerProcess.py 1003\""
