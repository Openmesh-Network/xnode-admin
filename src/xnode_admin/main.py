
import sys
from utils import parse_args
from xnode_builder import fetch_config_git, fetch_config_studio

def main():
    local_repo_path, remote_repo_path, fetch_interval, user_key, key_type, uuid,  = parse_args() # powerdns_url not implemented yet
    print(key_type, user_key, "with uuid ", uuid)

    # Fetch interval 0 means we do studio mode.

    if fetch_interval == 0: # Studio uses a hardcoded interval
        print("Running in Studio mode.")
        if key_type == "access_token":
            # Remote repo is the studio's URL and User key is a preshared secret.
            fetch_config_studio(remote_repo_path, uuid, user_key, local_repo_path)
        else:
            print("Error: Studio mode only supports access token authentication.")
            sys.exit(1)
    else:
        # Otherwise use a git remote to pull the nix configss
        fetch_config_git(local_repo_path, remote_repo_path, fetch_interval, key_type, user_key)

if __name__ == "__main__":
    main()