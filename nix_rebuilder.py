#!/usr/bin/env python

# Pull from https://github.com/harrys522/sample-nix-repo.git

import git
import os


def main():
    while True:
        repo = git.Repo()
        if not os.path.exists("./xnode-nix-repo"):
            git.Repo.clone_from("https://github.com/harrys522/sample-nix-repo.git", "xnode-nix-repo")

        repo
        os.system("nixos-rebuild switch --flake .#xnode-nix-repo")
    
if __name__ == "__main__":
    main()