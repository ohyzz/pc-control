#!/bin/bash
LEVEL=${1:-50}
pactl set-sink-volume @DEFAULT_SINK@ "${LEVEL}%"
