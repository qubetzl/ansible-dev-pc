#!/usr/bin/env bash
set -euo pipefail

if ! command -v git &> /dev/null
then
    sudo apt-get update && sudo apt-get install -y git
fi

[ ! -d ~/ansible-dev-pc ] && git clone https://github.com/qubetzl/ansible-dev-pc.git ~/ansible-dev-pc
pushd ~/ansible-dev-pc
git pull --rebase
bash scripts/setup.sh --interactive
