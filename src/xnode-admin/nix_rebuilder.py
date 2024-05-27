#!/usr/bin/env python

import git
import os
import time
import sys

def parse_args():
    # Simple function to pass in arguments from the command line, argument order is important.
    opts = [opt for opt in sys.argv[1:] if opt.startswith("-")]
    args = [arg for arg in sys.argv[1:] if not arg.startswith("-")]

    if len(args) >=3:
        print(sys.argv[1], sys.argv[2], sys.argv[3]) # Git remote
        # input validation for first 3 arguments (eg, int conversion, remote existence / reachability)
    else:
        print("Usage: xnode-rebuilder -[sgd] GIT_LOCATION GIT_REMOTE SEARCH_INTERVAL [USER_KEY] [POWERDNS_URL]")
        print("Git local and remote are required, user key can be SSH or GPG and powerdns is for scaling.")
        print("If using a USER_KEY please specify -s for SSH or -g for gpg.")
        sys.exit(1)

    # User key options
    if "-s" in opts:
        user_key = args[3]
        use_ssh = True
        print("Using SSH Public Key at directory: ", user_key)
    elif "-g" in opts:
        user_key = args[3]
        use_ssh = False
        print("Using PGP Public Key: ", user_key)
    else:
        user_key = None
        use_ssh = None
    # PowerDns options
    if "-d" in opts:
        powerdns_url = args[4]
        print("Using PowerDNS: ", powerdns_url)
    else:
        powerdns_url = ""

    return args[0], args[1], int(args[2]), user_key, use_ssh, powerdns_url


def main():
    # Program usage: xnode-rebuilder <local path> <git remote repo> <search interval> <optional: GPG Key> <optional: POWERDNS_URL>
    local_repo_path, remote_repo_path, search_interval, user_key, use_ssh, _powerdns_url = parse_args() # powerdns_url not implemented yet

    # Hack to use Xnode Studio API rather than git (for short deadline)
    if search_interval == 0:
        print("Running in Studio mode.")
        # Remote repo = Studio's backend url, whitelisted as only accepted connection
        # Logic for Studio API here...
        HandleStudioAPI()
    else:
        # If there is no git repository at the local path, clone it.
        if not os.path.exists(local_repo_path):
            try:
                git.Repo.clone_from(remote_repo_path, local_repo_path)
            except git.CommandError as e:
                print("Failed to clone repository: ", remote_repo_path, "Error:", e)

        # Initialise interval and git.Repo object
        last_checked = time.time() - search_interval # Eligible to search immediately on startup
        repo = git.Repo(local_repo_path)

        # If applicable, add the key to the repo's git config for commit verification
        configure_keys(user_key, use_ssh, repo)
        git_bin = repo.git

        # Loop forever, pulling changes from git.
        while True:
            # If the interval has passed since the last check then fetch the latest head.
            if last_checked + search_interval < time.time():
                fetch_info = repo.remotes.origin.fetch()
                for fetch in fetch_info:
                    print("Fetched from:", fetch.name)
                    print("Fetched commit:", fetch.commit)

                    # Assuming the branch you care about is 'master'
                    if 'origin/main' in fetch.name:
                        local_commit = repo.heads.main.commit
                        remote_commit = fetch.commit

                        if local_commit.hexsha != remote_commit.hexsha:
                            print("New commits are available on the remote master branch.")
                            # You can list the new commits if necessary

                            # This will print the verification result for each commit
                            try:
                                verification_output = git_bin.verify_commit(remote_commit.hexsha)                      
                                repo.remotes.origin.pull(remote_commit.hexsha)
                                print("Commit was verified and pulled.", verification_output)
                                rebuild_nixos()

                            except git.GitCommandError as e:
                                print(verification_output)
                                print(e)
                                print("Failed to verify commit:", remote_commit)
                                    
                        else:
                            print("Local master is up to date with the remote master.")
                            try:
                                verification_output = git_bin.verify_commit(repo.head.commit.hexsha)
                                print(verification_output)
                            except git.GitCommandError as e:
                                print(e)
                                print("Failed to verify commit:", repo.head.commit)
            # Fetch from origin
            last_checked = time.time()             
            # merge with fast forward

def configure_keys(user_key, use_ssh, repo):
    if user_key is not None:
        if use_ssh:
            try:
                with repo.config_writer() as config:
                    config.set_value("gpg", "format", "ssh")
                    config.set_value('gpg "ssh"',"allowedSignersFile", user_key) # Path to 'keyfile' (similar to an authorized_hosts)
                    config.release()
            except git.GitCommandError:
                print("Failed to set SSH key", git.GitCommandNotFound)
        elif use_ssh is False:
            try:
                with repo.config_writer() as config: # To-do: Implement GPG
                    config.set_value("gpg", "format", "") # UPDATE
                    config.set_value("user","signingKey", user_key) # Hex of gpg public key
                    config.release()
            except git.GitCommandError:
                print("Failed to set SSH key", git.GitCommandNotFound)
        else: # When use_ssh is None
            pass
        
def rebuild_nixos():
    # To-Do: Return errors to Xnode Studio, possibly by pushing error logs to the git repo.
    # To-Do: Rebuild NixOS function for error logging
    os.system("nixos-rebuild switch") # Rebuild NixOS  --flake .#xnode

def HandleStudioAPI():
    # Talks to the dpl backend to configure the xnode directly.
    # Can directly modify nix configuration files if we need to.
    pass

if __name__ == "__main__":
    main()