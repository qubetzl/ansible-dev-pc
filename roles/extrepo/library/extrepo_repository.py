#!/usr/bin/python
import os
from enum import Enum, auto

from ansible.module_utils.basic import AnsibleModule

__metaclass__ = type

APT_SOURCES_LIST_D = "/etc/apt/sources.list.d/"
EXTREPO_FILENAME_PREFIX = "extrepo_"
EXTREPO_FILENAME_EXT = ".sources"

EXTREPO_EXECUTABLE = "extrepo"


class ExtrepoModuleError(Exception):
    pass


class UnknownRepositoryName(ExtrepoModuleError):
    pass


class SourceFileState(Enum):
    NOT_PRESENT = auto()
    ENABLED_IMPLICIT = auto()
    ENABLED_EXPLICIT = auto()
    DISABLED = auto()
    BROKEN = auto()


class RepositoryState(Enum):
    NOT_INSTALLED = auto()
    ENABLED = auto()
    DISABLED = auto()
    DEFINITION_NOT_FOUND = auto()


class ExtrepoAction(Enum):
    NONE = auto()
    ENABLE_REPO = auto()
    DISABLE_REPO = auto()


def compute_sources_filename(repository_name):
    return f"{EXTREPO_FILENAME_PREFIX}{repository_name}{EXTREPO_FILENAME_EXT}"


def is_in_extrepo_metadata(module: AnsibleModule, repository_name: str) -> bool:
    """
    Searches based on a repository name and expects to find an _exact_ match.

    Steps:
    - Run `extrepo search <repositry_name>`
    - Search for 'Found' line for the exactrepository name
      Example: 'Found jellyfin:'
    """
    cmd = [EXTREPO_EXECUTABLE, "search", repository_name]
    rc, out, err = module.run_command(cmd)
    if rc != 0:
        module.fail_json(
            msg=f"Error attempting to search for repository [command: {' '.join(cmd)}]: ({rc}) {out + err}",
        )
    repositories_found_stanzas = [
        line for line in out.splitlines() if line.startswith("Found ")
    ]
    return f"Found {repository_name}:" in repositories_found_stanzas


def get_source_file_state(source_filepath: str) -> SourceFileState:
    absolute_path = os.path.join(APT_SOURCES_LIST_D, source_filepath)
    try:
        with open(absolute_path) as f:
            enabled_lines = [l.strip() for l in f if l.startswith("Enabled: ")]
    except OSError:
        return SourceFileState.NOT_PRESENT

    if not enabled_lines:
        return SourceFileState.ENABLED_IMPLICIT
    elif len(enabled_lines) > 1:
        return SourceFileState.BROKEN
    else:
        state = enabled_lines[0][len("Enabled: ") :]
        # Enabled: yes (or any other value really) or missing means "enabled"
        # Enabled: no means "disabled"
        # When explicitly disabled (Enabled: no) the .sources are not used by apt.
        # Any other value for Enabled is considered enabled by apt.
        # However, I rekon we shouldn't be this permissive.
        if state == "yes":
            return SourceFileState.ENABLED_EXPLICIT
        elif state == "no":
            return SourceFileState.DISABLED
        else:
            return SourceFileState.BROKEN


def get_repository_details(module: AnsibleModule, repository_name: str):
    if not is_in_extrepo_metadata(module, repository_name):
        module.fail_json(
            f"Repository {repository_name} is not present in extrepo's metadata"
        )

    source_filepath = compute_sources_filename(repository_name)
    source_file_state = get_source_file_state(source_filepath)

    repo_state = None
    if source_file_state in [
        SourceFileState.ENABLED_IMPLICIT,
        SourceFileState.ENABLED_EXPLICIT,
        SourceFileState.BROKEN,
    ]:
        repo_state = RepositoryState.ENABLED
    elif source_file_state == SourceFileState.DISABLED:
        repo_state = RepositoryState.DISABLED
    elif source_file_state == SourceFileState.NOT_PRESENT:
        repo_state = RepositoryState.NOT_INSTALLED
    return {
        "name": repository_name,
        "state": repo_state,
        "source_state": source_file_state,
    }


def determine_action(
    desired_state: RepositoryState,
    current_state: RepositoryState,
    current_source_state: SourceFileState,
) -> ExtrepoAction:
    if current_state == RepositoryState.DEFINITION_NOT_FOUND:
        raise AssertionError

    if (
        desired_state == RepositoryState.ENABLED
        and current_state == RepositoryState.ENABLED
        and current_source_state == SourceFileState.BROKEN
    ):
        # Fix the existing sources file, because it appears to be in an inconsistent state
        return ExtrepoAction.ENABLE_REPO
    elif desired_state == RepositoryState.ENABLED and (
        current_state
        in [
            RepositoryState.DISABLED,
            RepositoryState.NOT_INSTALLED,
        ]
    ):
        return ExtrepoAction.ENABLE_REPO
    elif (
        desired_state == RepositoryState.DISABLED
        and current_state == RepositoryState.ENABLED
    ):
        return ExtrepoAction.DISABLE_REPO
    else:
        return ExtrepoAction.NONE


def do_action(
    module: AnsibleModule,
    repository_name: str,
    action: ExtrepoAction,
) -> None:
    if action == ExtrepoAction.NONE:
        module.exit_json(
            changed=False, msg=f"Repository {repository_name} already in desired state"
        )
    elif action == ExtrepoAction.ENABLE_REPO:
        if not module.check_mode:
            cmd = [EXTREPO_EXECUTABLE, "enable", repository_name]
            rc, out, err = module.run_command(cmd)
            if rc != 0:
                module.fail_json(
                    msg=f"Error attempting to enable repository {repository_name} [command: {' '.join(cmd)}]: ({rc}) {out + err}"
                )
        module.exit_json(
            changed=True, msg=f"Repository {repository_name} was (re-)enabled"
        )
    elif action == ExtrepoAction.DISABLE_REPO:
        if not module.check_mode:
            cmd = [EXTREPO_EXECUTABLE, "disable", repository_name]
            rc, out, err = module.run_command(cmd)
            if rc != 0:
                module.fail_json(
                    msg=f"Error attempting to disable repository {repository_name} [command: {' '.join(cmd)}]: ({rc}) {out + err}",
                )
        module.exit_json(changed=True, msg=f"Repository {repository_name} was disabled")
    else:
        raise AssertionError


def run_module():
    module_args = dict(
        repository_name=dict(type="str", required=True),
        state=dict(
            type="str",
            default="enabled",
            choices=[
                "enabled",
                "disabled",
            ],
        ),
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)

    repository_name = module.params["repository_name"]
    state_param = module.params["state"]
    if state_param == "enabled":
        desired_state = RepositoryState.ENABLED
    elif state_param == "disabled":
        desired_state = RepositoryState.DISABLED
    else:
        raise AssertionError

    repository_details = get_repository_details(module, repository_name)
    current_state = repository_details["state"]
    current_source_state = repository_details["source_state"]

    action = determine_action(
        desired_state=desired_state,
        current_state=current_state,
        current_source_state=current_source_state,
    )
    do_action(module, repository_name, action)


def main():
    run_module()


if __name__ == "__main__":
    main()
