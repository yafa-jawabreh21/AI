#!/usr/bin/env bash
bash backend/run.sh &
sleep 2
xdg-open http://localhost:8010/
