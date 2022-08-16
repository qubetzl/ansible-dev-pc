# Dev PC setup

This repository sets-up my dev environment from a fresh PopOS install

# Running

The setup is designed to be able to be used to setup both the local and a remote machine.

## Running locally

Run the following command from a fresh install to bootstrap the machine and run the playbook.
```bash
wget https://raw.githubusercontent.com/qubetzl/ansible-dev-pc/master/bootstrap.sh && bash bootstrap.sh
```

Or run the following on an already bootstrapped machine.
```bash
./scripts/setup.sh
```

## Running on a remote machine

Before running the setup script, make sure to:
- Modify `inventory.remote` to point to the target machine
- Add your identity (`~/.ssh/id_rsa`) to the SSH agent

```bash
./scripts/setup-remote.sh
```

## Inspiration
https://github.com/crivetimihai/ansible_workstation
https://github.com/buluma/ansible_workstation
https://github.com/devroles/ansible_collection_system
https://github.com/ghyde/ansible-role-flatpak ?
https://github.com/crivetimihai/ansible_virtualization
