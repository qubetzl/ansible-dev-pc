import json
from pathlib import Path
from typing import Dict, Iterable, List
from unittest.mock import MagicMock, call, patch
import pytest
import extrepo_repository
from extrepo_repository import RepositoryState, SourceFileState, ExtrepoAction
from ansible.module_utils.basic import AnsibleModule

from ansible.module_utils import basic
from ansible.module_utils.common.text.converters import to_bytes


__metaclass__ = type


def set_module_args(args: Dict) -> None:
    args["_ansible_remote_tmp"] = "/tmp"
    args["_ansible_keep_remote_files"] = False

    args = json.dumps({"ANSIBLE_MODULE_ARGS": args})
    basic._ANSIBLE_ARGS = to_bytes(args)


class AnsibleExitJson(Exception):
    pass


class AnsibleFailJson(Exception):
    pass


def mock_exit_json(*args, **kwargs) -> None:
    raise AnsibleExitJson(kwargs)


def mock_fail_json(*args, **kwargs) -> None:
    kwargs["failed"] = True
    raise AnsibleFailJson(kwargs)


@pytest.fixture
def module_instance() -> AnsibleModule:
    set_module_args({})
    module = AnsibleModule(argument_spec={}, supports_check_mode=False)
    with patch.multiple(module, fail_json=mock_fail_json, exit_json=mock_exit_json):
        yield module


@pytest.mark.parametrize(
    ("repository_name", "expected"),
    [
        ("brave_release", "extrepo_brave_release.sources"),
        ("vscodium", "extrepo_vscodium.sources"),
    ],
)
def test_compute_sources_filename(repository_name: str, expected: str) -> None:
    assert extrepo_repository.compute_sources_filename(repository_name) == expected


@pytest.mark.parametrize(
    ("repository_name", "expected"),
    [
        ("jellyfin", True),
        ("something-not-found", False),
    ],
)
def test_is_in_extrepo_metadata(
    module_instance: AnsibleModule, repository_name: str, expected: bool
) -> None:
    with patch.object(module_instance, "run_command") as mock_run_command:
        mock_run_command.return_value = 0, get_extrepo_search_output(), ""

        assert (
            extrepo_repository.is_in_extrepo_metadata(module_instance, repository_name)
            is expected
        )

    assert mock_run_command.call_args_list == [
        call(["extrepo", "search", repository_name])
    ]


def test_is_in_extrepo_metadata__when_extrepo_is_not_installed__returns_an_error(
    module_instance: AnsibleModule,
) -> None:
    with patch.object(module_instance, "run_command") as mock_run_command:
        mock_run_command.return_value = 127, "", "bash: extrepo: command not found\n"

        with pytest.raises(AnsibleFailJson) as exc_info:
            extrepo_repository.is_in_extrepo_metadata(
                module_instance, "a_repository_name"
            )
        assert str(exc_info.value) == str(
            {
                "msg": "Error attempting to search for repository [command: extrepo search a_repository_name]: (127) bash: extrepo: command not found\n",
                "failed": True,
            }
        )

    assert mock_run_command.call_args_list == [
        call(["extrepo", "search", "a_repository_name"])
    ]


@pytest.mark.parametrize(
    "state",
    [
        SourceFileState.ENABLED_IMPLICIT,
        SourceFileState.ENABLED_EXPLICIT,
        SourceFileState.DISABLED,
    ],
)
def test_get_source_file_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    state: SourceFileState,
) -> None:
    monkeypatch.setattr(extrepo_repository, "APT_SOURCES_LIST_D", str(tmp_path))
    source_filepath = "extrepo_yarnpkg.sources"

    source_path = tmp_path / source_filepath
    source_path.write_text(get_sources_file_content(state))

    assert extrepo_repository.get_source_file_state(source_filepath) is state


def test_get_source_file_state__when_source_file_does_not_exist__returns__not_present(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(extrepo_repository, "APT_SOURCES_LIST_D", str(tmp_path))
    source_filepath = "extrepo_yarnpkg.sources"

    assert (
        extrepo_repository.get_source_file_state(source_filepath)
        is SourceFileState.NOT_PRESENT
    )


def test_get_source_file_state__when_there_are_multiple_enabled_lines__returns_broken(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(extrepo_repository, "APT_SOURCES_LIST_D", str(tmp_path))
    source_filepath = "extrepo_yarnpkg.sources"
    source_path = tmp_path / source_filepath

    content = get_sources_file_content(SourceFileState.DISABLED)
    content = content + f"Enabled: no\n"
    source_path.write_text(content)

    assert (
        extrepo_repository.get_source_file_state(source_filepath)
        is SourceFileState.BROKEN
    )


@pytest.mark.parametrize(
    ("source_file_state", "expected_repository_state"),
    [
        (SourceFileState.ENABLED_IMPLICIT, RepositoryState.ENABLED),
        (SourceFileState.ENABLED_EXPLICIT, RepositoryState.ENABLED),
        (SourceFileState.BROKEN, RepositoryState.ENABLED),
        (SourceFileState.DISABLED, RepositoryState.DISABLED),
        (SourceFileState.NOT_PRESENT, RepositoryState.NOT_INSTALLED),
    ],
)
@patch.object(extrepo_repository, "get_source_file_state", autospec=True)
@patch.object(extrepo_repository, "is_in_extrepo_metadata", autospec=True)
def test_get_repository_details__when_is_not_in_extrepo_metadata__returns_repository_definition_not_found(
    mock_is_in_extrepo_metadata: MagicMock,
    mock_get_source_file_state: MagicMock,
    module_instance: AnsibleModule,
    source_file_state: SourceFileState,
    expected_repository_state: RepositoryState,
):
    test_repository_name = "a_repository_name"
    mock_is_in_extrepo_metadata.return_value = False
    mock_get_source_file_state.return_value = source_file_state

    actual_result = extrepo_repository.get_repository_details(
        module_instance, test_repository_name
    )

    assert actual_result == {
        "name": test_repository_name,
        "state": expected_repository_state,
        "source_state": source_file_state,
    }

    assert mock_is_in_extrepo_metadata.call_args_list == [
        call(module_instance, test_repository_name)
    ]


@patch.object(extrepo_repository, "is_in_extrepo_metadata", autospec=True)
def test_get_repository_details__when_is_not_in_extrepo_metadata__returns_repository_definition_not_found(
    mock_is_in_extrepo_metadata: MagicMock,
    module_instance: AnsibleModule,
):
    mock_is_in_extrepo_metadata.return_value = False

    with pytest.raises(AnsibleFailJson) as exc_info:
        extrepo_repository.get_repository_details(module_instance, "unknown_repository")
        assert str(exc_info.value) == str(
            {
                "msg": "Repository unknown_repository is not present in extrepo's metadata\n",
                "failed": True,
            }
        )

    assert mock_is_in_extrepo_metadata.call_args_list == [
        call(module_instance, "unknown_repository")
    ]


@pytest.mark.parametrize(
    ("current_state", "current_source_states", "expected_action"),
    [
        (
            RepositoryState.NOT_INSTALLED,
            SourceFileState,
            ExtrepoAction.ENABLE_REPO,
        ),
        (
            RepositoryState.ENABLED,
            (
                SourceFileState.ENABLED_EXPLICIT,
                SourceFileState.ENABLED_IMPLICIT,
            ),
            ExtrepoAction.NONE,
        ),
        (
            RepositoryState.ENABLED,
            (SourceFileState.BROKEN,),
            ExtrepoAction.ENABLE_REPO,
        ),
        (
            RepositoryState.DISABLED,
            SourceFileState,
            ExtrepoAction.ENABLE_REPO,
        ),
    ],
)
def test_determine_action__when_desired_state_is_enabled(
    current_state: RepositoryState,
    current_source_states: Iterable[SourceFileState],
    expected_action: ExtrepoAction,
):
    for current_source_state in current_source_states:
        actual_action = extrepo_repository.determine_action(
            desired_state=RepositoryState.ENABLED,
            current_state=current_state,
            current_source_state=current_source_state,
        )
        assert actual_action == expected_action


@pytest.mark.parametrize(
    ("current_state", "current_source_states", "expected_action"),
    [
        (
            RepositoryState.NOT_INSTALLED,
            SourceFileState,
            ExtrepoAction.NONE,
        ),
        (
            RepositoryState.ENABLED,
            (
                SourceFileState.ENABLED_EXPLICIT,
                SourceFileState.ENABLED_IMPLICIT,
            ),
            ExtrepoAction.DISABLE_REPO,
        ),
        (
            RepositoryState.ENABLED,
            (SourceFileState.BROKEN,),
            ExtrepoAction.DISABLE_REPO,
        ),
        (
            RepositoryState.DISABLED,
            SourceFileState,
            ExtrepoAction.NONE,
        ),
    ],
)
def test_determine_action__when_desired_state_is_disabled(
    current_state: RepositoryState,
    current_source_states: Iterable[SourceFileState],
    expected_action: ExtrepoAction,
):
    for current_source_state in current_source_states:
        actual_action = extrepo_repository.determine_action(
            desired_state=RepositoryState.DISABLED,
            current_state=current_state,
            current_source_state=current_source_state,
        )
        assert actual_action == expected_action


def test_do_action__when_action_is_none__does_nothing(
    module_instance: AnsibleModule,
) -> None:
    with pytest.raises(AnsibleExitJson) as exc_info:
        extrepo_repository.do_action(
            module_instance,
            "jellyfin",
            ExtrepoAction.NONE,
        )
    assert str(exc_info.value) == str(
        {"changed": False, "msg": "Repository jellyfin already in desired state"}
    )


@pytest.mark.parametrize(
    ("action", "expected_msg"),
    [
        (ExtrepoAction.ENABLE_REPO, "Repository jellyfin was (re-)enabled"),
        (ExtrepoAction.DISABLE_REPO, "Repository jellyfin was disabled"),
    ],
)
def test_do_action__when_action_requires_changes__and_module_is_in_check_mode__does_not_run_commands__and_reports_changed(
    module_instance: AnsibleModule,
    action: ExtrepoAction,
    expected_msg: str,
) -> None:
    module_instance.check_mode = True
    with patch.object(module_instance, "run_command") as mock_run_command:
        mock_run_command.return_value = 0, "", ""
        with pytest.raises(AnsibleExitJson) as exc_info:
            extrepo_repository.do_action(module_instance, "jellyfin", action)
        assert str(exc_info.value) == str({"changed": True, "msg": expected_msg})
    assert mock_run_command.call_count == 0


@pytest.mark.parametrize(
    ("action", "expected_action_cmd", "expected_msg"),
    [
        (ExtrepoAction.ENABLE_REPO, "enable", "Repository jellyfin was (re-)enabled"),
        (ExtrepoAction.DISABLE_REPO, "disable", "Repository jellyfin was disabled"),
    ],
)
def test_do_action__when_action_requires_changes__and_module_is_not_in_check_mode__runs_commands__and_reports_changed(
    module_instance: AnsibleModule,
    action: ExtrepoAction,
    expected_action_cmd: str,
    expected_msg: str,
) -> None:
    with patch.object(module_instance, "run_command") as mock_run_command:
        mock_run_command.return_value = 0, "", ""
        with pytest.raises(AnsibleExitJson) as exc_info:
            extrepo_repository.do_action(module_instance, "jellyfin", action)
        assert str(exc_info.value) == str({"changed": True, "msg": expected_msg})
    assert mock_run_command.call_args_list == [
        call(["extrepo", expected_action_cmd, "jellyfin"])
    ]


def get_sources_file_content(state: SourceFileState):
    content = """\
Components: main
Uris: https://brave-browser-apt-release.s3.brave.com
Architectures: amd64
Suites: stable
Types: deb
Signed-By: /var/lib/extrepo/keys/brave_release.asc
"""
    if state == SourceFileState.ENABLED_IMPLICIT:
        state_value = None
    elif state == SourceFileState.ENABLED_EXPLICIT:
        state_value = "yes"
    elif state == SourceFileState.DISABLED:
        state_value = "no"
    elif state == SourceFileState.BROKEN:
        state_value = "bogus"
    else:
        raise AssertionError
    if state_value:
        content = f"{content}Enabled: {state_value}\n"
    return content


def get_extrepo_known_repositories() -> List[str]:
    return [
        "torproject",
        "zulu-openjdk",
        "whonix_proposed",
        "openmodelica-stable",
        "jellyfin",
        "i2pd",
        "yarnpkg",
    ]


def get_extrepo_search_output() -> str:
    return """\
Found torproject:
---
description: Torproject.org repository
gpg-key-checksum:
  sha256: bf7f499edec7e10f41b4e5ee7f72623c450c6e88dcbcd984d9ddf6e9773d25e1
gpg-key-file: torproject.asc
policy: main
source:
  Architectures: amd64 arm64 i386
  Components: main
  Suites: bookworm
  Types: deb deb-src
  URIs: https://deb.torproject.org/torproject.org/


Found zulu-openjdk:
---
contact: zulu-ci@azul.com
description: The world’s best supported builds of OpenJDK.
gpg-key-checksum:
  sha256: 687ad78aef29b15f5f7696e04760623bd1c85c557d1e54498d245c4b1e38e226
gpg-key-file: zulu-openjdk.asc
policy: main
source:
  Architectures: amd64 arm64
  Components: main
  Suites: stable
  Types: deb
  URIs: https://repos.azul.com/zulu/deb


Found whonix_proposed:
---
components:
- main
- contrib
- non-free
description: Whonix APT Repository
gpg-key-checksum:
  sha256: 49e117377fc182ad337b58359565aeedd58de89048584314bdb49699c50e6f23
gpg-key-file: whonix_proposed.asc
policies:
  contrib: contrib
  main: main
  non-free: non-free
source:
  Architectures: amd64 arm64 armel armhf hurd-i386 hurd-amd64 i386 kfreebsd-amd64
    kfreebsd-i386 mips mipsel powerpc ppc64el s390x sparc
  Components: <COMPONENTS>
  Suites: bookworm-proposed-updates
  Types: deb deb-src
  URIs: https://deb.whonix.org


Found openmodelica-stable:
---
contact: https://github.com/OpenModelica/OpenModelica/issues/new
description: Modelica-based modeling and simulation environment intended for industrial
  and academic usage.
gpg-key-checksum:
  sha256: 3bc922813f78da45e650a3cd6dcda44d13bae2167f04a79f66dd2b24f2108f47
gpg-key-file: openmodelica-stable.asc
policy: main
source:
  Architectures: amd64 i386 arm64 armhf
  Suites: bookworm
  Types: deb deb-src
  URIs: http://build.openmodelica.org/apt
  components: stable


Found jellyfin:
---
description: Jellyfin Free Software Media System APT repository
gpg-key-checksum:
  sha256: a0cde241ae297fa6f0265c0bf15ce9eb9ee97c008904a59ab367a67d59532839
gpg-key-file: jellyfin.asc
policy: main
source:
  Architectures: amd64 arm64 armhf
  Components: main
  Suites: bookworm
  Types: deb
  URIs: https://repo.jellyfin.org/debian


Found i2pd:
---
description: i2pd - an i2p router implemented in C
gpg-key-checksum:
  sha256: 5773812ca1fb48697d00d5d25b5706eb44bf5e74432e26641be34a9e8f24352a
gpg-key-file: i2pd.asc
policy: main
source:
  Architectures: amd64 i386 arm64 armhf
  Components: main
  Suites: bookworm
  Types: deb deb-src
  URIs: https://repo.i2pd.xyz/debian


Found yarnpkg:
---
description: yarn package manager for javascript
gpg-key-checksum:
  sha256: 8550a7e298b523fffa899069754fc150f2ff74092701e4d4109edd1cd6d5327f
gpg-key-file: yarnpkg.asc
policy: main
source:
  Architectures: amd64 arm64 armhf i386
  Components: main
  Suites: stable
  Types: deb
  URIs: https://dl.yarnpkg.com/debian/



"""
