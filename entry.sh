#!/bin/bash -ex
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

$DIR/bootstrap.sh $DIR $DIR/venv

$DIR/venv/bin/python $DIR/src/main.py $@ --port 50051
#There are other cameras also avalible
#50052 = OAK 1
#50053 = OAK 2
#50054 = OAK 4

exit 0
