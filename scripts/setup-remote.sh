#!/usr/bin/env bash
set -euo pipefail

inventory_filename="inventory.remote"
if ! [[ -f "${inventory_filename}" ]];
then
    echo "You need to have '${inventory_filename}' to do this. See ${inventory_filename}.sample"
    exit 1
fi

ansible-playbook -i "${inventory_filename}" bootstrap.yml
ansible-playbook -i "${inventory_filename}" update.yml
ansible-playbook -i "${inventory_filename}" playbook.yml
