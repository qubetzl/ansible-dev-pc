#!/usr/bin/env bash
set -euo pipefail

packagesToInstall=""
if [ ! command -v pip3 &> /dev/null ]
then
    packagesToInstall="python3-pip"
fi

if [ ! -d "/usr/share/doc/python3-venv" ]
then
    packagesToInstall="${packagesToInstall} python3-venv"
fi

if [[ -n "${packagesToInstall}" ]]
then
    sudo apt-get update
    sudo apt-get install -y ${packagesToInstall}
fi

[ ! -d "venv" ] && python3 -m venv venv

source venv/bin/activate
if [ ! command -v ansible &> /dev/null ]
then
    pip3 install ansible
fi

ansible-galaxy collection install -r requirements.yml
ansible-galaxy role install -r requirements.yml
ansible-playbook update.yml
ansible-playbook playbook.yml
