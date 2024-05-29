#!/usr/bin/env python

import git
import os
import time
import sys
import psutil

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

    # Studio mode override
    if args[2] == 0:
        user_key = args[3] # Set the preshared secret using a nix option

    return args[0], args[1], int(args[2]), user_key, use_ssh, powerdns_url

def main():
    # Program usage: xnode-rebuilder <local path> <git remote repo> <search interval> <optional: GPG Key> <optional: POWERDNS_URL>
    local_repo_path, remote_repo_path, fetch_interval, user_key, use_ssh, _powerdns_url = parse_args() # powerdns_url not implemented yet

    # Hack to use Xnode Studio API rather than a git remote
    if fetch_interval == 0: # Studio uses a hardcoded interval
        print("Running in Studio mode.")
        # Remote repo is the studio's URL and User key is a preshared secret.
        fetch_config_studio(remote_repo_path, user_key)
    else:
        # If there is no git repository at the local path, clone it.
        if not os.path.exists(local_repo_path):
            try:
                git.Repo.clone_from(remote_repo_path, local_repo_path)
            except git.CommandError as e:
                print("Failed to clone repository: ", remote_repo_path, "Error:", e)

        # Initialise interval and git.Repo object
        last_checked = time.time() - fetch_interval # Eligible to search immediately on startup
        repo = git.Repo(local_repo_path)

        # If applicable, add the key to the repo's git config for commit verification
        configure_keys(user_key, use_ssh, repo)
        git_bin = repo.git

        # Loop forever, pulling changes from git.
        while True:
            # If the interval has passed since the last check then fetch the latest head.
            if last_checked + fetch_interval < time.time():
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
            last_checked = time.time()

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

def fetch_config_studio(studio_url, preshared_secret):
    # Talks to the dpl backend to configure the xnode directly.
    
    hearbeat_interval = 15 # Heartbeat interval in seconds
    last_checked = time.time() - hearbeat_interval # Eligible to search immediately on startup
    cpu_usage_list = []
    mem_usage_list = []

    # Loop forever, pulling changes from Xnode Studio.
    while True:
        # Collect metrics
        cpu_usage_list.append(psutil.cpu_percent())
        mem_usage_list.append(psutil.virtual_memory().percent)

        # If the interval has passed since the last check then fetch from the studio.
        if last_checked + hearbeat_interval < time.time():
            # Calculate metrics (average and maximum)
            total = 0
            highest_cpu_usage = 0
            for i in cpu_usage_list:
                if i > highest_cpu_usage:
                    highest_cpu_usage = i
                total += i
            avg_cpu_usage = total / len(cpu_usage_list)

            total = 0
            highest_mem_usage = 0
            for i in mem_usage_list:
                if i > highest_mem_usage:
                    highest_mem_usage = i
                total += i
                avg_mem_usage = total / len(mem_usage_list)

            # Submit heartbeat with metrics, reconfigure if required.
            print(highest_cpu_usage, avg_cpu_usage)
            print(highest_mem_usage, avg_mem_usage)

            # Reset last_checked and empty the lists
            cpu_usage_list = []
            mem_usage_list = []
            last_checked = time.time()      
        time.sleep(1)
    
def fetch_config_git():
    # To-do: Modularise the main function for readability
    pass

if __name__ == "__main__":
    main()