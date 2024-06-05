#!/usr/bin/env python

import git
import os
import time
import sys
import psutil
from pathlib import Path
import requests
import json


# NOTE: Not secret, just used to prevent blind spam.
DPL_BACKEND_APP_KEY='as90qw90uj3j9201fj90fj90dwinmfwei98f98ew0-o0c1m221dds222143'


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

    user_key=None
    key_type=None
    userid=None

    for o in opts:
        if o.startswith("--uuid="):
            userid = o.split('=')[1]
        if o.startswith("--ssh-dir="):
            user_key = o.split('=')[1]
            key_type = "ssh"
        elif o.startswith("--gpg-key="):
            user_key = o.split('=')[1]
            key_type = "gpg"
        elif o.startswith("--access-token="):
            user_key = o.split('=')[1]
            key_type = "access_token"
        
        if o.startswith("-p"): # Find uuid / psk at /proc/cmdline
            with open("/proc/cmdline") as file:
                kvars = file.read.split(" ")
                for kvar in kvars:
                    if kvar.startswith("XNODE_UUID="):
                        userid = kvar.split('=')[1]
                    if kvar.startswith("XNODE_ACCESS_TOKEN="):
                        user_key = kvar.split('=')[1]
                if userid is None or user_key is None:
                    print("Failed to find XNODE_UUID or XNODE_ACCESS_TOKEN in /proc/cmdline")
                    sys.exit(1)
                else:
                    key_type = "access_token"

        if o.startswith("--powerdns="):
            powerdns_url = o.split('=')[1] # Todo

    return args[0], args[1], int(args[2]), user_key, key_type, userid

def main():
    # Program usage: xnode-rebuilder <local path> <git remote repo> <search interval> <optional: GPG Key> <optional: POWERDNS_URL>

    local_repo_path, remote_repo_path, fetch_interval, user_key, key_type, uuid,  = parse_args() # powerdns_url not implemented yet

    # Hack to use Xnode Studio API rather than a git remote
    if fetch_interval == 0: # Studio uses a hardcoded interval
        print("Running in Studio mode.")
        if key_type == "access_token":
            # Remote repo is the studio's URL and User key is a preshared secret.
            fetch_config_studio(remote_repo_path, uuid, user_key, local_repo_path)
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
        configure_keys(user_key, key_type, repo)
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

def fetch_config_studio(studio_url, xnode_Id, access_token, config_location):
    # Talks to the dpl backend to configure the xnode directly.
    hearbeat_interval = 15 # Heartbeat interval in seconds
    last_checked = time.time() - hearbeat_interval # Eligible to search immediately on startup
    cpu_usage_list = []
    mem_usage_list = []
    latest_config_location = Path(config_location) # Hardcoded, should be local_repo
    if not latest_config_location.is_file():
        # Create an empty json file so that the rest of the code can assume it is there.
        pass

    # Loop forever, pulling changes from Xnode Studio and collecting metrics to send.
    while True:
        # Collect metrics
        cpu_usage_list.append(psutil.cpu_percent())
        mem_usage_list.append(psutil.virtual_memory().used / (1024 * 1024))

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

            # TODO: Send metrics to Xnode Studio
            disk = psutil.disk_usage('/')
            message = {
                "id": str(xnode_Id),
                "cpuPercent": (avg_cpu_usage),
                "cpuPercentPeek": (highest_cpu_usage),
                "ramMbUsed": (avg_mem_usage),
                "ramMbPeek": (highest_mem_usage),
                "ramMbTotal": (psutil.virtual_memory().total),

                "storageMbUsed":  (disk.used / (1024 * 1024)),
                "storageMbTotal": (disk.total / (1024 * 1024)),
            }

            headers = {
                'content-type': 'application/json',
                'X-Parse-Application-Id': DPL_BACKEND_APP_KEY,
                'x-parse-session-token': access_token,
            }
            requests.post(studio_url + '/pushXnodeHeartbeat', headers=headers, json=message)

            message = {
                "id": str(xnode_Id),
            }

            # TODO: Add an option to check a hash or something to lower bandwidth.
            print('Fetching update message.')
            config_response = requests.get(studio_url + '/getXnodeServices', headers=headers, json=message)
            latest_config = json.loads(config_response.text)

            if config_response.ok:
                config_updated = process_config(latest_config, latest_config_location)

                if config_updated:
                    # TODO: Rebuild NixOS
                    rebuild_nixos()
            else:
                print('Request failed, status: ', config_response.status_code)
                print(config_response.content)

            # Reset last_checked and empty the lists
            cpu_usage_list = []
            mem_usage_list = []
            last_checked = time.time()

        precision = 1 # (seconds) Increase to trade performance for metric precision
        time.sleep(precision)

def process_config(raw_json_studio, xnode_nix_path):
    # 1 Check if config has changed
    if not os.path.isfile("/latest_config.json"):
        with open("./latest_config.json", "w") as f:
            last_config = "{}"
            f.write(last_config)
    else:
        with open("./latest_config.json", "r") as f:
            last_config = json.load(f)

    if last_config == raw_json_studio:
        return False # Same config as last update.

    # 2 Update config by constructing configuration from the new json
    new_sys_config = "{ config, pkgs, ... }:\n{"
    for module in raw_json_studio:
        module_config = "\n  services." + str(module["nixName"]) + " = {\n    enable = true;\n  "
        for option in module["options"]:
            module_config += "  " + str(option["nixName"]) + " = " + parse_nix_primitive(option["type"], option["value"]) + ";\n  "
        new_sys_config += module_config + "};"
    new_sys_config += "\n}"
    print(new_sys_config)
    # Write the new config to the .nix file
    with open(xnode_nix_path, "w") as f:
        f.write(new_sys_config)
    with open("./latest_config.json", "w") as f:
        f.write(json.dumps(raw_json_studio))
    return True

def parse_nix_primitive(type, value):
    if type == "int":
        return value
    elif type == "float":
        return float(value)
    elif type.startswith("/") or type.startswith("./"):
        return value
    elif type == "string":
        return '"' + value + '"'
    else:
        return value

def fetch_config_git():
    # To-do: Modularise the main function for readability
    pass

if __name__ == "__main__":
    main()