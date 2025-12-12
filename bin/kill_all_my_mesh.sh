#!/bin/bash

# kill all the process find by ps -ef | grep my-mesh

pids=$(ps -ef | grep "my-mesh" | grep -v grep | awk '{print $2}')

if [ -z "$pids" ]; then
    echo "No my-mesh processes found."
    exit 0
fi

echo "Found my-mesh processes: $pids"
echo "Killing processes..."

for pid in $pids; do
    kill -9 $pid 2>/dev/null && echo "Killed process $pid" || echo "Failed to kill process $pid"
done

echo "Done."
