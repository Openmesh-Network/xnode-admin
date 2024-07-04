
import sys
from utils import parse_all_args
from xnode_builder import fetch_config_git, fetch_config_studio

def main():
    program_args = parse_all_args()
    print("UUID:", program_args.uuid, "Access Token:", program_args.access_token, "Remote:", program_args.remote, "StateDir:", program_args.state_directory)
    state_directory, remote, uuid, access_token = program_args.state_directory, program_args.remote, program_args.uuid, program_args.access_token

    if program_args.git_mode:
        fetch_config_git(state_directory, remote, program_args.interval, program_args.git_key, program_args.key_type)
    else:
        print("Running in Studio mode.")
        if program_args.uuid and program_args.access_token and program_args.remote:
            # Remote repo is the studio's URL and User key is a preshared secret.
            fetch_config_studio(remote, uuid, access_token, state_directory)
        else:
            print("Error: Studio mode requires a uuid, access token and remote url to interact with the API.")
            sys.exit(1)

if __name__ == "__main__":
    main()