import json
import os
import psutil
import requests
import time
import git
from utils import calculate_metrics, parse_nix_primitive, parse_nix_json, configure_keys, generate_hmac
import base64

def fetch_config_studio(studio_url, xnode_uuid, access_token, state_directory):

    # Push a heartbeat with metrics to the studio and pull a configuration.
    hearbeat_interval = 15 # Heartbeat interval in seconds
    last_checked = time.time() - hearbeat_interval # Eligible to search immediately on startup
    cpu_usage_list = []
    mem_usage_list = []
    preshared_key = base64.b64decode(access_token).hex()

    while True:
        # Collect metrics
        cpu_usage_list.append(psutil.cpu_percent())
        mem_usage_list.append(psutil.virtual_memory().used / (1024 * 1024))

        # If the interval has passed since the last check then fetch from the studio.
        if last_checked + hearbeat_interval < time.time():
            # Calculate metrics (average and maximum)
            avg_cpu_usage, avg_mem_usage, highest_cpu_usage, highest_mem_usage = calculate_metrics(cpu_usage_list, mem_usage_list)

            disk = psutil.disk_usage('/') # Only gets disk usage from root
            heartbeat_message = {
                "id": str(xnode_uuid),
                "cpuPercent": (avg_cpu_usage),
                "cpuPercentPeek": (highest_cpu_usage),
                "ramMbUsed": (avg_mem_usage),
                "ramMbPeek": (highest_mem_usage),
                "ramMbTotal": (psutil.virtual_memory().total / (1024 * 1024)),

                "storageMbUsed":  (disk.used / (1024 * 1024)),
                "storageMbTotal": (disk.total / (1024 * 1024)),
            }
            heartbeat_hmac = generate_hmac(preshared_key, heartbeat_message)
            heartbeat_headers = {
                'x-parse-session-token': heartbeat_hmac  
            }

            # Try to send a heartbeat to the studio, then pull the config
            try:
                heartbeat_response = requests.post(studio_url + '/pushXnodeHeartbeat', headers=heartbeat_headers, json=heartbeat_message)
                if not heartbeat_response.ok:
                    print(heartbeat_response.content)   
            except requests.exceptions.RequestException as e:
                print(e)

            get_config_message = {
                "id": str(xnode_uuid),
            }
            get_config_hmac = generate_hmac(preshared_key, get_config_message)
            get_config_headers = {
                'x-parse-session-token': get_config_hmac  
            }
            print('Fetching update message at', time.time())
            try:
                config_response = requests.get(studio_url + '/getXnodeServices', headers=get_config_headers, json=get_config_message)
                if not config_response.ok:
                    print(config_response.content)
                # Process response if one is received
                if config_response.ok:
                    json_path = state_directory+"/latest_config.json"
                    latest_config = config_response.json()
                    if "message" in latest_config.keys():
                        message = latest_config["message"]
                        message_computed_hmac = generate_hmac(preshared_key, message)
                        if message_computed_hmac == latest_config["hmac"]:
                            print("HMAC of configuration verified")
                            parsed_message = json.loads(message)
                            if parsed_message["expiry"] > time.time()*1000:
                                xnode_config = parsed_message["xnode_config"]
                                config_updated = process_studio_config(xnode_config, state_directory, json_path)
                            else:
                                print("Configuration expiry has passed")
                                config_updated = False
                        else:
                            print("HMAC of configuration not verified:", message_computed_hmac, "against claimed:", latest_config["hmac"])
                            config_updated = False
                    else:
                        # XXX: Redundant for messages with no hmac
                        config_updated = process_studio_config(latest_config, state_directory, json_path)
                    # Rebuild system if config has changed
                    if config_updated:
                        rebuild_success = rebuild_os()
                        if rebuild_success:
                            with open(json_path, "w") as f:
                                f.write(json.dumps(latest_config))
                else:
                    print('Request failed, status: ', config_response.status_code)
                    print(config_response.content)   
            except requests.exceptions.RequestException as e:
                print(e)

            # Reset last_checked and empty the lists
            cpu_usage_list = []
            mem_usage_list = []
            last_checked = time.time()

        precision = 1 # (seconds) Increase to trade performance for metric precision
        time.sleep(precision)

def process_studio_config(studio_json_config, state_directory, json_path):
    # 1 Check if config has changed since last rebuild
    config_path = state_directory+"/config.nix"
    if not os.path.isfile(json_path):
        with open(json_path, "w") as f:
            last_config = "{}"
            f.write(last_config)
            print("Created empty config at", json_path)
    else:
        with open(json_path, "r") as f:
            last_config = json.load(f)

    if last_config == studio_json_config:
        return False # Same config as last saved.

    # 2 Update config by constructing configuration from the new json
    new_sys_config = "{ config, pkgs, ... }:\n{\n  "
    if "services" in studio_json_config:
        print("Ran using api v0.2")
        for module_config in studio_json_config:
            # config_type eg. services, users or networking
            print(studio_json_config[module_config]) # services
            new_sys_config += module_config + " = {\n  "
            for submodule in studio_json_config[module_config]:
                print("______________")
                if "nixName" in submodule.keys():
                    print("Parsing nix config for", submodule["nixName"])
                    new_sys_config += parse_nix_json(submodule)
                else:
                    print("No nixName found in:", submodule)

            new_sys_config += "};\n"
    else: # Otherwise assume all items are services (v0.1)
        print("Ran using api v0.1")
        for module in studio_json_config:
            module_config = "\n  services." + str(module["nixName"]) + " = {\n  "
            for option in module["options"]:
                module_config += "  " + str(option["nixName"]) + " = " + parse_nix_primitive(option["type"], option["value"]) + ";\n  "
            new_sys_config += module_config + "};"
    new_sys_config += "\n}"
    print(new_sys_config)

    # 3 Write the new config to the .nix file
    with open(config_path, "w") as f:
        f.write(new_sys_config)
    return True

def fetch_config_git(local_repo_path, remote_repo_path, fetch_interval, key_type, user_key):
    repo = git.Repo(local_repo_path)

    # Configure git signing keys if applicable
    # If applicable, add the key to the repo's git config for commit verification
    configure_keys(user_key, key_type, repo)
    git_bin = repo.git
    # If there is no git repository at the local path, clone it.
    if not os.path.exists(local_repo_path):
        try:
            git.Repo.clone_from(remote_repo_path, local_repo_path)
        except git.CommandError as e:
            print("Failed to clone repository: ", remote_repo_path, "Error:", e)

    # Initialise interval and git.Repo object
    last_checked = time.time() - fetch_interval # Eligible to search immediately on startup

    # Loop forever, pulling changes from git. (Todo: Abstract to function fetch_config_git)
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
                            rebuild_os()

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



def rebuild_os():
    # To-Do: Return errors to Xnode Studio, possibly by pushing error logs to the git repo.
    # To-Do: Add error handling for a failed nixos rebuild
    exit_code = os.system("/run/current-system/sw/bin/nixos-rebuild switch -I nixos-config=/etc/nixos/configuration.nix")
    print("Rebuild exit code: ", exit_code)
    return exit_code    