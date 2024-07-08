# xnode-admin
Administrator service to reconfigure and administrate a live xnode system. This services accompanies the Xnode Studio front-end 

## Objective
Develop configuration infrastructure for a deployed xnode that can be hosted by either openmesh itself or self-hosted by the user.
Develop scalability features to handle many configuration changes made through openmesh.

## Core functionality
* Xnode configuration 
    * Git-based .nix configuration
    * Xnode Studio API (Json->Nix)
* Sending a heartbeat message and system metrics back to the Studio UI.
* Logic for calling nixos-rebuild and returning readable output to the user/studio.
* Wallet signing / authentication (Not implemented)

# General Usage
Find helper shell scripts as samples of usage, there are a number of scripts that can be used speed up the development and testing.

## Usage as a json-based rebuilder
The initial release version of this software will communicate directly with the Studio via an API, building it's configuration from a JSON response received from the Xnode Studio.

Running rebuild_tests.py will emulate the studio using 'mock_studio_message.json', please run all the code from the root directory as there are currently some hardcoded paths.

In the XnodeOS implementation, the command is run as the following assuming that the UUID and ACCESS_TOKEN are passed as kernel parameters.

`src/xnode_admin/main.py --remote <url> [STATE_DIRECTORY]`

Run the following commands for development and testing on your local machine:

```
mkdir xnode
python src/xnode_admin/tests/rebuild_tests.py &
python src/xnode_admin/main.py --remote http://localhost:5000/xnodes/functions --uuid=ABC --access-token=XYZ xnode

```

## Progress / To-Do
* Integration with Isomorphic git on the front-end
* Wallet Connect signature and verification.
    * Determine whether we should convert to GPG/SSH format or use a custom verify-commit function.
* Refactor with a class to tidy up the main function.

## Usage as a git-based rebuilder
Development of the git-based system is currently not a priority for the core team.

`src/xnode_admin/main.py --git-mode --no-proc --remote <git_remote> --interval <search_interval> [state_directory]`

`state_directory` is the local directory to which the git repository will be cloned.

`git_remote` is the remote location to pull configuration updates from.

`search_interval` is the interval between git pulls measured in seconds (s).

() Future security feature: git signing keys

`key_type` the type of key, by default git supports ssh and gpg

`git_key` the path to an ssh key or the id for a gpg key.


### Planned Feature: WalletConnect integration
For the next interation of Xnode Studio, integrate WalletConnect authentication and require an Xnode configuration to be signed by its owner's wallet for it to be accepted by the machine.
