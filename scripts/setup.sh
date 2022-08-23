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
    local interactive="${1}"
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
        if [[ "${interactive}" == false ]]
        then
            echo "Cannot install missing packages without sudo password"
            exit 1
        fi
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
    local interactive="${2}"

    if [[ "${remote}" == false ]] && [[ "${interactive}" == false ]]
    then
        echo "Cannot run locally in non-interactive mode."
        exit 1
    fi

    local extraArgs=""
    if [[ "${remote}" == true ]]
    then
        extraArgs="--inventory ${REMOTE_INVENTORY_FILENAME} --extra-vars @vars/vault.yml"
    elif [[ "${interactive}" == true ]]
    then
        extraArgs="--ask-become-pass"
    fi

    if [[ "${remote}" == true ]]
    then
        setup_remote_env
    else
        setup_local_env "${interactive}"
    fi

    install_deps

    if [[ "${remote}" == true ]]
    then
        ansible-playbook ${extraArgs} bootstrap.yml
    fi

    ansible-playbook ${extraArgs} update.yml
    ansible-playbook ${extraArgs} playbook.yml
}

helpFunc() {
  echo "Usage: setup.sh [options]
Run Ansible plays with different sequences and command line options,
based on provided switches.

See README.md for more detailed information.

Options:
  -r, --remote         Run plays on the remote target(s) specified in
                       intentory.remote. Also affects the filename of
                       the expected vault, in case --interactive switch
                       was not provided.
  -i, --interactive    Make Ansible ask for passwords instead of
                       expecting a vault and 'vault_password_file' to
                       be present. Expected vault file changes based on
                       --remote switch.
  -h, --help           Show this help dialog"
  exit 0
}

main() {
    local LONGOPTS=remote,interactive,help
    local OPTIONS=rih

    local PARSED=$(getopt --options=$OPTIONS --longoptions=$LONGOPTS --name "$0" -- "$@")

    local remote=false;
    local interactive=false;
    for var in ${PARSED}
    do
    case "${var}" in
        "-r" | "--remote" ) remote=true;;
        "-i" | "--interactive" ) interactive=true;;
        "-h" | "--help" ) helpFunc;;
        "--") ;;
        *) echo "Mismatch between options"; exit 1;;
    esac
    done

    setup "${remote}" "${interactive}"
}

main "${@}"
