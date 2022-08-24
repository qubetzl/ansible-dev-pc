#!/usr/bin/env bash
set -euo pipefail

REMOTE_INVENTORY_FILENAME="inventory.remote"

setup_remote_env() {
    if ! [[ -f "${REMOTE_INVENTORY_FILENAME}" ]];
    then
        echo "You need to have '${REMOTE_INVENTORY_FILENAME}' to do this. See ${REMOTE_INVENTORY_FILENAME}.sample"
        exit 1
    fi
}

setup_local_env() {
    packagesToInstall=""
    if ! command -v pip3 &> /dev/null
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
    if ! command -v ansible &> /dev/null
    then
        pip3 install ansible
    fi
}

install_deps() {
    ansible-galaxy collection install -r requirements.yml
    ansible-galaxy role install -r requirements.yml
}

setup() {
    local remote="${1}"

    local extraArgs=""
    if [[ "${remote}" == true ]]
    then
        extraArgs="--inventory ${REMOTE_INVENTORY_FILENAME} --extra-vars @vars/vault.yml --vault-password-file .vault-password"
    else
        extraArgs="--ask-become-pass"
    fi

    if [[ "${remote}" == true ]]
    then
        setup_remote_env
    else
        setup_local_env
    fi

    install_deps

    ansible-playbook ${extraArgs} playbook.yml
}

helpFunc() {
  echo "Usage: setup.sh [options]
Run Ansible plays with different sequences and command line options,
based on provided switches.

See README.md for more detailed information.

Options:
  -r, --remote         Run plays on the remote target(s) specified in
                       intentory.remote and uses 'vars/vault.yml'.
  -h, --help           Show this help dialog"
  exit 0
}

main() {
    local LONGOPTS=remote,help
    local OPTIONS=rh

    local PARSED=$(getopt --options=$OPTIONS --longoptions=$LONGOPTS --name "$0" -- "$@")

    local remote=false;
    for var in ${PARSED}
    do
    case "${var}" in
        "-r" | "--remote" ) remote=true;;
        "-h" | "--help" ) helpFunc;;
        "--") ;;
        *) echo "Mismatch between options"; exit 1;;
    esac
    done

    setup "${remote}"
}

main "${@}"
