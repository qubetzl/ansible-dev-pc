#!/usr/bin/env bash
set -euo pipefail

if [ ! command -v pip3 &> /dev/null]
then
    apt-get install -y python3-pip
fi

if [ ! -f "/usr/share/doc/python3-venv" ]
then
    apt-get install -y python3-venv
fi

[ ! -d "venv" ] && python3 -m venv venv

source venv/bin/activate
if [ ! command -v ansible &> /dev/null]
then
    pip3 install ansible
fi

ansible-galaxy collection install -r requirements.yml
ansible-galaxy role install -r requirements.yml
ansible-playbook update.yml
ansible-playbook playbook.yml
