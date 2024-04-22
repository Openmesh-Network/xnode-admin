#!/usr/bin/env python

# Pull from https://github.com/harrys522/sample-nix-repo.git

import git
import os
import time
import sys
import gnupg

def main():
    # Program usage: xnode-rebuilder <local path> <git remote repo> <search interval> <optional: GPG Key> <optional: POWERDNS_URL>
    if len(sys.argv) >=3:
        print(sys.argv[1], sys.argv[2], sys.argv[3]) # Git remote
    else:
        print("Usage: xnode-rebuilder GIT_LOCATION GIT_REMOTE SEARCH_INTERVAL [GPG_KEY] [POWERDNS_URL]")
        print("Git local and remote are required, PGP public key can be a file path or in-line and is highly recommended, powerdns is for scaling")
        sys.exit(1)
    localRepoPath = sys.argv[1]
    remoteRepoPath = sys.argv[2]
    searchInterval = int(sys.argv[3])
    # Optional command line arguments
    GpgkeyOption = False
    PowerdnsOption = False
    if len(sys.argv) > 4:
        print(sys.argv[4]) # PGP public key
        GpgkeyOption = True
    if GpgkeyOption:
       # gnupg.GPG().import_keys(sys.argv[4])
       pass
    if len(sys.argv) > 5:
        print(sys.argv[5]) # Powerdns
        PowerdnsOption = True


    # Add the remote origin, validate it's reachability and print result (Success or failure) for debugging.

    # If there is no git repository at the local path, clone it.
    if not os.path.exists(localRepoPath):
        git.Repo.clone_from(remoteRepoPath, localRepoPath)

    # Preloop variable definitions
    startTime = time.time()
    lastChecked = time.time() - searchInterval
    repo = git.Repo(localRepoPath)

    # Loop forever, pulling changes from git.
    # If there 
    while True:
        o = repo.remotes.origin
        fetchInfo = o.pull()
        print(fetchInfo)
        for commit in list(repo.iter_commits()):
            print(commit)
            print(commit.gpgsig)

        time.sleep(5)

        # To-Do: Return errors to Xnode Studio, probably through pushing error logs to git repo.
        # To-Do: Rebuild NixOS in a separate function where we can handle failure or errors
        # os.system("nixos-rebuild switch --flake .#xnode-nix-repo") # Rebuild NixOS

if __name__ == "__main__":
    main()