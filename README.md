# xnode-admin
Administrator service to reconfigure and administrate a live xnode system. This services accompanies the Xnode Studio front-end 

## Objective
Develop configuration infrastructure for a deployed xnode that can be hosted by either openmesh itself or self-hosted by the user.
Develop scalability features to handle many configuration changes made through openmesh.

## Core functionality
* Wallet signing / authentication
* Nix configuration is changed through git 
* Logic for calling nixos-rebuild and returning readable output to the user/studio

isomorphic-git in front-end that pushes wallet-signed commits to a git repository.

This admin service will have the following loops:
* regularly pull from git remote per interval (eg. 5 mins, configurable via response from the server)
* quick pull txt record as bloom filter record from powerdns 
    * when it receives the correct uuid as a bloom filter it will trigger an instant git pull from the configured remote

## Progress / To-Do
* Integration with Isomorphic git on the front-end
* Wallet Connect signature and verification.
    * Determine whether we should convert to GPG/SSH format or use a custom verify-commit function.
* Refactor with a class to tidy up the main function.

## Usage
` xnode-rebuilder GIT_LOCATION GIT_REMOTE SEARCH_INTERVAL [GPG_KEY] [POWERDNS_URL] `

`GIT_LOCATION` is the local directory where the git folder should be cloned. Ensure that your configuration.nix imports this.

`GIT_REMOTE` is the remote location to pull configuration updates from.

`SEARCH_INTERVAL` is the interval between git pulls measured in seconds (s).

`GPG_KEY` (optional) path to the gpg public key.

`POWERDNS_URL` (optional) is for scalability, it is a way to receive TXT records that trigger immediate pull from git.

## Important note about security
If there are unsigned commits to the source repository for example if it is compromised or there is a malfunction, then the Xnode will not pull those commits due to a git command error exception. It will however pull the next signed commit, so Xnode Studio should handle notifying the user of untracked / unsigned commits and merging or dropping them.