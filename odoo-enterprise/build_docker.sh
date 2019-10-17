#!/bin/bash

version="0.0.1"

docker_repo="linshenqi/saturn_10"

docker build -t ${docker_repo}:${version} -t ${docker_repo}:latest .

docker push ${docker_repo}:${version}
docker push ${docker_repo}:latest
