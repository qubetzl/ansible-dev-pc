#!/usr/bin/env bash
set -euo pipefail

apt-get update
apt-get install -y git

[ ! -d ~/ansible-dev-pc ] && git clone https://github.com/qubetzl/ansible-dev-pc.git ~/ansible-dev-pc
pushd ~/ansible-dev-pc
git pull --rebase
bash scripts/setup.sh
